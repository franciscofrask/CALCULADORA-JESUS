"""
Seguridad: JWT y hashing de contraseñas.
"""
import jwt
import bcrypt
import os
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS
from .database import db

try:
    from Crypto.Cipher import AES  # pycryptodome
except ImportError:
    AES = None

security = HTTPBearer()

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Sin caracteres ambiguos (0/O, 1/l/I) para poder dictarla por telefono
_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"

def generate_temp_password() -> str:
    """Contraseña temporal legible: Abcd-Efg2-Hjk9."""
    import secrets
    return "-".join("".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(4)) for _ in range(3))

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def _b64url(s: str) -> bytes:
    s = (s or "").strip()
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)

def verify_firebase_password(password: str, hash_b64url: str, salt_b64url: str) -> bool:
    """Verifica una contraseña contra el hash scrypt de Firebase (usuarios importados de Calma).
    Reproduce el algoritmo de Firebase: scrypt(password, salt+salt_separator) y luego AES-256-CTR
    del signer_key con la clave derivada. True si coincide con el hash almacenado."""
    signer = os.environ.get("FIREBASE_SCRYPT_SIGNER_KEY", "")
    if not (password and hash_b64url and salt_b64url and signer and AES is not None):
        return False
    try:
        salt_sep = os.environ.get("FIREBASE_SCRYPT_SALT_SEP", "")
        rounds = int(os.environ.get("FIREBASE_SCRYPT_ROUNDS", "8") or 8)
        mem_cost = int(os.environ.get("FIREBASE_SCRYPT_MEM_COST", "14") or 14)
        dk = hashlib.scrypt(password.encode("utf-8"),
                            salt=_b64url(salt_b64url) + base64.b64decode(salt_sep),
                            n=2 ** mem_cost, r=rounds, p=1, dklen=64, maxmem=2 ** 26)
        cipher = AES.new(dk[:32], AES.MODE_CTR, nonce=b"", initial_value=0)
        return cipher.encrypt(base64.b64decode(signer)) == _b64url(hash_b64url)
    except Exception:
        return False

def create_token(user_id: str, role: str) -> str:
    """Create a JWT token."""
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    """Decode a JWT token."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get the current user from the JWT token."""
    payload = decode_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if user.get("deleted_at"):
        raise HTTPException(status_code=403, detail="Cuenta desactivada")
    return user

async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """Verify that the current user is an admin."""
    if user.get("role") not in ["admin", "trainer"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return user
