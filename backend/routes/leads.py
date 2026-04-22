"""
Rutas de gestión de leads (prospectos).
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
from typing import Optional
import uuid
import bcrypt

from core.database import db
from core.security import get_admin_user

router = APIRouter(prefix="/leads", tags=["leads"])

LEAD_STATUSES = ["nuevo", "contactado", "llamada_agendada", "propuesta_enviada", "convertido", "descartado"]
LEAD_SOURCES = ["instagram", "web", "referido", "ghl", "whatsapp", "otro"]

# ==================== CRUD ====================

@router.get("")
async def list_leads(
    status: Optional[str] = None,
    source: Optional[str] = None,
    user=Depends(get_admin_user)
):
    """Lista todos los leads, opcionalmente filtrados."""
    query = {}
    if status:
        query["status"] = status
    if source:
        query["source"] = source

    leads = await db.leads.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"leads": leads, "total": len(leads)}


@router.post("")
async def create_lead(data: dict, user=Depends(get_admin_user)):
    """Crear un lead nuevo manualmente."""
    lead = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "").strip(),
        "email": data.get("email", "").strip(),
        "phone": data.get("phone", "").strip(),
        "source": data.get("source", "otro"),
        "status": "nuevo",
        "notes": data.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("name", "admin"),
    }

    if not lead["name"]:
        raise HTTPException(status_code=400, detail="Nombre es obligatorio")

    await db.leads.insert_one(lead)
    return {k: v for k, v in lead.items() if k != "_id"}


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
    for field in ["name", "email", "phone", "source", "status", "notes"]:
        if field in data:
            update[field] = data[field]

    if "status" in update and update["status"] not in LEAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Estado no válido. Usa: {LEAD_STATUSES}")

    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.leads.update_one({"id": lead_id}, {"$set": update})

    updated = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return updated


@router.delete("/{lead_id}")
async def delete_lead(lead_id: str, user=Depends(get_admin_user)):
    """Eliminar un lead."""
    result = await db.leads.delete_one({"id": lead_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return {"message": "Lead eliminado"}


# ==================== CONVERT TO CLIENT ====================

@router.post("/{lead_id}/convert")
async def convert_lead_to_client(lead_id: str, data: dict, user=Depends(get_admin_user)):
    """
    Convierte un lead en cliente: crea user + client_profile automáticamente.
    Body: {"plan": "gold", "password": "temp123"} (optional password, defaults to email)
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

    plan = data.get("plan", "gold")
    password = data.get("password", email)
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # Create user
    new_user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": lead.get("name", ""),
        "password": hashed,
        "phone": lead.get("phone", ""),
        "role": "client",
        "plan": plan,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(new_user)

    # Create client profile
    plan_prices = {"gold": 149, "silver": 99, "bronze": 69, "elm": 39}
    from datetime import timedelta
    profile = {
        "id": str(uuid.uuid4()),
        "user_id": new_user["id"],
        "plan": plan,
        "price": plan_prices.get(plan, 99),
        "week": 1,
        "status": "activo",
        "trainer_id": None,
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
        "training_days": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.client_profiles.insert_one(profile)

    # Mark lead as converted
    await db.leads.update_one({"id": lead_id}, {"$set": {
        "status": "convertido",
        "converted_at": datetime.now(timezone.utc).isoformat(),
        "converted_user_id": new_user["id"],
        "converted_profile_id": profile["id"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})

    return {
        "message": f"Lead convertido a cliente ({plan})",
        "user_id": new_user["id"],
        "profile_id": profile["id"],
        "email": email,
        "plan": plan,
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


# ==================== WEBHOOK (GoHighLevel) ====================

@router.post("/webhook/ghl")
async def ghl_webhook(request: Request):
    """
    Webhook para recibir leads de GoHighLevel.
    GHL envía un POST con datos del formulario.
    No requiere autenticación (es un webhook externo).
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    # GHL sends different field names depending on the form
    name = body.get("full_name") or body.get("name") or body.get("first_name", "") + " " + body.get("last_name", "")
    email = body.get("email", "")
    phone = body.get("phone", "") or body.get("phone_number", "")

    lead = {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "email": email.strip(),
        "phone": phone.strip(),
        "source": "ghl",
        "status": "nuevo",
        "notes": f"Entrada automática desde GoHighLevel. Raw: {str(body)[:500]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "webhook_ghl",
        "ghl_raw": body,
    }

    await db.leads.insert_one(lead)
    return {"status": "ok", "lead_id": lead["id"]}
