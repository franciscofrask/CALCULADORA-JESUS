"""
Rutas de gestión de leads (prospectos).
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
from typing import Optional
import os
import secrets
import uuid
import bcrypt
from pymongo.errors import DuplicateKeyError

from core.database import db
from core.dias_de_entreno import DIAS_DE_ENTRENO_POR_DEFECTO
from core.security import get_admin_user, get_current_user, generate_temp_password
from core.notion_sync import upsert_lead_to_notion
from models.user import PLAN_CATALOG, planes_contratables
from routes.audit import audit

router = APIRouter(prefix="/leads", tags=["leads"])

LEAD_STATUSES = ["nuevo", "contactado", "llamada_agendada", "propuesta_enviada", "convertido", "descartado"]
LEAD_SOURCES = ["instagram", "web", "referido", "ghl", "whatsapp", "renovacion", "otro"]
DISCARD_REASONS = ["precio", "no_responde", "no_interesado", "competencia", "no_encaja", "otro"]


async def _find_lead_by_contact(email: str, phone: str):
    """Busca un lead existente por email o telefono (solo valores no vacios)."""
    ors = []
    if email:
        ors.append({"email": email})
    if phone:
        ors.append({"phone": phone})
    if not ors:
        return None
    return await db.leads.find_one({"$or": ors}, {"_id": 0})

# ==================== CRUD ====================

@router.get("")
async def list_leads(
    status: Optional[str] = None,
    source: Optional[str] = None,
    assigned_to: Optional[str] = None,
    user=Depends(get_admin_user)
):
    """Lista todos los leads, opcionalmente filtrados."""
    query = {}
    if status:
        query["status"] = status
    if source:
        query["source"] = source
    if assigned_to:
        query["assigned_to"] = assigned_to

    leads = await db.leads.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"leads": leads, "total": len(leads)}


@router.post("/quiero-volver")
async def quiero_volver(data: dict, user=Depends(get_current_user)):
    """El cliente al que se le acabo la membresia deja su correo para que le escriban.

    Francisco, 14-08-2026: «el hablar con nosotros, que deje su mail y queda como lead».

    Antes, la pantalla de caducado ofrecia escribir por WhatsApp y el numero nunca se
    puso, asi que decia «escribenos y lo vemos» sin decir a quien: el que queria volver
    se quedaba sin puerta. Ahora deja el correo aqui y aparece en Leads.

    Esto no puede pasar por `POST /leads`: ese exige ser admin y ademas rechaza a quien
    ya es cliente de la app, que es justo esta gente. Y no se crea un lead nuevo cada vez
    que le da al boton: si ya escribio, se le anota otra vez encima del mismo.
    """
    email = (data.get("email") or user.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Escribe un correo para que podamos avisarte")

    ahora = datetime.now(timezone.utc).isoformat()
    perfil = await db.client_profiles.find_one({"user_id": user["id"]},
                                               {"_id": 0, "plan": 1, "current_period_end": 1}) or {}
    nota = (f"Pidió seguir desde la app. Tenía el plan {perfil.get('plan') or 'sin plan'}"
            f"{', hasta el ' + str(perfil.get('current_period_end'))[:10] if perfil.get('current_period_end') else ''}.")
    if (data.get("mensaje") or "").strip():
        nota += " Dice: " + str(data["mensaje"]).strip()[:400]

    ya = await db.leads.find_one({"email": email}, {"_id": 0, "id": 1})
    if ya:
        await db.leads.update_one({"id": ya["id"]}, {
            "$set": {"status": "nuevo", "updated_at": ahora, "notes": nota},
            "$push": {"activity": {"fecha": ahora, "texto": "Volvió a pedir contacto desde la app"}},
        })
        return {"ok": True, "mensaje": "Ya te teníamos anotado. Te escribimos enseguida."}

    lead = {
        "id": str(uuid.uuid4()),
        "name": user.get("name") or email.split("@")[0],
        "email": email,
        "phone": (user.get("phone") or "").strip(),
        "source": "renovacion",
        "status": "nuevo",
        "notes": nota,
        "assigned_to": None,
        "next_action_date": None,
        "created_at": ahora,
        "updated_at": ahora,
        "created_by": "el propio cliente",
        "activity": [{"fecha": ahora, "texto": "Dejó su correo desde la pantalla de caducado"}],
    }
    await db.leads.insert_one(lead)
    try:
        await upsert_lead_to_notion(lead)
    except Exception:
        pass          # que Notion falle no puede tumbar la peticion del cliente
    return {"ok": True, "mensaje": "Hecho. Te escribimos enseguida."}


@router.post("")
async def create_lead(data: dict, user=Depends(get_admin_user)):
    """Crear un lead nuevo manualmente."""
    email = data.get("email", "").strip().lower()
    lead = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "").strip(),
        "email": email,
        "phone": data.get("phone", "").strip(),
        "source": data.get("source", "otro"),
        "status": "nuevo",
        "notes": data.get("notes", ""),
        "assigned_to": data.get("assigned_to") or None,
        "next_action_date": data.get("next_action_date") or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("name", "admin"),
    }

    if not lead["name"]:
        raise HTTPException(status_code=400, detail="Nombre es obligatorio")

    if email:
        if await db.users.find_one({"email": email, "deleted_at": None}):
            raise HTTPException(status_code=400, detail="Ese email ya es un cliente de la app")
        existing = await _find_lead_by_contact(email, "")
        if existing:
            raise HTTPException(status_code=400, detail=f"Ya existe un lead con ese email ({existing.get('name') or 'sin nombre'}, estado: {existing.get('status')})")

    await db.leads.insert_one(lead)
    return {k: v for k, v in lead.items() if k != "_id"}


# ==================== LLAMADAS DEL NIVEL 3 ====================
# El Nivel 3 se contrata hablando, asi que quien lo elige en el test de nivel deja
# nombre y telefono y aparece aqui. Estas dos rutas van ANTES de "/{lead_id}": FastAPI
# resuelve por orden y esa ruta se tragaria "llamadas-pendientes" como si fuera un id.

@router.get("/llamadas-pendientes")
async def llamadas_pendientes(user=Depends(get_admin_user)):
    """Quien ha pedido que le llamen y todavia no ha sido atendido."""
    docs = await db.leads.find(
        {"quiz_venta.quiere_llamada": True, "status": "nuevo"},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1, "quiz_venta": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(200)

    ahora = datetime.now(timezone.utc)
    for d in docs:
        # Cuantos dias lleva esperando: una peticion de llamada de hace una semana no es
        # lo mismo que una de esta mañana, y en el panel tiene que notarse.
        try:
            pedida = datetime.fromisoformat(d.get("quiz_venta", {}).get("fecha") or d["created_at"])
            d["dias_esperando"] = max(0, (ahora - pedida).days)
        except (ValueError, KeyError, TypeError):
            d["dias_esperando"] = 0
    return {"llamadas": docs, "total": len(docs)}


@router.post("/{lead_id}/enlace-pago")
async def crear_enlace_pago(lead_id: str, data: dict = None, user=Depends(get_admin_user)):
    """Genera el enlace de pago con tarjeta para un lead, ya hablado con el por telefono.

    Doc del 03-08: el Nivel 3 se vende por llamada, pero se cobra por Stripe con tarjeta
    igual que los demas. Esto es la via de cobro de despues de la llamada: el equipo saca
    el enlace y se lo manda por WhatsApp.

    Dos decisiones que conviene tener presentes:
      - `mode="payment"`: PAGO UNICO del ciclo de 12 semanas, no suscripcion. No se
        renueva solo; al llegar la semana 12 se le vuelve a hablar (doc 03-08).
      - El importe va en linea (`price_data`) desde el precio del catalogo, no por
        `STRIPE_PRICE_NIVEL3`. Esa variable esta vacia a proposito y con ella el checkout
        daria 503; asi el enlace se puede generar hoy y siempre cobra lo que diga el
        catalogo (overrides del panel incluidos).
    """
    from core.stripe_billing import (
        get_stripe_module, stripe_api_call, require_stripe_test_mode, build_frontend_url,
    )
    from models.user import merged_catalog

    data = data or {}
    plan_code = (data.get("plan") or "nivel3").lower().strip()

    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")

    overrides = {o["code"]: o.get("fields", {})
                 async for o in db.plan_overrides.find({}, {"_id": 0, "code": 1, "fields": 1})}
    plan = merged_catalog(overrides).get(plan_code)
    if not plan:
        raise HTTPException(status_code=400, detail="Plan no válido")
    if plan.get("estado") != "activo":
        raise HTTPException(status_code=400, detail="Ese plan ya no se contrata.")

    importe_eur = float(plan.get("precio") or 0)
    if importe_eur <= 0:
        raise HTTPException(status_code=400, detail="Ese plan no tiene precio para cobrar.")

    stripe_module = get_stripe_module()
    require_stripe_test_mode("La creación del enlace de pago")

    semanas = int((plan.get("ciclo") or {}).get("semanas") or plan.get("billing_cycle_weeks") or 12)
    metadata = {"tipo": "cobro_lead", "lead_id": lead_id, "plan": plan_code,
                "creado_por": user["id"]}
    session = await stripe_api_call(
        stripe_module.checkout.Session.create,
        mode="payment",
        client_reference_id=lead_id,
        **({"customer_email": lead["email"]} if lead.get("email") else {}),
        line_items=[{
            "price_data": {
                "currency": "eur",
                "unit_amount": int(round(importe_eur * 100)),
                "product_data": {"name": plan.get("name") or plan_code,
                                 "description": f"Ciclo de {semanas} semanas. Pago único, no se renueva solo."},
            },
            "quantity": 1,
        }],
        invoice_creation={"enabled": True},
        payment_intent_data={"metadata": metadata},
        billing_address_collection="auto",
        success_url=build_frontend_url("/planes?pago=ok", include_session_placeholder=True),
        cancel_url=build_frontend_url("/planes"),
        metadata=metadata,
    )

    ahora = datetime.now(timezone.utc).isoformat()
    enlace = {"url": session["url"], "session_id": session["id"], "plan": plan_code,
              "importe_eur": importe_eur, "estado": "enviado",
              "creado_at": ahora, "creado_por": user["id"]}
    await db.leads.update_one({"id": lead_id}, {"$set": {
        "enlace_pago": enlace,
        # Ya se le ha hablado y se le manda la propuesta: sale de la lista de llamadas
        # pendientes y queda en el CRM como propuesta enviada.
        "status": "propuesta_enviada",
        "quiz_venta.quiere_llamada": False,
        "updated_at": ahora,
    }})
    await audit(user, "lead",
                f"Generó el enlace de pago de {plan.get('name')} ({importe_eur:.0f}€) "
                f"para {lead.get('name') or lead_id}")
    return enlace


@router.post("/{lead_id}/llamada-atendida")
async def marcar_llamada_atendida(lead_id: str, user=Depends(get_admin_user)):
    """Ya se le ha contactado: sale del aviso, pero sigue siendo lead en el CRM."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0, "name": 1})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    await db.leads.update_one({"id": lead_id}, {"$set": {
        "status": "contactado",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})
    await audit(user, "lead", f"Atendió la petición de llamada de {lead.get('name') or lead_id}")
    return {"ok": True}


