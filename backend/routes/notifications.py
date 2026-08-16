"""
Notificaciones in-app del cliente ("campanita").

Tres cosas distintas viven aquí, y conviene no confundirlas:

  - `notify()`: el aviso suelto de toda la vida (cambio de coach, feedback de un
    check-in). Título y cuerpo los pone quien llama.
  - Los avisos de ACCIÓN del doc 16-08 (T10): macros, suplementación, rutina, informe y
    la confirmación del aplazamiento. Salen al guardar, tienen texto fijo de Jesús con
    variantes que rotan, y por eso viven aquí y no repartidos por cada ruta.
  - `sincronizar_avisos()`: los de CALENDARIO y los CONDICIONADOS, que no los dispara
    nadie sino el paso del tiempo y los datos del cliente. Las reglas son puras y están
    en `core/avisos_cliente.py`; aquí se leen los datos y se escribe el resultado.

No hay cron ni push: todo se evalúa AL ENTRAR el cliente en la app, así que una hora fija
solo decide DESDE CUÁNDO se puede ver un aviso. Y todo falla en silencio a propósito:
quedarse sin un aviso no puede impedirle entrar ni romper lo que estaba guardando.
"""
from fastapi import APIRouter, Body, Depends
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from core.database import db
from core.sin_futuro import hasta_hoy
from core.security import get_current_user
from core.tiempo import a_madrid, hoy_madrid

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def notify(user_id: str, type: str, title: str, link: Optional[str] = None, body: Optional[str] = None):
    """Crea una notificación para un usuario. Falla en silencio: un aviso nunca
    debe romper la operación principal (asignar coach, guardar macros...).

    `body` es el texto que escribe el coach (feedback al ajustar macros/suplementos):
    el cliente lo lee en el panel de novedades."""
    if not user_id:
        return
    try:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": type,
            "title": title,
            "body": (body or "").strip() or None,
            "link": link,
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


async def variante_para(user_id: str, familia: str, variantes: list) -> dict:
    """La variante que toca de un aviso con varios textos (regla 6 del doc 16-08:
    nunca el mismo dos veces seguidas).

    `familia` es la clave ESTABLE del aviso, sin fechas ("cierra_dia",
    "quincenal_abierto"...): la `clave` de deduplicación lleva la fecha dentro y
    cambia cada vez, así que no sirve para saber qué texto se usó la última vez.
    Devuelve el texto elegido con `familia` y `variante` dentro, para que el insert
    los persista y la rueda siga girando.
    """
    from core.avisos_cliente import rotar_variante
    ultimo = await db.notifications.find_one(
        {"user_id": user_id, "familia": familia},
        {"_id": 0, "variante": 1}, sort=[("created_at", -1)])
    return {**rotar_variante(variantes, (ultimo or {}).get("variante")), "familia": familia}


# ── Los avisos que salen de algo que hace Jesús (doc 16-08, T10) ─────────────
#
# Se disparan AL GUARDAR, sin hora fija. Viven aquí y no en cada ruta porque son textos
# de Jesús con variantes que rotan, y repartidos por admin.py, supplements.py y
# routines.py acabarían diciendo cada uno una cosa distinta.
#
# Todos fallan en silencio (`notify` no levanta): un aviso no puede impedir que se
# guarden unos macros.

