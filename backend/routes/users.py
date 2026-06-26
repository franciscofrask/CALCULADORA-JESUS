"""
Rutas de usuarios: perfiles, preferencias y macros.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import uuid

from core.database import db
from core.security import get_current_user
from models.user import (
    ClientProfile, ClientProfileCreate, ClientProfileUpdate,
    MacrosUpdate, PLAN_TYPES, QuestionnaireSubmit
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

# ==================== CUESTIONARIO INICIAL (ELM) ====================

def _age_from_birthdate(birthdate: Optional[str]) -> Optional[int]:
    """Edad en años a partir de 'YYYY-MM-DD'. None si no parsea."""
    if not birthdate:
        return None
    try:
        b = datetime.strptime(birthdate[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    today = datetime.now(timezone.utc).date()
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))

@router.post("/clients/questionnaire", response_model=ClientProfile)
async def submit_questionnaire(data: QuestionnaireSubmit, user = Depends(get_current_user)):
    """Cuestionario inicial obligatorio (ELM hombre). Guarda las respuestas en el perfil,
    marca questionnaire_completed y recalcula los macros automáticamente (peso/sexo/%graso/objetivo)."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado. Selecciona un plan primero.")
    if profile.get("questionnaire_completed"):
        raise HTTPException(status_code=409, detail="El cuestionario ya fue completado.")

    sexo = (data.sex or "hombre").strip().lower()
    if sexo not in ("hombre", "mujer"):
        sexo = "hombre"
    update = {
        "questionnaire_completed": True,
        "goal": data.goal,
        "weight": data.weight,
        "height": data.height,
        "body_fat": data.body_fat,
        "sex": sexo,
        "birthdate": data.birthdate,
        "age": _age_from_birthdate(data.birthdate),
        "training_experience": data.training_experience,
        "activity_level": data.activity_level,
        "biotype": data.biotype,
    }

    # Calcular y aplicar macros (no pisar si el coach ya los fijó manualmente).
    try:
        targets = calcular_targets(float(data.weight), sexo, float(data.body_fat), data.goal)
        profile_macros = targets_to_profile_macros(targets)
        if profile.get("macros_source") != "manual":
            update["macros_training"] = profile_macros["macros_training"]
            update["macros_rest"] = profile_macros["macros_rest"]
            update["macros_periworkout"] = profile_macros["macros_periworkout"]
            update["macros_source"] = "auto"
            update["macros_multiplicadores"] = targets["multiplicadores"]
    except (ValueError, KeyError):
        pass  # datos fuera de tabla → guardar respuestas igual, sin macros

    # Actualizar nombre/teléfono del usuario si los aportó.
    user_update = {}
    if data.name:
        user_update["name"] = data.name
    if data.phone:
        user_update["phone"] = data.phone
    if user_update:
        await db.users.update_one({"id": user["id"]}, {"$set": user_update})

    await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update})

    # Versionar en macro_history (Calma todosLosMacros) los macros calculados por el quiz, igual
    # que hacen PUT /macros y el admin. Sin esto, el resolver por fecha (dietas, ajustar macros)
    # usaría entradas antiguas o el fallback e ignoraría los macros recién calculados → desajuste.
    if "macros_training" in update:
        client_id = profile.get("id") or str(uuid.uuid4())
        if not profile.get("id"):
            await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": {"id": client_id}})
        training = update["macros_training"]
        rest = update["macros_rest"]
        peri = update.get("macros_periworkout")
        effective_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        await db.macro_history.insert_one({
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "user_id": user["id"],
            "previous_training": profile.get("macros_training"),
            "previous_rest": profile.get("macros_rest"),
            "new_training": training,
            "new_rest": rest,
            "training": training,
            "rest": rest,
            "peri": peri,
            "effective_date": effective_date,
            "note": "Cuestionario inicial",
            "changed_by": user.get("name", user.get("email", "cliente")),
            "client_weight": data.weight,
            "peso": data.weight,
            "porcentaje_graso": data.body_fat,
            "sexo": sexo,
            "objetivo": data.goal,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    updated = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    return ClientProfile(**updated)

# ==================== USER PREFERENCES ====================

@router.get("/user/preferences")
async def get_user_preferences(user = Depends(get_current_user)):
    """Obtener preferencias de alimentos del usuario."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        return {"food_preferences": [], "avoided_categories": [], "avoided_keywords": [], "has_preferences": False}

    preferences = profile.get("food_preferences", [])
    return {
        "food_preferences": preferences,
        "avoided_categories": profile.get("avoided_categories", []),
        "avoided_keywords": profile.get("avoided_keywords", []),
        "has_preferences": len(preferences) > 0
    }

@router.post("/user/preferences")
async def save_user_preferences(data: dict, user = Depends(get_current_user)):
    """Guardar preferencias y alimentos a evitar del usuario."""
    preferences = data.get("food_preferences", [])
    avoided_categories = data.get("avoided_categories", [])
    avoided_keywords = data.get("avoided_keywords", [])

    if len(preferences) < 3:
        raise HTTPException(status_code=400, detail="Debes seleccionar al menos 3 categorías")

    await db.client_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "food_preferences": preferences,
            "avoided_categories": avoided_categories,
            "avoided_keywords": avoided_keywords,
        }, "$setOnInsert": {"id": str(uuid.uuid4())}},
        upsert=True
    )

    return {"success": True, "food_preferences": preferences, "avoided_categories": avoided_categories, "avoided_keywords": avoided_keywords}

# ==================== DIET CONFIG ====================

@router.get("/user/diet-config")
async def get_diet_config(user = Depends(get_current_user)):
    """Obtener configuración de dieta persistida (momento entreno, num comidas, opcion peri)."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    defaults = {"momento_entreno": 1, "num_comidas": 4, "opcion_peri": "intra_post"}
    if not profile:
        return defaults
    # num_comidas: la elección del cliente manda; si no eligió, deriva del ajuste del
    # coach (single_meal_mode -> 1 comida), si no, 4.
    num_comidas = profile.get("diet_num_comidas")
    if num_comidas is None:
        num_comidas = 1 if profile.get("single_meal_mode") else 4
    return {
        "momento_entreno": profile.get("diet_momento_entreno", 1),
        "num_comidas": num_comidas,
        "opcion_peri": profile.get("diet_opcion_peri", "intra_post"),
    }

@router.patch("/user/diet-config")
async def save_diet_config(data: dict, user = Depends(get_current_user)):
    """Guardar configuración de dieta para el usuario (persiste entre dispositivos)."""
    allowed = {"momento_entreno", "num_comidas", "opcion_peri"}
    update = {}
    if "momento_entreno" in data and isinstance(data["momento_entreno"], int):
        update["diet_momento_entreno"] = data["momento_entreno"]
    if "num_comidas" in data and isinstance(data["num_comidas"], int):
        update["diet_num_comidas"] = data["num_comidas"]
    if "opcion_peri" in data and isinstance(data["opcion_peri"], str):
        update["diet_opcion_peri"] = data["opcion_peri"]
    if update:
        await db.client_profiles.update_one(
            {"user_id": user["id"]},
            {"$set": update},
            upsert=False
        )
    return {"ok": True}

# ==================== MACROS ====================

@router.get("/macros")
async def get_macros(fecha: Optional[str] = None, user = Depends(get_current_user)):
    """Obtener macros del usuario. Si se pasa `fecha` (YYYY-MM-DD), devuelve la versión de
    macros VIGENTE a esa fecha (date-versioned, Calma todosLosMacros): la última entrada de
    macro_history con effective_date <= fecha; antes del primer cambio, la más antigua; sin
    historial, los macros actuales del perfil. Así el editor precarga los del día elegido."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        return {
            "training": {"protein": 160, "carbs": 50, "fat": 40},
            "rest": {"protein": 140, "carbs": 40, "fat": 40},
            "periworkout": {"protein": 35, "carbs": 15},
            "source": "default"
        }
    if fecha:
        # Reusa el mismo resolver que las dietas, para no divergir.
        from routes.calculator import _resolve_macros_for_date, _choose_macro_entry_for_date
        training, rest, peri = await _resolve_macros_for_date(profile, fecha)
        entry = await _choose_macro_entry_for_date(profile, fecha)
        # Inputs de la entrada vigente; si la entrada es legacy (sin inputs) cae al perfil.
        inputs = {
            "peso": (entry or {}).get("peso") if entry else None,
            "porcentaje_graso": (entry or {}).get("porcentaje_graso") if entry else None,
            "sexo": (entry or {}).get("sexo") if entry else None,
            "objetivo": (entry or {}).get("objetivo") if entry else None,
        }
        if inputs["peso"] is None: inputs["peso"] = profile.get("weight")
        if inputs["porcentaje_graso"] is None: inputs["porcentaje_graso"] = profile.get("body_fat")
        if inputs["sexo"] is None: inputs["sexo"] = profile.get("sex")
        if inputs["objetivo"] is None: inputs["objetivo"] = profile.get("goal")
        return {
            "training": training or {"protein": 160, "carbs": 50, "fat": 40},
            "rest": rest or {"protein": 140, "carbs": 40, "fat": 40},
            "periworkout": peri or {"protein": 35, "carbs": 15},
            "source": profile.get("macros_source", "default"),
            "fecha": fecha,
            **inputs,
        }
    return {
        "training": profile.get("macros_training") or {"protein": 160, "carbs": 50, "fat": 40},
        "rest": profile.get("macros_rest") or {"protein": 140, "carbs": 40, "fat": 40},
        "periworkout": profile.get("macros_periworkout") or {"protein": 35, "carbs": 15},
        "source": profile.get("macros_source", "default"),
        "peso": profile.get("weight"),
        "porcentaje_graso": profile.get("body_fat"),
        "sexo": profile.get("sex"),
        "objetivo": profile.get("goal"),
    }

@router.put("/macros", response_model=Dict[str, Any])
async def update_macros(data: MacrosUpdate, user = Depends(get_current_user)):
    """Actualizar macros del usuario (override manual, versionado por fecha).

    El cliente ajusta sus propios macros igual que el admin: además de guardarlos en el
    perfil, se registra una entrada en `macro_history` con `effective_date` para que las
    dietas resuelvan la versión vigente a cada fecha (Calma todosLosMacros). Antes esto
    escribía en `macro_logs` sin fecha ni peri, así que los cambios del cliente no se
    versionaban ni los veía el resolver de dietas.
    """
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    training = data.training.model_dump()
    rest = data.rest.model_dump()
    training["calories"] = training["protein"] * 4 + training["carbs"] * 4 + training["fat"] * 9
    rest["calories"] = rest["protein"] * 4 + rest["carbs"] * 4 + rest["fat"] * 9
    # Formato alternativo (proteinas/hidratos/grasas) para el chatbot y el motor de dietas.
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

    peri = None
    if data.peri is not None:
        peri = data.peri.model_dump()
        peri["calories"] = peri["protein"] * 4 + peri["carbs"] * 4
        peri["proteinas"] = peri["protein"]
        peri["hidratos"] = peri["carbs"]
        update["macros_periworkout"] = peri

    # Calc inputs → también al perfil (peso/%graso/sexo/objetivo) para que la calculadora
    # precargue los últimos valores y haya trazabilidad del estado actual.
    if data.peso is not None:
        update["weight"] = data.peso
    if data.porcentaje_graso is not None:
        update["body_fat"] = data.porcentaje_graso
    if data.sexo:
        update["sex"] = data.sexo
    if data.objetivo:
        update["goal"] = data.objetivo

    # El versionado por fecha (macro_history) se indexa por profile.id. Algunos perfiles antiguos
    # no tienen el campo `id`; lo generamos y persistimos para que el resolver de dietas funcione.
    client_id = profile.get("id") or str(uuid.uuid4())
    if not profile.get("id"):
        update["id"] = client_id

    await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update})

    # Macros versionados por fecha (Calma todosLosMacros): la entrada registra la fecha DESDE la
    # que aplican. Por defecto = hoy. El resolver (_resolve_macros_for_date) elige la última
    # entrada con effective_date <= fecha de la dieta, así las dietas pasadas mantienen su versión.
    effective_date = data.effective_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    macro_log = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "user_id": user["id"],
        "previous_training": profile.get("macros_training"),
        "previous_rest": profile.get("macros_rest"),
        "new_training": training,
        "new_rest": rest,
        "training": training,
        "rest": rest,
        "peri": peri,
        "effective_date": effective_date,
        "note": data.note,
        "changed_by": user.get("name", user.get("email", "cliente")),
        "client_weight": data.peso if data.peso is not None else profile.get("weight"),
        # Calc inputs guardados POR cambio → trazabilidad de cómo se derivaron los macros.
        "peso": data.peso,
        "porcentaje_graso": data.porcentaje_graso,
        "sexo": data.sexo,
        "objetivo": data.objetivo,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.macro_history.insert_one(macro_log)

    return {
        "success": True,
        "training": training,
        "rest": rest,
        "peri": peri,
        "effective_date": effective_date,
    }


# ==================== FAVORITE FOODS ====================

@router.get("/favorites")
async def get_favorites(user = Depends(get_current_user)):
    """Get user's favorite food IDs."""
    doc = await db.food_favorites.find_one({"user_id": user["id"]}, {"_id": 0})
    return {"favorites": doc.get("food_ids", []) if doc else []}


@router.post("/favorites/{food_id}")
async def add_favorite(food_id: int, user = Depends(get_current_user)):
    """Add a food to favorites."""
    await db.food_favorites.update_one(
        {"user_id": user["id"]},
        {"$addToSet": {"food_ids": food_id}},
        upsert=True
    )
    doc = await db.food_favorites.find_one({"user_id": user["id"]}, {"_id": 0})
    return {"favorites": doc.get("food_ids", [])}


@router.delete("/favorites/{food_id}")
async def remove_favorite(food_id: int, user = Depends(get_current_user)):
    """Remove a food from favorites."""
    await db.food_favorites.update_one(
        {"user_id": user["id"]},
        {"$pull": {"food_ids": food_id}}
    )
    doc = await db.food_favorites.find_one({"user_id": user["id"]}, {"_id": 0})
    return {"favorites": doc.get("food_ids", []) if doc else []}
