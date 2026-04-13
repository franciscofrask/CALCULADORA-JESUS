"""
Rutas de administración: clientes, dashboard, entrenadores.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import uuid

from core.database import db
from core.security import get_admin_user
from models.user import ClientProfile, ClientProfileUpdate, MacrosUpdate

router = APIRouter(prefix="/admin", tags=["admin"])

# ==================== CLIENTS ====================

@router.get("/clients", response_model=List[Dict[str, Any]])
async def get_all_clients(
    plan: Optional[str] = None,
    status: Optional[str] = None,
    trainer_id: Optional[str] = None,
    user = Depends(get_admin_user)
):
    """Obtener todos los clientes con filtros opcionales."""
    query = {}
    if plan:
        query["plan"] = plan.lower()
    if status:
        query["status"] = status
    if trainer_id:
        query["trainer_id"] = trainer_id
    
    profiles = await db.client_profiles.find(query, {"_id": 0}).to_list(1000)
    
    result = []
    for profile in profiles:
        user_data = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "password": 0})
        if user_data:
            result.append({**profile, "user": user_data})
    
    return result

@router.get("/clients/{client_id}")
async def get_client_detail(client_id: str, user = Depends(get_admin_user)):
    """Obtener detalle completo de un cliente."""
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    user_data = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "password": 0})
    routines = await db.routines.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(10)
    reports = await db.reports.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(10)
    payments = await db.payments.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(10)
    messages = await db.messages.find(
        {"$or": [{"sender_id": profile["user_id"]}, {"receiver_id": profile["user_id"]}]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return {
        "profile": profile,
        "user": user_data,
        "routines": routines,
        "reports": reports,
        "payments": payments,
        "messages": messages
    }

@router.put("/clients/{client_id}", response_model=ClientProfile)
async def update_client_admin(client_id: str, data: ClientProfileUpdate, user = Depends(get_admin_user)):
    """Actualizar perfil de cliente (admin)."""
    profile = await db.client_profiles.find_one({"id": client_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_data:
        await db.client_profiles.update_one({"id": client_id}, {"$set": update_data})
    
    updated = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    return ClientProfile(**updated)

@router.put("/clients/{client_id}/macros")
async def update_client_macros(client_id: str, data: MacrosUpdate, user = Depends(get_admin_user)):
    """Actualizar macros de un cliente (admin). Marca como override manual."""
    profile = await db.client_profiles.find_one({"id": client_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    training = data.training.model_dump()
    rest = data.rest.model_dump()
    training["calories"] = training["protein"] * 4 + training["carbs"] * 4 + training["fat"] * 9
    rest["calories"] = rest["protein"] * 4 + rest["carbs"] * 4 + rest["fat"] * 9
    
    # Also store in alternative format for chatbot compatibility
    training["proteinas"] = training["protein"]
    training["hidratos"] = training["carbs"]
    training["grasas"] = training["fat"]
    rest["proteinas"] = rest["protein"]
    rest["hidratos"] = rest["carbs"]
    rest["grasas"] = rest["fat"]
    
    await db.client_profiles.update_one(
        {"id": client_id},
        {"$set": {
            "macros_training": training,
            "macros_rest": rest,
            "macros_source": "manual",
        }}
    )
    
    macro_log = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "training": training,
        "rest": rest,
        "note": data.note,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.macro_history.insert_one(macro_log)
    
    return {"training": training, "rest": rest}

# ==================== DASHBOARD ====================

@router.get("/dashboard")
async def get_dashboard_stats(user = Depends(get_admin_user)):
    """Obtener estadísticas del dashboard de admin."""
    total_clients = await db.client_profiles.count_documents({})
    active_clients = await db.client_profiles.count_documents({"status": "activo"})
    
    # Plans distribution
    plans = {}
    for plan in ["gold", "silver", "bronze", "elm"]:
        count = await db.client_profiles.count_documents({"plan": plan})
        plans[plan] = count
    
    # Recent activity
    recent_reports = await db.reports.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)
    recent_messages = await db.messages.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)
    
    # Revenue (mocked)
    payments = await db.payments.find({"status": "success"}, {"_id": 0}).to_list(1000)
    total_revenue = sum(p.get("amount", 0) for p in payments)
    
    return {
        "total_clients": total_clients,
        "active_clients": active_clients,
        "plans": plans,
        "recent_reports": recent_reports,
        "recent_messages": recent_messages,
        "total_revenue": total_revenue
    }

# ==================== TRAINERS ====================

@router.get("/trainers")
async def get_trainers(user = Depends(get_admin_user)):
    """Obtener lista de entrenadores."""
    trainers = await db.users.find(
        {"role": {"$in": ["trainer", "admin"]}},
        {"_id": 0, "password": 0}
    ).to_list(100)
    return trainers