@router.get("/{lead_id}")
async def get_lead(lead_id: str, user=Depends(get_admin_user)):
    """Obtener un lead por ID."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return lead


@router.put("/{lead_id}")
async def update_lead(lead_id: str, data: dict, user=Depends(get_admin_user)):
    """Actualizar un lead (datos, estado, notas)."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")

    update = {}
    for field in ["name", "email", "phone", "source", "status", "notes", "assigned_to", "next_action_date", "discard_reason"]:
        if field in data:
            update[field] = data[field]

    if "status" in update and update["status"] not in LEAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Estado no válido. Usa: {LEAD_STATUSES}")

    if update.get("discard_reason") and update["discard_reason"] not in DISCARD_REASONS:
        raise HTTPException(status_code=400, detail=f"Motivo no válido. Usa: {DISCARD_REASONS}")

    staff = None
    if update.get("assigned_to"):
        staff = await db.users.find_one({"id": update["assigned_to"], "role": {"$in": ["admin", "trainer"]}, "deleted_at": None})
        if not staff:
            raise HTTPException(status_code=400, detail="El responsable debe ser un miembro del equipo")

    now = datetime.now(timezone.utc).isoformat()

    # Eventos automaticos para el historial del lead
    events = []
    if "status" in update and update["status"] != lead.get("status"):
        # CUÁNTO LLEVA PARADO EN ESTA COLUMNA.
        # «Un lead de hace tres semanas en "contactado" no es lo mismo que uno de ayer»
        # (Jesús, 11-08). `updated_at` no vale: lo mueve cualquier edición, así que un
        # cambio de teléfono disimulaba tres semanas sin tocar. Esta fecha solo la mueve
        # un cambio de columna, que es justo lo que se quiere medir.
        update["status_changed_at"] = now
        if update["status"] == "descartado" and update.get("discard_reason"):
            events.append(f"Descartado · motivo: {update['discard_reason'].replace('_', ' ')}")
        else:
            events.append(f"Estado cambiado a '{update['status']}'")
        # Al salir de descartado, el motivo deja de aplicar
        if lead.get("status") == "descartado" and update["status"] != "descartado":
            update["discard_reason"] = None
    if "assigned_to" in update and (update.get("assigned_to") or None) != (lead.get("assigned_to") or None):
        events.append(f"Asignado a {staff['name']}" if staff else "Responsable quitado")
    if "next_action_date" in update and (update.get("next_action_date") or None) != (lead.get("next_action_date") or None):
        events.append(f"Próximo contacto: {update.get('next_action_date') or 'sin fecha'}")

    update["updated_at"] = now
    ops = {"$set": update}
    if events:
        ops["$push"] = {"activity": {"$each": [
            {"id": str(uuid.uuid4()), "type": "sistema", "author": user.get("name") or "staff", "text": t, "created_at": now}
            for t in events
        ]}}
    await db.leads.update_one({"id": lead_id}, ops)

    updated = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return updated


