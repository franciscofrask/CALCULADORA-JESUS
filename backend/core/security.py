"""
Seguridad: JWT y hashing de contraseñas.
"""
import jwt
import bcrypt
import os
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import HTTPException, Depends, Request
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

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """El usuario de esta peticion, a partir del JWT.

    Y, si la manda alguien del equipo con la cabecera `X-Actuar-Como`, el CLIENTE por el que
    esta actuando (punto 4.11): asi el entrenador abre la calculadora de su cliente y todas
    las pantallas funcionan sin duplicar media API. Los cerrojos y el porque, en
    `core/actuar_como.py`.
    """
    payload = decode_token(credentials.credentials)
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if user.get("deleted_at"):
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    from .actuar_como import CABECERA, CLAVE

    objetivo_id = (request.headers.get(CABECERA) or "").strip()
    if not objetivo_id or objetivo_id == user.get("id"):
        return user

    # Cerrojo 1: solo el equipo.
    if user.get("role") not in ("admin", "trainer"):
        raise HTTPException(status_code=403, detail="Acceso denegado")

    objetivo = await db.users.find_one({"id": objetivo_id}, {"_id": 0})
    if not objetivo or objetivo.get("deleted_at"):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Cerrojo 2: solo hacia clientes. Actuar como otro admin seria una escalada de
    # privilegios con nombre bonito.
    if objetivo.get("role") != "client":
        raise HTTPException(status_code=403, detail="Solo se puede actuar como un cliente")

    # Cerrojo 3: solo sobre los suyos, la misma regla que la ficha.
    perfil = await db.client_profiles.find_one({"user_id": objetivo_id}, {"_id": 0})
    assert_client_access(user, perfil)

    # Cerrojo 4: queda anotado. Solo lo que ESCRIBE -- anotar cada lectura llenaria el
    # registro de ruido y taparia justo lo que hay que poder encontrar.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        try:
            from routes.audit import audit
            await audit(user, "actuar_como",
                        f"{request.method} {request.url.path} como {objetivo.get('name') or objetivo.get('email')}")
        except Exception:
            pass  # el registro no puede tumbar la operacion

    return {**objetivo, CLAVE: {"por_id": user.get("id"),
                                "por_nombre": user.get("name") or user.get("email") or "el equipo"}}

async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """Verify that the current user is staff (admin OR trainer).

    OJO: concede acceso a admin Y trainer. Para endpoints que operan sobre UN cliente
    concreto, NO basta con esto: hay que llamar además a `assert_client_access` para que
    un entrenador solo toque a los clientes que puede ver (los admin acceden a todos)."""
    if user.get("role") not in ["admin", "trainer"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return user


async def get_admin_only_user(user: dict = Depends(get_current_user)) -> dict:
    """Solo administradores (excluye a los entrenadores). Para la gestión de
    usuarios/staff, que no debe estar al alcance de un trainer."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden acceder a esta sección")
    return user


def assert_client_access(user: dict, profile: Optional[dict]) -> None:
    """Autorización a nivel de recurso para endpoints staff que operan sobre un cliente.

    - admin y trainer: cualquier cliente.
    - resto: denegado.

    JESÚS, 13-08-2026: *«los entrenadores ven a todos los clientes. Es lo que decidí el 21
    de julio»*, y el motivo: *«con 177 clientes y el equipo que tienes, separas: el día que
    uno se va de vacaciones, los suyos se quedan sin nadie que los mire»*.

    Entre el 06-08 y hoy esto hacía lo contrario -- un coach solo entraba en los SUYOS y en
    los que no tenían coach --, y el caso 83 de sus 85 llevaba en rojo esperando a que él
    desempatara las dos decisiones. Ya lo ha hecho, y la que vale es la suya del 21-07.

    Contradice A PROPÓSITO un hallazgo de la auditoría de seguridad («un trainer accede a
    clientes ajenos»): no es un fallo, es cómo quiere que trabaje su equipo. Lo que NO se
    abre con esto es la pestaña Usuarios (roles y contraseñas), que sigue siendo solo de
    admin, ni el acceso de un cliente a otro cliente.

    `profile` es el documento de client_profiles del cliente objetivo (o None si no existe).
    Lanza 404 si el perfil no existe y 403 si no le corresponde.
    """
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    role = (user or {}).get("role")
    if role in ("admin", "trainer"):
        return
    raise HTTPException(status_code=403, detail="No tienes acceso a este cliente")
