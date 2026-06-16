"""
Rutas de rutinas: obtener, generar con IA, guardar.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import uuid
import os
import json

from core.database import db
from core.security import get_current_user, get_admin_user
from models.common import RoutineResponse, RoutineCreate
from models.user import PLAN_TYPES
from llm_client import LlmChat, UserMessage

router = APIRouter(prefix="/routines", tags=["routines"])

@router.get("/current", response_model=Optional[RoutineResponse])
async def get_current_routine(user = Depends(get_current_user)):
    """Obtener rutina actual del cliente."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    routine = await db.routines.find_one(
        {"client_id": profile["id"], "status": "active"},
        {"_id": 0}
    )
    
    if not routine:
        return None
    
    return RoutineResponse(**routine)

@router.get("/history", response_model=List[RoutineResponse])
async def get_routine_history(user = Depends(get_current_user)):
    """Obtener historial de rutinas."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    routines = await db.routines.find(
        {"client_id": profile["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    
    return [RoutineResponse(**r) for r in routines]


# ==================== ADMIN ROUTES ====================

admin_router = APIRouter(prefix="/admin/routines", tags=["admin-routines"])

@admin_router.post("/generate")
async def generate_routine_ai(data: RoutineCreate, user = Depends(get_admin_user)):
    """Generar rutina con IA."""
    profile = await db.client_profiles.find_one({"id": data.client_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    client_user = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "password": 0})
    
    reports = await db.reports.find({"client_id": data.client_id}, {"_id": 0}).sort("created_at", -1).to_list(3)
    prev_routines = await db.routines.find({"client_id": data.client_id}, {"_id": 0}).sort("created_at", -1).to_list(2)
    
    plan_features = PLAN_TYPES.get(profile["plan"], {}).get("features", [])
    include_cardio = "cardio" in plan_features
    
    context = f"""
Cliente: {client_user.get('name', 'Cliente')}
Plan: {profile['plan'].upper()}
Objetivo: {profile.get('goal', 'No especificado')}
Peso: {profile.get('weight', 'No especificado')} kg
Altura: {profile.get('height', 'No especificado')} cm
Edad: {profile.get('age', 'No especificado')} años
Sexo: {profile.get('sex', 'No especificado')}
Días de entrenamiento: {profile.get('training_days', 4)}
Equipamiento disponible: {', '.join(profile.get('equipment') or ['Gimnasio completo'])}
Lesiones/Limitaciones: {', '.join(profile.get('injuries') or ['Ninguna'])}

Macros actuales (entreno): P:{(profile.get('macros_training') or {}).get('protein', 'N/A')}g, H:{(profile.get('macros_training') or {}).get('carbs', 'N/A')}g, G:{(profile.get('macros_training') or {}).get('fat', 'N/A')}g

Incluir cardio: {'Sí' if include_cardio else 'No'}
Instrucciones del entrenador: {data.instructions or 'Generar rutina estándar según objetivo'}
"""

    prompt = f"""Genera una rutina de entrenamiento personalizada en formato JSON para el siguiente cliente:

{context}

La rutina debe tener este formato exacto:
{{
  "days": [
    {{"day": "Lunes", "is_rest": false, "exercises": [{{"name": "Nombre", "sets": 4, "reps": "10-12", "rest": "90s"}}]}},
    {{"day": "Martes", "is_rest": true, "exercises": []}}
  ],
  "trainer_notes": "Notas generales"
}}

Genera una rutina completa de 7 días. Responde SOLO con el JSON."""

    try:
        llm_key = os.environ.get('ANTHROPIC_API_KEY')
        chat = LlmChat(
            api_key=llm_key,
            session_id=f"routine-{data.client_id}-{uuid.uuid4()}",
            system_message="Eres un entrenador personal experto. Genera rutinas en formato JSON."
        ).with_model("anthropic", "claude-sonnet-4-6")
        
        response = await chat.send_message(UserMessage(text=prompt))
        
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        routine_data = json.loads(response_text)
        
        return {"generated": True, "routine": routine_data, "client_context": context}
        
    except Exception as e:
        default_routine = _get_default_routine()
        return {
            "generated": True,
            "routine": default_routine,
            "client_context": context,
            "note": "Rutina por defecto debido a error en generación IA"
        }

@admin_router.post("/save", response_model=RoutineResponse)
async def save_routine(client_id: str, routine: Dict[str, Any], user = Depends(get_admin_user)):
    """Guardar rutina para un cliente."""
    profile = await db.client_profiles.find_one({"id": client_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    await db.routines.update_many(
        {"client_id": client_id, "status": "active"},
        {"$set": {"status": "inactive"}}
    )
    
    routine_id = str(uuid.uuid4())
    routine_doc = {
        "id": routine_id,
        "client_id": client_id,
        "days": routine.get("days", []),
        "trainer_notes": routine.get("trainer_notes"),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.routines.insert_one(routine_doc)
    
    return RoutineResponse(**routine_doc)


def _get_default_routine():
    """Rutina por defecto."""
    return {
        "days": [
            {"day": "Lunes", "is_rest": False, "exercises": [
                {"name": "Press banca", "sets": 4, "reps": "8-10", "rest": "90s"},
                {"name": "Press inclinado", "sets": 3, "reps": "10-12", "rest": "75s"},
                {"name": "Aperturas", "sets": 3, "reps": "12-15", "rest": "60s"}
            ]},
            {"day": "Martes", "is_rest": True, "exercises": []},
            {"day": "Miércoles", "is_rest": False, "exercises": [
                {"name": "Sentadilla", "sets": 4, "reps": "8-10", "rest": "120s"},
                {"name": "Prensa", "sets": 4, "reps": "10-12", "rest": "90s"},
                {"name": "Curl femoral", "sets": 3, "reps": "10-12", "rest": "75s"}
            ]},
            {"day": "Jueves", "is_rest": True, "exercises": []},
            {"day": "Viernes", "is_rest": False, "exercises": [
                {"name": "Dominadas", "sets": 4, "reps": "6-10", "rest": "90s"},
                {"name": "Remo", "sets": 4, "reps": "8-10", "rest": "90s"},
                {"name": "Curl bíceps", "sets": 3, "reps": "10-12", "rest": "60s"}
            ]},
            {"day": "Sábado", "is_rest": True, "exercises": []},
            {"day": "Domingo", "is_rest": True, "exercises": []}
        ],
        "trainer_notes": "Rutina generada automáticamente."
    }
