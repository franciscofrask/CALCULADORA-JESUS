from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
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
async def get_foods(search: Optional[str] = None, user = Depends(get_current_user)):
    # Common foods database
    foods = [
        {"id": "1", "name": "Pollo (pechuga)", "calories": 165, "protein": 31, "carbs": 0, "fat": 3.6},
        {"id": "2", "name": "Arroz blanco", "calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3},
        {"id": "3", "name": "Huevo entero", "calories": 155, "protein": 13, "carbs": 1.1, "fat": 11},
        {"id": "4", "name": "Avena", "calories": 389, "protein": 17, "carbs": 66, "fat": 7},
        {"id": "5", "name": "Plátano", "calories": 89, "protein": 1.1, "carbs": 23, "fat": 0.3},
        {"id": "6", "name": "Atún (lata)", "calories": 116, "protein": 26, "carbs": 0, "fat": 1},
        {"id": "7", "name": "Pasta", "calories": 131, "protein": 5, "carbs": 25, "fat": 1.1},
        {"id": "8", "name": "Salmón", "calories": 208, "protein": 20, "carbs": 0, "fat": 13},
        {"id": "9", "name": "Brócoli", "calories": 34, "protein": 2.8, "carbs": 7, "fat": 0.4},
        {"id": "10", "name": "Patata", "calories": 77, "protein": 2, "carbs": 17, "fat": 0.1},
        {"id": "11", "name": "Leche entera", "calories": 61, "protein": 3.2, "carbs": 4.8, "fat": 3.3},
        {"id": "12", "name": "Yogur griego", "calories": 97, "protein": 9, "carbs": 3.6, "fat": 5},
        {"id": "13", "name": "Almendras", "calories": 579, "protein": 21, "carbs": 22, "fat": 50},
        {"id": "14", "name": "Aceite de oliva", "calories": 884, "protein": 0, "carbs": 0, "fat": 100},
        {"id": "15", "name": "Aguacate", "calories": 160, "protein": 2, "carbs": 9, "fat": 15},
    ]
    
    # Add client-suggested foods
    suggested = await db.food_suggestions.find({"status": "approved"}, {"_id": 0}).to_list(100)
    for s in suggested:
        foods.append({
            "id": s["id"],
            "name": s["food"]["name"],
            "calories": s["food"].get("calories_per_100g", 0),
            "protein": s["food"].get("protein_per_100g", 0),
            "carbs": s["food"].get("carbs_per_100g", 0),
            "fat": s["food"].get("fat_per_100g", 0)
        })
    
    if search:
        foods = [f for f in foods if search.lower() in f["name"].lower()]
    
    return foods

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

# Include the router
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
