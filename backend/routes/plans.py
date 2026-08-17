"""
Catálogo de planes y membresías.

Fuente única: PLAN_CATALOG (código) + overrides editables por el admin (db.plan_overrides).
El catálogo refleja el documento "JG - Catálogo de Planes y Membresías".
"""
from fastapi import APIRouter, Body, HTTPException, Depends
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import os
import re
import uuid

from core.database import db
from core.security import get_admin_only_user
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


# Cuánta gente ha pasado por el método. Se recuerda unos minutos porque va en la portada
# del test, que es la pantalla más visitada, y cruzar las dos listas en cada visita es
# leer 1.300 correos para un número que no cambia de un segundo a otro.
_COMUNIDAD_CACHE: Dict[str, Any] = {"n": None, "hasta": None}
_COMUNIDAD_MINUTOS = 10

_CORREO_INTERNO = re.compile(r"@(jg12|test)\.(com|local)$|@jg12test\.com$", re.I)


@router.get("/comunidad")
async def get_comunidad():
    """Cuánta gente se ha dado de alta alguna vez. PUBLICO: es prueba social.

    Criterio de Jesús (documento del acceso gratis): "sale de los registros de la
    calculadora antigua -- cuánta gente se dio de alta alguna vez [...] a eso se le suman
    algunos más aparte. Y es un contador VIVO, no un número escrito a mano: sube con cada
    alta nueva. Esa es la diferencia entre prueba social y publicidad".

    Así que son las personas de la calculadora antigua MÁS las que se han dado de alta en
    la app y no estaban allí. Sin contar a nadie dos veces: 168 de los 170 clientes
    actuales ya estaban en la lista vieja, porque migraron de Calma.

    Fuera quedan las cuentas internas y de prueba. El número tiene que poder decirse en
    voz alta y explicarse si alguien pregunta.
    """
    ahora = datetime.now(timezone.utc)
    if _COMUNIDAD_CACHE["n"] is not None and _COMUNIDAD_CACHE["hasta"] > ahora:
        return {"personas": _COMUNIDAD_CACHE["n"]}

    de_la_calculadora = {
        e.strip().lower() for e in await db.calma_raw.distinct("email")
        if e and not _CORREO_INTERNO.search(e)
    }
    nuevos = set()
    async for u in db.users.find({"role": "client", "deleted_at": None},
                                 {"_id": 0, "email": 1}):
        correo = (u.get("email") or "").strip().lower()
        if correo and not _CORREO_INTERNO.search(correo) and correo not in de_la_calculadora:
            nuevos.add(correo)

    n = len(de_la_calculadora) + len(nuevos)
    _COMUNIDAD_CACHE.update({"n": n, "hasta": ahora + timedelta(minutes=_COMUNIDAD_MINUTOS)})
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

# SOLO ADMINISTRADORES, no los entrenadores. Aquí se decide qué incluye cada plan, y de
# esas habilitaciones dependen el precio, lo que ve el cliente y a qué endpoints llega:
# quitarle "reportes" a un plan se lo quita a todos sus clientes a la vez. Es una decisión
# de negocio, del mismo orden que Usuarios y Cobros, no del día a día de un entrenador.
admin_router = APIRouter(prefix="/admin/plans", tags=["admin-plans"])


def _tiene_price_en_stripe(plan: Dict[str, Any]) -> bool:
    """Si este plan puede cobrarse hoy: tiene variable de Price y la variable trae un id.

    Sin esto el checkout revienta con un 503 y un mensaje que al cliente no le dice nada.
    Es lo que decide si el interruptor de «renovable por los suyos» se puede encender: de
    poco sirve reabrirle el plan a alguien si al darle a pagar no hay nada que cobrarle.
    """
    env = (plan.get("stripe_price_env") or "").strip()
    return bool(env and os.environ.get(env, "").strip())


@admin_router.get("")
async def admin_list_plans(user=Depends(get_admin_only_user)):
    """Catálogo completo para el panel admin (con overrides aplicados). Marca qué
    planes tienen alguna edición respecto al valor por defecto del código."""
    overrides = await _overrides_by_code()
    catalog = merged_catalog(overrides)
    for code, p in catalog.items():
        p["has_override"] = bool(overrides.get(code))
        # Para que el panel pueda dejar el interruptor bloqueado en vez de dejar encender
        # algo que despues no cobra.
        p["tiene_price_en_stripe"] = _tiene_price_en_stripe(p)
    return catalog


@admin_router.put("/{code}")
async def admin_update_plan(code: str, data: dict, user=Depends(get_admin_only_user)):
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

    # EL INTERRUPTOR DEL PLAN ANTIGUO SE COMPRUEBA AL GUARDAR, no solo en la pantalla.
    # Encenderlo en un plan que no tiene Price en Stripe deja una promesa que no se puede
    # cumplir: el cliente ve «Seguir igual», le da, y el checkout responde un 503. Mejor
    # decirlo aquí, cuando se guarda, que descubrirlo cuando alguien intente pagar. Se
    # valida contra el catálogo YA mezclado (lo guardado + lo que llega ahora), que es el
    # que va a mandar cuando el cliente entre a renovar.
    if merged_fields.get("renovable_por_los_suyos"):
        resultante = merged_catalog({code: merged_fields}).get(code, {})
        if resultante.get("estado") != "legacy":
            raise HTTPException(
                status_code=400,
                detail="Ese interruptor es solo para los planes que ya no se venden.",
            )
        if not _tiene_price_en_stripe(resultante):
            raise HTTPException(
                status_code=400,
                detail=f"{resultante.get('name') or code} no tiene precio configurado en Stripe, "
                       "así que no se le podría cobrar la renovación. Hay que crearlo antes de encenderlo.",
            )

    await db.plan_overrides.update_one(
        {"code": code},
        {"$set": {"code": code, "fields": merged_fields,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    await audit(user, "plan", f"Editó el plan {code} ({', '.join(sorted(fields.keys()))})")
    return merged_catalog({code: merged_fields})[code]


@admin_router.delete("/{code}")
async def admin_reset_plan(code: str, user=Depends(get_admin_only_user)):
    """Elimina los overrides de un plan y lo restaura al valor por defecto del código."""
    code = (code or "").lower().strip()
    if code not in PLAN_CATALOG:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    await db.plan_overrides.delete_one({"code": code})
    await audit(user, "plan", f"Restauró el plan {code} a los valores por defecto")
    return merged_catalog()[code]
