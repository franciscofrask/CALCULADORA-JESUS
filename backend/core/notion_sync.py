"""
Sincronización best-effort de leads de GoHighLevel a una base de Notion.

Se activa SOLO si están en el entorno NOTION_TOKEN (secreto de la integración interna
"12en12" de Notion) y NOTION_LEADS_DB_ID (id de la base "Leads GHL"). Si faltan, es un
no-op silencioso. Nunca lanza excepción: si Notion no responde, se registra un aviso y el
webhook de leads sigue su curso normal (la app no debe caerse por un fallo de Notion).

El upsert se hace por "ID contacto GHL" (contact_id de GHL); si no hubiera, por email.
"""
import os
import logging

import httpx

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Estado del lead en la app -> opción del select "Estado" en Notion.
_ESTADO_MAP = {
    "nuevo": "Nuevo",
    "contactado": "Contactado",
    "en_proceso": "Contactado",
    "convertido": "Convertido",
    "descartado": "Descartado",
}


def _rt(text):
    """rich_text de Notion a partir de un string (recortado al límite de Notion)."""
    text = (text or "").strip()
    return [{"type": "text", "text": {"content": text[:1900]}}] if text else []


def _config():
    tok = os.environ.get("NOTION_TOKEN", "").strip()
    db = os.environ.get("NOTION_LEADS_DB_ID", "").strip()
    return (tok, db)


async def _find_existing(client, headers, db, ghl_id, email):
    """Página existente por ID de contacto GHL (o email) para no duplicar. None si no hay."""
    if ghl_id:
        flt = {"property": "ID contacto GHL", "rich_text": {"equals": ghl_id}}
    elif email:
        flt = {"property": "Email", "email": {"equals": email}}
    else:
        return None
    r = await client.post(f"{NOTION_API}/databases/{db}/query", headers=headers,
                          json={"filter": flt, "page_size": 1})
    if r.status_code == 200:
        results = r.json().get("results", [])
        return results[0]["id"] if results else None
    logger.warning("Notion query devolvió %s: %s", r.status_code, r.text[:200])
    return None


async def upsert_lead_to_notion(lead: dict) -> None:
    """Crea o actualiza la fila del lead en la base de Notion. Best-effort."""
    tok, db = _config()
    if not tok or not db:
        return
    raw = lead.get("ghl_raw") or {}
    if not isinstance(raw, dict):
        raw = {}
    ghl_id = str(raw.get("contact_id") or "").strip()
    email = (lead.get("email") or "").strip()

    estado = _ESTADO_MAP.get((lead.get("status") or "nuevo").lower(), "Nuevo")
    fecha = (raw.get("date_created") or lead.get("created_at") or "")[:10] or None

    props = {
        "Nombre": {"title": _rt(lead.get("name") or email or "Lead sin nombre")},
        "Email": {"email": email or None},
        "Teléfono": {"phone_number": (lead.get("phone") or "").strip() or None},
        "Estado": {"select": {"name": estado}},
        "Origen": {"select": {"name": "GHL"}},
        "Etiquetas": {"rich_text": _rt(raw.get("tags"))},
        "ID contacto GHL": {"rich_text": _rt(ghl_id)},
    }
    if fecha:
        props["Fecha de entrada"] = {"date": {"start": fecha}}

    headers = {
        "Authorization": f"Bearer {tok}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            page_id = await _find_existing(client, headers, db, ghl_id, email)
            if page_id:
                r = await client.patch(f"{NOTION_API}/pages/{page_id}", headers=headers,
                                       json={"properties": props})
            else:
                r = await client.post(f"{NOTION_API}/pages", headers=headers,
                                      json={"parent": {"database_id": db}, "properties": props})
            if r.status_code >= 300:
                logger.warning("Notion upsert %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        logger.warning("No se pudo sincronizar el lead con Notion: %s", exc)
