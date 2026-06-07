"""
Rutas de administración: clientes, dashboard, entrenadores.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
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
    """Obtener detalle completo de un cliente (8 pestañas)."""
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    user_data = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "password": 0})
    routines = await db.routines.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(10)
    reports = await db.reports.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    payments = await db.payments.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    messages = await db.messages.find(
        {"$or": [{"sender_id": profile["user_id"]}, {"receiver_id": profile["user_id"]}]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    macro_history = await db.macro_history.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(50)

    # Nutrition stats: recent diets + top foods
    diets = await db.diets.find(
        {"user_id": profile["user_id"]},
        {"_id": 0, "fecha": 1, "comidas": 1, "tipo_dia": 1}
    ).sort("fecha", -1).to_list(30)

    food_counts = {}
    for diet in diets:
        for meal_data in (diet.get("comidas") or {}).values():
            for a in (meal_data.get("alimentos") or []):
                name = a.get("nombre", "?")
                food_counts[name] = food_counts.get(name, 0) + 1
    top_foods = sorted(food_counts.items(), key=lambda x: -x[1])[:5]

    nutrition_stats = {
        "total_diets": len(diets),
        "recent_diets": [{"fecha": d["fecha"], "tipo_dia": d.get("tipo_dia", "?")} for d in diets[:7]],
        "top_foods": [{"nombre": n, "count": c} for n, c in top_foods],
    }

    return {
        "profile": profile,
        "user": user_data,
        "routines": routines,
        "reports": reports,
        "payments": payments,
        "messages": messages,
        "macro_history": macro_history,
        "nutrition_stats": nutrition_stats,
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
        "previous_training": profile.get("macros_training"),
        "previous_rest": profile.get("macros_rest"),
        "new_training": training,
        "new_rest": rest,
        "training": training,
        "rest": rest,
        "note": data.note,
        "changed_by": user.get("name", user.get("email", "admin")),
        "client_weight": profile.get("weight"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.macro_history.insert_one(macro_log)

    return {"training": training, "rest": rest}

@router.post("/clients/{client_id}/calculator/apply")
async def admin_calculator_apply(client_id: str, data: dict, user = Depends(get_admin_user)):
    """Calcular targets con tablas JG y aplicarlos al perfil del cliente."""
    from target_calculator import calcular_targets, targets_to_profile_macros

    profile = await db.client_profiles.find_one({"id": client_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    peso = data.get("peso")
    sexo = data.get("sexo")
    bf = data.get("porcentaje_graso")
    objetivo = data.get("objetivo")
    note = data.get("note", "Cálculo automático JG")

    if not all([peso, sexo, bf is not None, objetivo]):
        raise HTTPException(status_code=400, detail="Faltan campos: peso, sexo, porcentaje_graso, objetivo")

    try:
        targets = calcular_targets(float(peso), sexo, float(bf), objetivo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    profile_macros = targets_to_profile_macros(targets)
    training = profile_macros["macros_training"]
    rest = profile_macros["macros_rest"]
    peri = profile_macros["macros_periworkout"]

    # Aliases for chatbot compatibility
    for m in (training, rest):
        m["proteinas"] = m["protein"]
        m["hidratos"] = m["carbs"]
        m["grasas"] = m["fat"]

    await db.client_profiles.update_one(
        {"id": client_id},
        {"$set": {
            "weight": float(peso),
            "sex": sexo,
            "body_fat": float(bf),
            "goal": objetivo,
            "macros_training": training,
            "macros_rest": rest,
            "macros_periworkout": peri,
            "macros_source": "auto",
            "macros_multiplicadores": targets["multiplicadores"],
        }}
    )

    macro_log = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "previous_training": profile.get("macros_training"),
        "previous_rest": profile.get("macros_rest"),
        "new_training": training,
        "new_rest": rest,
        "training": training,
        "rest": rest,
        "note": note,
        "changed_by": user.get("name", user.get("email", "admin")),
        "client_weight": float(peso),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.macro_history.insert_one(macro_log)

    return {"applied": True, "targets": targets, "training": training, "rest": rest, "peri": peri}

# ==================== DASHBOARD ====================

@router.get("/dashboard-stats")
async def get_dashboard_stats_v2(user = Depends(get_admin_user)):
    """Métricas reales del negocio con agregación MongoDB."""
    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total = await db.client_profiles.count_documents({})
    active = await db.client_profiles.count_documents({"status": "activo"})
    inactive = await db.client_profiles.count_documents({"status": {"$in": ["inactivo", "baja", "cancelado"]}})

    # At-risk: active but week >= 3 and no report in last 14 days
    fourteen_ago = (now - timedelta(days=14)).isoformat()
    active_profiles = await db.client_profiles.find(
        {"status": "activo", "week": {"$gte": 3}}, {"_id": 0, "id": 1, "user_id": 1}
    ).to_list(500)
    at_risk = 0
    for p in active_profiles:
        recent_report = await db.reports.find_one(
            {"client_id": p["id"], "created_at": {"$gte": fourteen_ago}}
        )
        if not recent_report:
            at_risk += 1

    # Bajas del mes
    bajas_mes = await db.client_profiles.count_documents({
        "status": {"$in": ["baja", "cancelado", "inactivo"]},
    })

    # Plan distribution
    plans = {}
    for plan in ["gold", "silver", "bronze", "elm"]:
        plans[plan] = await db.client_profiles.count_documents({"plan": plan, "status": "activo"})

    # MRR (Monthly Recurring Revenue)
    mrr = 0
    active_for_mrr = await db.client_profiles.find(
        {"status": "activo"}, {"_id": 0, "price": 1}
    ).to_list(500)
    mrr = sum(p.get("price", 0) for p in active_for_mrr)

    # Revenue this month
    payments = await db.payments.find(
        {"status": "success"}, {"_id": 0, "amount": 1}
    ).to_list(1000)
    total_revenue = sum(p.get("amount", 0) for p in payments)

    return {
        "total_clients": total,
        "active_clients": active,
        "at_risk_clients": at_risk,
        "bajas_mes": bajas_mes,
        "inactive_clients": inactive,
        "plans": plans,
        "mrr": mrr,
        "total_revenue": total_revenue,
    }


@router.get("/upcoming-payments")
async def get_upcoming_payments(user = Depends(get_admin_user)):
    """Clientes con cobro en los próximos 7 días."""
    now = datetime.now(timezone.utc)
    seven_days = now + timedelta(days=7)
    now_iso = now.isoformat()
    seven_iso = seven_days.isoformat()

    profiles = await db.client_profiles.find(
        {
            "status": "activo",
            "next_payment": {"$gte": now_iso, "$lte": seven_iso}
        },
        {"_id": 0}
    ).sort("next_payment", 1).to_list(100)

    results = []
    for p in profiles:
        user_data = await db.users.find_one({"id": p["user_id"]}, {"_id": 0, "name": 1, "email": 1})
        results.append({
            "client_id": p["id"],
            "name": user_data.get("name", "?") if user_data else "?",
            "email": user_data.get("email", "") if user_data else "",
            "plan": p.get("plan"),
            "price": p.get("price", 0),
            "next_payment": p.get("next_payment"),
        })

    return {"upcoming": results, "total": len(results)}


@router.get("/dashboard")
async def get_dashboard_stats(user = Depends(get_admin_user)):
    """Legacy dashboard endpoint (backwards compatible)."""
    stats = await get_dashboard_stats_v2(user)
    return {
        "total_clients": stats["total_clients"],
        "active_clients": stats["active_clients"],
        "plans": stats["plans"],
        "mrr": stats["mrr"],
        "total_revenue": stats["total_revenue"],
        "clients_by_plan": stats["plans"],
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
