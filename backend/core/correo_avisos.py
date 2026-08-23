"""Los avisos del reporte, POR CORREO (punto 59 del doc del 23-08).

El sistema de avisos se evalúa al entrar en la app, y eso explica el 33 contra 1 de
los reportes: el que no entra, no se entera. Esta pieza da la vuelta a eso para las
familias que tocan dinero: una pasada periódica evalúa los avisos de TODOS los
clientes activos (con el mismo `sincronizar_avisos` de siempre, así la campanita y el
correo cuentan lo mismo) y manda por correo los de reporte y fin de ciclo.

CÓMO NO SE DISPARA DOS VECES
  - Interruptor `correos_avisos` en app_settings, APAGADO de fábrica: desplegar esto
    no manda ni un correo; lo enciende Francisco desde el panel cuando quiera.
  - Prod corre DOS réplicas y las dos llevan este bucle: el que gana es el que
    consigue insertar la marca en `db.correos_de_avisos` (índice único user+clave);
    el otro se encuentra el duplicado y pasa. Un aviso = un correo, como mucho.
  - La clave del aviso ya trae el evento (p. ej. `mensual_ultimo:2026-08-21`): el
    mismo reporte no genera dos correos aunque la pasada corra veinte veces.

El correo va al de CONTACTO del cliente (core/correo.correo_del_cliente), en texto
plano y con el enlace a la app. Sin SMTP (dev), `enviar` lo deja en
`db.correos_pendientes` como 'sin_enviar': se ve lo que habría salido.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from core.database import db

log = logging.getLogger("uvicorn.error")

# Qué familias de aviso salen por correo. Las del REPORTE (aperturas, últimos días y
# el «no nos llegó», que es el que más dinero vale) y el final del ciclo. Las
# condicionadas de hábitos (sin cerrar, sin entrar...) se quedan en la campanita: un
# correo por no apuntar la cena sería ruido.
FAMILIAS_CORREO = {
    "quincenal_abierto", "quincenal_ultimo",
    "semanal_abierto", "semanal_ultimo",
    "mensual_abierto", "mensual_ultimo",
    "reporte_no_llego",
    "fin_ciclo", "ciclo_terminado",
}

CADA_SEGUNDOS = 15 * 60
APP_URL = "https://12en12app.jesusgallegopt.com"


def _cuerpo(nombre, titulo, cuerpo, link) -> str:
    saludo = f"Hola {nombre.split()[0]}," if nombre else "Hola,"
    partes = [saludo, "", titulo]
    if cuerpo:
        partes += ["", cuerpo]
    partes += ["", f"Entra aquí: {APP_URL}{link or ''}", "", "El equipo de 12EN12"]
    return "\n".join(partes)


async def pasada_de_correos_de_avisos(solo_user_id: str = None) -> int:
    """Una pasada completa. Devuelve cuántos correos intentó mandar.

    `solo_user_id` acota la pasada a un cliente: lo usan los tests (recorrer los
    trescientos perfiles de dev por un aviso de mentira tarda minutos) y vale para
    forzar a mano el correo de alguien concreto sin esperar al bucle.
    """
    from routes.settings import pantalla_activa
    if not await pantalla_activa("correos_avisos"):
        return 0

    from core.correo import correo_del_cliente, enviar
    from routes.notifications import sincronizar_avisos

    # La marca de enviado, única por usuario y clave de aviso (la carrera entre réplicas
    # se decide aquí). create_index es idempotente: no pasa nada por repetirlo.
    await db.correos_de_avisos.create_index(
        [("user_id", 1), ("clave", 1)], unique=True, name="user_clave_unico")

    # Los clientes con cuenta viva. `es_prueba` fuera: a las cuentas del QA no se les
    # escribe. El correo del alta puede faltar en migrados: se resuelve por usuario.
    filtro = {"plan": {"$nin": [None, ""]}, "status": {"$ne": "baja"}}
    if solo_user_id:
        filtro["user_id"] = solo_user_id
    perfiles = await db.client_profiles.find(
        filtro, {"_id": 0, "user_id": 1}).to_list(3000)

    ahora = datetime.now(timezone.utc)
    desde = (ahora - timedelta(days=3)).isoformat()
    enviados = 0

    for p in perfiles:
        uid = p.get("user_id")
        if not uid:
            continue
        try:
            usuario = await db.users.find_one(
                {"id": uid, "deleted_at": None},
                {"_id": 0, "email": 1, "name": 1, "es_pruebas": 1})
            if not usuario or not usuario.get("email") or usuario.get("es_pruebas"):
                continue

            # La misma evaluación que al entrar: crea (o no) los avisos que toquen.
            await sincronizar_avisos(uid)

            pendientes = await db.notifications.find(
                {"user_id": uid, "familia": {"$in": list(FAMILIAS_CORREO)},
                 "created_at": {"$gte": desde}},
                {"_id": 0, "clave": 1, "title": 1, "body": 1, "link": 1},
            ).to_list(20)

            for aviso in pendientes:
                clave = aviso.get("clave")
                if not clave:
                    continue
                try:
                    await db.correos_de_avisos.insert_one({
                        "id": str(uuid.uuid4()), "user_id": uid, "clave": clave,
                        "creado_en": ahora.isoformat()})
                except Exception:
                    continue    # ya salió (por esta réplica o por la otra)
                destino = await correo_del_cliente(db, uid, usuario["email"])
                await enviar(db, destino, aviso["title"],
                             _cuerpo(usuario.get("name"), aviso["title"],
                                     aviso.get("body"), aviso.get("link")),
                             tipo="aviso")
                enviados += 1
        except Exception as e:   # noqa: BLE001 - un cliente roto no para la pasada
            log.warning("correo_avisos: fallo con el cliente %s: %s", uid, e)

    if enviados:
        log.info("correo_avisos: %d correos en esta pasada", enviados)
    return enviados


async def bucle_de_correos() -> None:
    """El bucle de fondo: una pasada cada 15 minutos, para siempre.

    Arranca con el servidor (lifespan) y no revienta nunca: si una pasada falla, se
    apunta y se espera a la siguiente. Con el interruptor apagado, cada pasada es un
    no-op de una consulta.
    """
    await asyncio.sleep(60)     # que el arranque termine tranquilo
    while True:
        try:
            await pasada_de_correos_de_avisos()
        except Exception as e:   # noqa: BLE001
            log.warning("correo_avisos: la pasada falló entera: %s", e)
        await asyncio.sleep(CADA_SEGUNDOS)