@router.post("/{lead_id}/activity")
async def add_lead_activity(lead_id: str, data: dict, user=Depends(get_admin_user)):
    """Añade una nota fechada al historial del lead."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0, "id": 1})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    text = (data.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="La nota no puede estar vacía")
    entry = {
        "id": str(uuid.uuid4()),
        "type": "nota",
        "author": user.get("name") or "staff",
        "text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.leads.update_one({"id": lead_id}, {
        "$push": {"activity": entry},
        "$set": {"updated_at": entry["created_at"]},
    })
    return entry


@router.delete("/{lead_id}/activity/{entry_id}")
async def delete_lead_activity(lead_id: str, entry_id: str, user=Depends(get_admin_user)):
    """Borra una nota del historial del lead."""
    result = await db.leads.update_one({"id": lead_id}, {"$pull": {"activity": {"id": entry_id}}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return {"ok": True}


@router.delete("/{lead_id}")
async def delete_lead(lead_id: str, user=Depends(get_admin_user)):
    """Eliminar un lead."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0, "name": 1, "email": 1})
    result = await db.leads.delete_one({"id": lead_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    await audit(user, "lead", f"Eliminó el lead {(lead or {}).get('name') or (lead or {}).get('email') or lead_id}")
    return {"message": "Lead eliminado"}


# ==================== CONVERT TO CLIENT ====================

@router.post("/{lead_id}/convert")
async def convert_lead_to_client(lead_id: str, data: dict, user=Depends(get_admin_user)):
    """
    Convierte un lead en cliente: crea user + client_profile automáticamente.
    Body: {"plan": "nivel2", "password": "temp123"} (la contraseña es opcional)

    El plan tiene que ser uno de los CONTRATABLES (punto 43 del doc del 07-08): convertir
    un lead es un alta nueva, y a un alta nueva no se le puede poner un plan legacy. Antes
    el valor por defecto era "gold", que es legacy desde el 31-07: cada lead convertido sin
    decir el plan entraba en un plan que ya no se vende, con el precio de referencia de
    otra época.
    """
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")

    if lead.get("status") == "convertido":
        raise HTTPException(status_code=400, detail="Este lead ya fue convertido")

    email = lead.get("email", "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="El lead necesita email para convertirse en cliente")

    # Check if user already exists
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un usuario con email {email}")

    plan = (data.get("plan") or "").lower().strip()
    contratables = planes_contratables()
    if not plan:
        raise HTTPException(
            status_code=400,
            detail=f"Dime con qué plan entra. Se puede contratar: {', '.join(contratables)}")
    if plan not in contratables:
        nombre = (PLAN_CATALOG.get(plan) or {}).get("name", plan)
        raise HTTPException(
            status_code=400,
            detail=f"'{nombre}' ya no se contrata. Un alta nueva entra con uno de estos: "
                   f"{', '.join(contratables)}. Si de verdad tiene que quedarse con el plan "
                   f"viejo, se le cambia después desde su ficha.")
    password = data.get("password") or generate_temp_password()
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # Coach opcional al convertir
    trainer_id = data.get("trainer_id") or None
    trainer_name = None
    if trainer_id:
        trainer = await db.users.find_one({"id": trainer_id, "role": {"$in": ["trainer", "admin"]}, "deleted_at": None}, {"_id": 0, "name": 1})
        if not trainer:
            raise HTTPException(status_code=400, detail="Entrenador no válido")
        trainer_name = trainer.get("name")

    # Create user
    new_user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": lead.get("name", ""),
        "password": hashed,
        "phone": lead.get("phone", ""),
        "role": "client",
        "plan": plan,
        "trainer_id": trainer_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(new_user)

    # Create client profile
    # El precio sale del CATALOGO (con los overrides del panel), no de una tabla fija: la de
    # antes tenia gold/silver/bronze/elm, planes que ya no se venden, y a un cliente nuevo se
    # le grababa un importe que no coincidia con lo que se le cobra (peticion de Jesus 05-08).
    from models.user import merged_catalog
    overrides = {o["code"]: o.get("fields", {})
                 async for o in db.plan_overrides.find({}, {"_id": 0, "code": 1, "fields": 1})}
    plan_cat = merged_catalog(overrides).get(plan) or {}
    precio = plan_cat.get("precio")
    from datetime import timedelta
    profile = {
        "id": str(uuid.uuid4()),
        "user_id": new_user["id"],
        "plan": plan,
        # Sin precio en el catalogo se deja a None: mejor vacio y visible que un numero
        # inventado, que es lo que acababa en la ficha y en los informes.
        "price": float(precio) if precio not in (None, "") else None,
        "week": 1,
        "status": "activo",
        "trainer_id": trainer_id,
        "next_payment": (datetime.now(timezone.utc) + timedelta(days=28)).isoformat(),
        "macros_training": None,
        "macros_rest": None,
        "macros_periworkout": None,
        "macros_source": None,
        "weight": None,
        "height": None,
        "age": None,
        "sex": None,
        "goal": None,
        "body_fat": None,
        "equipment": [],
        "injuries": [],
        # Cuatro, como en el alta normal: la pregunta se retira del cuestionario el 18-08
        # porque la respuesta es siempre la misma. Un lead convertido a cliente entra por
        # aquí, así que si aquí sigue naciendo a None su rutina queda bloqueada igual.
        "training_days": DIAS_DE_ENTRENO_POR_DEFECTO,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.client_profiles.insert_one(profile)

    # Mark lead as converted
    converted_at = datetime.now(timezone.utc).isoformat()
    await db.leads.update_one({"id": lead_id}, {"$set": {
        "status": "convertido",
        "converted_at": converted_at,
        "converted_user_id": new_user["id"],
        "converted_profile_id": profile["id"],
        "updated_at": converted_at,
    }, "$push": {"activity": {
        "id": str(uuid.uuid4()),
        "type": "sistema",
        "author": user.get("name") or "staff",
        "text": f"Convertido a cliente (plan {plan})" + (f" · coach: {trainer_name}" if trainer_name else ""),
        "created_at": converted_at,
    }}})

    await audit(user, "lead", f"Convirtió el lead {lead.get('name') or email} a cliente (plan {plan})")

    return {
        "message": f"Lead convertido a cliente ({plan})",
        "user_id": new_user["id"],
        "profile_id": profile["id"],
        "email": email,
        "name": lead.get("name", ""),
        "plan": plan,
        "temp_password": password,
        "trainer_id": trainer_id,
        "trainer_name": trainer_name,
    }


# ==================== STATS ====================

@router.get("/stats/summary")
async def get_lead_stats(user=Depends(get_admin_user)):
    """Estadísticas de leads por estado."""
    stats = {}
    for status in LEAD_STATUSES:
        stats[status] = await db.leads.count_documents({"status": status})
    stats["total"] = sum(stats.values())
    return stats


@router.get("/stats/metrics")
async def get_lead_metrics(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    source: Optional[str] = None,
    assigned_to: Optional[str] = None,
    user=Depends(get_admin_user),
):
    """Métricas del embudo: conversión, tiempos, origenes, motivos de descarte y evolución
    semanal. Filtros opcionales: rango de fechas de creación (YYYY-MM-DD), origen y responsable."""
    query = {}
    if from_date or to_date:
        rng = {}
        if from_date:
            rng["$gte"] = from_date
        if to_date:
            rng["$lte"] = to_date + "T23:59:59"
        query["created_at"] = rng
    if source:
        query["source"] = source
    if assigned_to:
        query["assigned_to"] = assigned_to

    leads = await db.leads.find(
        query, {"_id": 0, "status": 1, "source": 1, "created_at": 1, "converted_at": 1, "discard_reason": 1}
    ).to_list(10000)

    total = len(leads)
    by_status = {s: 0 for s in LEAD_STATUSES}
    by_source = {}
    discard_reasons = {}
    conv_days = []
    weekly = {}

    for l in leads:
        status = l.get("status") or "nuevo"
        by_status[status] = by_status.get(status, 0) + 1

        src = l.get("source") or "otro"
        entry = by_source.setdefault(src, {"total": 0, "convertidos": 0})
        entry["total"] += 1

        if status == "convertido":
            entry["convertidos"] += 1
            if l.get("converted_at") and l.get("created_at"):
                try:
                    d1 = datetime.fromisoformat(l["created_at"])
                    d2 = datetime.fromisoformat(l["converted_at"])
                    conv_days.append((d2 - d1).total_seconds() / 86400)
                except (ValueError, TypeError):
                    pass

        if status == "descartado":
            reason = l.get("discard_reason") or "sin_motivo"
            discard_reasons[reason] = discard_reasons.get(reason, 0) + 1

        try:
            dt = datetime.fromisoformat(l["created_at"])
            year, week, _ = dt.isocalendar()
            weekly[f"{year}-S{week:02d}"] = weekly.get(f"{year}-S{week:02d}", 0) + 1
        except (ValueError, TypeError, KeyError):
            pass

    converted = by_status.get("convertido", 0)
    return {
        "total": total,
        "by_status": by_status,
        "converted": converted,
        "conversion_rate": round(converted / total * 100, 1) if total else 0,
        "avg_days_to_convert": round(sum(conv_days) / len(conv_days), 1) if conv_days else None,
        "by_source": by_source,
        "discard_reasons": discard_reasons,
        # Con rango de fechas explícito se muestran todas sus semanas; sin él, las últimas 8
        "weekly": [{"week": w, "count": weekly[w]}
                   for w in (sorted(weekly.keys()) if (from_date or to_date) else sorted(weekly.keys())[-8:])],
    }


# ==================== WEBHOOK (GoHighLevel) ====================

@router.post("/webhook/ghl")
async def ghl_webhook(request: Request):
    """
    Webhook para recibir leads de GoHighLevel. GHL envia un POST con los datos del
    formulario. No lleva auth de usuario -- lo llama un sistema externo --, asi que la
    unica puerta es el secreto: la URL tiene que traer ?secret=<valor> o la cabecera
    x-webhook-secret (las dos se configuran en la accion webhook de GHL).

    SIN SECRETO CONFIGURADO, ESTE ENDPOINT NO ATIENDE (punto 64 del doc del 07-08). Antes
    era `if expected_secret:`, o sea que si la variable no estaba puesta el webhook se
    quedaba ABIERTO en silencio: cualquiera con la URL podia meter leads en el CRM, y no
    habia forma de notarlo -- desde fuera se ve igual que funcionando bien.

    Fallar cerrado es la unica opcion defendible: un webhook que no atiende se detecta en
    minutos porque dejan de entrar leads; uno abierto puede estar meses sin que nadie lo
    vea. En produccion el secreto ESTA puesto (comprobado el 08-08, y el endpoint devuelve
    401 sin el).
    """
    expected_secret = os.environ.get("GHL_WEBHOOK_SECRET", "").strip()
    if not expected_secret:
        raise HTTPException(
            status_code=503,
            detail="El webhook de GHL no está configurado (falta GHL_WEBHOOK_SECRET).")
    provided = request.query_params.get("secret", "") or request.headers.get("x-webhook-secret", "")
    # Comparacion en tiempo constante: con `!=` se puede adivinar el secreto caracter a
    # caracter midiendo lo que tarda en responder.
    if not secrets.compare_digest(provided, expected_secret):
        raise HTTPException(status_code=401, detail="Webhook secret inválido")

    try:
        body = await request.json()
    except Exception:
        body = {}

    # GHL sends different field names depending on the form
    name = body.get("full_name") or body.get("name") or body.get("first_name", "") + " " + body.get("last_name", "")
    name = name.strip()
    email = body.get("email", "").strip().lower()
    phone = (body.get("phone", "") or body.get("phone_number", "")).strip()
    now = datetime.now(timezone.utc).isoformat()

    # Un cliente actual no es un prospecto: no crear lead
    if email and await db.users.find_one({"email": email, "deleted_at": None}):
        return {"status": "ok", "skipped": "already_client"}

    async def _apply_reentry(existing: dict) -> dict:
        """Actualiza un lead existente con los datos de la reentrada (dedup)."""
        update = {"updated_at": now, "ghl_raw": body}
        if name and not existing.get("name"):
            update["name"] = name
        if email and not existing.get("email"):
            update["email"] = email
        if phone and not existing.get("phone"):
            update["phone"] = phone
        # Un descartado que vuelve a entrar es interes nuevo
        if existing.get("status") == "descartado":
            update["status"] = "nuevo"
            update["discard_reason"] = None
        entry = {
            "id": str(uuid.uuid4()),
            "type": "sistema",
            "author": "GoHighLevel",
            "text": "Reentrada automática: el contacto volvió a llegar por el webhook (dedup)",
            "created_at": now,
        }
        await db.leads.update_one({"id": existing["id"]}, {"$set": update, "$push": {"activity": entry}})
        await upsert_lead_to_notion({**existing, **update})
        return {"status": "ok", "lead_id": existing["id"], "deduped": True}

    # Dedup: si ya existe un lead con ese email/telefono, actualizarlo en vez de duplicar
    existing = await _find_lead_by_contact(email, phone)
    if existing:
        return await _apply_reentry(existing)

    lead = {
        "id": str(uuid.uuid4()),
        "name": name,
        "email": email,
        "phone": phone,
        "source": "ghl",
        "status": "nuevo",
        "notes": f"Entrada automática desde GoHighLevel. Raw: {str(body)[:500]}",
        "created_at": now,
        "updated_at": now,
        "created_by": "webhook_ghl",
        "ghl_raw": body,
    }

    try:
        await db.leads.insert_one(lead)
    except DuplicateKeyError:
        # Carrera: otro webhook simultáneo insertó el mismo email entre la comprobación
        # y este insert. El índice único parcial lo bloquea; tratamos como reentrada.
        existing = await _find_lead_by_contact(email, phone)
        if existing:
            return await _apply_reentry(existing)
        raise
    await upsert_lead_to_notion(lead)
    return {"status": "ok", "lead_id": lead["id"]}
