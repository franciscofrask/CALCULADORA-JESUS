"""Los avisos del reporte, POR CORREO (punto 59 del doc del 23-08).

El sistema de avisos se evalúa al entrar en la app, y eso explica el 33 contra 1 de
los reportes: el que no entra, no se entera. Esta pieza da la vuelta a eso para las
familias que tocan dinero: una pasada periódica evalúa los avisos de TODOS los
clientes activos (con el mismo `sincronizar_avisos` de siempre, así lo que sale por
correo es exactamente lo que le aparece en la campanita) y manda por correo los de
reporte y fin de ciclo.

ESTO NO ES EL CLIENTE ENTRANDO, y `sincronizar_avisos` tiene que saberlo: la pasada no
deja la huella de «ha entrado» ni crea avisos condicionados (los de hábitos, que además
no salen por correo). Ver `marcar_entrada` y `solo_calendario` allí.

CÓMO NO SE DISPARA DOS VECES
  - Interruptor `correos_avisos` en app_settings, APAGADO de fábrica: desplegar esto
    no manda ni un correo; lo enciende Francisco desde el panel cuando quiera.
  - Prod corre DOS réplicas y las dos llevan este bucle: el que gana es el que
    consigue insertar la marca en `db.correos_de_avisos` (índice único user+clave);
    el otro se encuentra el duplicado y pasa. Un aviso = un correo, como mucho.
  - La clave del aviso ya trae el evento (p. ej. `mensual_ultimo:2026-08-21`): el
    mismo reporte no genera dos correos aunque la pasada corra veinte veces.
  - Y si el relay falla, la marca se queda pero en rojo (`fallido`), con un contador:
    se reintenta hasta `MAX_INTENTOS` y después se para. Ni se pierde el correo ni se
    reintenta durante tres días seguidos.

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

# CUÁNTAS VECES SE VUELVE A INTENTAR UN CORREO QUE NO SALIÓ. El reintento no puede ser
# infinito: la pasada corre cada 15 minutos y la ventana de avisos es de 3 días, así que un
# relay caído dejaría hasta 288 filas en `correos_pendientes` y 288 warnings POR AVISO Y
# CLIENTE, y la cola de sin_enviar -- que es lo único que se puede mirar después -- dejaría
# de leerse. Con tres, el relay tiene 45 minutos para volver y el rastro sigue siendo un
# rastro.
MAX_INTENTOS = 3


def _cuerpo(nombre, titulo, cuerpo, link) -> str:
    saludo = f"Hola {nombre.split()[0]}," if nombre else "Hola,"
    partes = [saludo, "", titulo]
    if cuerpo:
        partes += ["", cuerpo]
    partes += ["", f"Entra aquí: {APP_URL}{link or ''}", "", "El equipo de 12EN12"]
    return "\n".join(partes)


async def pasada_de_correos_de_avisos(solo_user_id: str = None) -> int:
    """Una pasada completa. Devuelve cuántos correos SALIERON.

    `solo_user_id` acota la pasada a un cliente: lo usan los tests (recorrer los
    trescientos perfiles de dev por un aviso de mentira tarda minutos) y vale para
    forzar a mano el correo de alguien concreto sin esperar al bucle.
    """
    from routes.settings import pantalla_activa
    if not await pantalla_activa("correos_avisos"):
        return 0

    from core.correo import configurado, correo_del_cliente, enviar
    from routes.notifications import sincronizar_avisos

    # La marca de enviado, única por usuario y clave de aviso (la carrera entre réplicas
    # se decide aquí). create_index es idempotente: no pasa nada por repetirlo.
    await db.correos_de_avisos.create_index(
        [("user_id", 1), ("clave", 1)], unique=True, name="user_clave_unico")

    # Los clientes con cuenta viva. `es_prueba` fuera: a las cuentas del QA no se les
    # escribe. El correo del alta puede faltar en migrados: se resuelve por usuario.
    #
    # LA MARCA ES `es_prueba`, NO `es_pruebas`. Aquí se filtraba por `es_pruebas`, que es
    # otra cosa -- el modo laboratorio de una cuenta concreta --, así que las prueba.nivel1,
    # prueba.bronze, prueba.caducado... quedaban fuera del panel y de las tareas pero
    # habrían recibido correos de verdad. Y va en la consulta para no recorrerlas.
    filtro = {"plan": {"$nin": [None, ""]}, "status": {"$ne": "baja"},
              "es_prueba": {"$ne": True}}
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
                {"_id": 0, "email": 1, "name": 1, "es_prueba": 1, "es_pruebas": 1})
            if (not usuario or not usuario.get("email")
                    or usuario.get("es_prueba") or usuario.get("es_pruebas")):
                continue

            # La misma evaluación que al entrar, pero esto NO es el cliente abriendo la app:
            #   - sin dejar la huella de «ha entrado», que mataba los avisos de «llevas días
            #     sin entrar»,
            #   - y solo avisos de calendario, que son los únicos que salen por correo
            #     (`FAMILIAS_CORREO`). Esta pasada corre también de madrugada, y una
            #     condicionada nacida a las 00:15 gastaba el «uno al día» y dejaba sin nacer
            #     el «tu reporte está abierto» de las 10:00, que solo es candidato ese día.
            await sincronizar_avisos(uid, marcar_entrada=False, solo_calendario=True)

            # «POR CORREO», APAGADO (doc «El día», 31-08). Se va el correo, no el aviso: en
            # la app le siguen saliendo los que no haya apagado.
            #
            # OJO, QUE AQUÍ HAY UNA TRAMPA. `FAMILIAS_CORREO` incluye el fuera de plazo y los
            # dos del contrato, y esos tres están entre los CUATRO QUE NO SE APAGAN NUNCA
            # («si lo apaga, se le caduca la suscripción sin enterarse y luego la culpa es
            # tuya»). Así que apagar el correo no puede ser un `continue`: hay que dejar
            # pasar esos y quitar el resto.
            from core.avisos_cliente import NUNCA_SE_APAGAN
            perfil_avisos = await db.client_profiles.find_one(
                {"user_id": uid}, {"_id": 0, "avisos": 1})
            quiere_correo = ((perfil_avisos or {}).get("avisos") or {}).get("por_correo", True)
            familias = (FAMILIAS_CORREO if quiere_correo
                        else FAMILIAS_CORREO & NUNCA_SE_APAGAN)
            if not familias:
                continue

            pendientes = await db.notifications.find(
                {"user_id": uid, "familia": {"$in": list(familias)},
                 "created_at": {"$gte": desde}},
                {"_id": 0, "clave": 1, "title": 1, "body": 1, "link": 1},
            ).to_list(20)

            for aviso in pendientes:
                clave = aviso.get("clave")
                if not clave:
                    continue
                # La marca se pone ANTES de mandar: es lo que decide la carrera entre las
                # dos réplicas. Si el envío falla no se borra, se marca `fallido` con su
                # contador. Borrarla dejaba el reintento sin freno: la siguiente pasada
                # empezaba de cero y no había nada que supiera cuántas veces se había
                # intentado ya.
                intento = 1
                try:
                    await db.correos_de_avisos.insert_one({
                        "id": str(uuid.uuid4()), "user_id": uid, "clave": clave,
                        "intentos": 1, "creado_en": ahora.isoformat()})
                except Exception:
                    # Ya hay marca. Si el correo salió, aquí no se toca nada: un aviso, un
                    # correo. Si falló y le quedan intentos, este es quien lo coge, y el
                    # find_one_and_update es atómico, así que la otra réplica no lo repite.
                    marca = await db.correos_de_avisos.find_one_and_update(
                        {"user_id": uid, "clave": clave, "fallido": True,
                         "intentos": {"$lt": MAX_INTENTOS}},
                        {"$inc": {"intentos": 1}})
                    if not marca:
                        continue
                    intento = int(marca.get("intentos") or 1) + 1
                destino = await correo_del_cliente(db, uid, usuario["email"])
                salio = await enviar(db, destino, aviso["title"],
                                     _cuerpo(usuario.get("name"), aviso["title"],
                                             aviso.get("body"), aviso.get("link")),
                                     tipo="aviso")
                if salio:
                    enviados += 1
                    if intento > 1:     # salió al reintentar: la marca deja de estar en rojo
                        await db.correos_de_avisos.update_one(
                            {"user_id": uid, "clave": clave}, {"$set": {"fallido": False}})
                elif configurado():
                    # SI EL RELAY TIENE UN MAL RATO, ESTO NO SE PUEDE DAR POR MANDADO. Con la
                    # marca limpia, este aviso -- los de reporte y fin de ciclo, los que traen
                    # el dinero -- no se volvería a intentar nunca más y nadie mira la cola de
                    # `correos_pendientes`. Se deja en rojo para que la pasada de dentro de 15
                    # minutos lo reintente, hasta `MAX_INTENTOS`.
                    #
                    # Sin SMTP (dev) no se toca: ahí no hay nada que reintentar, el correo
                    # queda a la vista en `correos_pendientes` como 'sin_enviar' y reintentar
                    # solo serviría para apuntar el mismo cuatro veces por hora.
                    await db.correos_de_avisos.update_one(
                        {"user_id": uid, "clave": clave},
                        {"$set": {"fallido": True, "ultimo_fallo": ahora.isoformat()}})
                    if intento < MAX_INTENTOS:
                        log.warning("correo_avisos: no salió el aviso %s de %s (intento %d de "
                                    "%d); se reintenta en la próxima pasada",
                                    clave, uid, intento, MAX_INTENTOS)
                    else:
                        log.warning("correo_avisos: el aviso %s de %s no salió en %d intentos; "
                                    "se deja de intentar y queda en correos_pendientes",
                                    clave, uid, MAX_INTENTOS)
        except Exception as e:   # noqa: BLE001 - un cliente roto no para la pasada
            log.warning("correo_avisos: fallo con el cliente %s: %s", uid, e)

    if enviados:
        log.info("correo_avisos: %d correos en esta pasada", enviados)
    return enviados


async def pasada_de_promesas_del_reporte() -> int:
    """Avisa al equipo de los reportes cuya respuesta se prometió para HOY.

    Una vez al día y a las 10:00 de España: a esa hora queda media jornada por delante, que
    es lo que hace que la promesa se cumpla en vez de dejar constancia de que se rompió.
    Ver `core/promesa_del_reporte` para el porqué de avisar al equipo y no al cliente.

    Idempotente por el día: la marca es la misma clave que usan los correos, así que aunque
    el bucle pase cuatro veces entre las 10:00 y las 11:00, el aviso sale uno.
    """
    from core.avisos_equipo import avisar_al_equipo
    from core.promesa_del_reporte import HORA_DEL_REPASO, a_quien_le_toca, texto_del_aviso
    from core.tiempo import ahora_madrid

    ahora_es = ahora_madrid()
    if ahora_es.hour != HORA_DEL_REPASO:
        return 0
    hoy = ahora_es.date()

    clave = f"promesa_reporte:{hoy.isoformat()}"
    try:
        await db.correos_de_avisos.insert_one({
            "id": str(uuid.uuid4()), "user_id": "equipo", "clave": clave,
            "intentos": 1, "creado_en": datetime.now(timezone.utc).isoformat()})
    except Exception:
        return 0        # ya salió hoy (o lo está sacando la otra réplica)

    # Los de las tres últimas semanas: más atrás la promesa no vence hoy ni por asomo.
    desde = (hoy - timedelta(days=21)).isoformat()
    reportes = await db.reports.find(
        {"created_at": {"$gte": desde}},
        {"_id": 0, "id": 1, "client_id": 1, "tipo": 1, "created_at": 1,
         "informe_estado": 1, "calma_migrated": 1, "trainer_feedback": 1},
    ).to_list(2000)

    esperando = a_quien_le_toca(reportes, hoy)
    if not esperando:
        return 0

    texto = texto_del_aviso(len(esperando))
    await avisar_al_equipo(
        db, tipo="promesa_reporte", titulo=texto["titulo"], mensaje=texto["mensaje"],
        # Sin `client_id`: es una lista, no un cliente. Quien lo abra va a la de reportes.
        extra={"reportes": [r.get("id") for r in esperando][:50]})
    log.info("promesa del reporte: %d esperando respuesta hoy", len(esperando))
    return len(esperando)


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
        # LA PROMESA DEL REPORTE, EN EL MISMO BUCLE (doc «El día», 31-08). No merece una
        # tarea de fondo propia -- es una consulta al día -- y aquí ya hay un reloj andando.
        # Va aparte del `try` de arriba para que un fallo del correo no se la lleve.
        try:
            await pasada_de_promesas_del_reporte()
        except Exception as e:   # noqa: BLE001
            log.warning("promesa del reporte: la pasada falló: %s", e)
        await asyncio.sleep(CADA_SEGUNDOS)
