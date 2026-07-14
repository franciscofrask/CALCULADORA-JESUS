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
    if user.get("deleted_at"):
        raise HTTPException(status_code=403, detail="Cuenta desactivada. Contacta con tu entrenador.")

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


@router.put("/me", response_model=UserResponse)
async def update_me(data: dict, user = Depends(get_current_user)):
    """Actualizar los datos propios (nombre y teléfono)."""
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")
    update = {}
    name = data.get("name")
    if isinstance(name, str) and name.strip():
        update["name"] = name.strip()
    if "phone" in data:
        phone = data["phone"]
        if phone is not None and not isinstance(phone, str):
            raise HTTPException(status_code=400, detail="El teléfono debe ser texto.")
        update["phone"] = phone
    if update:
        await db.users.update_one({"id": user["id"]}, {"$set": update})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return UserResponse(**{k: v for k, v in fresh.items() if k != "password"})


@router.post("/change-password")
async def change_password(data: dict, user = Depends(get_current_user)):
    """Cambiar la contraseña propia verificando la actual."""
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")
    current = data.get("current_password")
    new = data.get("new_password")
    if not isinstance(current, str) or not isinstance(new, str):
        raise HTTPException(status_code=400, detail="Las contraseñas deben ser texto.")
    if len(new) < 8:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 8 caracteres")
    stored = user.get("password")
    if not stored or not verify_password(current, stored):
        raise HTTPException(status_code=401, detail="La contraseña actual no es correcta")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password": hash_password(new)}})
    return {"ok": True}
