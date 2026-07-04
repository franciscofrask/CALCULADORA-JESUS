"""
Rutas de autenticación: registro, login, me.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import uuid

from core.database import db
from core.security import hash_password, verify_password, verify_firebase_password, create_token, get_current_user, Depends
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
    """Iniciar sesión. Acepta la contraseña bcrypt normal o, para usuarios importados de Calma,
    la contraseña original verificada con scrypt de Firebase (migrada a bcrypt al primer acceso)."""
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    stored = user.get("password")
    ok = bool(stored) and verify_password(data.password, stored)
    if not ok and user.get("firebase_password_hash"):
        # Usuario de Calma: validar contra el hash scrypt de Firebase y migrar a bcrypt.
        if verify_firebase_password(data.password, user["firebase_password_hash"], user.get("firebase_password_salt")):
            ok = True
            await db.users.update_one(
                {"id": user["id"]},
                {"$set": {"password": hash_password(data.password)},
                 "$unset": {"firebase_password_hash": "", "firebase_password_salt": ""}},
            )
    if not ok:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token = create_token(user["id"], user["role"])
    known = {"id", "email", "name", "phone", "role", "plan", "trainer_id", "created_at"}
    user_response = {k: v for k, v in user.items() if k in known}
    return TokenResponse(access_token=token, user=UserResponse(**user_response))

@router.get("/me", response_model=UserResponse)
async def get_me(user = Depends(get_current_user)):
    """Obtener información del usuario actual."""
    return UserResponse(**{k: v for k, v in user.items() if k != "password"})
