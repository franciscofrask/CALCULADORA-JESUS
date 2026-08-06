"""
Catálogo de planes y membresías.

Fuente única: PLAN_CATALOG (código) + overrides editables por el admin (db.plan_overrides).
El catálogo refleja el documento "JG - Catálogo de Planes y Membresías".
"""
from fastapi import APIRouter, Body, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import re
import uuid

from core.database import db
from core.security import get_admin_user
from models.user import PLAN_CATALOG, PLAN_EDITABLE_FIELDS, merged_catalog
from routes.audit import audit

router = APIRouter(tags=["plans"])


async def _overrides_by_code() -> Dict[str, Dict[str, Any]]:
    docs = await db.plan_overrides.find({}, {"_id": 0}).to_list(200)
    return {d["code"]: d.get("fields", {}) for d in docs if d.get("code")}


@router.get("/plans")
async def get_plans(estado: Optional[str] = None):
    """Catálogo público (con overrides del admin aplicados). Cada plan incluye estado,
    ciclo, precios, habilitaciones y `features`. Filtra por
    ?estado=activo|legacy|especial|complemento.
    """
    catalog = merged_catalog(await _overrides_by_code())
    if estado:
        return {c: p for c, p in catalog.items() if p.get("estado") == estado}
    return catalog


@router.get("/comunidad")
async def get_comunidad():
    """Cuánta gente ha pasado ya por el método. PUBLICO: es prueba social, va debajo del
    Nivel 1 ("y debajo, el contador: tantas personas han pasado ya por aquí", documento
    del test de nivel del 06-08-2026).

    Se cuentan los clientes de verdad, incluidos los que vienen de Calma, y se dejan
    fuera los borrados y las cuentas internas. El número tiene que poder decirse en voz
    alta: si un día hay que explicarlo, se explica.
    """
    n = await db.users.count_documents({
        "role": "client",
        "deleted_at": None,
        "email": {"$not": {"$regex": r"@(jg12|test)\.(com|local)$|@jg12test\.com$"}},
    })
    return {"personas": n}


@router.get("/quiz-venta")
async def get_quiz_venta():
    """Las cuatro preguntas del quiz de venta. PUBLICO: se responde antes de registrarse."""
    from core.quiz_venta import PREGUNTAS
    return {"preguntas": PREGUNTAS}


@router.post("/quiz-venta")
async def post_quiz_venta(data: Dict[str, Any] = Body(default={})):
    """
    El resultado del quiz: que nivel le pega y por que (especificacion 31-07-2026, parte 3).

    PUBLICO A PROPOSITO. "Ve su resultado sin dar el correo" es una decision cerrada del
    documento (parte 10): pedirle el correo para enseñarle lo que acaba de contestar es
    justo lo que hace que la gente cierre la pestaña. El correo se le ofrece DESPUES,
    para guardarlo o recibirlo.

    No guarda nada ni crea usuario: solo calcula.
    """
    from core.quiz_venta import resultado_completo

    respuestas = (data or {}).get("respuestas") or {}
    if not isinstance(respuestas, dict):
        raise HTTPException(status_code=400, detail="Respuestas inválidas")

    catalogo = merged_catalog(await _overrides_by_code())
    return resultado_completo(respuestas, catalogo)


_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_RE_DIGITOS = re.compile(r"\D")