async def _avisar(user_id: str, familia: str, tipo: str, link: str,
                  variantes: List[Dict[str, Any]], nota: Optional[str] = None) -> None:
    """Manda uno de los avisos de acción con la variante que toque.

    La nota del coach va DETRÁS del texto ("+ tu nota" del doc): el cuerpo fijo explica
    qué ha pasado y lo suyo es lo que el cliente venía a leer."""
    if not user_id:
        return
    try:
        elegido = await variante_para(user_id, familia, variantes)
        cuerpo = elegido.get("cuerpo") or ""
        nota = (nota or "").strip()
        if nota:
            cuerpo = f"{cuerpo}\n\n{nota}".strip()
        cuando = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": tipo,
            "title": elegido["titulo"],
            "body": cuerpo or None,
            "link": link,
            "read": False,
            "familia": familia,
            "variante": elegido.get("variante"),
            # La `clave` marca los avisos que ESCRIBE LA APP: la campanita entrecomilla el
            # cuerpo solo cuando no la lleva, porque entonces es lo que escribió una
            # persona. Sin ella, "La verás en cuanto entres a entrenar." salía entre
            # comillas como si se lo hubiera dicho Jesús, y la nota del coach se quedaba
            # dentro de esas mismas comillas.
            #
            # Lleva la hora dentro para que sea única: la deduplicación de
            # `sincronizar_avisos` compara claves, y una clave estable aquí podría hacerle
            # creer que un aviso de calendario ya salió.
            "clave": f"{familia}:{cuando}",
            "created_at": cuando,
        }
        await db.notifications.insert_one(doc)
    except Exception:
        pass


async def avisar_macros(user_id: str, nota: Optional[str] = None,
                        sin_cambios: bool = False) -> None:
    """"Tienes macros nuevos", o "Este mes no te toco nada" si le guardó los mismos.

    Lo dispara SOLO guardar la pestaña Macros del cliente (`PUT .../macros` y
    `POST .../calculator/apply`), nunca guardar la dieta de un día: montando una dieta se
    guarda muchas veces y no puede saltar un aviso cada vez (T12 del doc)."""
    from routes.settings import pantalla_activa
    if not await pantalla_activa("t10_avisos_nuevos"):
        await notify(user_id, "macros", "Hemos actualizado tus macros",
                     "/dashboard/nutrition", body=nota)
        return
    if sin_cambios:
        # Que no le toquen nada también es una decisión, y el cliente que la recibe en
        # silencio cree que se han olvidado de él.
        await _avisar(user_id, "macros_sin_cambios", "macros", "/dashboard/nutrition", [
            {"titulo": "Este mes no te toco nada",
             "cuerpo": "Vas bien con lo que tienes. Seguimos igual."},
        ], nota)
        return
    await _avisar(user_id, "macros_nuevos", "macros", "/dashboard/nutrition", [
        {"titulo": "Tienes macros nuevos",
         "cuerpo": "Los he ajustado con lo que me contaste."},
        {"titulo": "Te he tocado los macros",
         "cuerpo": "Ya los tienes en Nutrición."},
    ], nota)


async def avisar_suplementos(user_id: str, nota: Optional[str] = None) -> None:
    """Al guardar la suplementación del cliente."""
    from routes.settings import pantalla_activa
    if not await pantalla_activa("t10_avisos_nuevos"):
        await notify(user_id, "suplementos", "Tu protocolo de suplementos se ha actualizado",
                     "/dashboard/supplements", body=nota)
        return
    await _avisar(user_id, "suplementos", "suplementos", "/dashboard/supplements", [
        {"titulo": "Te he cambiado la suplementación", "cuerpo": None},
        {"titulo": "Tienes suplementación nueva",
         "cuerpo": "Míralo antes de comprar nada."},
    ], nota)


async def avisar_rutina_nueva(user_id: str) -> None:
    """Al subir una rutina desde el apartado Rutinas, del plan que sea."""
    from routes.settings import pantalla_activa
    if not await pantalla_activa("t10_avisos_nuevos"):
        await notify(user_id, "rutina", "Te hemos preparado una rutina nueva",
                     "/dashboard/routine")
        return
    await _avisar(user_id, "rutina_nueva", "rutina", "/dashboard/routine", [
        {"titulo": "Tienes rutina nueva", "cuerpo": "Ya la tienes en tu entreno de mañana."},
        {"titulo": "Rutina nueva cargada", "cuerpo": "La verás en cuanto entres a entrenar."},
    ])


