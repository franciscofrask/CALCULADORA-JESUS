"""
Rutas de usuarios: perfiles, preferencias y macros.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import uuid

from core.database import db
from core.security import get_current_user
from models.user import (
    ClientProfile, ClientProfileCreate, ClientProfileUpdate,
    MacrosUpdate, PLAN_TYPES
)
from target_calculator import calcular_targets, targets_to_profile_macros

router = APIRouter(tags=["users"])

# ==================== CLIENT PROFILE ====================

@router.post("/clients/profile", response_model=ClientProfile)
async def create_client_profile(data: ClientProfileCreate, user = Depends(get_current_user)):
    """Crear perfil de cliente."""
    existing = await db.client_profiles.find_one({"user_id": user["id"]})
    if existing:
        raise HTTPException(status_code=400, detail="Ya tienes un perfil de cliente")
    
    plan_info = PLAN_TYPES.get(data.plan.lower())
    if not plan_info:
        raise HTTPException(status_code=400, detail="Plan no válido")
    
    profile_id = str(uuid.uuid4())
    profile = {
        "id": profile_id,
        "user_id": user["id"],
        "plan": data.plan.lower(),
        "price": data.price or plan_info["price"],
        "week": 1,
        "status": "activo",
        "trainer_id": data.trainer_id,
        "next_payment": (datetime.now(timezone.utc) + timedelta(days=28)).isoformat(),
        "macros_training": None,
        "macros_rest": None,
        "weight": None,
        "height": None,
        "age": None,
        "sex": None,
        "goal": None,
        "equipment": None,
        "injuries": None,
        "training_days": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.client_profiles.insert_one(profile)
    
    # Update user plan
    await db.users.update_one({"id": user["id"]}, {"$set": {"plan": data.plan.lower()}})
    
    # Create mock payment
    payment = {
        "id": str(uuid.uuid4()),
        "client_id": profile_id,
        "amount": profile["price"],
        "status": "success",
        "method": "card",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payments.insert_one(payment)
    
    return ClientProfile(**profile)

@router.get("/clients/profile", response_model=ClientProfile)
async def get_client_profile(user = Depends(get_current_user)):
    """Obtener perfil del cliente actual."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return ClientProfile(**profile)

@router.put("/clients/profile", response_model=ClientProfile)
async def update_client_profile(data: ClientProfileUpdate, user = Depends(get_current_user)):
    """Actualizar perfil del cliente. Si peso/sexo/bf/objetivo cambian, recalcula macros."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    # Auto-calculate macros if body data is provided and macros_source is not 'manual'
    body_fields = {"weight", "sex", "goal", "body_fat"}
    if body_fields & set(update_data.keys()):
        # Merge with existing profile data
        peso = update_data.get("weight") or profile.get("weight")
        sexo = update_data.get("sex") or profile.get("sex")
        bf = update_data.get("body_fat") or profile.get("body_fat")
        objetivo = update_data.get("goal") or profile.get("goal")

        if all([peso, sexo, bf, objetivo]):
            try:
                targets = calcular_targets(float(peso), sexo, float(bf), objetivo)
                profile_macros = targets_to_profile_macros(targets)
                # Only auto-set if macros haven't been manually overridden
                if profile.get("macros_source") != "manual":
                    update_data["macros_training"] = profile_macros["macros_training"]
                    update_data["macros_rest"] = profile_macros["macros_rest"]
                    update_data["macros_periworkout"] = profile_macros["macros_periworkout"]
                    update_data["macros_source"] = "auto"
                    update_data["macros_multiplicadores"] = targets["multiplicadores"]
            except (ValueError, KeyError):
                pass  # Si los datos no son válidos, no recalcular

    if update_data:
        await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update_data})
    
    updated = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    return ClientProfile(**updated)

# ==================== USER PREFERENCES ====================

@router.get("/user/preferences")
async def get_user_preferences(user = Depends(get_current_user)):
    """Obtener preferencias de alimentos del usuario."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        return {"food_preferences": [], "has_preferences": False}
    
    preferences = profile.get("food_preferences", [])
    return {
        "food_preferences": preferences,
        "has_preferences": len(preferences) > 0
    }

@router.post("/user/preferences")
async def save_user_preferences(data: dict, user = Depends(get_current_user)):
    """Guardar preferencias de alimentos del usuario."""
    preferences = data.get("food_preferences", [])
    
    if len(preferences) < 3:
        raise HTTPException(status_code=400, detail="Debes seleccionar al menos 3 categorías")
    
    await db.client_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {"food_preferences": preferences}},
        upsert=True
    )
    
    return {"success": True, "food_preferences": preferences}

# ==================== MACROS ====================

@router.get("/macros")
async def get_macros(user = Depends(get_current_user)):
    """Obtener macros del usuario."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        return {
            "training": {"protein": 160, "carbs": 50, "fat": 40},
            "rest": {"protein": 140, "carbs": 40, "fat": 40},
            "periworkout": {"protein": 35, "carbs": 15},
            "source": "default"
        }
    return {
        "training": profile.get("macros_training") or {"protein": 160, "carbs": 50, "fat": 40},
        "rest": profile.get("macros_rest") or {"protein": 140, "carbs": 40, "fat": 40},
        "periworkout": profile.get("macros_periworkout") or {"protein": 35, "carbs": 15},
        "source": profile.get("macros_source", "default")
    }

@router.put("/macros", response_model=Dict[str, Any])
async def update_macros(data: MacrosUpdate, user = Depends(get_current_user)):
    """Actualizar macros del usuario (manual override)."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    training = data.training.model_dump()
    rest = data.rest.model_dump()
    training["proteinas"] = training["protein"]
    training["hidratos"] = training["carbs"]
    training["grasas"] = training["fat"]
    rest["proteinas"] = rest["protein"]
    rest["hidratos"] = rest["carbs"]
    rest["grasas"] = rest["fat"]

    update = {
        "macros_training": training,
        "macros_rest": rest,
        "macros_source": "manual",
    }
    
    await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update})
    
    # Log the macro change
    macro_log = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "training": data.training.model_dump(),
        "rest": data.rest.model_dump(),
        "note": data.note,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.macro_logs.insert_one(macro_log)
    
    return {
        "success": True,
        "training": data.training.model_dump(),
        "rest": data.rest.model_dump()
    }
