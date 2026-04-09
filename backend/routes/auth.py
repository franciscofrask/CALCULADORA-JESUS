"""
Rutas de autenticación: registro, login, me.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import uuid

from core.database import db
from core.security import hash_password, verify_password, create_token, get_current_user, Depends
from models.user import UserRegister, UserLogin, UserResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister):
    """Registrar un nuevo usuario."""
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    
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

@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin):
    """Iniciar sesión."""
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    token = create_token(user["id"], user["role"])
    user_response = {k: v for k, v in user.items() if k != "password"}
    return TokenResponse(access_token=token, user=UserResponse(**user_response))

@router.get("/me", response_model=UserResponse)
async def get_me(user = Depends(get_current_user)):
    """Obtener información del usuario actual."""
    return UserResponse(**{k: v for k, v in user.items() if k != "password"})