async def _avisos_nuevos_encendidos() -> bool:
    """Los tres de abajo son avisos que hoy NO existen: no tienen versión antigua a la que
    caer, así que con `t10_avisos_nuevos` apagado simplemente no salen. Quien los llame
    desde T8 y T9 tiene que contar con ello: apagar T10 los apaga también."""
    from routes.settings import pantalla_activa
    return await pantalla_activa("t10_avisos_nuevos")


async def avisar_ajustes_nuevos(user_id: str, nota: Optional[str] = None) -> None:
    """Silver y Bronze, al generarse el informe: reciben los AJUSTES, sin feedback.

    QUIÉN LLAMA A ESTO: T9 (el informe con estado). Cuando Jesús guarde el informe de un
    cliente sin quincenal en sus habilitaciones -- los "Silver y Bronze" del doc --, ahí va
    esta llamada. No se engancha antes porque hoy el informe no se genera ni se guarda en
    ningún sitio, y un aviso que apunta a algo que no existe es peor que ninguno."""
    if not await _avisos_nuevos_encendidos():
        return
    await _avisar(user_id, "ajustes_nuevos", "reporte", "/dashboard/reports", [
        {"titulo": "Tienes ajustes nuevos", "cuerpo": "Los he hecho con tu reporte."},
    ], nota)


async def avisar_informe_listo(user_id: str) -> None:
    """Solo Gold (quien tenga `quincenal` en habilitaciones), y solo cuando Jesús PUBLICA
    el informe: el doc dice que no sale hasta que él lo revisa y añade lo suyo.

    QUIÉN LLAMA A ESTO: T9, en el botón "Publicar" del informe (`informe_estado` pasa a
    "entregado")."""
    if not await _avisos_nuevos_encendidos():
        return
    await _avisar(user_id, "informe_listo", "reporte", "/dashboard/reports", [
        {"titulo": "Tu informe está listo", "cuerpo": "Con mi feedback y tus macros nuevos."},
        {"titulo": "Ya tienes tu informe",
         "cuerpo": "Te cuento lo que veo en tus datos de este mes."},
    ])


async def avisar_reporte_aplazado(user_id: str) -> None:
    """El de confirmación: el cliente marca "aplázalo" en el reporte mensual.

    QUIÉN LLAMA A ESTO: T8, en `POST /reports/aplazar`, justo después de correr su ventana
    siete días. Texto único: es una confirmación, no un recordatorio, y una confirmación
    que cambia de redacción parece otra cosa."""
    if not await _avisos_nuevos_encendidos():
        return
    await _avisar(user_id, "reporte_aplazado", "reporte", "/dashboard/reports", [
        {"titulo": "Te lo he aplazado 7 días",
         "cuerpo": "Tu reporte se vuelve a abrir el viernes que viene. Sigue registrando como siempre."},
    ])


