from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from emergentintegrations.llm.chat import LlmChat, UserMessage
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', '12en12-secret-key')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Create the main app
app = FastAPI(title="12EN12 API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Create indexes for fast search
@app.on_event("startup")
async def create_indexes():
    try:
        await db.foods.create_index([("nombre", "text")])
        await db.foods.create_index("id", unique=True)
        await db.foods.create_index("categorias")
        await db.diets.create_index([("user_id", 1), ("fecha", 1)], unique=True)
        logger.info("MongoDB indexes created successfully")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")


# ==================== MODELS ====================

# Plan Types
PLAN_TYPES = {
    "gold": {"name": "Gold", "price": 149, "features": ["rutina", "macros", "chat", "reporte_quincenal", "suplementacion", "cardio", "audio"]},
    "silver": {"name": "Silver", "price": 99, "features": ["rutina", "macros", "chat", "reporte_mensual"]},
    "bronze": {"name": "Bronze", "price": 69, "features": ["rutina", "macros", "chat", "reporte_mensual"]},
    "elm": {"name": "ELM", "price": 39, "features": ["macros", "chat"]}
}

# User Models
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    phone: Optional[str] = None
    role: str
    plan: Optional[str] = None
    trainer_id: Optional[str] = None
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Client Profile Models
class ClientProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    plan: str
    price: float
    week: int = 1
    status: str = "activo"
    trainer_id: Optional[str] = None
    next_payment: Optional[str] = None
    macros_training: Optional[Dict[str, float]] = None
    macros_rest: Optional[Dict[str, float]] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    goal: Optional[str] = None
    equipment: Optional[List[str]] = None
    injuries: Optional[List[str]] = None
    training_days: Optional[int] = None
    created_at: str

class ClientProfileCreate(BaseModel):
    plan: str
    price: Optional[float] = None
    trainer_id: Optional[str] = None

class ClientProfileUpdate(BaseModel):
    plan: Optional[str] = None
    price: Optional[float] = None
    week: Optional[int] = None
    status: Optional[str] = None
    trainer_id: Optional[str] = None
    macros_training: Optional[Dict[str, float]] = None
    macros_rest: Optional[Dict[str, float]] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    goal: Optional[str] = None
    equipment: Optional[List[str]] = None
    injuries: Optional[List[str]] = None
    training_days: Optional[int] = None

# Macros Models
class MacrosData(BaseModel):
    protein: float
    carbs: float
    fat: float
    calories: Optional[float] = None

class MacrosUpdate(BaseModel):
    training: MacrosData
    rest: MacrosData
    note: Optional[str] = None

# Routine Models
class Exercise(BaseModel):
    name: str
    sets: int
    reps: str
    rest: str
    video_url: Optional[str] = None
    notes: Optional[str] = None

class RoutineDay(BaseModel):
    day: str
    is_rest: bool = False
    exercises: List[Exercise] = []
    cardio: Optional[Dict[str, Any]] = None

class RoutineCreate(BaseModel):
    client_id: str
    instructions: Optional[str] = None

class RoutineResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    days: List[RoutineDay]
    trainer_notes: Optional[str] = None
    created_at: str
    status: str = "active"

# Report Models
class ReportCreate(BaseModel):
    weight: float
    measurements: Optional[Dict[str, float]] = None
    photos: Optional[List[str]] = None
    training_compliance: Optional[int] = None
    nutrition_compliance: Optional[int] = None
    sleep_quality: Optional[int] = None
    energy_level: Optional[int] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None

class ReportResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    weight: float
    measurements: Optional[Dict[str, float]] = None
    photos: Optional[List[str]] = None
    training_compliance: Optional[int] = None
    nutrition_compliance: Optional[int] = None
    sleep_quality: Optional[int] = None
    energy_level: Optional[int] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None
    trainer_feedback: Optional[str] = None
    created_at: str

# Message Models
class MessageCreate(BaseModel):
    receiver_id: str
    content: str

class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    sender_id: str
    receiver_id: str
    content: str
    read: bool = False
    created_at: str

# Payment Models (Mocked)
class PaymentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    amount: float
    status: str
    method: str = "card"
    created_at: str

# Food Suggestion Models
class FoodSuggestion(BaseModel):
    name: str
    calories_per_100g: Optional[float] = None
    protein_per_100g: Optional[float] = None
    carbs_per_100g: Optional[float] = None
    fat_per_100g: Optional[float] = None

class FoodSuggestionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    food: FoodSuggestion
    status: str = "pending"
    created_at: str

# ==================== AUTH HELPERS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

async def get_admin_user(user = Depends(get_current_user)):
    if user["role"] not in ["admin", "operations", "trainer"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return user

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(data: UserRegister):
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": data.email,
        "password": hash_password(data.password),
        "name": data.name,
        "phone": data.phone,
        "role": "client",
        "plan": None,
        "trainer_id": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user)
    
    token = create_token(user_id, "client")
    user_response = {k: v for k, v in user.items() if k != "password"}
    return TokenResponse(access_token=token, user=UserResponse(**user_response))

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(data: UserLogin):
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    token = create_token(user["id"], user["role"])
    user_response = {k: v for k, v in user.items() if k != "password"}
    return TokenResponse(access_token=token, user=UserResponse(**user_response))

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user = Depends(get_current_user)):
    return UserResponse(**{k: v for k, v in user.items() if k != "password"})

# ==================== CLIENT PROFILE ROUTES ====================

@api_router.post("/clients/profile", response_model=ClientProfile)
async def create_client_profile(data: ClientProfileCreate, user = Depends(get_current_user)):
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

@api_router.get("/clients/profile", response_model=ClientProfile)
async def get_client_profile(user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return ClientProfile(**profile)

@api_router.put("/clients/profile", response_model=ClientProfile)
async def update_client_profile(data: ClientProfileUpdate, user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_data:
        await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": update_data})
    
    updated = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    return ClientProfile(**updated)


# ==================== USER PREFERENCES ====================

@api_router.get("/user/preferences")
async def get_user_preferences(user = Depends(get_current_user)):
    """
    Devuelve las preferencias de alimentos del usuario.
    Si nunca configuró preferencias: { "food_preferences": [], "has_preferences": false }
    """
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        return {"food_preferences": [], "has_preferences": False}
    
    preferences = profile.get("food_preferences", [])
    return {
        "food_preferences": preferences,
        "has_preferences": len(preferences) > 0
    }


@api_router.post("/user/preferences")
async def save_user_preferences(data: dict, user = Depends(get_current_user)):
    """
    Guarda las preferencias de alimentos del usuario.
    Recibe: { "food_preferences": ["aves", "lacteos", "fruta", "chocolates"] }
    """
    preferences = data.get("food_preferences", [])
    
    if len(preferences) < 3:
        raise HTTPException(status_code=400, detail="Debes seleccionar al menos 3 categorías")
    
    # Update or create profile with preferences
    result = await db.client_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {"food_preferences": preferences}},
        upsert=True
    )
    
    return {"success": True, "food_preferences": preferences}


