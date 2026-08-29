# -*- coding: utf-8 -*-
"""SIN PLAN NO SE USA LA APP. Solo se puede elegir uno para recuperar el acceso.

Francisco, 29-08-2026: «una persona que no tiene plan no puede utilizar el sistema, solo
puede seleccionar un plan para volver a recuperar acceso».

Y no era asi. Medido con una cuenta recien registrada, sin plan, contra el backend:

    ENTRA  200  Nutricion, su dieta de hoy          parado  402  Suplementos
    ENTRA  200  Nutricion, sus favoritas            parado  402  Rutina
    ENTRA  200  GUARDAR una dieta
    ENTRA  200  Seguimiento, sus check-ins

Solo paraban los tres endpoints que usan `require_access` (rutina, suplementos, registro
de entrenos). Lo demas estaba abierto, y en la pantalla el bloqueo vivia unicamente en el
Inicio: escribiendo /dashboard/nutrition se entraba igual.

POR QUE UN CANDADO CENTRAL Y NO UN `Depends` EN CADA SITIO. Porque la regla es «no puede
usar el sistema», no «no puede usar estas doce rutas». Puesto endpoint por endpoint, el
agujero vuelve con la siguiente ruta que alguien añada -- que es exactamente como se llego
hasta aqui. Aqui se cierra todo y se abre lo justo.

LO QUE SIGUE ABIERTO SIN PLAN, y por que:
  - entrar, salir y su cuenta (`/auth`, `/users/me`): sin esto no puede ni identificarse.
  - el catalogo y la compra (`/plans`, `/billing`, `/payments`): es LO UNICO que se
    espera que haga, y sin ello no hay forma de volver.
  - su perfil (`/clients/profile`): es lo que lee la pantalla para saber que no tiene plan
    y enseñarle la de elegir uno. Cerrarlo dejaria la app en blanco sin decir por que.
  - avisos y mensajes: para que pueda escribir al equipo si algo va mal con su pago. Se le
    cierra la app, no la puerta para hablar con una persona.
  - el cuestionario del alta (`/questionnaire`): se rellena antes de tener plan.

QUIEN NO PASA POR AQUI:
  - admin y entrenadores: el equipo no compra planes. Cuando uno de ellos ACTUA COMO un
    cliente, `get_current_user` ya devuelve al cliente, asi que se le aplica la regla del
    cliente y no la suya (ver `core/actuar_como.py`).
  - las peticiones sin sesion: de esas ya se ocupa el 401 de siempre.

QUE DEVUELVE: 402 con `motivo`, que es lo que la pantalla necesita para saber si enseñar
«selecciona un plan» (sin_plan), «termina el pago» (sin_pagar) o «se te acabo» (caducado).
La regla de los tres casos es de `estado_de_acceso`, no se repite aqui.
"""
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Prefijos (bajo /api) que puede tocar quien no tiene acceso. Se comparan por comienzo de
# ruta, asi que `/api/plans` cubre `/api/plans/loquesea`.
ABIERTO_SIN_PLAN = (
    "/api/auth",
    "/api/health",
    "/api/plans",
    "/api/billing",
    "/api/payments",
    "/api/users/me",
    "/api/clients/profile",
    "/api/questionnaire",
    "/api/notifications",
    "/api/messages",
    "/api/settings",
)

# Metodos que no cambian nada. No se dejan pasar por ser de lectura -- leer la dieta de
# alguien sin plan tambien es usar la app --, pero se listan aparte por si algun dia se
# quiere abrir la mano solo con las consultas.
SEGUROS = ("OPTIONS", "HEAD")


def _abierto(ruta: str) -> bool:
    return any(ruta.startswith(p) for p in ABIERTO_SIN_PLAN)


async def candado_de_plan(request: Request, call_next):
    """Middleware: corta la API al cliente sin acceso, salvo lo de `ABIERTO_SIN_PLAN`."""
    ruta = request.url.path
    if request.method in SEGUROS or not ruta.startswith("/api") or _abierto(ruta):
        return await call_next(request)

    # Sin cabecera de sesion no hay nada que decidir: el 401 de siempre se encarga.
    if not request.headers.get("authorization"):
        return await call_next(request)

    try:
        from core.database import db
        from core.plan_access import estado_de_acceso
        from core.security import decode_token

        token = request.headers["authorization"].split(" ")[-1]
        payload = decode_token(token)
        user = await db.users.find_one({"id": payload["sub"]},
                                       {"_id": 0, "id": 1, "role": 1})
        if not user:
            return await call_next(request)
        # El equipo no compra planes. Si esta ACTUANDO COMO un cliente, la cabecera manda
        # y quien se comprueba es el cliente: se resuelve igual que en `get_current_user`.
        objetivo_id = (request.headers.get("X-Actuar-Como") or "").strip()
        if user.get("role") in ("admin", "trainer") and not objetivo_id:
            return await call_next(request)
        if objetivo_id:
            user = await db.users.find_one({"id": objetivo_id},
                                           {"_id": 0, "id": 1, "role": 1}) or user
            if user.get("role") in ("admin", "trainer"):
                return await call_next(request)

        perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
        acceso = estado_de_acceso(perfil)
        if acceso.get("activo"):
            return await call_next(request)
    except Exception:
        # Si esto falla, NO se cierra la app: un fallo del candado no puede dejar fuera a
        # quien si ha pagado. Se deja pasar y que decidan los cerrojos de cada endpoint.
        logger.exception("[candado_de_plan] no se pudo comprobar el acceso; se deja pasar")
        return await call_next(request)

    return JSONResponse(
        status_code=402,
        content={"detail": "Necesitas un plan activo para usar la aplicación.",
                 "motivo": acceso.get("motivo") or "sin_plan"},
    )