async def sincronizar_avisos(user_id: str) -> int:
    """Mira si al cliente le toca algún aviso de los de la parte 9 y lo crea.

    Se evalúa al entrar en la app en vez de con un cron: un aviso in-app solo se ve
    cuando entra, así que no gana nada existiendo antes. Cada aviso lleva una clave
    única del evento y no se repite mientras esa clave siga viva, así que da igual
    cuántas veces se llame aquí.

    Falla en silencio, como `notify`: quedarse sin un aviso no puede impedirle entrar.
    """
    try:
        from core.avisos_cliente import (
            avisos_condicionados, avisos_de_calendario, avisos_de_calendario_doc,
            elegir_avisos)

        perfil = await db.client_profiles.find_one({"user_id": user_id}, {"_id": 0})
        if not perfil:
            return 0

        ahora = datetime.now(timezone.utc)
        datos = await _datos_para_avisos(perfil, ahora)

        # Las reglas de avisos son puras a proposito (se prueban sin base): el estado del
        # interruptor de la rutina se lee aqui y se les pasa.
        from core.plan_access import rutina_visible_para_el_cliente
        from routes.settings import pantalla_activa

        rutina_visible = await rutina_visible_para_el_cliente()
        # T10 del doc 16-08. Apagado, la app sigue mandando exactamente lo de antes.
        nuevos = await pantalla_activa("t10_avisos_nuevos")

        calendario = avisos_de_calendario(
            perfil=perfil, ahora=ahora,
            proximo_ajuste=datos["proximo_ajuste"],
            semanas_ciclo=datos["semanas_ciclo"],
            macros_puestos_por_alguien=datos["macros_puestos_por_alguien"],
            rutina_visible=rutina_visible,
            nuevos=nuevos,
        )
        if nuevos:
            calendario += avisos_de_calendario_doc(
                # En hora de España: todas las horas del doc lo son. Este es el borde.
                ahora_es=a_madrid(ahora),
                cliente_id=perfil.get("id"),
                arranque=datos["arranque"],
                cerro_hoy=datos["cerro_hoy"],
                quiere_cierre_dia=datos["quiere_cierre_dia"],
                ventanas=datos["ventanas"],
                semana=datos["semana"],
                semanas_ciclo=datos["semanas_ciclo"],
                rutina_visible=rutina_visible,
            )
        condicionados = avisos_condicionados(
            ahora=ahora,
            semanas_sin_ajustar=datos["semanas_sin_ajustar"],
            reporte_sin_fotos=datos["reporte_sin_fotos"],
            dias_sin_cerrar=datos["dias_sin_cerrar"],
            dias_sin_entrar=datos["dias_sin_entrar"],
        )

        # Antes de mirar si le toca una nueva, se retiran las que ya no tocan: si no, se
        # acumulan y el cliente lee tres condicionadas a la vez cuando la regla es UNA cada
        # siete dias (#52 del 15-08).
        await _caducar_condicionadas(user_id, {a["clave"] for a in condicionados})

        # Lo ya enviado, para no repetir. Un mes cubre de sobra cualquier clave viva.
        desde = (ahora - timedelta(days=35)).isoformat()
        previas = await db.notifications.find(
            {"user_id": user_id, "created_at": {"$gte": desde}},
            {"_id": 0, "clave": 1, "created_at": 1, "condicionada": 1},
        ).to_list(200)
        claves = {p.get("clave") for p in previas if p.get("clave")}
        ultima_cond = max((p["created_at"] for p in previas if p.get("condicionada")), default=None)

        elegidos = elegir_avisos(calendario, condicionados, claves, ultima_cond, ahora)
        for aviso in elegidos:
            # El texto se elige AQUI, no al montar la regla: la rotacion solo puede
            # avanzar cuando el aviso se manda de verdad. Si se resolviera antes,
            # cualquier aviso descartado por el tope semanal se llevaria por delante un
            # turno de la rueda y el cliente veria repetido el de la vez anterior.
            if aviso.get("variantes"):
                aviso = {**aviso, **await variante_para(
                    user_id, aviso["familia"], aviso["variantes"])}
            doc = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "type": aviso["tipo"],
                "title": aviso["titulo"],
                "body": aviso.get("cuerpo"),
                "link": aviso.get("link"),
                "read": False,
                "clave": aviso["clave"],
                "condicionada": not aviso.get("calendario"),
                "created_at": ahora.isoformat(),
            }
            # Avisos con textos que rotan (regla 6 del doc 16-08): se guarda qué
            # variante salió para que `variante_para` no repita la misma dos veces.
            if aviso.get("familia") is not None:
                doc["familia"] = aviso["familia"]
                doc["variante"] = aviso.get("variante")
            await db.notifications.insert_one(doc)
        return len(elegidos)
    except Exception:
        return 0


