# -*- coding: utf-8 -*-
"""
Sync incremental GoHighLevel -> Notion (base 'Oportunidades GHL').

Pensado para correr por cron (cada 2 h) en el VPS, en su propio venv, aislado de la app.
Cada corrida:
  1. Lee TODAS las oportunidades de GHL (barato: unas pocas llamadas paginadas).
  2. Lee TODAS las filas de la base de Notion (id GHL -> pagina + campos actuales).
  3. Crea las nuevas, ACTUALIZA solo las que cambiaron (etapa/estado/valor/contacto/...),
     y salta las iguales. Tras el backfill, la 1a corrida no escribe nada.

Config por entorno (o backend/.env en local):
  GHL_PIT_TOKEN, GHL_LOCATION, NOTION_TOKEN, NOTION_OPPS_DB_ID
No borra en Notion las oportunidades borradas en GHL (raro; se puede añadir luego).
"""
import os
import sys
import time
import logging

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ghl_notion_sync")

GHL_TOKEN = os.environ.get("GHL_PIT_TOKEN", "").strip()
GHL_LOCATION = os.environ.get("GHL_LOCATION", "5eARA7SCq3qldys1JxzV").strip()
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
NOTION_DB = os.environ.get("NOTION_OPPS_DB_ID", "").strip()

GHL_H = {"Authorization": "Bearer " + GHL_TOKEN, "Version": "2021-07-28", "Accept": "application/json"}
N_H = {"Authorization": "Bearer " + NOTION_TOKEN, "Notion-Version": "2022-06-28",
       "Content-Type": "application/json"}
STATUS_MAP = {"open": "Abierta", "won": "Ganada", "lost": "Perdida", "abandoned": "Abandonada"}


def _req(method, url, **kw):
    kw.setdefault("timeout", 30)
    last = None
    for attempt in range(7):
        try:
            r = requests.request(method, url, **kw)
        except requests.exceptions.RequestException as e:
            last = e
            time.sleep(min(2 ** attempt, 20))
            continue
        if r.status_code == 429:
            time.sleep(float(r.headers.get("Retry-After", 2)))
            continue
        return r
    raise RuntimeError(f"req falló tras reintentos ({url}): {last}")


def rt(text):
    text = (str(text) if text is not None else "").strip()
    return [{"type": "text", "text": {"content": text[:1900]}}] if text else []


def get_maps():
    r = _req("GET", "https://services.leadconnectorhq.com/opportunities/pipelines",
             headers=GHL_H, params={"locationId": GHL_LOCATION})
    r.raise_for_status()
    pipes, stages = {}, {}
    for p in r.json().get("pipelines", []):
        pipes[p["id"]] = p["name"]
        for s in p.get("stages", []):
            stages[s["id"]] = s["name"]
    return pipes, stages


def fetch_all_ghl():
    """Devuelve (lista de oportunidades, total según GHL). Si alguna página falla, _req
    reintenta y, si no lo logra, lanza -> la corrida aborta ANTES de tocar bajas (así un
    fetch parcial nunca provoca archivados erróneos)."""
    opps, total = [], None
    params = {"location_id": GHL_LOCATION, "limit": 100}
    while True:
        r = _req("GET", "https://services.leadconnectorhq.com/opportunities/search",
                 headers=GHL_H, params=params)
        r.raise_for_status()
        d = r.json()
        if total is None:
            total = d.get("meta", {}).get("total")
        opps.extend(d.get("opportunities", []))
        meta = d.get("meta", {})
        if not meta.get("startAfterId"):
            break
        params["startAfter"] = meta["startAfter"]
        params["startAfterId"] = meta["startAfterId"]
    return opps, total


def notion_rows():
    """id GHL -> {page_id, campos actuales} para comparar y decidir si actualizar."""
    out, cursor = {}, None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = _req("POST", f"https://api.notion.com/v1/databases/{NOTION_DB}/query", headers=N_H, json=body)
        r.raise_for_status()
        d = r.json()
        for p in d.get("results", []):
            pr = p["properties"]
            gid = "".join(x["plain_text"] for x in pr["ID oportunidad GHL"]["rich_text"])
            if not gid:
                continue
            out[gid] = {
                "page_id": p["id"],
                "Nombre": "".join(x["plain_text"] for x in pr["Nombre"]["title"]),
                "Pipeline": (pr["Pipeline"]["select"] or {}).get("name"),
                "Etapa": (pr["Etapa"]["select"] or {}).get("name"),
                "Estado": (pr["Estado"]["select"] or {}).get("name"),
                "Valor": pr["Valor"]["number"],
                "Fuente": "".join(x["plain_text"] for x in pr["Fuente"]["rich_text"]),
                "Email": pr["Email"]["email"],
                "Teléfono": pr["Teléfono"]["phone_number"],
            }
        if not d.get("has_more"):
            break
        cursor = d.get("next_cursor")
    return out


