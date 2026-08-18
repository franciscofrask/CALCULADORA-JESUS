"""
Rutas de autenticación: registro, login, me.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import uuid

from core.database import db
from core.dias_de_entreno import DIAS_DE_ENTRENO_POR_DEFECTO
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
    ahora = datetime.now(timezone.utc).isoformat()
    user = {
        "id": user_id,
        "email": data.email,
        "password": hash_password(data.password),
        # Sin nombre se usa la parte de delante del correo: la app lo saluda por su
        # nombre en muchos sitios y "Hola, undefined" es peor que "Hola, marcos".
        "name": (data.name or "").strip() or data.email.split("@")[0],
        "phone": data.phone,
        "role": "client",
        "plan": None,
        "trainer_id": None,
        "created_at": ahora,
    }
    await db.users.insert_one(user)

    # La ficha se crea AQUÍ, al registrarse, y no al iniciar el pago como hasta ahora.
    # En el acceso gratis el regalo ES la ficha: su índice de muscularidad, sus kilos de
    # músculo y grasa. Sin ficha no hay dónde ponerlo.
    #
    # Nace en "registrado", que NO da acceso a nada de pago: has_active_access solo deja
    # pasar con status "activo" o suscripción de Stripe al día. Es una ficha vacía
    # esperando datos, no un cliente.
    await db.client_profiles.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "plan": None,
        "price": None,
        # SEMANA 1, NO NULO. `ClientProfile.week` es un entero, asi que un `None` aqui hace
        # reventar la validacion mas adelante: `/clients/questionnaire` devuelve el perfil
        # validado al terminar, y con el nulo daba un 500 A TODO EL QUE SE REGISTRARA. Y
        # reventaba DESPUES de guardarlo todo: la persona veia «Error al enviar el
        # cuestionario», no se le aplicaban los modificadores de las preguntas 5 a 8, no se
        # le montaba el dia, no llegaba a la bienvenida, y al reintentar le salia un 409
        # porque el alta ya constaba hecha. Se quedaba con los macros base y sin saber por que.
        # En produccion hay 5 fichas asi; las de la migracion traen el campo y por eso no
        # habia saltado antes (caso 04 de la lista del 12-08).
        "week": 1,
        "status": "registrado",
        "trainer_id": None,
        "macros_training": None,
        "macros_rest": None,
        "weight": None,
        "height": None,
        "age": None,
        "sex": None,
        "goal": None,
        "body_fat": None,
        "equipment": [],
        "injuries": [],
        # CUATRO, NO NULO. La pregunta «¿cuántos días puedes entrenar?» se retira del alta el
        # 18-08 porque la respuesta es siempre la misma, y el campo se rellena solo. Naciendo
        # a None el dato no existía en ninguna ficha nueva y el panel de Rutinas dejaba fuera
        # a 158 de los 164 clientes que pagan rutina por «falta saber lo básico».
        "training_days": DIAS_DE_ENTRENO_POR_DEFECTO,
        "created_at": ahora,
    })

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


# ── Recuperar la contraseña ──────────────────────────────────────────────────────
# Hasta hoy no existía: quien la perdía tenía que escribirle a su entrenador por
# WhatsApp. Eso se aguanta con clientes que conoces; con el registro abierto y gente
# que llega de Instagram sin entrenador detrás, se rompe el primer día.

HORAS_VALIDEZ_ENLACE = 2


@router.post("/forgot-password")
async def forgot_password(data: dict):
    """Pide el correo con el enlace para cambiarla. PUBLICO.

    Responde SIEMPRE lo mismo, exista el correo o no. Si dijera "ese correo no está
    registrado" cualquiera podría averiguar quién es cliente probando correos, que es
    justo lo que no se quiere en una app donde estar dentro dice algo de ti.
    """
    import hashlib
    import os
    import secrets
    from datetime import timedelta

    from core.correo import enviar, texto_recuperar

    email = str((data or {}).get("email") or "").strip().lower()[:120]
    respuesta = {"ok": True,
                 "mensaje": "Si ese correo tiene cuenta, te llega un enlace en un minuto."}
    if not email or "@" not in email:
        return respuesta

    user = await db.users.find_one({"email": email, "deleted_at": None},
                                   {"_id": 0, "id": 1, "name": 1})
    if not user:
        return respuesta

    # El token viaja en el enlace; en la base solo se guarda su hash. Si alguien leyera
    # la colección no podría usar los enlaces pendientes.
    token = secrets.token_urlsafe(32)
    ahora = datetime.now(timezone.utc)
    await db.password_resets.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "expira_en": (ahora + timedelta(hours=HORAS_VALIDEZ_ENLACE)).isoformat(),
        "usado_en": None,
        "creado_en": ahora.isoformat(),
    })

    base = (os.environ.get("APP_URL") or "https://12en12app.jesusgallegopt.com").rstrip("/")
    enlace = f"{base}/recuperar?token={token}"
    await enviar(db, email, "Cambiar tu contraseña de 12EN12",
                 texto_recuperar(user.get("name"), enlace, HORAS_VALIDEZ_ENLACE),
                 tipo="recuperar_password")
    return respuesta


@router.post("/reset-password")
async def reset_password(data: dict):
    """Cambia la contraseña con el token del correo. PUBLICO.

    El token vale una vez y dos horas. Al usarlo se cierran también las sesiones que
    hubiera abiertas por el camino de Calma: si alguien recupera su cuenta, la
    contraseña vieja de Firebase no puede seguir sirviendo.
    """
    import hashlib

    token = str((data or {}).get("token") or "").strip()
    nueva = (data or {}).get("password")
    if not token or not isinstance(nueva, str) or len(nueva) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    doc = await db.password_resets.find_one(
        {"token_hash": hashlib.sha256(token.encode()).hexdigest()}, {"_id": 0})
    if not doc or doc.get("usado_en"):
        raise HTTPException(status_code=400, detail="Este enlace ya no vale. Pide otro.")
    if doc["expira_en"] < datetime.now(timezone.utc).isoformat():
        raise HTTPException(status_code=400, detail="Este enlace ha caducado. Pide otro.")

    await db.users.update_one(
        {"id": doc["user_id"]},
        {"$set": {"password": hash_password(nueva)},
         "$unset": {"firebase_password_hash": "", "firebase_password_salt": ""}},
    )
    await db.password_resets.update_one(
        {"id": doc["id"]}, {"$set": {"usado_en": datetime.now(timezone.utc).isoformat()}})
    return {"ok": True}