# ==================== ADMIN CLIENT ROUTES ====================

@api_router.get("/admin/clients", response_model=List[Dict[str, Any]])
async def get_all_clients(
    plan: Optional[str] = None,
    status: Optional[str] = None,
    trainer_id: Optional[str] = None,
    user = Depends(get_admin_user)
):
    query = {}
    if plan:
        query["plan"] = plan.lower()
    if status:
        query["status"] = status
    if trainer_id:
        query["trainer_id"] = trainer_id
    
    profiles = await db.client_profiles.find(query, {"_id": 0}).to_list(1000)
    
    # Enrich with user data
    result = []
    for profile in profiles:
        user_data = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "password": 0})
        if user_data:
            result.append({**profile, "user": user_data})
    
    return result

@api_router.get("/admin/clients/{client_id}")
async def get_client_detail(client_id: str, user = Depends(get_admin_user)):
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

@api_router.put("/admin/clients/{client_id}", response_model=ClientProfile)
async def update_client_admin(client_id: str, data: ClientProfileUpdate, user = Depends(get_admin_user)):
    profile = await db.client_profiles.find_one({"id": client_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_data:
        await db.client_profiles.update_one({"id": client_id}, {"$set": update_data})
    
    updated = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    return ClientProfile(**updated)

# ==================== MACROS ROUTES ====================

@api_router.get("/macros")
async def get_macros(user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    return {
        "training": profile.get("macros_training"),
        "rest": profile.get("macros_rest")
    }

@api_router.put("/macros", response_model=Dict[str, Any])
async def update_macros(data: MacrosUpdate, user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    # Calculate calories
    training = data.training.model_dump()
    rest = data.rest.model_dump()
    training["calories"] = training["protein"] * 4 + training["carbs"] * 4 + training["fat"] * 9
    rest["calories"] = rest["protein"] * 4 + rest["carbs"] * 4 + rest["fat"] * 9
    
    await db.client_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {"macros_training": training, "macros_rest": rest}}
    )
    
    # Log macro history
    macro_log = {
        "id": str(uuid.uuid4()),
        "client_id": profile["id"],
        "training": training,
        "rest": rest,
        "note": data.note,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.macro_history.insert_one(macro_log)
    
    return {"training": training, "rest": rest}

@api_router.put("/admin/clients/{client_id}/macros")
async def update_client_macros(client_id: str, data: MacrosUpdate, user = Depends(get_admin_user)):
    profile = await db.client_profiles.find_one({"id": client_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    training = data.training.model_dump()
    rest = data.rest.model_dump()
    training["calories"] = training["protein"] * 4 + training["carbs"] * 4 + training["fat"] * 9
    rest["calories"] = rest["protein"] * 4 + rest["carbs"] * 4 + rest["fat"] * 9
    
    await db.client_profiles.update_one(
        {"id": client_id},
        {"$set": {"macros_training": training, "macros_rest": rest}}
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

# ==================== MACRO CALCULATOR ROUTES ====================

@api_router.get("/calculator/foods")
async def get_foods(search: Optional[str] = None, category: Optional[str] = None, limit: int = 100, user = Depends(get_current_user)):
    """Obtiene la lista de alimentos desde MongoDB con filtros opcionales"""
    query = {}
    
    if search:
        # Búsqueda por nombre (case-insensitive)
        query["nombre"] = {"$regex": search, "$options": "i"}
    
    if category:
        # Búsqueda por categoría
        query["categorias"] = {"$regex": category}
    
    foods_cursor = db.foods.find(query, {"_id": 0}).limit(limit)
    foods = await foods_cursor.to_list(limit)
    
    return foods


@api_router.get("/calculator/foods/count")
async def get_foods_count(user = Depends(get_current_user)):
    """Retorna el conteo total de alimentos en la base de datos"""
    count = await db.foods.count_documents({})
    return {"total": count}


@api_router.get("/calculator/categories")
async def get_food_categories(user = Depends(get_current_user)):
    """Obtiene todas las categorías de alimentos desde MongoDB"""
    categories_cursor = db.food_categories.find({}, {"_id": 0})
    categories = await categories_cursor.to_list(500)
    return categories


@api_router.get("/calculator/categories/count")
async def get_categories_count(user = Depends(get_current_user)):
    """Retorna el conteo total de categorías en la base de datos"""
    count = await db.food_categories.count_documents({})
    return {"total": count}

@api_router.post("/calculator/meal")
async def calculate_meal(foods: List[Dict[str, Any]], user = Depends(get_current_user)):
    """Calculate total macros for a meal from food items with quantities"""
    total = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    
    for item in foods:
        quantity = item.get("quantity", 100) / 100  # Convert to 100g units
        total["calories"] += item.get("calories", 0) * quantity
        total["protein"] += item.get("protein", 0) * quantity
        total["carbs"] += item.get("carbs", 0) * quantity
        total["fat"] += item.get("fat", 0) * quantity
    
    return {k: round(v, 1) for k, v in total.items()}

@api_router.post("/calculator/suggest-food", response_model=FoodSuggestionResponse)
async def suggest_food(food: FoodSuggestion, user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    suggestion = {
        "id": str(uuid.uuid4()),
        "client_id": profile["id"],
        "food": food.model_dump(),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.food_suggestions.insert_one(suggestion)
    
    return FoodSuggestionResponse(**suggestion)

# ==================== ROUTINE ROUTES ====================

@api_router.get("/routines/current", response_model=Optional[RoutineResponse])
async def get_current_routine(user = Depends(get_current_user)):
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

@api_router.get("/routines/history", response_model=List[RoutineResponse])
async def get_routine_history(user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    routines = await db.routines.find(
        {"client_id": profile["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    
    return [RoutineResponse(**r) for r in routines]

@api_router.post("/admin/routines/generate")
async def generate_routine_ai(data: RoutineCreate, user = Depends(get_admin_user)):
    profile = await db.client_profiles.find_one({"id": data.client_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    client_user = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "password": 0})
    
    # Get client context
    reports = await db.reports.find({"client_id": data.client_id}, {"_id": 0}).sort("created_at", -1).to_list(3)
    prev_routines = await db.routines.find({"client_id": data.client_id}, {"_id": 0}).sort("created_at", -1).to_list(2)
    
    # Build AI prompt
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

Últimos reportes: {len(reports)} disponibles
Rutinas anteriores: {len(prev_routines)} disponibles

Incluir cardio: {'Sí' if include_cardio else 'No'}

Instrucciones del entrenador: {data.instructions or 'Generar rutina estándar según objetivo'}
"""

    prompt = f"""Genera una rutina de entrenamiento personalizada en formato JSON para el siguiente cliente:

{context}

La rutina debe tener este formato exacto:
{{
  "days": [
    {{
      "day": "Lunes",
      "is_rest": false,
      "exercises": [
        {{"name": "Nombre ejercicio", "sets": 4, "reps": "10-12", "rest": "90s", "notes": "opcional"}}
      ],
      "cardio": {{"type": "HIIT/LISS", "duration": "20min", "notes": ""}} // solo si include_cardio es true
    }},
    {{
      "day": "Martes",
      "is_rest": true,
      "exercises": []
    }}
  ],
  "trainer_notes": "Notas generales sobre la rutina"
}}

Genera una rutina completa de 7 días adaptada al cliente. Responde SOLO con el JSON, sin texto adicional."""

    try:
        llm_key = os.environ.get('EMERGENT_LLM_KEY')
        chat = LlmChat(
            api_key=llm_key,
            session_id=f"routine-{data.client_id}-{uuid.uuid4()}",
            system_message="Eres un entrenador personal experto. Genera rutinas de entrenamiento personalizadas en formato JSON."
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        response = await chat.send_message(UserMessage(text=prompt))
        
        # Parse JSON response
        import json
        # Clean response - remove markdown code blocks if present
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        routine_data = json.loads(response_text)
        
        return {
            "generated": True,
            "routine": routine_data,
            "client_context": context
        }
        
    except Exception as e:
        logger.error(f"Error generating routine: {e}")
        # Return a default routine template
        default_routine = {
            "days": [
                {"day": "Lunes", "is_rest": False, "exercises": [
                    {"name": "Press banca", "sets": 4, "reps": "8-10", "rest": "90s"},
                    {"name": "Press inclinado mancuernas", "sets": 3, "reps": "10-12", "rest": "75s"},
                    {"name": "Aperturas", "sets": 3, "reps": "12-15", "rest": "60s"},
                    {"name": "Press militar", "sets": 4, "reps": "8-10", "rest": "90s"},
                    {"name": "Elevaciones laterales", "sets": 3, "reps": "12-15", "rest": "60s"}
                ]},
                {"day": "Martes", "is_rest": True, "exercises": []},
                {"day": "Miércoles", "is_rest": False, "exercises": [
                    {"name": "Sentadilla", "sets": 4, "reps": "8-10", "rest": "120s"},
                    {"name": "Prensa", "sets": 4, "reps": "10-12", "rest": "90s"},
                    {"name": "Extensiones cuádriceps", "sets": 3, "reps": "12-15", "rest": "60s"},
                    {"name": "Curl femoral", "sets": 3, "reps": "10-12", "rest": "75s"},
                    {"name": "Elevaciones gemelos", "sets": 4, "reps": "15-20", "rest": "60s"}
                ]},
                {"day": "Jueves", "is_rest": True, "exercises": []},
                {"day": "Viernes", "is_rest": False, "exercises": [
                    {"name": "Dominadas", "sets": 4, "reps": "6-10", "rest": "90s"},
                    {"name": "Remo con barra", "sets": 4, "reps": "8-10", "rest": "90s"},
                    {"name": "Jalón al pecho", "sets": 3, "reps": "10-12", "rest": "75s"},
                    {"name": "Curl bíceps barra", "sets": 3, "reps": "10-12", "rest": "60s"},
                    {"name": "Curl martillo", "sets": 3, "reps": "12-15", "rest": "60s"}
                ]},
                {"day": "Sábado", "is_rest": True, "exercises": []},
                {"day": "Domingo", "is_rest": True, "exercises": []}
            ],
            "trainer_notes": "Rutina generada automáticamente. Ajustar según feedback del cliente."
        }
        
        return {
            "generated": True,
            "routine": default_routine,
            "client_context": context,
            "note": "Rutina por defecto debido a error en generación IA"
        }

@api_router.post("/admin/routines/save", response_model=RoutineResponse)
async def save_routine(client_id: str, routine: Dict[str, Any], user = Depends(get_admin_user)):
    profile = await db.client_profiles.find_one({"id": client_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Deactivate previous routines
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

# ==================== REPORT ROUTES ====================

@api_router.post("/reports", response_model=ReportResponse)
async def create_report(data: ReportCreate, user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    report_id = str(uuid.uuid4())
    report = {
        "id": report_id,
        "client_id": profile["id"],
        **data.model_dump(),
        "trainer_feedback": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.reports.insert_one(report)
    
    # Update client weight
    await db.client_profiles.update_one(
        {"id": profile["id"]},
        {"$set": {"weight": data.weight}}
    )
    
    return ReportResponse(**report)

@api_router.get("/reports", response_model=List[ReportResponse])
async def get_reports(user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    reports = await db.reports.find(
        {"client_id": profile["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return [ReportResponse(**r) for r in reports]

@api_router.get("/reports/evolution")
async def get_evolution(user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    reports = await db.reports.find(
        {"client_id": profile["id"]},
        {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    
    evolution = {
        "weight": [{"date": r["created_at"], "value": r["weight"]} for r in reports if r.get("weight")],
        "measurements": {},
        "photos": [{"date": r["created_at"], "photos": r.get("photos", [])} for r in reports if r.get("photos")]
    }
    
    # Aggregate measurements
    for report in reports:
        if report.get("measurements"):
            for key, value in report["measurements"].items():
                if key not in evolution["measurements"]:
                    evolution["measurements"][key] = []
                evolution["measurements"][key].append({"date": report["created_at"], "value": value})
    
    return evolution

# ==================== MESSAGE ROUTES ====================

@api_router.post("/messages", response_model=MessageResponse)
async def send_message(data: MessageCreate, user = Depends(get_current_user)):
    message_id = str(uuid.uuid4())
    message = {
        "id": message_id,
        "sender_id": user["id"],
        "receiver_id": data.receiver_id,
        "content": data.content,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(message)
    
    return MessageResponse(**message)

@api_router.get("/messages", response_model=List[MessageResponse])
async def get_messages(with_user: Optional[str] = None, user = Depends(get_current_user)):
    query = {"$or": [{"sender_id": user["id"]}, {"receiver_id": user["id"]}]}
    
    if with_user:
        query = {
            "$or": [
                {"sender_id": user["id"], "receiver_id": with_user},
                {"sender_id": with_user, "receiver_id": user["id"]}
            ]
        }
    
    messages = await db.messages.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    return [MessageResponse(**m) for m in messages]

@api_router.put("/messages/{message_id}/read")
async def mark_message_read(message_id: str, user = Depends(get_current_user)):
    await db.messages.update_one(
        {"id": message_id, "receiver_id": user["id"]},
        {"$set": {"read": True}}
    )
    return {"success": True}

@api_router.get("/messages/unread-count")
async def get_unread_count(user = Depends(get_current_user)):
    count = await db.messages.count_documents({"receiver_id": user["id"], "read": False})
    return {"count": count}

# ==================== PAYMENT ROUTES (MOCKED) ====================

@api_router.get("/payments", response_model=List[PaymentResponse])
async def get_payments(user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    payments = await db.payments.find(
        {"client_id": profile["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return [PaymentResponse(**p) for p in payments]

@api_router.post("/payments/simulate")
async def simulate_payment(amount: float, user = Depends(get_current_user)):
    """Simulate a payment (for testing)"""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    payment = {
        "id": str(uuid.uuid4()),
        "client_id": profile["id"],
        "amount": amount,
        "status": "success",
        "method": "card",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payments.insert_one(payment)
    
    return PaymentResponse(**payment)

# ==================== DASHBOARD STATS (ADMIN) ====================

@api_router.get("/admin/dashboard")
async def get_dashboard_stats(user = Depends(get_admin_user)):
    total_clients = await db.client_profiles.count_documents({"status": "activo"})
    
    # Clients by plan
    pipeline = [
        {"$match": {"status": "activo"}},
        {"$group": {"_id": "$plan", "count": {"$sum": 1}}}
    ]
    clients_by_plan = await db.client_profiles.aggregate(pipeline).to_list(10)
    
    # Calculate MRR
    mrr_pipeline = [
        {"$match": {"status": "activo"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}}
    ]
    mrr_result = await db.client_profiles.aggregate(mrr_pipeline).to_list(1)
    mrr = mrr_result[0]["total"] if mrr_result else 0
    
    # Recent payments
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_payments = await db.payments.find(
        {"created_at": {"$gte": today.isoformat()}},
        {"_id": 0}
    ).to_list(100)
    
    # Pending reports (clients in week 3)
    pending_reports = await db.client_profiles.count_documents({"week": 3, "status": "activo"})
    
    # Pending routines (clients needing new routine)
    pending_routines = await db.client_profiles.count_documents({"week": 4, "status": "activo"})
    
    # Unread messages
    unread_messages = await db.messages.count_documents({"read": False})
    
    return {
        "total_clients": total_clients,
        "clients_by_plan": {item["_id"]: item["count"] for item in clients_by_plan},
        "mrr": mrr,
        "today_payments": {
            "count": len(today_payments),
            "total": sum(p["amount"] for p in today_payments),
            "payments": today_payments[:10]
        },
        "pending_reports": pending_reports,
        "pending_routines": pending_routines,
        "unread_messages": unread_messages
    }

# ==================== TRAINERS ====================

@api_router.get("/trainers")
async def get_trainers(user = Depends(get_admin_user)):
    trainers = await db.users.find(
        {"role": {"$in": ["trainer", "admin"]}},
        {"_id": 0, "password": 0}
    ).to_list(50)
    
    # Add client count for each trainer
    for trainer in trainers:
        count = await db.client_profiles.count_documents({"trainer_id": trainer["id"]})
        trainer["client_count"] = count
    
    return trainers

# ==================== ROOT ====================

@api_router.get("/")
async def root():
    return {"message": "12EN12 API v1.0", "status": "running"}

@api_router.get("/plans")
async def get_plans():
    return PLAN_TYPES


# ============================================================
# ENDPOINTS CALMA v2 — Motor de conteo de macros
# ============================================================
from calma_engine import calcular_macros_efectivos_alimento as calcular_macros_efectivos, que_macros_cuentan, calcular_macros_brutos, run_tests as calma_run_tests

@api_router.post("/calculator/macros-efectivos")
async def get_macros_efectivos(data: dict, user = Depends(get_current_user)):
    """
    Calcula los macros que CUENTAN de un alimento para una cantidad dada.
    
    Body:
    {
        "alimento_id": 2045,
        "cantidad_g": 150,
        "es_vegano": false
    }
    
    Response:
    {
        "efectivos": {"P": 31.5, "H": 0, "G": 0, "kcal": 126},
        "brutos": {"P": 31.5, "H": 0, "G": 2.25, "kcal": 146.3},
        "que_cuenta": {"P": true, "H": false, "G": false}
    }
    """
    alimento_id = data.get("alimento_id")
    cantidad_g = data.get("cantidad_g", 100)
    es_vegano = data.get("es_vegano", False)
    
    # Buscar alimento en MongoDB (colección foods)
    alimento = await db.foods.find_one({"id": alimento_id}, {"_id": 0})
    if not alimento:
        raise HTTPException(status_code=404, detail="Alimento no encontrado")
    
    efectivos = calcular_macros_efectivos(alimento, cantidad_g, es_vegano)
    brutos = calcular_macros_brutos(alimento, cantidad_g)
    cuenta = que_macros_cuentan(alimento, cantidad_g, es_vegano)
    
    return {
        "alimento": {
            "id": alimento.get("id"),
            "nombre": alimento.get("nombre"),
            "categorias": alimento.get("categorias"),
            "racion": alimento.get("racion")
        },
        "cantidad_g": cantidad_g,
        "efectivos": efectivos,
        "brutos": brutos,
        "que_cuenta": cuenta
    }


@api_router.post("/calculator/macros-comida")
async def get_macros_comida(data: dict, user = Depends(get_current_user)):
    """
    Calcula los macros totales de una comida (múltiples alimentos).
    
    Body:
    {
        "alimentos": [
            {"alimento_id": 2045, "cantidad_g": 150},
            {"alimento_id": 1822, "cantidad_g": 80},
            {"alimento_id": 15, "cantidad_g": 10}
        ],
        "es_vegano": false
    }
    
    Response:
    {
        "total_efectivos": {"P": 45.2, "H": 62.4, "G": 10.1, "kcal": 521.7},
        "total_brutos": {"P": 48.5, "H": 62.4, "G": 12.3, "kcal": 563.9},
        "detalle": [
            {"alimento_id": 2045, "nombre": "Pechuga pollo", "efectivos": {...}, "brutos": {...}, "que_cuenta": {...}},
            ...
        ]
    }
    """
    alimentos_input = data.get("alimentos", [])
    es_vegano = data.get("es_vegano", False)
    
    total_P = 0.0
    total_H = 0.0
    total_G = 0.0
    total_P_bruto = 0.0
    total_H_bruto = 0.0
    total_G_bruto = 0.0
    detalle = []
    
    for item in alimentos_input:
        alimento = await db.foods.find_one({"id": item["alimento_id"]}, {"_id": 0})
        if not alimento:
            continue
        
        cantidad = item.get("cantidad_g", alimento.get("racion", 100))
        
        efectivos = calcular_macros_efectivos(alimento, cantidad, es_vegano)
        brutos = calcular_macros_brutos(alimento, cantidad)
        cuenta = que_macros_cuentan(alimento, cantidad, es_vegano)
        
        total_P += efectivos["P"]
        total_H += efectivos["H"]
        total_G += efectivos["G"]
        total_P_bruto += brutos["P"]
        total_H_bruto += brutos["H"]
        total_G_bruto += brutos["G"]
        
        detalle.append({
            "alimento_id": item["alimento_id"],
            "nombre": alimento.get("nombre", ""),
            "cantidad_g": cantidad,
            "efectivos": efectivos,
            "brutos": brutos,
            "que_cuenta": cuenta
        })
    
    return {
        "total_efectivos": {
            "P": round(total_P, 1),
            "H": round(total_H, 1),
            "G": round(total_G, 1),
            "kcal": round(total_P * 4 + total_H * 4 + total_G * 9, 1)
        },
        "total_brutos": {
            "P": round(total_P_bruto, 1),
            "H": round(total_H_bruto, 1),
            "G": round(total_G_bruto, 1),
            "kcal": round(total_P_bruto * 4 + total_H_bruto * 4 + total_G_bruto * 9, 1)
        },
        "detalle": detalle
    }


@api_router.get("/calculator/test-calma")
async def test_calma():
    """
    Endpoint de verificación: ejecuta los tests del motor CALMA v2.
    Responde con el resultado de cada test.
    """
    results = calma_run_tests()
    return results


# ============================================================
# ENDPOINT DISTRIBUCIÓN DE MACROS
# ============================================================
from macro_distribution import distribuir_macros as dist_macros, run_tests as dist_run_tests

@api_router.post("/calculator/distribute")
async def distribute_macros(data: dict, user = Depends(get_current_user)):
    """
    Distribuye los macros del usuario entre sus comidas del día.
    
    Body:
    {
        "tipo_dia": "entrenamiento",     // "entrenamiento" o "descanso"
        "num_comidas": 4,                // 3 o 4
        "momento_entreno": 1,            // 0, 1, 2, 3
        "opcion_peri": "intra_post"      // "intra_post", "solo_post", "solo_intra", "sin_peri"
    }
    
    Los macros se obtienen del perfil del usuario (no se pasan en el body).
    """
    # Obtener macros del perfil del cliente
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil de cliente no encontrado")
    
    training = profile.get("macros_training", {})
    rest = profile.get("macros_rest", {})
    peri = profile.get("macros_peri", {"protein": 40, "carbs": 30})
    
    if not training or not rest:
        raise HTTPException(status_code=400, detail="No tienes macros asignados")
    
    tipo_dia = data.get("tipo_dia", "entrenamiento")
    num_comidas = data.get("num_comidas", 4)
    momento_entreno = data.get("momento_entreno", 1)
    opcion_peri = data.get("opcion_peri", "intra_post")
    
    resultado = dist_macros(
        p_entreno=float(training.get("protein", 0)),
        h_entreno=float(training.get("carbs", 0)),
        g_entreno=float(training.get("fat", 0)),
        p_peri=float(peri.get("protein", 0)),
        h_peri=float(peri.get("carbs", 0)),
        p_descanso=float(rest.get("protein", 0)),
        h_descanso=float(rest.get("carbs", 0)),
        g_descanso=float(rest.get("fat", 0)),
        tipo_dia=tipo_dia,
        num_comidas=num_comidas,
        momento_entreno=momento_entreno,
        opcion_peri=opcion_peri
    )
    
    return resultado


@api_router.get("/calculator/test-distribution")
async def test_distribution():
    """Endpoint de verificación: ejecuta tests de distribución."""
    import io
    import sys
    
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    all_passed = dist_run_tests()
    output = buffer.getvalue()
    sys.stdout = old_stdout
    
    return {"all_passed": all_passed, "output": output}


# ============================================================
# ENDPOINTS CALCULADORA — Búsqueda, Ajuste, Validación, Sugerencias
# ============================================================
from calculator import (
    calcular_cantidad_automatica,
    validar_comida,
    sugerir_alimentos,
    buscar_alimentos,
    run_tests as calc_run_tests
)


@api_router.get("/calculator/search")
async def search_foods(
    q: str = "",
    category: str = "",
    tipo_comida: str = "normal",
    limit: int = 50,
    offset: int = 0,
    vegano: bool = False,
    tag: str = ""
):
    """
    Búsqueda de alimentos con filtros y macros efectivos.
    
    Query params:
        q: texto de búsqueda (busca en nombre, ignora acentos)
        category: filtro de categoría (ej: "2" para carnes, "17.2" para frutos secos)
        tipo_comida: "normal", "intra", "post" - filtra categorías permitidas
        limit: máximo resultados (default 50)
        offset: para paginación
        vegano: si true, oculta categorías animales
        tag: filtro por tag (ej: "GEN" para genéricos)
    
    Response incluye macros_efectivos calculados por CALMA para cada alimento.
    """
    alimentos = await buscar_alimentos(
        db, query=q, categoria=category,
        tipo_comida=tipo_comida, es_vegano=vegano, limit=limit,
        calcular_efectivos=True, tag_filter=tag
    )
    
    return {
        "alimentos": alimentos,
        "total": len(alimentos),
        "limit": limit,
        "offset": offset
    }


@api_router.post("/calculator/foods-sorted")
async def get_foods_sorted_by_fit(data: dict):
    """
    Obtiene alimentos de una categoría ordenados por mejor ajuste a los macros restantes.
    
    BUGS CORREGIDOS:
    - BUG 1: No muestra alimentos con 0g de macros (excepto verduras)
    - BUG 2: Verduras muestran 100g por defecto
    - BUG 3: Verifica categoría PRINCIPAL para evitar alimentos mal categorizados
    - BUG 11: Aplica cantidades mínimas
    """
    prefixes = data.get("category_prefixes", [])
    macros_restantes = data.get("macros_restantes", {"P": 0, "H": 0, "G": 0})
    limit = data.get("limit", 200)
    offset = data.get("offset", 0)
    
    if not prefixes:
        return {"alimentos": [], "total": 0}
    
    # Construir filtro de categorías con formato pipe-separated
    or_conditions = []
    for prefix in prefixes:
        or_conditions.append({"categorias": {"$regex": f"(^|\\| ){re.escape(prefix)}(\\.|\\s|\\||$)"}})
    
    filtro = {"$or": or_conditions} if len(or_conditions) > 1 else or_conditions[0]
    
    # Obtener todos los alimentos que coinciden
    cursor = db.foods.find(filtro, {"_id": 0})
    alimentos_raw = await cursor.to_list(length=5000)
    
    # Calcular cantidad sugerida y score para cada alimento
    p_rest = float(macros_restantes.get("P", 0) or 0)
    h_rest = float(macros_restantes.get("H", 0) or 0)
    g_rest = float(macros_restantes.get("G", 0) or 0)
    
    # Helper para obtener categoría principal
    def get_primary_category(cats_str, nombre=""):
        """
        Devuelve la categoría principal.
        Prioridad: comida preparada > proteínas > lácteos > primera
        Excepción: si el nombre contiene "hamburguesa", es comida preparada
        """
        if not cats_str:
            return ""
        
        # Si el nombre contiene hamburguesa, tratarlo como comida preparada
        if "hamburguesa" in nombre.lower():
            return "32"  # Pizza/lasaña/empanadas = comida preparada
        
        cats = [c.strip() for c in cats_str.split('|')]
        # Si tiene categoría de comida preparada, esa es la principal
        comida_prep_prefixes = ['32', '39', '49', '50', '51', '53', 'PRE', 'HAM']
        for cat in cats:
            for prep in comida_prep_prefixes:
                if cat.startswith(prep) or cat == prep:
                    return cat
        # Si no, devolver la primera
        return cats[0] if cats else ""
    
    # Helper para verificar si categoría principal coincide con prefixes
    def primary_matches_prefixes(cats_str, prefixes, nombre=""):
        primary = get_primary_category(cats_str, nombre)
        for prefix in prefixes:
            if primary.startswith(prefix):
                return True
        return False
    
    # Helper para verificar si es verdura
    def is_verdura(cats_str, nombre=""):
        primary = get_primary_category(cats_str, nombre)
        return primary.startswith('13')
    
    alimentos_scored = []
    for alimento in alimentos_raw:
        cats_str = alimento.get("categorias", "")
        nombre = alimento.get("nombre", "")
        
        # BUG 3: Verificar que la categoría PRINCIPAL coincide con los prefixes
        if not primary_matches_prefixes(cats_str, prefixes, nombre):
            continue  # Saltar este alimento, su categoría principal no es la que buscamos
        
        try:
            resultado = calcular_cantidad_automatica(alimento, macros_restantes, es_vegano=False)
            cantidad = resultado.get("cantidad_g", 0)
            macros_ef = resultado.get("macros_efectivos", {"P": 0, "H": 0, "G": 0})
            config = resultado.get("config", {})
            
            # Score = suma de macros efectivos aportados
            score = (macros_ef.get("P", 0) or 0) + (macros_ef.get("H", 0) or 0) + (macros_ef.get("G", 0) or 0)
            
            # BUG 1 y BUG 2: Filtrar alimentos con score 0 EXCEPTO verduras
            if score == 0:
                if is_verdura(cats_str, nombre):
                    # BUG 2: Verduras siempre con 100g por defecto
                    cantidad = 100
                    macros_ef = {"P": 0, "H": 0, "G": 0}
                else:
                    # No es verdura y score 0 → no incluir
                    continue
            
            # BUG 11: Aplicar cantidades mínimas
            minimo = config.get("minimo", 10)
            if cantidad < minimo:
                cantidad = minimo
                # Recalcular macros con la cantidad mínima
                if cantidad > 0 and resultado.get("cantidad_g", 0) > 0:
                    ratio = cantidad / resultado.get("cantidad_g", 1)
                    macros_ef = {
                        "P": round((resultado.get("macros_efectivos", {}).get("P", 0) or 0) * ratio, 1),
                        "H": round((resultado.get("macros_efectivos", {}).get("H", 0) or 0) * ratio, 1),
                        "G": round((resultado.get("macros_efectivos", {}).get("G", 0) or 0) * ratio, 1)
                    }
            
            # Formatear cantidad usando el config (BUG 2: huevos, hamburguesas como unidades enteras)
            racion = alimento.get("racion", 100)
            nombre_lower = alimento.get("nombre", "").lower()
            
            if config.get("por_unidad", False) and config.get("peso_unidad", 0) > 0:
                # BUG 2 FIX: Formatear como unidades enteras o medias
                peso_unidad = config["peso_unidad"]
                permite_media = config.get("permite_media", False)
                unidades = cantidad / peso_unidad
                
                if permite_media:
                    # Redondear a 0.5
                    unidades = round(unidades * 2) / 2
                    if unidades < 0.5:
                        unidades = 0.5
                else:
                    # Redondear a enteros SIEMPRE
                    unidades = round(unidades)
                    if unidades < 1:
                        unidades = 1
                
                # Formatear: "2 ud (110g)" o "1.5 ud (150g)"
                if unidades == int(unidades):
                    formatted = f"{int(unidades)} ud ({round(cantidad)}g)"
                else:
                    formatted = f"{unidades} ud ({round(cantidad)}g)"
            else:
                formatted = f"{round(cantidad)}g"
            
            alimento_con_score = {
                **alimento,
                "_cantidad_sugerida": round(cantidad),
                "_macros_sugeridos": macros_ef,
                "_formatted_qty": formatted,
                "_score": round(score, 1),
                "_config": config
            }
            alimentos_scored.append(alimento_con_score)
            
        except Exception as e:
            # Si falla el cálculo, incluir con cantidad por defecto si es verdura
            if is_verdura(alimento.get("categorias", ""), alimento.get("nombre", "")):
                alimento_con_score = {
                    **alimento,
                    "_cantidad_sugerida": 100,
                    "_macros_sugeridos": {"P": 0, "H": 0, "G": 0},
                    "_formatted_qty": "100g",
                    "_score": 0,
                    "_config": {}
                }
                alimentos_scored.append(alimento_con_score)
    
    # Ordenar por score descendente (mejor fit primero)
    alimentos_scored.sort(key=lambda x: x.get("_score", 0), reverse=True)
    
    # Aplicar paginación
    total = len(alimentos_scored)
    alimentos_paginated = alimentos_scored[offset:offset + limit]
    
    return {
        "alimentos": alimentos_paginated,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@api_router.post("/calculator/adjust")
async def adjust_quantity(data: dict, user = Depends(get_current_user)):
    """
    Calcula la cantidad automática de un alimento para una comida.
    
    Body:
    {
        "alimento_id": 2045,
        "macros_restantes": {"P": 45, "H": 50, "G": 15},
        "es_vegano": false
    }
    """
    alimento_id = data.get("alimento_id")
    macros_restantes = data.get("macros_restantes", {"P": 0, "H": 0, "G": 0})
    es_vegano = data.get("es_vegano", False)
    
    alimento = await db.foods.find_one({"id": alimento_id}, {"_id": 0})
    if not alimento:
        raise HTTPException(status_code=404, detail="Alimento no encontrado")
    
    resultado = calcular_cantidad_automatica(alimento, macros_restantes, es_vegano)
    resultado["alimento"] = alimento
    
    return resultado


@api_router.post("/calculator/validate-meal")
async def validate_meal(data: dict, user = Depends(get_current_user)):
    """
    Valida si una comida está cuadrada.
    
    Body:
    {
        "alimentos": [
            {"alimento_id": 2045, "cantidad_g": 150},
            {"alimento_id": 1822, "cantidad_g": 80}
        ],
        "macros_objetivo": {"P": 45, "H": 50, "G": 15},
        "es_vegano": false
    }
    """
    alimentos_input = data.get("alimentos", [])
    macros_objetivo = data.get("macros_objetivo", {"P": 0, "H": 0, "G": 0})
    es_vegano = data.get("es_vegano", False)
    
    alimentos_comida = []
    for item in alimentos_input:
        al = await db.foods.find_one({"id": item["alimento_id"]}, {"_id": 0})
        if al:
            alimentos_comida.append({
                "alimento": al,
                "cantidad_g": item.get("cantidad_g", al.get("racion", 100))
            })
    
    resultado = validar_comida(alimentos_comida, macros_objetivo, es_vegano)
    return resultado


@api_router.post("/calculator/suggest")
async def suggest_foods_endpoint(data: dict, user = Depends(get_current_user)):
    """
    Sugiere alimentos para completar una comida, ordenados por mayor aporte.
    
    Body:
    {
        "macros_restantes": {"P": 12, "H": 6, "G": 3},
        "tipo_comida": "normal",  // "normal", "intra", "post"
        "es_vegano": false,
        "max_resultados": 20,
        "excluir_ids": [],
        "paso": "proteina" | "acompanamiento" | null
    }
    """
    macros_restantes = data.get("macros_restantes", {"P": 0, "H": 0, "G": 0})
    tipo_comida = data.get("tipo_comida", "normal")
    es_vegano = data.get("es_vegano", False)
    max_resultados = data.get("max_resultados", 20)
    excluir_ids = data.get("excluir_ids", [])
    paso = data.get("paso", None)  # "proteina", "acompanamiento", or None
    
    # Cargar alimentos de MongoDB
    cursor = db.foods.find({}, {"_id": 0}).limit(3200)
    todos = await cursor.to_list(length=3200)
    
    sugerencias = sugerir_alimentos(
        todos, macros_restantes, tipo_comida, es_vegano,
        max_resultados, excluir_ids, paso
    )
    
    return {"sugerencias": sugerencias, "count": len(sugerencias)}


@api_router.get("/calculator/test-calculator")
async def test_calculator():
    """Ejecuta tests de la calculadora."""
    results = calc_run_tests()
    return results


# ============================================================
# ENDPOINTS DIETAS — Guardar, Cargar, Copiar, Calendario
# ============================================================

@api_router.post("/diets")
async def save_diet(data: dict, user = Depends(get_current_user)):
    """
    Guarda la dieta completa de un día.
    
    Body:
    {
        "fecha": "2026-03-11",
        "tipo_dia": "entrenamiento",
        "num_comidas": 4,
        "momento_entreno": 1,
        "opcion_peri": "intra_post",
        "comidas": {
            "C1": {
                "alimentos": [
                    {"alimento_id": 2045, "nombre": "Pechuga de pollo", "cantidad_g": 200},
                    ...
                ]
            },
            ...
        }
    }
    """
    fecha = data.get("fecha")
    if not fecha:
        raise HTTPException(status_code=400, detail="Fecha requerida")
    
    diet_doc = {
        "user_id": user["id"],
        "fecha": fecha,
        "tipo_dia": data.get("tipo_dia", "entrenamiento"),
        "num_comidas": data.get("num_comidas", 4),
        "momento_entreno": data.get("momento_entreno", 1),
        "opcion_peri": data.get("opcion_peri", "intra_post"),
        "comidas": data.get("comidas", {}),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "macros_snapshot": data.get("macros_snapshot", None)
    }
    
    # Upsert: si ya existe dieta para ese día, reemplazar
    await db.diets.update_one(
        {"user_id": user["id"], "fecha": fecha},
        {"$set": diet_doc},
        upsert=True
    )
    
    return {"message": "Dieta guardada", "fecha": fecha}


@api_router.get("/diets/recent")
async def get_recent_diets(limit: int = 14, user = Depends(get_current_user)):
    """
    Lista los últimos días con dieta guardada.
    Devuelve resumen de cada día para el modal "Repetir de otro día".
    """
    cursor = db.diets.find(
        {"user_id": user["id"]},
        {"_id": 0, "fecha": 1, "tipo_dia": 1, "num_comidas": 1, "comidas": 1}
    ).sort("fecha", -1).limit(limit)
    
    diets = await cursor.to_list(length=limit)
    
    result = []
    for diet in diets:
        # Crear resumen de comidas
        comidas_resumen = {}
        for key, meal_data in (diet.get("comidas") or {}).items():
            alimentos = meal_data.get("alimentos") or []
            if alimentos:
                nombres = [a.get("nombre", "?")[:20] for a in alimentos[:3]]
                comidas_resumen[key] = " + ".join(nombres)
                if len(alimentos) > 3:
                    comidas_resumen[key] += f" +{len(alimentos)-3}"
        
        result.append({
            "fecha": diet.get("fecha"),
            "tipo_dia": diet.get("tipo_dia", "entrenamiento"),
            "num_comidas": diet.get("num_comidas", 4),
            "comidas_resumen": comidas_resumen,
            "comidas": diet.get("comidas", {})  # Include full meals for copying
        })
    
    return {"diets": result, "count": len(result)}


@api_router.get("/diets/{fecha}")
async def get_diet(fecha: str, user = Depends(get_current_user)):
    """Obtiene la dieta guardada para una fecha."""
    diet = await db.diets.find_one(
        {"user_id": user["id"], "fecha": fecha},
        {"_id": 0}
    )
    if not diet:
        return {"fecha": fecha, "exists": False}
    
    diet["exists"] = True
    return diet


@api_router.post("/diets/copy")
async def copy_diet(data: dict, user = Depends(get_current_user)):
    """
    Copia una dieta de una fecha a otra.
    
    Body:
    {
        "fecha_origen": "2026-03-11",
        "fecha_destino": "2026-03-12"
    }
    """
    fecha_origen = data.get("fecha_origen")
    fecha_destino = data.get("fecha_destino")
    
    if not fecha_origen or not fecha_destino:
        raise HTTPException(status_code=400, detail="Fechas requeridas")
    
    diet = await db.diets.find_one(
        {"user_id": user["id"], "fecha": fecha_origen},
        {"_id": 0}
    )
    
    if not diet:
        raise HTTPException(status_code=404, detail="No hay dieta en la fecha origen")
    
    diet["fecha"] = fecha_destino
    diet["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.diets.update_one(
        {"user_id": user["id"], "fecha": fecha_destino},
        {"$set": diet},
        upsert=True
    )
    
    return {"message": f"Dieta copiada a {fecha_destino}"}


@api_router.get("/diets/calendar/{year}/{month}")
async def get_calendar(year: int, month: int, user = Depends(get_current_user)):
    """
    Obtiene el estado del calendario de un mes.
    Devuelve qué días tienen dieta y si están cuadrados.
    """
    # Generar rango de fechas del mes
    fecha_inicio = f"{year}-{month:02d}-01"
    if month == 12:
        fecha_fin = f"{year + 1}-01-01"
    else:
        fecha_fin = f"{year}-{month + 1:02d}-01"
    
    cursor = db.diets.find(
        {
            "user_id": user["id"],
            "fecha": {"$gte": fecha_inicio, "$lt": fecha_fin}
        },
        {"_id": 0, "fecha": 1, "comidas": 1}
    )
    
    diets = await cursor.to_list(length=31)
    
    days = {}
    for diet in diets:
        fecha = diet["fecha"]
        comidas = diet.get("comidas", {})
        has_alimentos = any(
            len(c.get("alimentos", [])) > 0 
            for c in comidas.values() 
            if isinstance(c, dict)
        )
        days[fecha] = {
            "has_diet": True,
            "status": "guardada" if has_alimentos else "vacia"
        }
    
    return {"days": days}


@api_router.delete("/diets/{fecha}")
async def delete_diet(fecha: str, user = Depends(get_current_user)):
    """Elimina la dieta de una fecha."""
    result = await db.diets.delete_one(
        {"user_id": user["id"], "fecha": fecha}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No hay dieta para esa fecha")
    return {"message": "Dieta eliminada"}



# ============================================================
# ENDPOINTS PLANTILLAS DE MENÚ — Opciones A/B/C
# ============================================================

@api_router.get("/calculator/test-templates")
async def test_templates():
    """Ejecuta tests de las plantillas de menú."""
    from meal_templates import run_tests
    return run_tests()


@api_router.post("/calculator/menu-options")
async def get_menu_options(data: dict, user = Depends(get_current_user)):
    """Genera 3 opciones de menú A/B/C para una comida."""
    from meal_templates import generar_opciones_menu
    
    momento = data.get("momento", "comida")
    macros_objetivo = data.get("macros_objetivo", {"P": 45, "H": 75, "G": 13})
    es_vegano = data.get("es_vegano", False)
    excluir_proteinas = data.get("excluir_proteinas", [])
    
    opciones = await generar_opciones_menu(
        db, momento, macros_objetivo, es_vegano, excluir_proteinas
    )
    
    return {"opciones": opciones, "count": len(opciones)}



# Include the router
# ==================== CHATBOT ENDPOINTS ====================

from chatbot import get_or_create_chatbot, clear_session, NutritionChatbot

class ChatMessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatConfigRequest(BaseModel):
    tipo_dia: str  # "entrenamiento" o "descanso"
    num_comidas: int = 4
    momento_entreno: int = 1
    opcion_peri: str = "intra_post"

class CompleteMealRequest(BaseModel):
    pass

@api_router.post("/chatbot/start")
async def chatbot_start(current_user: dict = Depends(get_current_user)):
    """Inicia una nueva sesión de chatbot."""
    user_id = current_user.get('id') or current_user.get('user_id')
    session_id = f"chat_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Obtener macros del usuario desde su perfil
    profile = await db.client_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    user_macros = {}
    if profile:
        mt = profile.get("macros_training", {})
        mr = profile.get("macros_rest", {})
        mp = profile.get("macros_periworkout", {})
        
        user_macros = {
            "p_entreno": mt.get("proteinas", 160),
            "h_entreno": mt.get("hidratos", 50),
            "g_entreno": mt.get("grasas", 40),
            "p_peri": mp.get("proteinas", 35),
            "h_peri": mp.get("hidratos", 15),
            "p_descanso": mr.get("proteinas", 140),
            "h_descanso": mr.get("hidratos", 40),
            "g_descanso": mr.get("grasas", 40)
        }
    else:
        # Macros de prueba por defecto
        user_macros = {
            "p_entreno": 160,
            "h_entreno": 50,
            "g_entreno": 40,
            "p_peri": 35,
            "h_peri": 15,
            "p_descanso": 140,
            "h_descanso": 40,
            "g_descanso": 40
        }
    
    chatbot = await get_or_create_chatbot(session_id, db, user_macros)
    
    return {
        "session_id": session_id,
        "macros": user_macros,
        "message": "¡Hola! Soy tu asistente de nutrición. ¿Hoy es día de entrenamiento o descanso?"
    }

@api_router.post("/chatbot/configure")
async def chatbot_configure(
    config: ChatConfigRequest,
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Configura el día (tipo, comidas, momento entreno)."""
    chatbot = await get_or_create_chatbot(session_id, db)
    
    distribucion = chatbot.configure_day(
        tipo_dia=config.tipo_dia,
        num_comidas=config.num_comidas,
        momento_entreno=config.momento_entreno,
        opcion_peri=config.opcion_peri
    )
    
    # Construir mensaje de respuesta
    comida_1 = distribucion["comidas"]["C1"]
    mensaje = f"Perfecto, día de {config.tipo_dia} con {config.num_comidas} comidas."
    mensaje += f"\n\nVamos con la Comida 1. Tu objetivo es: P={comida_1['P']}g, H={comida_1['H']}g, G={comida_1['G']}g."
    mensaje += "\n\n¿Qué te apetece desayunar?"
    
    return {
        "session_id": session_id,
        "distribucion": distribucion,
        "comida_actual": 1,
        "mensaje": mensaje
    }

@api_router.post("/chatbot/message")
async def chatbot_message(
    request: ChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """Envía un mensaje al chatbot."""
    session_id = request.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id requerido")
    
    chatbot = await get_or_create_chatbot(session_id, db)
    
    response = await chatbot.process_message(request.message)
    
    return {
        "session_id": session_id,
        "response": response,
        "state": {
            "step": chatbot.state["step"],
            "comida_actual": chatbot.state["comida_actual"],
            "restante": chatbot.get_remaining_macros()
        }
    }

@api_router.post("/chatbot/complete-meal")
async def chatbot_complete_meal(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Marca la comida actual como completa."""
    chatbot = await get_or_create_chatbot(session_id, db)
    
    resultado = chatbot.complete_current_meal()
    
    if chatbot.state["step"] == "complete":
        # Día completo
        summary = chatbot.get_day_summary()
        return {
            "session_id": session_id,
            "comida_completada": resultado,
            "dia_completo": True,
            "resumen": summary,
            "mensaje": "¡Día completo! Aquí tienes el resumen de tu dieta."
        }
    else:
        # Siguiente comida
        siguiente = chatbot.state["comida_actual"]
        objetivo = chatbot.get_current_meal_macros()
        return {
            "session_id": session_id,
            "comida_completada": resultado,
            "dia_completo": False,
            "comida_actual": siguiente,
            "objetivo": objetivo,
            "mensaje": f"Comida {siguiente-1} guardada. Vamos con la Comida {siguiente}. Objetivo: P={objetivo['P']}g, H={objetivo['H']}g, G={objetivo['G']}g. ¿Qué quieres comer?"
        }

@api_router.get("/chatbot/summary")
async def chatbot_summary(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Obtiene el resumen del día."""
    chatbot = await get_or_create_chatbot(session_id, db)
    return chatbot.get_day_summary()

@api_router.post("/chatbot/reset")
async def chatbot_reset(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Reinicia la sesión de chatbot."""
    clear_session(session_id)
    return {"message": "Sesión reiniciada", "session_id": session_id}

# ==================== END CHATBOT ====================


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