@router.post("/quiz-venta/guardar")
async def guardar_quiz_venta(data: Dict[str, Any] = Body(default={})):
    """
    Guarda el resultado del quiz como lead. PUBLICO: es el paso de DESPUES del resultado
    ("puede guardarlo o recibirlo por email", parte 10), nunca el peaje para verlo.

    Cae en el CRM que ya existe (db.leads, source "web") en vez de en una coleccion
    aparte, para que Jesus lo vea donde ve el resto.

    Es un endpoint abierto que escribe, asi que:
      - solo entra lo que se necesita, recortado,
      - si el correo ya es lead o ya es cliente NO se dice (seria un enumerador de
        correos): se responde lo mismo y no se toca nada,
      - no llama a Notion ni a GHL: una llamada de red en un endpoint publico es un
        grifo abierto. La sincronizacion ya la hace el flujo normal de leads.
    """
    email = str((data or {}).get("email") or "").strip().lower()[:120]
    if not _RE_EMAIL.match(email):
        raise HTTPException(status_code=400, detail="Necesitamos un correo válido")

    nombre = str((data or {}).get("nombre") or "").strip()[:80]
    telefono = str((data or {}).get("telefono") or "").strip()[:30]
    respuestas = (data or {}).get("respuestas") or {}
    recomendado = str((data or {}).get("recomendado") or "")[:20]
    quiere_llamada = bool((data or {}).get("quiere_llamada"))
    # "Te llamo yo, dime cuándo te viene bien": sin esto el equipo llama a ciegas y
    # quema la mitad de los intentos (documento del test de nivel, 06-08-2026).
    franja = str((data or {}).get("franja") or "").strip()[:40]

    # Si pide que le llamen, hace falta a quien llamar y a que numero. Sin esto el aviso
    # del panel llegaria sin con que atenderlo, que es peor que no llegar.
    if quiere_llamada:
        if not nombre:
            raise HTTPException(status_code=400, detail="Necesitamos tu nombre para llamarte")
        if len(_RE_DIGITOS.sub("", telefono)) < 9:
            raise HTTPException(status_code=400, detail="Necesitamos un teléfono válido")

    ahora = datetime.now(timezone.utc).isoformat()
    ya_cliente = await db.users.find_one({"email": email, "deleted_at": None}, {"_id": 1})
    ya_lead = await db.leads.find_one({"email": email}, {"_id": 0, "id": 1, "notes": 1})

    quiz = {
        "respuestas": {str(k): str(v)[:2] for k, v in list(respuestas.items())[:10]},
        "recomendado": recomendado,
        "quiere_llamada": quiere_llamada,
        "franja": franja or None,
        "fecha": ahora,
    }
    # La franja va también en las notas del lead: es lo que se lee de un vistazo en el
    # panel, y el que va a llamar no abre el JSON del quiz.
    cuando = f" Llamarle: {franja}." if (quiere_llamada and franja) else ""

    if ya_lead:
        # Ya estaba en el CRM: no se duplica, pero si ahora pide llamada eso SI se anota.
        # Perder la peticion por haber dejado el correo antes seria perder la venta.
        if quiere_llamada:
            # Las notas se AÑADEN, no se pisan: ahí escribe el comercial.
            previas = (ya_lead.get("notes") or "").strip()
            aviso = f"Test de nivel: sale {recomendado}. PIDE LLAMADA (Nivel 3).{cuando}"
            await db.leads.update_one({"id": ya_lead["id"]}, {"$set": {
                "quiz_venta": quiz, "updated_at": ahora,
                "notes": f"{previas}\n{aviso}".strip() if previas else aviso,
                **({"phone": telefono} if telefono else {}),
            }})
    elif not ya_cliente:
        await db.leads.insert_one({
            "id": str(uuid.uuid4()),
            "name": nombre or email.split("@")[0],
            "email": email,
            "phone": telefono,
            "source": "web",
            "status": "nuevo",
            "notes": (f"Test de nivel: sale {recomendado}."
                      + (" PIDE LLAMADA (Nivel 3)." if quiere_llamada else "")
                      + cuando),
            "quiz_venta": quiz,
            "assigned_to": None,
            "next_action_date": None,
            "created_at": ahora,
            "updated_at": ahora,
            "created_by": "test de nivel",
        })

    return {"guardado": True, "quiere_llamada": quiere_llamada}


# ==================== ADMIN ====================

admin_router = APIRouter(prefix="/admin/plans", tags=["admin-plans"])


@admin_router.get("")
async def admin_list_plans(user=Depends(get_admin_user)):
    """Catálogo completo para el panel admin (con overrides aplicados). Marca qué
    planes tienen alguna edición respecto al valor por defecto del código."""
    overrides = await _overrides_by_code()
    catalog = merged_catalog(overrides)
    for code, p in catalog.items():
        p["has_override"] = bool(overrides.get(code))
    return catalog


@admin_router.put("/{code}")
async def admin_update_plan(code: str, data: dict, user=Depends(get_admin_user)):
    """Edita campos del catálogo de un plan (se guardan como override sobre el
    valor por defecto). Solo se aceptan campos editables."""
    code = (code or "").lower().strip()
    if code not in PLAN_CATALOG:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    fields = {k: v for k, v in (data or {}).items() if k in PLAN_EDITABLE_FIELDS}
    if not fields:
        raise HTTPException(
            status_code=400,
            detail=f"Nada que editar. Campos válidos: {', '.join(sorted(PLAN_EDITABLE_FIELDS))}",
        )

    existing = await db.plan_overrides.find_one({"code": code}, {"_id": 0, "fields": 1})
    merged_fields = {**(existing.get("fields") if existing else {}), **fields}
    await db.plan_overrides.update_one(
        {"code": code},
        {"$set": {"code": code, "fields": merged_fields,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    await audit(user, "plan", f"Editó el plan {code} ({', '.join(sorted(fields.keys()))})")
    return merged_catalog({code: merged_fields})[code]


@admin_router.delete("/{code}")
async def admin_reset_plan(code: str, user=Depends(get_admin_user)):
    """Elimina los overrides de un plan y lo restaura al valor por defecto del código."""
    code = (code or "").lower().strip()
    if code not in PLAN_CATALOG:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    await db.plan_overrides.delete_one({"code": code})
    await audit(user, "plan", f"Restauró el plan {code} a los valores por defecto")
    return merged_catalog()[code]