async def _caducar_condicionadas(user_id: str, claves_vivas: set) -> None:
    """Retira de la campanita las condicionadas que ya no vienen a cuento.

    Dos cosas, las dos de las pruebas del 15-08:

      - un aviso que dejo de ser verdad -- «llevas 4 semanas con los mismos macros» dos dias
        despues de ajustarlos -- se quedaba en la lista para siempre (#51),
      - y como cada semana puede entrar una nueva, se acumulaban: Jesus vio tres a la vez
        cuando la regla del documento es UNA condicionada cada siete dias (#52).

    Se queda viva la mas reciente que siga cumpliendose; el resto se marcan. NO se borran:
    el registro es lo que sostiene el tope semanal, y borrandolo le llegaria otra al dia
    siguiente. Se marcan tambien como leidas para que no dejen la campanita encendida.
    """
    pendientes = await db.notifications.find(
        {"user_id": user_id, "condicionada": True, "read": False, "caducada": {"$ne": True}},
        {"_id": 0, "id": 1, "clave": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(50)

    fuera, ya_hay_viva = [], False
    for n in pendientes:            # de la mas nueva a la mas vieja
        if not ya_hay_viva and n.get("clave") in claves_vivas:
            ya_hay_viva = True
            continue
        fuera.append(n["id"])

    if fuera:
        await db.notifications.update_many(
            {"user_id": user_id, "id": {"$in": fuera}},
            {"$set": {"caducada": True, "read": True}})


async def _datos_para_avisos(perfil: dict, ahora: datetime) -> dict:
    """Los datos que miran los disparadores. Consultas cortas y contadas."""
    from core.avisos_cliente import _dias_desde

    client_id, user_id = perfil.get("id"), perfil.get("user_id")

    # Hasta hoy (punto 22): un reporte fechado en 2028 hacia creer que se acababa de pesar,
    # y el aviso de "hace X que no te pesas" no salia nunca.
    ultimo_peso = await db.reports.find_one(
        hasta_hoy({"client_id": client_id, "weight": {"$ne": None}}),
        {"_id": 0, "created_at": 1, "photos": 1}, sort=[("created_at", -1)])
    # `origen` y `changed_by` van en la proyeccion para saber si sus macros los puso ALGUIEN
    # o salieron del calculo del alta. De eso depende que se le diga o no que son
    # provisionales (punto 4.1): si se los puso su coach, no lo son.
    # Por `effective_date`, no por `created_at`: ver `macros_por_fecha.ultima_vigente`. Aqui
    # importaba el doble, porque de la fecha sale «lleva X dias sin ajustar»: con la fecha de
    # importacion, los 185 clientes migrados salian ajustados el 05-08 y el aviso no podia
    # saltar nunca.
    from macros_por_fecha import ultima_vigente, ultimo_cambio
    ultimos_macros = await ultima_vigente(db, client_id)

    # «LLEVAS 4 SEMANAS CON LOS MISMOS MACROS» A LOS DOS DIAS DE AJUSTARLOS (#51 del 15-08).
    #
    # La cuenta salia de la entrada VIGENTE HOY, y esa se corta en hoy a proposito. Si el
    # ajuste se guarda con efecto manana -- que es un cambio ya hecho, solo que programado --
    # la vigente sigue siendo la vieja y el aviso le decia al cliente que lleva un mes igual
    # justo despues de que le tocaran los macros. Se cuenta desde el ultimo cambio
    # REGISTRADO, y como `_dias_desde` no devuelve negativos, un ajuste con fecha futura da
    # cero dias: no hay nada de lo que avisarle.
    cambio = await ultimo_cambio(db, client_id)
    dias_sin_ajustar = _dias_desde(
        (cambio or {}).get("effective_date") or (cambio or {}).get("created_at"),
        ahora)

    # Un reporte reciente sin fotos: sin ellas no se le puede generar el informe.
    sin_fotos = bool(ultimo_peso and not (ultimo_peso.get("photos") or [])
                     and (_dias_desde(ultimo_peso.get("created_at"), ahora) or 99) <= 7)

    semanas_ciclo = None
    proximo_ajuste = None
    semana = None
    ventanas: List[Dict[str, Any]] = []
    try:
        from routes.plans import _overrides_by_code
        from models.user import merged_catalog
        catalogo = merged_catalog(await _overrides_by_code())
        plan = catalogo.get(perfil.get("plan") or "", {})
        semanas_ciclo = (plan.get("ciclo") or {}).get("semanas")
        semana, ventanas = await _ventanas_de_reporte(perfil, catalogo, ahora)
    except Exception:
        pass

    # ¿Sus macros los puso alguien, o salieron del calculo del alta? (punto 4.1). La regla
    # vive en un solo sitio porque la usan dos pantallas -- los avisos y el Inicio -- y si
    # cada una tuviera la suya volveriamos a tener dos verdades.
    from core.macros_de_quien import de_una_persona

    hoy = hoy_madrid()
    cerro_hoy, dias_sin_cerrar = await _cierres_del_cliente(client_id, hoy)

    return {
        "semanas_sin_ajustar": (dias_sin_ajustar // 7) if dias_sin_ajustar is not None else None,
        "reporte_sin_fotos": sin_fotos,
        "proximo_ajuste": proximo_ajuste,
        "semanas_ciclo": semanas_ciclo,
        "semana": semana,
        "ventanas": ventanas,
        "macros_puestos_por_alguien": de_una_persona(ultimos_macros),
        "cerro_hoy": cerro_hoy,
        "dias_sin_cerrar": dias_sin_cerrar,
        "dias_sin_entrar": await _dias_sin_entrar(perfil, hoy),
        # El arranque del ciclo, en día de España: es el "día 1" del que habla el doc.
        "arranque": (a_madrid(perfil.get("cycle_start") or perfil.get("created_at")) or ahora).date(),
        # Activado por defecto: el cliente lo apaga desde su perfil, no al revés.
        "quiere_cierre_dia": bool((perfil.get("avisos") or {}).get("cierre_dia", True)),
    }


async def _cierres_del_cliente(client_id: str, hoy) -> tuple:
    """(¿cerró hoy?, días desde el último cierre). De `checkins`, no de la dieta.

    Un cliente puede llevar la dieta cuadrada en Nutrición y no haber cerrado un solo día:
    lo que Jesús no ve es el cierre, y es lo que piden los dos avisos que dependen de esto
    (el diario de las 20:00 y el de cinco días sin apuntar nada).

    Los cierres de antes del 16-08 no llevan `dia` y hay que sacárselo del `created_at`,
    que va en UTC: uno de las 23:30 de Madrid está guardado con la fecha del día siguiente.
    """
    ultimo = await db.checkins.find_one(
        {"client_id": client_id, "type": "daily"},
        {"_id": 0, "dia": 1, "created_at": 1}, sort=[("created_at", -1)])
    if not ultimo:
        return False, None
    dia = ultimo.get("dia")
    if not dia:
        cuando = a_madrid(ultimo.get("created_at"))
        dia = cuando.date().isoformat() if cuando else None
    if not dia:
        return False, None
    try:
        d = date.fromisoformat(str(dia)[:10])
    except (ValueError, TypeError):
        return False, None
    return d == hoy, max(0, (hoy - d).days)


async def _dias_sin_entrar(perfil: dict, hoy) -> Optional[int]:
    """Cuántos días lleva sin abrir la app, y de paso deja constancia de que hoy entró.

    LO QUE ESTO NO PUEDE HACER: sin push ni cron, el aviso de los catorce días no le llega
    mientras está fuera; le llega en cuanto vuelve, que es cuando la app se entera. Se
    calcula igual porque el dato hay que empezar a guardarlo: el día que existan las push,
    la regla ya está escrita y el histórico también.
    """
    anterior = perfil.get("ultima_entrada")
    dias = None
    if anterior:
        try:
            dias = max(0, (hoy - date.fromisoformat(str(anterior)[:10])).days)
        except (ValueError, TypeError):
            dias = None
    # Una escritura al día como mucho: esto se evalúa en cada consulta de la campanita.
    if str(anterior or "")[:10] != hoy.isoformat():
        await db.client_profiles.update_one(
            {"id": perfil.get("id")}, {"$set": {"ultima_entrada": hoy.isoformat()}})
    return dias


async def _ventanas_de_reporte(perfil: dict, catalogo: dict, ahora: datetime) -> tuple:
    """(semana de ciclo, ventanas de reporte que importan hoy), en hora de España.

    Se miran DOS semanas de ciclo, la de ahora y la anterior, porque el aviso del martes
    («No me llegó tu reporte») cae cuando el cliente ya ha empezado la semana siguiente:
    con solo la semana en curso, ese aviso no podría existir.
    """
    from core.calendario_reportes import reporte_de_la_semana, ventana_del_reporte
    from core.cycle import compute_cycle
    from core.tiempo import a_utc
    from routes.report_cadence import _cal, _week_window_start

    # La semana del ciclo se devuelve SIEMPRE, tenga reportes o no: de ella depende el
    # aviso de "tu ciclo acaba en una semana", que le toca a los tres planes.
    semana = compute_cycle(perfil, ahora)["week"]
    cal = _cal(perfil, catalogo)
    if not (cal.get("patron") or []):
        return semana, []

    inicio = _week_window_start(perfil, ahora)

    ventanas: List[Dict[str, Any]] = []
    for atras in (1, 0):
        n = semana - atras
        if n < 1:
            continue
        tipo = reporte_de_la_semana(cal, n)
        if not tipo:
            continue
        v = ventana_del_reporte(cal, tipo, (inicio - timedelta(days=7 * atras)).date())
        if not v:
            continue
        # ¿Mandó ya el suyo? Dentro de la ventana, con margen por delante: el reporte que
        # llega el jueves por la mañana vale para el aviso del martes siguiente.
        mandado = await db.reports.find_one(
            {"client_id": perfil.get("id"),
             "created_at": {"$gte": a_utc(v["abre"]).isoformat(),
                            "$lte": a_utc(v["cierra"] + timedelta(days=1)).isoformat()}},
            {"_id": 0, "id": 1})
        ventanas.append({"tipo": tipo, "semana": n, "abre": v["abre"],
                         "cierra": v["cierra"], "mandado": bool(mandado)})
    return semana, ventanas


@router.get("")
async def list_notifications(user = Depends(get_current_user)):
    """Últimas notificaciones del usuario actual."""
    await sincronizar_avisos(user["id"])
    # Las caducadas no se pintan: son avisos que dejaron de ser verdad (ver
    # `_caducar_condicionadas`). Se conservan en la base, solo que fuera de la vista.
    items = await db.notifications.find(
        {"user_id": user["id"], "caducada": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", -1).to_list(30)
    return {"notifications": items}


@router.get("/unread-count")
async def unread_count(user = Depends(get_current_user)):
    await sincronizar_avisos(user["id"])
    count = await db.notifications.count_documents(
        {"user_id": user["id"], "read": False, "caducada": {"$ne": True}})
    return {"count": count}


@router.get("/preferencias")
async def get_preferencias(user=Depends(get_current_user)):
    """Qué avisos quiere recibir. Hoy solo se puede apagar el del cierre del día: es el
    único diario, y es el que el doc marca como "activado por defecto · puede apagarlo".

    Va aparte del perfil porque el perfil es del coach tanto como del cliente, y esto es
    una preferencia suya que no tiene que pasar por `PUT /clients/profile`."""
    perfil = await db.client_profiles.find_one(
        {"user_id": user["id"]}, {"_id": 0, "avisos": 1})
    avisos = (perfil or {}).get("avisos") or {}
    return {"cierre_dia": bool(avisos.get("cierre_dia", True))}


@router.put("/preferencias")
async def update_preferencias(payload: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    """Guarda las preferencias de avisos del cliente."""
    cambios = {}
    if "cierre_dia" in payload:
        cambios["avisos.cierre_dia"] = bool(payload.get("cierre_dia"))
    if cambios:
        await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": cambios})
    return await get_preferencias(user)


@router.put("/read-all")
async def mark_all_read(user = Depends(get_current_user)):
    result = await db.notifications.update_many(
        {"user_id": user["id"], "read": False}, {"$set": {"read": True}}
    )
    return {"ok": True, "marked": result.modified_count}