def desired(o, pipes, stages):
    c = o.get("contact") or {}
    return {
        "Nombre": (o.get("name") or c.get("name") or "Sin nombre"),
        "Pipeline": pipes.get(o.get("pipelineId"), "Otro"),
        "Etapa": stages.get(o.get("pipelineStageId"), "Otra"),
        "Estado": STATUS_MAP.get(o.get("status"), "Abierta"),
        "Valor": float(o.get("monetaryValue") or 0),
        "Fuente": (o.get("source") or ""),
        "Email": (c.get("email") or None),
        "Teléfono": (c.get("phone") or None),
        "_contactId": o.get("contactId"),
        "_createdAt": (o.get("createdAt") or "")[:10],
    }


def to_props(d):
    props = {
        "Nombre": {"title": rt(d["Nombre"])},
        "Pipeline": {"select": {"name": d["Pipeline"][:100]}},
        "Etapa": {"select": {"name": d["Etapa"][:100]}},
        "Estado": {"select": {"name": d["Estado"]}},
        "Valor": {"number": d["Valor"]},
        "Fuente": {"rich_text": rt(d["Fuente"])},
        "Email": {"email": d["Email"]},
        "Teléfono": {"phone_number": d["Teléfono"]},
    }
    return props


def differs(d, cur):
    """True si algún campo sincronizado cambió respecto a lo que hay en Notion.
    Comparación case-insensitive: Notion normaliza el valor de un select a la opción ya
    existente (p.ej. escribir 'NUEVO' se guarda como 'Nuevo' si esa opción ya existe), así
    que comparar con mayúsculas provocaba reescrituras en bucle en cada corrida."""
    def norm(v):
        return (v or "").strip().casefold() if isinstance(v, str) else v
    for k in ("Nombre", "Pipeline", "Etapa", "Estado", "Fuente", "Email", "Teléfono"):
        if norm(d[k]) != norm(cur[k]):
            return True
    if abs(float(d["Valor"] or 0) - float(cur["Valor"] or 0)) > 0.001:
        return True
    return False


def main():
    if not (GHL_TOKEN and NOTION_TOKEN and NOTION_DB):
        log.error("Faltan credenciales: GHL_PIT_TOKEN / NOTION_TOKEN / NOTION_OPPS_DB_ID")
        sys.exit(1)
    pipes, stages = get_maps()
    have = notion_rows()
    opps, total = fetch_all_ghl()
    ghl_ids = {o.get("id") for o in opps}
    log.info("GHL opps=%d (total=%s) etapas=%d | filas en Notion=%d",
             len(opps), total, len(stages), len(have))

    creados = actualizados = iguales = archivados = errores = 0
    for o in opps:
        gid = o.get("id")
        d = desired(o, pipes, stages)
        try:
            if gid not in have:
                props = to_props(d)
                props["ID oportunidad GHL"] = {"rich_text": rt(gid)}
                props["ID contacto GHL"] = {"rich_text": rt(d["_contactId"])}
                if d["_createdAt"]:
                    props["Fecha creada"] = {"date": {"start": d["_createdAt"]}}
                r = _req("POST", "https://api.notion.com/v1/pages", headers=N_H,
                         json={"parent": {"database_id": NOTION_DB}, "properties": props})
                if r.status_code >= 300:
                    raise RuntimeError(r.text[:200])
                creados += 1
                time.sleep(0.34)
            elif differs(d, have[gid]):
                r = _req("PATCH", f"https://api.notion.com/v1/pages/{have[gid]['page_id']}",
                         headers=N_H, json={"properties": to_props(d)})
                if r.status_code >= 300:
                    raise RuntimeError(r.text[:200])
                actualizados += 1
                time.sleep(0.34)
            else:
                iguales += 1
        except Exception as e:
            errores += 1
            if errores <= 5:
                log.warning("error en opp %s: %s", gid, e)

    # Bajas: oportunidades que están en Notion pero YA NO en GHL (se borraron) -> archivar
    # (a la papelera de Notion, reversible). SALVAGUARDA: solo si el fetch de GHL vino
    # completo (>= 90% del total que reporta GHL); si no, se salta para no archivar por
    # una lectura parcial.
    if total and len(ghl_ids) < total * 0.9:
        log.warning("fetch GHL incompleto (%d de %s): NO se archivan bajas esta corrida",
                    len(ghl_ids), total)
    else:
        for gid, row in have.items():
            if gid in ghl_ids:
                continue
            try:
                r = _req("PATCH", f"https://api.notion.com/v1/pages/{row['page_id']}",
                         headers=N_H, json={"archived": True})
                if r.status_code >= 300:
                    raise RuntimeError(r.text[:200])
                archivados += 1
                time.sleep(0.34)
            except Exception as e:
                errores += 1
                if errores <= 5:
                    log.warning("error archivando %s: %s", gid, e)

    log.info("FIN sync: creados=%d actualizados=%d iguales=%d archivados=%d errores=%d",
             creados, actualizados, iguales, archivados, errores)


if __name__ == "__main__":
    main()
