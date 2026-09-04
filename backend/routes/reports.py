"""
Rutas de reportes: crear, listar, evolución.
"""
from fastapi import APIRouter, Body, HTTPException, Depends
from datetime import date, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import logging
import uuid

from core.database import db
from core.security import get_current_user, get_admin_user, assert_client_access
from core.plan_access import plan_grants_feature
from core.series_cliente import anotar_peso
from core.sin_futuro import hasta_hoy
from core.tiempo import a_madrid, hoy_madrid
from models.common import ReportCreate, ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])
logger = logging.getLogger(__name__)

# CUÁNTO PERIODO MIRA CADA REPORTE (doc 16-08, T7 y T8).
#
# El quincenal habla de las dos últimas semanas ("de los 6 que tenías") y el mensual del
# mes ("25 de 28 días"). Va por ventana fija y no por "desde el reporte anterior": a un
# cliente con quincenal, el mensual caería a catorce días del anterior y su "este mes"
# serían dos semanas. El único recorte es el arranque, para no pedirle cuentas de un mes
# en el que todavía no era cliente.
DIAS_DEL_PERIODO = {"quincenal": 14, "mensual": 28, "semanal": 7}
# Rutas del equipo sobre el reporte de un cliente (punto 45): meterlo en su nombre.
admin_router = APIRouter(prefix="/admin", tags=["admin-reports"])

# EL REPORTE SABE SU CICLO Y SU BLOQUE (doc de Jesús del 2-09, fase 1; Francisco, 4-09).
#
# Jesús: «un punto de control es un reporte; cada uno se llama bloque y ciclo». Hasta hoy el
# reporte no guardaba ni ciclo, ni semana, ni bloque, y la semana del informe se
# RECALCULABA a posteriori sobre el perfil de hoy (ver `_montar_informe_del_reporte`), que
# es la de ahora y no la del reporte. Y el ancla del ciclo (`cycle_start`) se pisa en cada
# renovación, así que un reporte de hace tres meses ya no se puede situar. Por eso los
# cinco se CONGELAN al crearlo, en las dos vías, y de ahí los leerá Evolución.
CAMPOS_CICLO = ("ciclo_id", "ciclo_numero", "ciclo_inicio", "semana_del_ciclo", "bloque")
# Cuántos días atrás mira la vía del equipo buscando las fotos sueltas del reporte que
# está pasando a la app (los Premium mandan por WhatsApp y alguien las sube días después).
DIAS_DE_FOTOS_PARA_EL_EQUIPO = 14
# Cuántas fotos se cosen como mucho a un reporte, en las dos vías (tres poses, con margen).
TOPE_FOTOS_POR_REPORTE = 6


async def _ciclo_del_reporte(profile: dict, dia) -> dict:
    """Los cinco campos del ciclo para el día del reporte. Si el cuaderno de ciclos falla,
    los cinco a None y un aviso: el reporte nunca se pierde por esto. El import va dentro
    por lo mismo: si `core.ciclos` no carga, los reportes se siguen mandando."""
    try:
        from core.ciclos import ciclo_de
        return await ciclo_de(profile or {}, dia)
    except Exception as e:      # noqa: BLE001 - el cuaderno de ciclos es secundario
        logger.warning("reporte de %s sin ciclo (se guarda igual): %s",
                       (profile or {}).get("id"), e)
        return {k: None for k in CAMPOS_CICLO}


async def _fotos_sueltas_de(client_id: str, *, desde: str, hasta: Optional[str] = None,
                            tope: int = TOPE_FOTOS_POR_REPORTE, mas_recientes: bool = False) -> List[str]:
    """Las fotos de progreso del cliente que todavía no son de ningún reporte, subidas
    entre `desde` y `hasta` (ISO), hasta `tope`, en orden cronológico.

    Fuera las del alta (`uso`: la del carrusel de grasa y la de su mejor forma, que
    core/fotos ya deja fuera al listar) y fuera las que otro reporte ya se llevó
    (`report_id`): sin esto una foto subida en la ventana podía acabar en dos reportes.
    `report_id: None` casa también con las de antes de este código, que no tienen el campo.

    Con `mas_recientes` se quedan las últimas `tope` (lo que hacía la vía del cliente:
    lo que acaba de subir); sin él, las primeras `tope` de la ventana."""
    filtro = {"client_id": client_id, "uploaded_at": {"$gte": desde},
              "uso": {"$exists": False}, "report_id": None}
    if hasta:
        filtro["uploaded_at"]["$lte"] = hasta
    cursor = db.client_photos.find(filtro, {"_id": 0, "id": 1}).sort(
        "uploaded_at", -1 if mas_recientes else 1).limit(tope)
    ids = [d["id"] async for d in cursor]
    if mas_recientes:
        ids.reverse()
    return ids


async def _atar_fotos_al_reporte(report: dict) -> None:
    """LA FOTO Y EL REPORTE, ATADOS EN LOS DOS SENTIDOS (4-09).

    El reporte ya lleva sus fotos en `photos`; aquí se les escribe a ellas el `report_id`,
    que es lo que deja preguntar «¿de qué reporte es esta foto?» sin recorrer los reportes.
    Y si la foto se subió sin poder situarla en su ciclo (los cinco a None), se le ponen
    los del reporte, campo a campo: son de la misma ventana.

    Solo fotos DE ESTE CLIENTE: un body con ids ajenos no puede apropiárselos. Y si esto
    falla, el reporte ya está guardado y no se pierde nada del cliente; el detalle, a
    consola.
    """
    ids = [f for f in (report.get("photos") or []) if f]
    if not ids:
        return
    de_este_cliente = {"id": {"$in": ids}, "client_id": report["client_id"]}
    try:
        await db.client_photos.update_many(de_este_cliente, {"$set": {"report_id": report["id"]}})
        for campo in CAMPOS_CICLO:
            if report.get(campo) is not None:
                await db.client_photos.update_many(
                    {**de_este_cliente, campo: None}, {"$set": {campo: report[campo]}})
    except Exception as e:      # noqa: BLE001
        logger.warning("no se pudieron atar las fotos al reporte %s: %s", report.get("id"), e)

@router.post("")
async def create_report(data: ReportCreate, user = Depends(get_current_user)):
    """Crear un reporte de seguimiento.

    Devuelve el reporte MAS lo que la pantalla de "enviado" tiene que decirle (T9): si su
    plan lleva feedback y, con eso, qué se le promete y para cuándo. Por eso ya no lleva
    `response_model`: el modelo describe el reporte guardado, no la respuesta al envío.
    """
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    if not plan_grants_feature(profile.get("plan"), "reportes"):
        raise HTTPException(status_code=403, detail="Tu plan no incluye reportes de seguimiento.")

    # Ventana de envío: fuera de ella se bloquea. Cada reporte tiene la suya (el quincenal
    # de miércoles a jueves, el mensual de viernes a lunes), así que lo que se le dice al
    # cliente sale de SU ventana y no de una frase fija.
    from routes.report_cadence import compute_client_report_state, rutina_activa_de, _fecha_es, _hora_es
    from routes.plans import _overrides_by_code
    from models.user import merged_catalog
    now = datetime.now(timezone.utc)
    state = compute_client_report_state(profile, merged_catalog(await _overrides_by_code()), now,
                                        rutina=await rutina_activa_de(profile.get("id")))
    if not state["due"]:
        raise HTTPException(status_code=403, detail="Esta semana no toca reporte. Te avisaremos cuando abra la ventana.")
    # Los dos cerrojos miran `is_open`, que es quien sabe de verdad si la ventana está
    # abierta. Antes comparaban las fechas por su cuenta, y en el clon de pruebas -- donde
    # la ventana se abre a la fuerza (VENTANAS_SIEMPRE_ABIERTAS) -- eso dejaba al cliente
    # viendo el formulario y sin poder mandarlo: peor que no enseñárselo.
    if not state["is_open"]:
        if now < state["window_open"]:
            # Decía «se rellena el fin de semana», que es verdad para el mensual y mentira
            # para el quincenal: ese se rellena el miércoles y el jueves.
            raise HTTPException(
                status_code=403,
                detail=f"Todavía no toca: se abre el {_fecha_es(state['window_open'])} "
                       f"a las {_hora_es(state['window_open'])} y lo tienes hasta el "
                       f"{_fecha_es(state['window_close'])} a las {_hora_es(state['window_close'])}.")
        raise HTTPException(status_code=403, detail="La ventana de esta semana ya se cerró. Espera a la semana que viene.")

    # Confirmación de huecos: el cumplimiento sale del registro, no de que se puntúe
    # (documento, parte 7.1). Si el cliente contestó a los huecos, ese cumplimiento manda
    # sobre lo que llegue en los campos viejos, que quedan solo por compatibilidad.
    from core.confirmacion_huecos import (
        huecos_del_periodo, cumplimiento as _cumplimiento, limpiar_respuestas)

    respuestas_huecos = limpiar_respuestas(getattr(data, "huecos", None))
    cumpl = None
    if respuestas_huecos:
        prev_rep = await db.reports.find_one(
            hasta_hoy({"client_id": profile["id"]}), {"_id": 0, "created_at": 1},
            sort=[("created_at", -1)],
        )
        desde = now - timedelta(days=28)
        if prev_rep and prev_rep.get("created_at"):
            try:
                desde = datetime.fromisoformat(str(prev_rep["created_at"]).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        d_per, d_dieta, d_entreno, _ = await _actividad_del_periodo(
            profile, desde.isoformat(), now.isoformat())
        por_semana = profile.get("training_days") or profile.get("dias_entreno")
        previstos = round(float(por_semana) * d_per / 7) if por_semana else None
        cumpl = _cumplimiento(
            huecos_del_periodo(d_per, d_dieta, d_entreno, previstos), respuestas_huecos)

    # LAS FOTOS QUE ACABA DE SUBIR, ENGANCHADAS AL REPORTE.
    #
    # El cliente las sube con `POST /reports/photos`, que las guarda en `client_photos`, y el
    # formulario NO manda el campo `photos`. Nadie las juntaba: medido en produccion, de
    # 3.151 reportes **ninguno** tiene fotos, y hay 646 fotos huerfanas. Y `montar_informe`
    # empieza con «sin fotos, no hay informe», asi que **el informe mensual no se le ha
    # generado nunca a nadie** por la via normal de la app (caso 51 de la lista del 12-08).
    #
    # Se recogen aqui y no se le pide nada al front: las fotos ya estan subidas y fechadas, y
    # lo que faltaba era la costura. Se cogen las de la ventana de este reporte, que es
    # exactamente lo que el cliente acaba de hacer.
    #
    # Desde el 4-09 solo las de progreso y solo las sueltas (ver `_fotos_sueltas_de`): ni
    # las del alta ni las que ya se llevó otro reporte.
    fotos = [f for f in (data.photos or []) if f]
    if not fotos:
        fotos = await _fotos_sueltas_de(
            profile["id"], desde=state["window_open"].isoformat(), mas_recientes=True)

    # NO SE MANDA MEDIO MENSUAL (caso 51 de los 85, punto 21 del repaso del 23-08): las
    # diez medidas y las tres fotos son obligatorias, y hasta hoy solo las miraba el
    # navegador. Se comprueba con las fotos YA recogidas arriba, que es lo que de verdad
    # tiene el reporte. La vía del equipo (Premium por WhatsApp) no pasa por aquí: esa
    # sigue aceptando lo que llegue, que es su razón de existir.
    tipo_de_hoy = (state["tipos"] or [data.tipo])[0] if (state["tipos"] or data.tipo) else None
    if tipo_de_hoy == "mensual":
        falta = ReportCreate(**{**data.model_dump(), "tipo": "mensual"}).falta_para_el_mensual(
            fotos_subidas=len(fotos))
        if falta:
            raise HTTPException(
                status_code=400,
                detail=f"Para mandar el reporte del mes te faltan {' y '.join(falta)}.")

    report_id = str(uuid.uuid4())
    creado = datetime.now(timezone.utc).isoformat()
    # El día del reporte es el de `created_at` (el mismo instante del que abajo sale
    # `dia_reporte` para la serie de peso): el reporte no lleva otro día del cliente.
    ciclo = await _ciclo_del_reporte(profile, creado)
    report = {
        "id": report_id,
        "client_id": profile["id"],
        # De qué ciclo, semana y bloque es (ver CAMPOS_CICLO arriba; 4-09).
        "ciclo_id": ciclo.get("ciclo_id"),
        "ciclo_numero": ciclo.get("ciclo_numero"),
        "ciclo_inicio": ciclo.get("ciclo_inicio"),
        "semana_del_ciclo": ciclo.get("semana_del_ciclo"),
        "bloque": ciclo.get("bloque"),
        "weight": data.weight,
        "measurements": data.measurements,
        "photos": fotos or None,
        "huecos": respuestas_huecos or None,
        "cumplimiento": cumpl,
        "training_compliance": (cumpl or {}).get("entreno_pct", data.training_compliance),
        "nutrition_compliance": (cumpl or {}).get("dieta_pct", data.nutrition_compliance),
        "sleep_quality": data.sleep_quality,
        "energy_level": data.energy_level,
        "stress_level": data.stress_level,
        "notes": data.notes,
        # Las tres preguntas del formulario de siempre (punto 5 del 05-08)
        "proximo_objetivo": data.proximo_objetivo,
        "viabilidad_ajuste": data.viabilidad_ajuste,
        "cumplimiento_entreno": data.cumplimiento_entreno,
        # Lo que trae el formulario nuevo (T7 y T8). El `tipo` que manda es el del
        # calendario, no el que diga el front: es el servidor quien sabe qué semana es.
        "tipo": (state["tipos"] or [data.tipo])[0] if (state["tipos"] or data.tipo) else None,
        "molestias": (data.molestias or "").strip() or None,
        "sensaciones": data.sensaciones,
        # La del semanal (doc 21-08): qué le altera la rutina la semana que viene. Es lo
        # que el entrenador necesita leer ANTES de ajustar, porque ajusta para esa semana.
        "semana_proxima": (data.semana_proxima or "").strip() or None,
        "dieta_dificultad": data.dieta_dificultad,
        "entreno": data.entreno.model_dump() if data.entreno else None,
        "lesiones": [l.model_dump() for l in data.lesiones] if data.lesiones else None,
        "lesion_nueva": (data.lesion_nueva or "").strip() or None,
        "cardio_proximo_mes": data.cardio_proximo_mes,
        "suplementacion": data.suplementacion.model_dump() if data.suplementacion else None,
        "energia_motivo": data.energia_motivo,
        "valoracion_resultado": data.valoracion_resultado,
        "motivacion": data.motivacion,
        # Las del documento «El reporte mensual» (1-09): el compromiso (que habla de él,
        # no del programa), las expectativas de 0 a 10 y las máquinas que no tiene.
        "compromiso": data.compromiso,
        "expectativas": data.expectativas,
        "maquinas_no_disponibles": data.maquinas_no_disponibles or None,
        "ejercicios_molestos": data.ejercicios_molestos or None,
        "suplementacion_motivo": data.suplementacion_motivo,
        "sugerencias": (data.sugerencias or "").strip() or None,
        # Las del 1-09: las cinco estrellas del paso 1 cuando no hay check-in de los que
        # sacar la quincena, y las dos escalas de 0 a 10 del paso 2.
        "dieta_grado": data.dieta_grado,
        "entreno_grado": data.entreno_grado,
        "cardio_grado": data.cardio_grado,
        "suplementacion_grado": data.suplementacion_grado,
        "descanso_grado": data.descanso_grado,
        "sensaciones_0a10": data.sensaciones_0a10,
        "esfuerzo_resultados": data.esfuerzo_resultados,
        "trainer_feedback": None,
        "created_at": creado,
    }
    await db.reports.insert_one(report)
    # Y a las fotos, su reporte (4-09).
    await _atar_fotos_al_reporte(report)

    # El objetivo que marca el cliente MANDA sobre la fase del perfil: es lo que dispara el
    # cambio de fase, y sin esto un Nivel 1 no cambiaria de fase nunca (no tiene coach que se
    # la cambie). `fase_desde` guarda CUANDO empezo, que es lo que necesita el informe para
    # la foto de "inicio de fase".
    # `ultimo_reporte` va aqui a proposito duplicado (punto 29 del 07-08, ver
    # core/seguimiento.py): es lo que deja ordenar la lista de clientes por "quien lleva
    # mas sin que le toquen" sin recorrer los reportes de todos para pintar una tabla.
    # EL DIA DEL REPORTE, EN ESPAÑA (bloque F, 23-08). `created_at[:10]` era el dia UTC
    # del instante: un reporte mandado a las 00:30 de aqui fechaba el pesaje en AYER, y si
    # ese dia ya tenia punto en la serie, lo pisaba.
    from core.tiempo import a_madrid
    try:
        _instante = datetime.fromisoformat(str(report["created_at"]).replace("Z", "+00:00"))
        dia_reporte = (a_madrid(_instante) or _instante).date().isoformat()
    except (ValueError, TypeError):
        dia_reporte = report["created_at"][:10]
    set_perfil = {"ultimo_reporte": dia_reporte}
    # El peso NO se escribe aqui: va a la serie con la fecha del reporte, y el "actual"
    # sale de la serie (punto 30). Es lo que arregla los dos pesos distintos del punto 9.
    #
    # PERO NO PISA UN PESAJE DE VERDAD (fallo 5 del repaso del 24-08). Lo que viene en el
    # reporte no es un pesaje de hoy: es el numero que el cliente escribe para resumir la
    # semana, y casi siempre es la media que le propone la propia app. Como se archivaba con
    # la fecha del documento y `poner_en_serie` sustituye el punto de ese dia, enviar el
    # reporte un VIERNES -- que es cuando abre la ventana del semanal -- borraba el pesaje
    # del viernes: con jueves 80,0 y viernes 82,0 la serie quedaba jueves 80,0 y viernes
    # 81,0, el peso de la semana pasaba de 81,0 a 80,5 y cada reenvio lo movia otra vez.
    # Con `pisa_pesajes=False` el reporte solo escribe si ese dia esta libre (o si el punto
    # lo puso otro reporte, que entonces es una correccion del mismo documento).
    await anotar_peso(profile["id"], data.weight, dia_reporte, origen="reporte",
                      pisa_pesajes=False)
    # Y EL % DE GRASA, cuando toca (cada 12 semanas). Va a su serie igual que el peso, con la
    # fecha del reporte: es un dato que se estima mirando fotos, y sin fecha no hay forma de
    # saber si el que se está usando para calcular macros es de hace un mes o de hace un año.
    if data.body_fat is not None:
        from core.series_cliente import anotar_grasa
        await anotar_grasa(profile["id"], data.body_fat, dia_reporte,
                           origen="reporte")
    if data.proximo_objetivo in ("definicion", "volumen", "mantenimiento"):
        if profile.get("goal") != data.proximo_objetivo:
            set_perfil["goal"] = data.proximo_objetivo
            set_perfil["fase_desde"] = dia_reporte

    # LAS LESIONES SE QUEDAN EN EL PERFIL, NO SOLO EN EL REPORTE (T8, bloque 06).
    # Es lo que hace que el mes que viene salga "LO QUE YA ME CONTASTE" en vez de una
    # hoja en blanco. Las superadas se guardan igual, con su estado: así se sabe que se
    # cerró y no se le vuelve a preguntar (`lesiones_del_perfil` las filtra).
    if data.lesiones is not None:
        set_perfil["lesiones"] = [
            {"zona": l.zona, "desde": l.desde, "estado_mes": l.estado_mes,
             "ejercicios_vetados": l.ejercicios, "actualizado": dia_reporte}
            for l in data.lesiones
        ]

    # LAS MÁQUINAS QUE NO TIENE, TAMBIÉN AL PERFIL, y por el mismo motivo: el documento del
    # 1-09 dice «Actualiza aquí tu listado: si ha entrado alguna nueva, dímelo», y eso solo
    # se puede pedir si el mes que viene sale con lo que dejó puesto. Es un listado, no una
    # respuesta: se pisa entero, porque quitar una máquina es tan válido como añadirla.
    if data.maquinas_no_disponibles is not None:
        set_perfil["maquinas_no_disponibles"] = [
            m.strip() for m in data.maquinas_no_disponibles if str(m).strip()]

    # LOS EJERCICIOS QUE LE MOLESTAN VAN A `injuries`, Y AQUÍ SE CIERRA UN AGUJERO.
    #
    # `injuries` es el campo que lee el generador de rutinas para agrupar, y hasta hoy lo
    # escribía SOLO el cuestionario del alta: lo que el cliente contestaba cada mes se
    # guardaba en `client_profiles.lesiones`, que el generador no mira. O sea que se le
    # preguntaba por sus lesiones todos los meses y esa respuesta no llegaba nunca a su
    # rutina. La pregunta 5 del documento del 1-09 pide justo la lista que ese campo
    # necesita, así que al hacerla como él la pide se arregla solo.
    #
    # Se pisa entera, como las máquinas: quitar un ejercicio de la lista es tan válido como
    # añadirlo, y ese es el sentido de «quita los que ya no».
    if data.ejercicios_molestos is not None:
        set_perfil["injuries"] = [
            e.strip() for e in data.ejercicios_molestos if str(e).strip()]
    await db.client_profiles.update_one({"id": profile["id"]}, {"$set": set_perfil})
    # Y el perfil que se lleva el informe es el de DESPUÉS: si acaba de cambiar de fase,
    # la foto de "inicio de fase" es la de ahora, no la de la fase que deja atrás.
    profile.update(set_perfil)

    # El aplazamiento se cierra al mandarlo: si ya está el reporte, no hay nada que correr.
    # Y el contador de seguidos vuelve a cero: mandar un reporte corta la racha (doc 19-08).
    await db.client_profiles.update_one(
        {"id": profile["id"]},
        {"$unset": {"reporte_aplazado_hasta": "", "reporte_aplazado_tipo": "",
                    "reporte_aplazado_nota": ""},
         "$set": {"aplazamientos_seguidos": 0}})

    await _avisar_de_lo_que_pidio(profile, user, data, report_id)

    # LA TAREA DEL EVENTO (doc 19-08, apartado 05): «un cliente manda su reporte →
    # Reporte nuevo de Nuria Garrido → su entrenador». Cae en su lista de hoy.
    try:
        from core.tareas_automaticas import tarea_reporte_nuevo
        await tarea_reporte_nuevo(db, client_id=profile["id"],
                                  nombre=user.get("name") or "cliente",
                                  trainer_id=profile.get("trainer_id"))
    except Exception:
        pass    # quedarse sin la tarea no puede tumbar el envío del reporte

    # EL INFORME SE GENERA AL ENVIAR (T9). Hasta ahora se montaba al vuelo cada vez que
    # alguien abría la pantalla, así que no existía como cosa: no se podía revisar, ni
    # tenía estado, ni había nada que publicar. Se guarda con `pendiente_revision` y no
    # sale hasta que el coach lo publica.
    #
    # Solo con el MENSUAL: el informe es del mes -- compara fotos, medidas y el ritmo de
    # cuatro semanas -- y en el quincenal no hay nada nuevo que comparar. Generarlo
    # también allí solo serviría para dejar el informe del mes escondido detrás de un
    # "pendiente de revisión" que nadie ha prometido.
    #
    # "Sin fotos no hay informe" sigue mandando: si no las subió, `montar_informe`
    # devuelve `generado: False` y eso es lo que se guarda -- el equipo lo ve al abrirlo
    # y sabe por qué no hay informe que revisar.
    if report.get("tipo") == "mensual":
        try:
            informe = await _montar_informe_del_reporte(report, profile)
            await db.reports.update_one(
                {"id": report_id},
                {"$set": {"informe": informe, "informe_estado": "pendiente_revision",
                          "informe_generado_at": datetime.now(timezone.utc).isoformat()}},
            )
            report["informe_estado"] = "pendiente_revision"
        except Exception as e:      # noqa: BLE001
            # Un informe que no se puede montar no puede tumbar el envío del reporte: lo
            # que no se puede perder es lo que ha escrito el cliente. El detalle, a la
            # consola del servidor.
            print(f"[reportes] no se pudo montar el informe de {report_id}: {e}")

    # LO QUE SE LE PROMETE AL TERMINAR, QUE NO ES IGUAL PARA TODOS (T9).
    #
    # Quien lleva alguien detrás recibe el informe completo con su feedback, y eso tarda
    # hasta el sábado; el resto recibe sus ajustes, y esos están el viernes. Los dos
    # textos son los del doc, literales, y los pinta la pantalla de "enviado".
    #
    # En el QUINCENAL se promete lo mismo a todos -- ajustes -- porque el informe es del
    # mes: prometerle el sábado un informe completo por un reporte de dos semanas sería
    # prometer algo que no llega (regla 4 del doc: nunca prometer lo que no se sabe).
    hab = await _habilitaciones_de(profile)
    lleva_feedback = "quincenal" in (hab.get("reportes") or [])
    respuesta = ReportResponse(**report).model_dump()
    respuesta["lleva_feedback"] = lleva_feedback
    # En el SEMANAL el feedback es PARA LA SEMANA SIGUIENTE (doc 21-08): el entrenador
    # tiene hasta el domingo a las 10:00, el cliente lo lee el domingo y el lunes empieza
    # sabiendo qué cambia. Prometerle aquí «antes del viernes» era prometerle una fecha
    # que ya había pasado: el semanal se manda el viernes o el sábado.
    respuesta["mensaje_envio"] = (
        "El domingo tienes mi feedback: empiezas el lunes sabiendo qué cambia. Te aviso por aquí."
        if report.get("tipo") == "semanal" else
        "Antes del sábado tienes tu informe completo con mi feedback y tus ajustes. Te aviso por aquí."
        if lleva_feedback and report.get("tipo") == "mensual" else
        "Antes del viernes tienes tus ajustes nuevos. Te aviso por aquí.")
    # EL DÍA, SUELTO, PARA EL PASO 4 DEL MENSUAL (documento del 1-09). Esa pantalla lo
    # necesita dos veces: en el rótulo («ANTES DEL PRÓXIMO SÁBADO») y en la línea del
    # final. Sale de aquí y no se deduce del mensaje para que las tres frases no puedan
    # decir días distintos: la promesa se escribe en un solo sitio.
    respuesta["promesa_dia"] = (
        "domingo" if report.get("tipo") == "semanal" else
        "sábado" if lleva_feedback and report.get("tipo") == "mensual" else
        "viernes")
    return respuesta


async def _avisar_de_lo_que_pidio(profile: dict, user: dict, data: ReportCreate,
                                  report_id: str) -> None:
    """Lo que el cliente pide EN el reporte y alguien tiene que atender (T8, bloque 05).

    Son dos cosas y las dos son del plan sin rutina: la rutina del mes y el interés por
    el plan de arriba. Van a la campana del equipo porque no las resuelve la app: alguien
    tiene que montarle la rutina y alguien tiene que llamarle.

    La rutina, además, SE COBRA: "al marcar «Sí» autorizas el cargo en tu tarjeta". El cobro
    va en `core/rutina_del_mes.py` y nunca levanta: si no entra, el reporte se manda igual y
    el aviso del equipo dice por qué, para que nadie se quede con una rutina sin pagar sin
    que conste.
    """
    entreno = data.entreno
    if not entreno:
        return
    from core.avisos_equipo import avisar_al_equipo

    nombre = user.get("name") or user.get("email") or "Un cliente"
    if entreno.rutina_del_mes in ("basica", "avanzada", "ahora_no"):
        # Contestó de verdad (sí o no): si venía de un «pregúntame en una semana», ese
        # recordatorio ya no tiene sentido.
        await db.client_profiles.update_one(
            {"id": profile["id"]}, {"$unset": {"rutina_mes_aplazada_hasta": ""}})
    if entreno.rutina_del_mes in ("basica", "avanzada"):
        modalidad = "básica" if entreno.rutina_del_mes == "basica" else "avanzada"
        # «Al marcar «Sí» autorizas el cargo en tu tarjeta»: se le cobra en la que ya tiene
        # guardada. Si no se puede, el reporte se manda igual y el equipo se entera de por
        # qué; lo que no se hace es dejar la petición sin cobrar y sin decirlo.
        from core.rutina_del_mes import PRECIO_EUR, cobrar
        cobro = await cobrar(profile, entreno.rutina_del_mes, report_id)

        # SI HAY ALGO PREPARADO, SE LE ENTREGA AQUÍ MISMO (verificación 24-08, fallo 14).
        #
        # Este camino solo cobraba y avisaba al equipo para que se la mandara a mano, porque
        # cuando se escribió (19-08) no existía «la rutina del mes vigente»: no había nada que
        # entregar. Desde el 24-08 sí lo hay -- una plantilla marcada o el PDF del mes -- y la
        # otra puerta, el botón de la pantalla de Rutina, ya la entrega sola. Que el mismo
        # producto llegue solo o a mano según por dónde lo pidas no tiene defensa.
        #
        # Si no hay nada preparado NO se deja de cobrar, y es deliberado: aquí el cliente ya ha
        # dicho que sí dentro de su reporte y el circuito manual existe desde el principio. Lo
        # que no puede pasar es que nadie se entere, así que el aviso lo dice con todas las
        # letras y por eso se lee distinto según haya llegado o no.
        entregada = None
        if cobro["cobrado"]:
            from core.rutina_del_mes import _entregarsela
            entregada = await _entregarsela(profile.get("id"))

        if cobro["cobrado"] and entregada:
            estado = f"Cobrados {PRECIO_EUR:.0f} € en su tarjeta y ya la tiene puesta ({entregada})."
        elif cobro["cobrado"]:
            estado = (f"Cobrados {PRECIO_EUR:.0f} € en su tarjeta. NO HAY NADA PREPARADO este mes: "
                      "hay que montársela y mandársela a mano.")
        else:
            porques = {
                "sin_tarjeta": "no tiene tarjeta guardada",
                "requiere_autenticacion": "su banco pide que lo confirme él",
                "rechazada": "la tarjeta la rechazó",
                "sin_stripe": "los pagos no están configurados en este entorno",
            }
            estado = ("SIN COBRAR: " + porques.get(cobro.get("motivo"), str(cobro.get("motivo")))
                      + ". Hay que cobrárselo a mano.")

        await avisar_al_equipo(
            db, tipo="rutina_del_mes",
            titulo="Quiere la rutina del mes",
            mensaje=f"{nombre} ha marcado la rutina del mes en modalidad {modalidad} "
                    f"({PRECIO_EUR:.0f} €) en su reporte. {estado}",
            client_id=profile["id"], trainer_id=profile.get("trainer_id"),
            extra={"modalidad": entreno.rutina_del_mes, "cobrado": cobro["cobrado"],
                   "motivo": cobro.get("motivo"), "payment_intent": cobro.get("payment_intent"),
                   # `entregada` es el nombre de lo que se le ha puesto, o None si no había
                   # nada preparado y se la tiene que mandar alguien. Lo que decide si esta
                   # fila es trabajo pendiente para el equipo o solo una venta apuntada.
                   "entregada": entregada,
                   "importe_eur": PRECIO_EUR},
        )
    if entreno.rutina_del_mes == "aplazar_una_semana":
        # LA APLAZÓ MARCÁNDOLO (doc 19-08): ni sí ni no, «pregúntamelo en una semana». Se
        # apunta la fecha en su ficha -- de ella sale el aviso del cliente a los 7 días --
        # y el equipo se entera para no darle caza antes de tiempo.
        en_una_semana = (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat()
        await db.client_profiles.update_one(
            {"id": profile["id"]},
            {"$set": {"rutina_mes_aplazada_hasta": en_una_semana}})
        await avisar_al_equipo(
            db, tipo="rutina_del_mes",
            titulo="Aplazó la rutina del mes",
            mensaje=f"{nombre} ha marcado «pregúntame en una semana» para la rutina del mes. "
                    f"Se le recuerda solo el {en_una_semana}.",
            client_id=profile["id"], trainer_id=profile.get("trainer_id"),
            extra={"modalidad": "aplazar_una_semana", "recordar_el": en_una_semana},
        )
    if entreno.quiere_saber_del_silver:
        await avisar_al_equipo(
            db, tipo="interes_plan",
            titulo="Quiere que le cuentes el plan de arriba",
            mensaje=f"{nombre} ha marcado «Cuéntame el Silver» en su reporte mensual.",
            client_id=profile["id"], trainer_id=profile.get("trainer_id"),
        )

@admin_router.post("/clients/{client_id}/reporte", response_model=ReportResponse)
async def crear_reporte_por_el_cliente(client_id: str, data: ReportCreate,
                                       user=Depends(get_admin_user)):
    """El equipo mete un reporte EN NOMBRE de un cliente (punto 45 del doc del 07-08).

    Los Premium no rellenan el formulario: mandan el reporte y las fotos por WhatsApp y
    alguien del equipo se lo pasa a la app. Hasta ahora eso no se podia hacer, asi que o se
    entraba con su cuenta o el reporte se quedaba fuera -- y lo que se queda fuera no
    alimenta ni la curva de peso ni el modelo.

    A diferencia del reporte del cliente, aqui NO se comprueba la ventana de envio ni que
    el plan incluya reportes: si el equipo lo esta metiendo es porque ya llego por otro
    lado, y bloquearlo por el calendario no protege nada. Queda marcado con quien lo metio,
    que es lo que hay que poder mirar despues.
    """
    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)

    creado = datetime.now(timezone.utc).isoformat()
    # LA MISMA COSTURA QUE EN LA VÍA DEL CLIENTE (4-09). Aquí no hay ventana: si el body no
    # trae fotos, se cogen las del cliente que todavía no son de ningún reporte y sin `uso`,
    # subidas en los DIAS_DE_FOTOS_PARA_EL_EQUIPO anteriores al reporte (el equipo sube por
    # WhatsApp y pasa el reporte días después), las más antiguas primero y hasta el tope.
    fotos = [f for f in (data.photos or []) if f]
    if not fotos:
        desde = (datetime.fromisoformat(creado)
                 - timedelta(days=DIAS_DE_FOTOS_PARA_EL_EQUIPO)).isoformat()
        fotos = await _fotos_sueltas_de(client_id, desde=desde, hasta=creado)
    # El día del reporte es el de `created_at`: el equipo no pasa otra fecha (es la misma
    # que abajo se convierte en `dia_reporte` para la serie de peso).
    ciclo = await _ciclo_del_reporte(profile, creado)

    report = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        # De qué ciclo, semana y bloque es (ver CAMPOS_CICLO arriba; 4-09).
        "ciclo_id": ciclo.get("ciclo_id"),
        "ciclo_numero": ciclo.get("ciclo_numero"),
        "ciclo_inicio": ciclo.get("ciclo_inicio"),
        "semana_del_ciclo": ciclo.get("semana_del_ciclo"),
        "bloque": ciclo.get("bloque"),
        "weight": data.weight,
        "measurements": data.measurements,
        "photos": fotos or None,
        "training_compliance": data.training_compliance,
        "nutrition_compliance": data.nutrition_compliance,
        "sleep_quality": data.sleep_quality,
        "energy_level": data.energy_level,
        "stress_level": data.stress_level,
        "notes": data.notes,
        "proximo_objetivo": data.proximo_objetivo,
        "viabilidad_ajuste": data.viabilidad_ajuste,
        "cumplimiento_entreno": data.cumplimiento_entreno,
        "trainer_feedback": None,
        # De quien es el reporte de verdad: lo mando el cliente por otra via y lo paso el
        # equipo. Sin esta marca, dentro de tres meses nadie sabe por que este reporte
        # aparecio fuera de su ventana.
        "metido_por": user.get("name", user.get("email", "equipo")),
        "origen": "lo metio el equipo",
        "created_at": creado,
    }
    await db.reports.insert_one(report)
    # Y a las fotos, su reporte (4-09), igual que en la vía del cliente.
    await _atar_fotos_al_reporte(report)

    # El dia en España, no el UTC del instante (bloque F, 23-08; igual que en la via del
    # cliente).
    from core.tiempo import a_madrid
    try:
        _instante = datetime.fromisoformat(str(report["created_at"]).replace("Z", "+00:00"))
        dia_reporte = (a_madrid(_instante) or _instante).date().isoformat()
    except (ValueError, TypeError):
        dia_reporte = str(report["created_at"])[:10]
    set_perfil = {"ultimo_reporte": dia_reporte}
    if data.proximo_objetivo in ("definicion", "volumen", "mantenimiento"):
        if profile.get("goal") != data.proximo_objetivo:
            set_perfil["goal"] = data.proximo_objetivo
            set_perfil["fase_desde"] = dia_reporte
    await db.client_profiles.update_one({"id": client_id}, {"$set": set_perfil})
    # El peso, a su serie con la fecha del reporte (punto 30), y sin pisar un pesaje de
    # verdad de ese dia: mismo motivo que en la via del cliente (fallo 5 del 24-08), y aqui
    # mas todavia, porque el equipo pasa a la app un reporte que el Premium mando por
    # WhatsApp dias antes.
    await anotar_peso(client_id, data.weight, dia_reporte,
                      origen="reporte (lo metió el equipo)", pisa_pesajes=False)

    # EL INFORME TAMBIÉN POR ESTA VÍA (punto 41 del doc del 23-08): los Premium mandan
    # por WhatsApp, el equipo lo pasa a la app, y como el informe solo se generaba en el
    # envío del cliente, los Premium no tenían informe NUNCA. Se genera igual que allí y
    # queda `pendiente_revision` para que el coach lo publique. Sin la marca de tipo:
    # esta vía no la trae, y lo que pasa el equipo es el reporte del mes.
    try:
        informe = await _montar_informe_del_reporte(report, profile)
        await db.reports.update_one(
            {"id": report["id"]},
            {"$set": {"informe": informe, "informe_estado": "pendiente_revision",
                      "informe_generado_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as e:      # noqa: BLE001 - el reporte metido no se puede perder
        print(f"[reportes] no se pudo montar el informe (vía equipo) de {report['id']}: {e}")

    return ReportResponse(**report)


@router.get("", response_model=List[ReportResponse])
async def get_reports(skip: int = 0, limit: int = 50, user = Depends(get_current_user)):
    """Obtener reportes del cliente (paginado con skip/limit para 'cargar más')."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    # HASTA HOY (punto 22): el historial empezaba por un reporte de noviembre de este año.
    # Son 31 reportes fechados por delante de hoy, casi todos de la importacion de Calma.
    reports = await db.reports.find(
        hasta_hoy({"client_id": profile["id"]}),
        {"_id": 0}
    ).sort("created_at", -1).skip(max(0, skip)).to_list(min(max(1, limit), 100))

    return [ReportResponse(**r) for r in reports]

@router.get("/previous")
async def get_previous_report(user = Depends(get_current_user)):
    """Último reporte del cliente (peso + medidas + fecha), como referencia al rellenar
    el nuevo (tarea 12: medidas con referencia del mes anterior)."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    # Hasta HOY: en producción hay reportes fechados en 2027 y 2028, y ordenando por fecha
    # a secas ganaba uno de esos. Esta pantalla enseñaba «Último: 118 kg · 21 feb» -- de un
    # reporte de 2028 -- mientras Ajustar macros decía 94 kg, que es el punto 9 del
    # documento del 07-08: dos pesos distintos en la misma app.
    hoy = datetime.now(timezone.utc).isoformat()
    prev = await db.reports.find_one(
        {"client_id": profile["id"], "created_at": {"$lte": hoy}},
        {"_id": 0, "weight": 1, "measurements": 1, "created_at": 1},
        sort=[("created_at", -1)],
    )
    return prev or {}


@router.get("/confirmacion-huecos")
async def get_confirmacion_huecos(user = Depends(get_current_user)):
    """Lo que se le pregunta ANTES de rellenar el reporte (documento, partes 6 y 7).

    Sustituye a los deslizadores de cumplimiento: en vez de pedirle que se puntúe, se le
    enseñan los días que no registró y se le pregunta si es que no lo hizo o que no lo
    apuntó. El cumplimiento sale de ahí.
    """
    from core.confirmacion_huecos import huecos_del_periodo

    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    # Desde el reporte anterior hasta hoy: es el periodo del que se le pregunta.
    # Con hasta_hoy (punto 22): un reporte importado con fecha de 2027 ganaba el sort y
    # ponia el inicio del periodo en el futuro, o sea un periodo negativo.
    prev = await db.reports.find_one(
        hasta_hoy({"client_id": profile["id"]}), {"_id": 0, "created_at": 1}, sort=[("created_at", -1)]
    )
    hasta = datetime.now(timezone.utc)
    desde = hasta - timedelta(days=28)
    if prev and prev.get("created_at"):
        try:
            desde = datetime.fromisoformat(str(prev["created_at"]).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    # EL PERIODO NO PUEDE EMPEZAR ANTES DE QUE TUVIERA LA APP (punto 4.18). Sin esto, a
    # alguien que acaba de entrar se le preguntaba por los 28 dias anteriores y lo primero
    # que leia era «No registraste la dieta 37 dias de los ultimos 38». No es un fallo de
    # redaccion: es que se le esta pidiendo cuentas de un mes en el que no era cliente.
    arranque = profile.get("arranque_lunes") or profile.get("created_at")
    if arranque:
        try:
            d = datetime.fromisoformat(str(arranque).replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            desde = max(desde, d)
        except (ValueError, TypeError):
            pass

    dias_periodo, dias_dieta, dias_entreno, _ = await _actividad_del_periodo(
        profile, desde.isoformat(), hasta.isoformat()
    )

    # Entrenos que TOCABAN: los días de entreno por semana del perfil, prorrateados. Sin
    # ese dato no se pregunta por el entrenamiento (lo dice el módulo, no se fuerza aquí).
    por_semana = profile.get("training_days") or profile.get("dias_entreno")
    previstos = round(float(por_semana) * dias_periodo / 7) if por_semana else None

    return huecos_del_periodo(dias_periodo, dias_dieta, dias_entreno, previstos)


# ════════════════════════════════════════════════════════════════════════════
# EL FORMULARIO (T7 y T8): qué le toca rellenar y con qué datos delante
# ════════════════════════════════════════════════════════════════════════════

async def _habilitaciones_de(perfil: dict) -> dict:
    """Las habilitaciones vivas de su plan (las del catálogo con lo editado en el panel)."""
    from routes.plans import _overrides_by_code
    from models.user import codigo_de_plan, merged_catalog
    catalogo = merged_catalog(await _overrides_by_code())
    return (catalogo.get(codigo_de_plan(perfil.get("plan"))) or {}).get("habilitaciones") or {}


def _periodo_del_reporte(perfil: dict, tipo: str):
    """(desde, hasta) del periodo del que habla el reporte, en días de España."""
    hasta = hoy_madrid()
    desde = hasta - timedelta(days=DIAS_DEL_PERIODO.get(tipo, 28) - 1)
    arranque = perfil.get("arranque_lunes") or perfil.get("created_at")
    if arranque:
        try:
            d = datetime.fromisoformat(str(arranque).replace("Z", "+00:00")).date()
            desde = max(desde, d)
        except (ValueError, TypeError):
            pass
    return desde, hasta


def bloques_del_rapido(tiene_rutina: bool, semanal: bool = False) -> list:
    """Los bloques del formulario corto (quincenal, semanal y el mensual «rápido»).

    SE MIRA EL DATO, NO EL PLAN, como en el mensual: sin rutina cargada no hay
    ejercicios por los que preguntar molestias ni entrenos previos que confirmar, así
    que esos dos bloques no salen y los demás se renumeran solos. Hasta ahora la lista
    era fija y al cliente sin rutina se le preguntaba por las molestias «de la rutina».

    `semanal` añade la cuarta pregunta del doc del 21-08 (apartado 15): «¿Hay algo la
    semana que viene que te altere la rutina?». Solo en esa cadencia: el quincenal y el
    mensual no la llevan, porque su ajuste no es para la semana que entra.
    """
    base = (["peso", "sensaciones", "libre"] if not tiene_rutina
            else ["entreno_previo", "peso", "molestias", "sensaciones", "libre"])
    if semanal:
        base = base + ["semana_proxima"]
    return base


@router.get("/formulario")
async def get_formulario_del_reporte(tipo: Optional[str] = None, user=Depends(get_current_user)):
    """TODO lo que el formulario necesita antes de preguntar nada (doc 16-08, T7 y T8).

    Devuelve qué reporte toca, qué bloques lleva ESE cliente y los datos que la app ya
    sabe: los días que registró la dieta, los entrenos que hizo de los que tenía, su
    energía, sus lesiones y su último peso. La regla 5 del doc, entera: "si la app ya
    sabe algo, se lo dice; solo se pregunta lo que no se puede saber".

    `tipo` solo se acepta para poder repasar el formulario fuera de su semana (modo
    revisión del equipo); si no viene, manda el calendario.
    """
    from core.datos_reporte import bloques_del_mensual, datos_del_reporte, perfil_de_reporte

    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    hab = await _habilitaciones_de(perfil)
    reportes = hab.get("reportes") or []
    if tipo not in ("quincenal", "mensual", "semanal"):
        from routes.report_cadence import compute_client_report_state, rutina_activa_de
        from routes.plans import _overrides_by_code
        from models.user import merged_catalog
        estado = compute_client_report_state(
            perfil, merged_catalog(await _overrides_by_code()), datetime.now(timezone.utc),
            rutina=await rutina_activa_de(perfil.get("id")))
        tipo = (estado["tipos"] or ["mensual"])[0]

    perfil_rep = perfil_de_reporte(hab)
    d0, d1 = _periodo_del_reporte(perfil, tipo)
    datos = await datos_del_reporte(perfil, tipo, d0, d1)

    # EL % DE GRASA, CADA DOCE SEMANAS. Lo promete el pie de la pantalla donde se lo pide la
    # primera vez, y no había ningún sitio donde se le volviera a preguntar: el dato se
    # quedaba con la edad que tuviera. La regla de las doce semanas ya existía y ya se sabe
    # calcular; lo que faltaba era el sitio donde preguntarlo.
    from core.series_cliente import grasa_vigente
    grasa = grasa_vigente(perfil)
    # «EL RÁPIDO, MENSUAL» (tabla del bloque 11, doc 19-08): en la Calculadora (y en ELM
    # si algún día su calendario trae reporte) la cadencia es la del mensual pero el
    # formulario es el corto de cuatro preguntas, el mismo del quincenal.
    forma_rapida = bool(hab.get("reporte_rapido")) and tipo == "mensual"
    bloques = bloques_del_mensual(perfil_rep, pedir_grasa=bool(grasa.get("hay_que_pedirlo"))) \
        if tipo == "mensual" and not forma_rapida else \
        bloques_del_rapido(bool((datos.get("entreno") or {}).get("tiene_rutina")),
                           semanal=(tipo == "semanal"))
    datos["grasa"] = grasa
    # SE MIRA EL DATO, NO EL PLAN (regla 3 del doc): sin rutina cargada, el bloque del
    # entreno no tiene ni dato que enseñar ni pregunta que hacer, así que no sale y los de
    # abajo se renumeran solos. El del plan sin rutina SÍ se queda: ahí ese bloque no
    # habla de lo que entrenó, es donde va la rutina del mes.
    if (tipo == "mensual" and perfil_rep != "sin_rutina"
            and not (datos.get("entreno") or {}).get("tiene_rutina")):
        bloques = [b for b in bloques if b != "entreno"]
    # LA ENERGÍA SOLO SI LA LLEVA BAJA ("si va bien, no aparece"). Se quita de la lista y
    # no solo de la pantalla para que los bloques de abajo se renumeren: un reporte que
    # salta del 06 al 08 parece que se ha perdido algo por el camino.
    if tipo == "mensual" and not (datos.get("cierres") or {}).get("energia_baja"):
        bloques = [b for b in bloques if b != "energia"]

    return {
        "tipo": tipo,
        # Cuál de los tres mensuales le toca: completo / con_rutina / sin_rutina.
        "perfil": perfil_rep,
        # «rapido» cuando el mensual va con el formulario corto (Calculadora, ELM).
        "forma": "rapido" if forma_rapida else None,
        "bloques": bloques,
        # Si su plan lleva alguien detrás que le escriba el informe. De esto depende lo
        # que se le promete al enviar: ajustes (viernes) o informe con feedback (sábado).
        "lleva_feedback": "quincenal" in reportes,
        "datos": datos,
        # Si ya lo aplazó este mes, para que la casilla salga marcada y no lo aplace dos veces.
        "aplazado_hasta": perfil.get("reporte_aplazado_hasta"),
    }


@router.get("/mensual/paso1")
async def get_paso1_del_mensual(periodo: str = "ultimo", user=Depends(get_current_user)):
    """EL PASO 1 DEL MENSUAL, con su selector de periodo (documento del 1-09).

    «El selector de arriba cambia el bloque entero, no solo el peso.» Por eso esto es una
    ruta propia y no un trozo de `/formulario`: el cliente lo cambia con el reporte ya
    abierto y tiene que volver el peso, la actividad y las sensaciones del otro tramo.

    `periodo`:
      - `ultimo`    los 28 días del mensual («Desde tu último reporte»).
      - `principio` desde que arrancó («Desde que empezaste»).

    Los huecos solo viajan en `ultimo`: son siempre de los últimos 28 y no cambian al
    mirar el programa entero.

    Y SU OTRA VERSIÓN, la del que no tiene check-in con los que llenar el paso: «El paso 1
    se acorta, igual que en el quincenal. El peso y las fotos se le piden igual, que ésos no
    dependen de haber apuntado nada.» Lo dicen `sin_datos` y `preguntas`.
    """
    from core.actividad_mensual import hay_datos_suficientes, preguntas_sin_checkin
    from core.datos_reporte import datos_del_paso1
    from core.plan_access import plan_grants_feature

    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    desde_el_principio = periodo == "principio"
    if desde_el_principio:
        d1 = hoy_madrid()
        # El arranque, con el mismo criterio que el resto: sin él no hay «desde que
        # empezaste» que valga y se cae al mes de siempre en vez de inventarse una fecha.
        d0 = d1 - timedelta(days=DIAS_DEL_PERIODO["mensual"] - 1)
        arranque = perfil.get("arranque_lunes") or perfil.get("created_at")
        if arranque:
            try:
                d0 = min(d0, datetime.fromisoformat(str(arranque).replace("Z", "+00:00")).date())
            except (ValueError, TypeError):
                pass
    else:
        d0, d1 = _periodo_del_reporte(perfil, "mensual")

    ficha = await datos_del_paso1(perfil, d0, d1, desde_el_principio=desde_el_principio)

    # ¿HAY CON QUÉ LLENARLO? Se mide SIEMPRE contra los últimos 28, también cuando se está
    # mirando el programa entero: la pregunta es «¿tengo sus check-in de este mes?», y en
    # «desde que empezaste» la respuesta no puede cambiar solo porque se mire más atrás.
    corto = (d0, d1) if not desde_el_principio else _periodo_del_reporte(perfil, "mensual")
    cierres = await db.checkins.count_documents(
        {"client_id": perfil.get("id"), "type": "daily",
         "created_at": {"$gte": corto[0].isoformat(), "$lte": corto[1].isoformat() + "T23:59:59"}})
    hay_datos = hay_datos_suficientes(cierres, (corto[1] - corto[0]).days + 1)
    return {
        **ficha,
        "sin_datos": not hay_datos,
        "preguntas": [] if hay_datos else preguntas_sin_checkin(
            plan_grants_feature(perfil.get("plan"), "suplementacion")),
    }


@router.get("/quincenal/paso1")
async def get_paso1_del_quincenal(dia: Optional[str] = None, user=Depends(get_current_user)):
    """EL PASO 1 DEL QUINCENAL («Todo lo validado antes del 1 de septiembre»).

    Es el mismo paso que el del mensual -- lo que ha hecho, cómo se ha sentido y los huecos
    -- con dos diferencias, y las dos son del documento:

      - EL PESO ES EL SEMANAL, no la curva del mes. Los tres días en los que se puede pesar
        con la pareja marcada, que es lo que hace que el número de arriba se entienda.
      - SIN SELECTOR DE PERIODO. «Desde que empezaste» es del mensual: en quince días no hay
        dos tramos que comparar.

    Y LA OTRA VERSIÓN: al que no tiene check-in suficientes no se le enseña nada, se le
    pregunta. `sin_datos` lo dice y `preguntas` trae las cinco.

    `dia` ES DEL MODO REVISIÓN Y SOLO DEL EQUIPO. La semana del peso es la del día en que se
    abre el reporte, así que en martes esta pantalla no puede enseñar una pareja: el
    miércoles todavía no ha pasado. Con `?dia=` el equipo la mira en la semana que quiera y
    comprueba los textos, que es para lo que existe `?ver=` en la app. A un cliente se le
    ignora: su semana es la suya.
    """
    from core.actividad_mensual import hay_datos_suficientes, preguntas_sin_checkin
    from core.datos_reporte import datos_del_paso1, peso_semanal_por_dias
    from core.plan_access import plan_grants_feature

    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    d0, d1 = _periodo_del_reporte(perfil, "quincenal")
    if dia and user.get("role") in ("admin", "trainer"):
        try:
            d1 = date.fromisoformat(dia[:10])
            d0 = d1 - timedelta(days=DIAS_DEL_PERIODO["quincenal"] - 1)
        except (ValueError, TypeError):
            pass
    ficha = await datos_del_paso1(perfil, d0, d1)
    tiene_suplementacion = plan_grants_feature(perfil.get("plan"), "suplementacion")

    # Los cierres del tramo, para saber si hay con qué llenar el paso. Se cuentan aquí y no
    # dentro de `datos_del_paso1` porque es una decisión del quincenal: el mensual enseña
    # sus datos aunque estén flojos, que para eso tiene 28 días y las fotos.
    cierres = await db.checkins.count_documents(
        {"client_id": perfil.get("id"), "type": "daily",
         "created_at": {"$gte": d0.isoformat(), "$lte": d1.isoformat() + "T23:59:59"}})
    hay_datos = hay_datos_suficientes(cierres, ficha["periodo"]["dias"])

    return {
        **ficha,
        "peso_semanal": peso_semanal_por_dias(perfil, d1),
        "sin_datos": not hay_datos,
        "preguntas": [] if hay_datos else preguntas_sin_checkin(tiene_suplementacion),
    }


@router.post("/aplazar")
async def aplazar_reporte(payload: Optional[Dict[str, Any]] = Body(default=None),
                          user=Depends(get_current_user)):
    """«No puedo esta semana» (doc 19-08). Con una línea opcional -- «¿Quieres decirme
    algo?» -- que viaja al panel de su entrenador junto al aplazamiento.

    Guarda hasta cuándo se le corre la ventana en su perfil y deja el aviso de
    confirmación. La ventana de envío la sigue mandando `report_cadence`, que es quien
    tiene que leer este campo: aquí solo se escribe.

    Lo pide él, no se deduce de que no conteste un correo: es la diferencia entre
    organizarse y quedarse fuera.
    """
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    from routes.report_cadence import compute_client_report_state, rutina_activa_de
    from routes.plans import _overrides_by_code
    from models.user import merged_catalog

    ahora = datetime.now(timezone.utc)
    estado = compute_client_report_state(
        perfil, merged_catalog(await _overrides_by_code()), ahora,
        rutina=await rutina_activa_de(perfil.get("id")))
    if not estado["due"]:
        raise HTTPException(status_code=403,
                            detail="Esta semana no te toca reporte, así que no hay nada que aplazar.")

    # Siete días desde el cierre de SU ventana, no desde hoy: aplazarlo el viernes y
    # aplazarlo el domingo tienen que dejarle el mismo plazo nuevo.
    hasta = estado["window_close"] + timedelta(days=7)
    nota = str((payload or {}).get("nota") or "").strip()[:500]
    ya_aplazado = perfil.get("reporte_aplazado_hasta")
    if ya_aplazado and str(ya_aplazado) >= hasta.isoformat():
        # Ya lo aplazó: se le contesta con lo que tiene, sin correrle la fecha otra vez.
        # La nota sí se guarda si trae una y aún no había: pulsar otra vez para añadir
        # el «¿quieres decirme algo?» no puede perderse por llegar segundo.
        hasta = datetime.fromisoformat(str(ya_aplazado).replace("Z", "+00:00"))
        if nota and not perfil.get("reporte_aplazado_nota"):
            await db.client_profiles.update_one(
                {"id": perfil["id"]}, {"$set": {"reporte_aplazado_nota": nota}})
    else:
        await db.client_profiles.update_one(
            {"id": perfil["id"]},
            {"$set": {"reporte_aplazado_hasta": hasta.isoformat(),
                      # Lo que haya querido decir, para el panel; vacía si no dijo nada,
                      # que no quede la nota del aplazamiento anterior.
                      "reporte_aplazado_nota": nota,
                      # QUÉ reporte se aplazó, no solo hasta cuándo: la semana que viene
                      # puede que no le toque ninguno, y sin esto la ventana ampliada no
                      # sabría de qué reporte está hablando.
                      "reporte_aplazado_tipo": (estado["tipos"] or [None])[0],
                      "reporte_aplazado_at": ahora.isoformat()},
             # Y CUÁNTOS SEGUIDOS LLEVA (doc 19-08, tareas automáticas): «dos aplazamientos
             # seguidos ya no es un imprevisto». Lo resetea mandar un reporte de verdad.
             "$inc": {"aplazamientos_seguidos": 1}},
        )

    # El aviso de confirmación del doc (T10, "el de confirmación"). El texto no se escribe
    # aquí: vive con los demás, que es lo que evita dos redacciones de la misma frase.
    from routes.notifications import avisar_reporte_aplazado
    await avisar_reporte_aplazado(user["id"])

    local = a_madrid(hasta)
    return {
        "ok": True,
        "hasta": hasta.isoformat(),
        "hasta_label": f"{local.day} de {_MESES_LARGOS[local.month - 1]}" if local else None,
        "titulo": "Te lo he aplazado 7 días",
        "mensaje": "Tu reporte se vuelve a abrir el viernes que viene. Sigue registrando como siempre.",
    }


_MESES_LARGOS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                 "septiembre", "octubre", "noviembre", "diciembre")


@router.get("/evolution")
async def get_evolution_data(user = Depends(get_current_user)):
    """Obtener datos de evolución para gráficos."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    # La grafica tampoco: un peso de 2028 estiraba el eje y aplastaba el resto de la curva.
    reports = await db.reports.find(
        hasta_hoy({"client_id": profile["id"]}),
        {"_id": 0, "weight": 1, "measurements": 1, "created_at": 1}
    ).sort("created_at", 1).to_list(100)

    # EL PESO SALE DE LA SERIE, NO DE LOS REPORTES (punto 4 del documento del 17-08).
    #
    # Esto cogia el `weight` de cada reporte en crudo y cortaba a cien. «Mis macros» pinta la
    # MISMA grafica con otra cosa: la serie `pesos` del perfil, saneada, y ademas con los
    # pesajes que viajaron en los ajustes viejos. Resultado en produccion el 17-08, mismo
    # cliente y mismo dia: «Ahora 77,1 kg · +2,1 kg · 106 pesajes» en Mis macros y «Ahora
    # 50 kg · -25 kg · 100 pesajes» en Evolucion. Lo contrario, con la misma grafica.
    #
    # El documento proponia quitar la de Mis macros. Es al reves: la buena era esa. Aqui se
    # arregla la fuente, y las dos pantallas pasan a decir lo mismo porque leen lo mismo.
    from core.series_cliente import sanea_peso
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pesos: Dict[str, float] = {}
    for p in (profile.get("pesos") or []):
        fecha, valor = str(p.get("fecha") or "")[:10], sanea_peso(p.get("valor"))
        if fecha and fecha <= hoy and valor is not None:
            pesos[fecha] = valor
    # Y LOS PESAJES QUE VIAJARON CON UN AJUSTE DE MACROS. Cada fila de `macro_history` lleva
    # el peso del cliente ese día, y los importados de Calma van de 2022 en adelante: sin
    # ellos la curva empieza el día que estrenamos la serie y se pierde justo el recorrido
    # que le da sentido. Mis macros ya los sumaba; aquí no, y por eso -- ya con la fuente
    # arreglada y el «ahora» coincidiendo -- Evolución seguía enseñando 2 pesajes donde Mis
    # macros enseñaba 5 del mismo cliente (Francisco, 17-08: «¿ninguna miente, verdad?»).
    if profile.get("id"):
        async for h in db.macro_history.find(
            hasta_hoy({"client_id": profile["id"]}, campo="effective_date", campo_es_dia=True),
            {"_id": 0, "effective_date": 1, "created_at": 1, "peso": 1, "client_weight": 1},
        ):
            # Por `effective_date`, nunca por `created_at`: en las filas importadas ese campo
            # es el día de la importación, no el del pesaje (ver `macros_por_fecha`).
            fecha = h.get("effective_date") or str(h.get("created_at") or "")[:10]
            valor = sanea_peso(h.get("peso") if h.get("peso") is not None else h.get("client_weight"))
            if fecha and str(fecha)[:10] not in pesos and valor is not None:
                pesos[str(fecha)[:10]] = valor

    # Un reporte con peso que todavia no este en la serie tambien cuenta: los importados de
    # Calma no pasaron por ella. Sin pisar lo que ya hay, que es lo mas reciente.
    for r in reports:
        fecha, valor = str(r.get("created_at") or "")[:10], sanea_peso(r.get("weight"))
        if fecha and fecha not in pesos and valor is not None:
            pesos[fecha] = valor

    weight_data = [{"date": f, "value": v} for f, v in sorted(pesos.items())]

    measurements_data = {}
    for r in reports:
        if r.get("measurements"):
            for key, value in r["measurements"].items():
                if key not in measurements_data:
                    measurements_data[key] = []
                measurements_data[key].append({"date": r["created_at"], "value": value})
    
    # HASTA CUÁNDO ATRÁS SE PUEDE FECHAR UN PESAJE, dicho por quien manda la regla. El campo
    # del peso vive ahora en Evolución («Todo lo validado antes del 1 de septiembre», bloque
    # 4) y necesita el mismo número que el cierre del día: el desplegable de «¿de qué día es
    # este peso?» tiene que ofrecer exactamente lo que el servidor acepta. Es el fallo 7 del
    # repaso del 24-08 -- tres sitios y tres números para la misma decisión -- y no se
    # repite escribiendo un 14 en la pantalla nueva.
    from core.series_cliente import DIAS_ATRAS_PARA_UN_PESAJE
    return {
        "weight": weight_data,
        "measurements": measurements_data,
        "peso_dias_atras": DIAS_ATRAS_PARA_UN_PESAJE,
    }


async def _ritmos_de_su_perfil(perfil: dict) -> List[float]:
    """Cambio semanal de peso (%) de OTROS clientes con el mismo perfil.

    Mismo sexo, mismo objetivo y tramo de grasa parecido (±5 puntos). De cada uno se coge
    su ultimo tramo entre reportes, que es lo comparable con el tramo de este cliente.

    Solo devuelve numeros: ni nombres, ni ids, ni nada que identifique a nadie.
    """
    # Sin sexo y objetivo no hay "gente de su perfil" que valga: comparar el ritmo de
    # alguien en volumen con el de alguien en definición no significa nada, y sin sexo
    # tampoco. Antes que comparar con cualquiera, no se compara.
    sexo, objetivo = perfil.get("sex"), perfil.get("goal")
    if not sexo or not objetivo:
        return []

    # El campo `sex` mezcla dos vocabularios: 138 perfiles dicen "hombre" y 4 dicen
    # "male" (y "mujer"/"female"). Comparando en crudo, un cliente guardado como "male"
    # solo encontraba a los otros 3 "male" y se quedaba sin cohorte para siempre. Se
    # buscan todas las formas del mismo sexo.
    EQUIVALENTES = {
        "hombre": ["hombre", "male", "m", "h"],
        "male": ["hombre", "male", "m", "h"],
        "mujer": ["mujer", "female", "f"],
        "female": ["mujer", "female", "f"],
    }
    formas = EQUIVALENTES.get(str(sexo).strip().lower(), [sexo])

    grasa = perfil.get("body_fat")
    filtro = {
        "id": {"$ne": perfil.get("id")},
        "sex": {"$in": formas},
        "goal": objetivo,
        "status": "activo",
    }
    if grasa:
        filtro["body_fat"] = {"$gte": float(grasa) - 5, "$lte": float(grasa) + 5}

    pares = await db.client_profiles.find(filtro, {"_id": 0, "id": 1}).to_list(400)
    ritmos: List[float] = []
    for p in pares:
        reps = await db.reports.find(
            hasta_hoy({"client_id": p["id"], "weight": {"$ne": None}}),
            {"_id": 0, "weight": 1, "created_at": 1},
        ).sort("created_at", -1).to_list(2)
        if len(reps) < 2:
            continue
        nuevo, viejo = reps[0], reps[1]
        try:
            d1 = datetime.fromisoformat(str(nuevo["created_at"]).replace("Z", "+00:00"))
            d0 = datetime.fromisoformat(str(viejo["created_at"]).replace("Z", "+00:00"))
            semanas = max(0.5, (d1 - d0).days / 7.0)
            p0 = float(viejo["weight"])
            if p0 > 0:
                ritmos.append((float(nuevo["weight"]) - p0) / p0 * 100.0 / semanas)
        except (ValueError, TypeError, KeyError):
            continue
    return ritmos


@router.get("/{report_id}/informe")
async def get_informe_mensual(report_id: str, user = Depends(get_current_user)):
    """
    El informe que recibe el cliente tras su reporte (especificacion 31-07-2026, parte 6).

    Junta lo que ya esta repartido por la base -- el reporte, el anterior, sus dietas
    registradas, sus check-ins y sus macros -- y lo devuelve montado en los ocho
    apartados. No calcula nada de macros: eso ya esta hecho y guardado.

    Lo puede pedir el propio cliente o su coach.

    EL INFORME NO SALE HASTA QUE JESUS LO REVISA (doc 16-08, T9). Desde que se genera al
    enviar el reporte, el informe se guarda con `informe_estado`. Mientras esté en
    "pendiente_revision" el CLIENTE no lo ve: se le prometió "antes del sábado, con mi
    feedback", y enseñarle antes el montado a secas es entregarle media promesa. El
    equipo lo ve siempre (es lo que tiene que revisar) y los reportes viejos -- que no
    tienen estado -- se siguen montando al vuelo como hasta ahora.
    """
    reporte = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    perfil = await db.client_profiles.find_one({"id": reporte["client_id"]}, {"_id": 0})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    es_del_equipo = user.get("role") in ("admin", "trainer")
    if perfil.get("user_id") != user["id"] and not es_del_equipo:
        raise HTTPException(status_code=403, detail="Este informe no es tuyo")

    # EL INFORME SE ENTREGA AL ENVIAR (documento «El informe del mes», 1-09-2026):
    #
    #     «Se le entrega al enviar, con el hueco del feedback vacío, y el mismo informe se
    #      completa cuando le llegas con el programa nuevo.»
    #
    # Aquí había un candado: mientras el reporte estuviera en `pendiente_revision`, al
    # cliente se le decía «tu informe está en camino» y no veía nada. Venía de T9 (doc
    # 16-08), cuando el informe ERA el feedback y enseñarlo antes era entregar media
    # promesa. El documento nuevo lo separa en dos cosas: los nueve bloques son suyos y
    # salen ya; el feedback es el décimo y tiene su hueco, con el día y la hora.
    #
    # `informe_estado` no se toca: sigue diciéndole al equipo qué le queda por revisar.

    # Ya montado: se devuelve tal cual se guardó. Un informe es la foto de un momento, y
    # recalcularlo meses después lo cambiaría con datos que entonces no había.
    if reporte.get("informe"):
        return reporte["informe"]

    return await _montar_informe_del_reporte(reporte, perfil)


async def _montar_informe_del_reporte(reporte: dict, perfil: dict) -> dict:
    """Junta de la base todo lo que necesita `montar_informe` y lo monta.

    Estaba dentro del GET, y desde T9 hace falta también al ENVIAR el reporte: el informe
    se genera solo en ese momento y se guarda con su estado, en vez de montarse cada vez
    que alguien abre la pantalla.
    """
    from core.cycle import enrich_cycle
    from core.informe_mensual import montar_informe

    # LA SEMANA DEL CICLO SE CALCULA, NO SE LEE (3-09-2026).
    #
    # El informe decía «Semana 1 de 12» a TODO EL MUNDO. El 1 no era la semana de nadie: es
    # el literal que escribe el alta en `client_profiles.week` para que no reviente la
    # validación, y desde entonces no lo mueve nada -- ni un cron, ni un `$inc`, ni una
    # pantalla. Medido: 184 de 188 fichas de producción están en `week: 1`, y las otras 4 no
    # tienen el campo. Nadie llega nunca a la semana 2.
    #
    # La semana de verdad se calcula desde `cycle_start` y ya lo hace `core/cycle`, que es
    # lo que leen Mi perfil, el panel, la renovación y la cadencia de reportes. Aquí no se
    # llamaba: el informe era el único sitio que se creía el campo muerto. `enrich_cycle`
    # solo toca el dict en memoria, así que no escribe nada en la base.
    #
    # OJO: los informes YA GUARDADOS (`reports.informe`) seguirán diciendo «Semana 1» --
    # se congelan al enviar el reporte y se devuelven tal cual, a propósito.
    #
    # PENDIENTE (4-09, doc de Jesús del 2-09, fase 1): desde hoy el reporte nace con
    # `semana_del_ciclo`, `bloque`, `ciclo_id`, `ciclo_numero` y `ciclo_inicio` congelados
    # al crearlo (ver CAMPOS_CICLO). El informe debería leer la semana DEL REPORTE cuando
    # la tenga y calcularla solo para los de antes: esto de aquí abajo sigue calculándola
    # sobre el perfil de hoy, que es la del momento de montarlo, no la del reporte si se
    # monta después. Es de otra tarea; aquí no se toca.
    perfil = enrich_cycle(dict(perfil))

    anterior = await db.reports.find_one(
        {"client_id": reporte["client_id"], "created_at": {"$lt": reporte["created_at"]}},
        {"_id": 0}, sort=[("created_at", -1)],
    )
    # Las fotos del punto de partida son las del PRIMER reporte que las tuviera: son la
    # comparacion que de verdad enseña el cambio, no la del mes pasado.
    primero = await db.reports.find_one(
        {"client_id": reporte["client_id"], "photos": {"$ne": []}},
        {"_id": 0}, sort=[("created_at", 1)],
    )
    # La foto de INICIO DE FASE (3.2): la del primer reporte con fotos desde que empezo la
    # fase actual. `fase_desde` lo pone el propio cliente al marcar otro objetivo en su
    # reporte (punto 5). Sin fase_desde no hay etiqueta de fase, y entonces la comparativa
    # se queda en tres fotos, que es justo lo que dice su tabla para "sin cambio de fase".
    inicio_fase = None
    if perfil.get("fase_desde"):
        inicio_fase = await db.reports.find_one(
            {"client_id": reporte["client_id"], "photos": {"$ne": []},
             "created_at": {"$gte": perfil["fase_desde"]}},
            {"_id": 0}, sort=[("created_at", 1)],
        )

    desde = (anterior or {}).get("created_at") or perfil.get("created_at")
    dias_periodo, dias_dieta, dias_entreno, macros_comidos = await _actividad_del_periodo(
        perfil, desde, reporte.get("created_at"))

    # Los macros que MANDAN hoy, por `effective_date` y no por `created_at`: ver
    # `macros_por_fecha.ultima_vigente`. Con la fecha de importacion, a un cliente migrado el
    # informe le podia poner como «macros nuevos» unos de hace cuatro años.
    from macros_por_fecha import ultima_vigente
    ultimos_macros = await ultima_vigente(db, reporte["client_id"])

    from routes.plans import _overrides_by_code
    from models.user import merged_catalog
    catalogo = merged_catalog(await _overrides_by_code())
    plan = catalogo.get(perfil.get("plan") or "", {})
    hab = plan.get("habilitaciones", {})

    informe = montar_informe(
        perfil=perfil,
        reporte=reporte,
        reporte_anterior=anterior,
        fotos_dia_cero=(primero or {}).get("photos"),
        reporte_inicial=primero,
        reporte_inicio_fase=inicio_fase,
        ritmos_cohorte=await _ritmos_de_su_perfil(perfil),
        semanas_ciclo=(plan.get("ciclo") or {}).get("semanas"),
        dias_dieta=dias_dieta,
        dias_entreno=dias_entreno,
        dias_periodo=dias_periodo,
        macros_comidos=macros_comidos,
        macros_nuevos=({"training": ultimos_macros.get("training"),
                        "rest": ultimos_macros.get("rest"),
                        "periworkout": ultimos_macros.get("periworkout"),
                        # La fecha del AJUSTE, no la de la fila: en lo migrado son distintas.
                        "fecha": (ultimos_macros.get("effective_date")
                                  or ultimos_macros.get("created_at"))} if ultimos_macros else None),
        explicacion_equipo=reporte.get("trainer_feedback"),
        # "En los niveles 2 y 3 la explicacion la escribe el equipo. En el 1, el sistema."
        # Aqui eso es: si el plan trae entrenador detras, la escribe una persona.
        la_escribe_el_equipo=hab.get("acompanamiento", "solo_app") != "solo_app",
    )

    # LOS DIEZ BLOQUES DEL DOCUMENTO DEL 1-09, al lado de lo que ya había. Se añaden y no
    # sustituyen: los informes que ya están guardados siguen teniendo solo los ocho
    # apartados viejos, y la pantalla cae en ellos cuando `bloques` no viene.
    informe["bloques"] = await _bloques_del_informe(reporte, perfil, anterior)
    return informe


async def _bloques_del_informe(reporte: dict, perfil: dict,
                               anterior: Optional[dict]) -> Dict[str, Any]:
    """Los diez bloques del documento «El informe del mes» (1-09-2026), en su orden.

    Junta de la base lo que hace falta y llama a `core.informe_del_mes`, que es donde están
    las reglas. Aquí solo se consulta.
    """
    from core.actividad_mensual import cierres_del_periodo
    from core.datos_reporte import (comidas_y_extras_del_periodo, datos_dieta,
                                    datos_entreno, fecha_larga, serie_de_pesos)
    from core.informe_del_mes import (ETIQUETAS_MEDIDAS, dia_tipo, donde_estas,
                                      extras_registrados, feedback_del_informe,
                                      grasa_del_informe, lo_que_has_hecho,
                                      medidas_del_informe, peso_del_mes,
                                      preferencias_de_alimentos)
    from core.series_cliente import grasa_vigente

    # EL PERIODO ES EL DE ESTE REPORTE, NO EL DE HOY. `_periodo_del_reporte` cuenta hacia
    # atrás desde el día de hoy, que es lo que hace falta para el FORMULARIO; aquí no. Un
    # informe es la foto del mes que cerró ese reporte, y abriéndolo en octubre tiene que
    # seguir contando agosto. Con el otro criterio, el informe de un reporte de hace tres
    # meses enseñaría las dietas de esta semana.
    d1 = _dia_del_reporte(reporte)
    dias = DIAS_DEL_PERIODO.get(reporte.get("tipo") or "mensual", 28)
    d0 = d1 - timedelta(days=dias - 1)
    if anterior:
        # Y nunca antes del reporte anterior: lo que ya se contó en aquel no se vuelve a
        # contar aquí.
        d0 = max(d0, _dia_del_reporte(anterior) + timedelta(days=1))
    arranque = perfil.get("arranque_lunes") or perfil.get("created_at")
    if arranque:
        try:
            d0 = max(d0, datetime.fromisoformat(str(arranque).replace("Z", "+00:00")).date())
        except (ValueError, TypeError):
            pass
    if d0 > d1:
        d0 = d1

    dieta = await datos_dieta(perfil, d0, d1)
    entreno = await datos_entreno(perfil, d0, d1)
    cierres_crudos = await db.checkins.find(
        {"client_id": perfil.get("id"), "type": "daily",
         "created_at": {"$gte": d0.isoformat(), "$lte": d1.isoformat() + "T23:59:59"}},
        {"_id": 0, "extras_respuesta": 1, "movimiento": 1, "suplementos": 1},
    ).to_list(400)
    cierres = cierres_del_periodo(
        cierres_crudos, (d1 - d0).days + 1,
        tiene_suplementacion=plan_grants_feature(perfil.get("plan"), "suplementacion"))

    # LA PRIMERA TOMA DE MEDIDAS de toda su historia, que es contra lo que se compara la
    # segunda columna. No es la del mes pasado: es la del día que entró.
    primera_medida = await db.reports.find_one(
        {"client_id": reporte["client_id"], "measurements": {"$nin": [None, {}]}},
        {"_id": 0, "measurements": 1}, sort=[("created_at", 1)])

    serie = serie_de_pesos(perfil)
    comido = await comidas_y_extras_del_periodo(perfil, d0, d1)
    grasa = grasa_vigente(perfil)

    from routes.plans import _overrides_by_code
    from models.user import merged_catalog
    catalogo = merged_catalog(await _overrides_by_code())
    semanas_ciclo = ((catalogo.get(perfil.get("plan") or "", {}).get("ciclo")) or {}).get("semanas")

    firmante = None
    if reporte.get("trainer_feedback"):
        entrenador = await db.users.find_one(
            {"id": perfil.get("trainer_id")}, {"_id": 0, "name": 1}) if perfil.get("trainer_id") else None
        firmante = (entrenador or {}).get("name") or "Jesús Gallego"

    return {
        "periodo": {"desde": d0.isoformat(), "hasta": d1.isoformat(),
                    "dias": (d1 - d0).days + 1,
                    "label": (f"Del {fecha_larga(d0.isoformat())} al "
                              f"{fecha_larga(d1.isoformat())} · {(d1 - d0).days + 1} días")},
        "donde_estas": donde_estas(perfil.get("goal"), perfil.get("week"), semanas_ciclo),
        "feedback": feedback_del_informe(
            reporte.get("trainer_feedback"), firmante,
            fecha_larga(reporte.get("informe_publicado_at") or reporte.get("created_at")),
            # El día se decide en un solo sitio, el mismo que avisa al equipo si vence.
            dia_prometido=dia_prometido_de(reporte.get("tipo"))),
        "peso": peso_del_mes(serie_de_pesos(perfil, d0, d1),
                             peso_al_empezar=(serie[0]["valor"] if serie else None)),
        "medidas": medidas_del_informe(
            reporte.get("measurements"), (anterior or {}).get("measurements"),
            (primera_medida or {}).get("measurements"),
            ETIQUETAS_MEDIDAS, objetivo=perfil.get("goal")),
        "grasa": grasa_del_informe(grasa.get("valor"), fecha_larga(grasa.get("fecha")),
                                   grasa.get("semanas")),
        "hecho": lo_que_has_hecho(dieta, entreno, cierres),
        "dia_tipo": dia_tipo(comido["comidas"]),
        "preferencias": preferencias_de_alimentos(comido["usos"]),
        "extras": extras_registrados(comido["extras"]),
    }


def _dia_del_reporte(reporte: dict):
    """El día (de España) en que se mandó. Sin zona, la medianoche de UTC cae en el día
    anterior aquí, y el mes del informe empezaría y acabaría un día antes."""
    from datetime import date as _date
    crudo = reporte.get("created_at") or reporte.get("fecha")
    try:
        instante = datetime.fromisoformat(str(crudo).replace("Z", "+00:00"))
        return (a_madrid(instante) or instante).date()
    except (ValueError, TypeError):
        try:
            return _date.fromisoformat(str(crudo)[:10])
        except (ValueError, TypeError):
            return hoy_madrid()


_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def dia_prometido_de(tipo: Optional[str]) -> str:
    """Cómo se le nombra al cliente el día que se le prometió.

    SALE DEL MISMO SITIO QUE EL AVISO AL EQUIPO (`core/promesa_del_reporte.DIA_PROMETIDO`).
    Escribirlo a mano aquí sería tener la promesa en dos sitios, y el día que uno cambie el
    cliente leería una fecha y el aviso vencería en otra.

    OJO, HAY UN DESACUERDO ABIERTO: el documento «El informe del mes» (1-09) dice «antes
    del viernes a las 15:00» para el mensual, y el módulo dice sábado, que viene del doc
    «El día» del 31-08. Mientras no se decida manda el módulo, que es lo que hoy usa el
    aviso del equipo: así la pantalla no promete un día distinto del que se vigila.
    """
    from core.promesa_del_reporte import DIA_PROMETIDO
    return _DIAS[DIA_PROMETIDO.get((tipo or "mensual").lower(), 4)]


async def _actividad_del_periodo(perfil: dict, desde: Optional[str], hasta: Optional[str]):
    """Que hizo de verdad entre los dos reportes: dias con dieta, entrenos y macros medios.

    El cumplimiento sale de aqui y no de preguntarle cuanto cree que ha cumplido, que es
    justo lo que el documento manda quitar.
    """
    def _fecha(v):
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None

    d0, d1 = _fecha(desde), _fecha(hasta)
    if not d0 or not d1:
        return 28, 0, 0, {}

    dias_periodo = max(1, (d1 - d0).days)
    filtro_fecha = {"$gte": d0.isoformat(), "$lte": d1.isoformat()}

    dietas = await db.diets.find(
        {"user_id": perfil.get("user_id"), "fecha": filtro_fecha},
        {"_id": 0, "comidas": 1},
    ).to_list(200)

    con_comida, suma = 0, {"protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for d in dietas:
        total = {"protein": 0.0, "carbs": 0.0, "fat": 0.0}
        for comida in (d.get("comidas") or {}).values():
            for a in ((comida or {}).get("alimentos") or []):
                m = a.get("macros_efectivos") or {}
                total["protein"] += float(m.get("P") or 0)
                total["carbs"] += float(m.get("H") or 0)
                total["fat"] += float(m.get("G") or 0)
        if total["protein"] or total["carbs"] or total["fat"]:
            con_comida += 1
            for k in suma:
                suma[k] += total[k]

    medios = {k: round(v / con_comida, 1) for k, v in suma.items()} if con_comida else {}

    entrenos = await db.checkins.count_documents({
        "client_id": perfil.get("id"), "trained": True,
        "created_at": {"$gte": d0.isoformat(), "$lte": d1.isoformat() + "T23:59:59"},
    })

    return dias_periodo, con_comida, entrenos, medios


@router.put("/{report_id}/feedback")
async def set_report_feedback(report_id: str, data: dict, user = Depends(get_admin_user)):
    """El coach escribe (o edita) el feedback de un reporte del cliente.

    Si el informe todavía está por publicar, el feedback NO avisa al cliente: el aviso lo
    da el botón de publicar, cuando el informe entero está listo. Avisar aquí sería
    llamarle para enseñarle algo que aún no puede ver (T9).
    """
    feedback = (data.get("feedback") or "").strip()
    report = await db.reports.find_one({"id": report_id}, {"_id": 0, "client_id": 1,
                                                           "informe_estado": 1})
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    await db.reports.update_one(
        {"id": report_id}, {"$set": {"trainer_feedback": feedback or None}}
    )

    if feedback and report.get("informe_estado") != "pendiente_revision":
        profile = await db.client_profiles.find_one({"id": report["client_id"]}, {"_id": 0, "user_id": 1})
        if profile:
            from routes.notifications import notify
            await notify(profile["user_id"], "feedback", "Hemos comentado tu reporte", "/dashboard/reports")

    return {"ok": True}


@router.post("/{report_id}/informe/publicar")
async def publicar_informe(report_id: str, user=Depends(get_admin_user)):
    """PUBLICAR EL INFORME (T9): hasta aquí, el cliente no lo ve.

    Se vuelve a montar con lo que el coach acaba de escribir dentro -- el feedback es la
    parte que lo distingue -- y pasa a "entregado". Solo entonces sale el aviso.
    """
    reporte = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    perfil = await db.client_profiles.find_one({"id": reporte["client_id"]}, {"_id": 0})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    assert_client_access(user, perfil)

    informe = await _montar_informe_del_reporte(reporte, perfil)
    ahora = datetime.now(timezone.utc).isoformat()
    await db.reports.update_one(
        {"id": report_id},
        {"$set": {"informe": informe, "informe_estado": "entregado",
                  "informe_publicado_at": ahora, "informe_publicado_por": user.get("id")}},
    )

    # EL AVISO NO SE ESCRIBE AQUÍ. Los textos y sus variantes viven en un solo sitio (T10),
    # que es lo que hace que roten y que no haya dos redacciones de la misma frase sueltas
    # por el código. Aquí solo se decide CUÁL toca, y eso sale de sus habilitaciones:
    # quien tiene quincenal recibe el informe con el feedback de Jesús; el resto reciben
    # los ajustes, que es lo que el doc les promete al enviar.
    if perfil.get("user_id"):
        from routes.notifications import avisar_ajustes_nuevos, avisar_informe_listo
        hab = await _habilitaciones_de(perfil)
        if "quincenal" in (hab.get("reportes") or []):
            await avisar_informe_listo(perfil["user_id"])
        else:
            await avisar_ajustes_nuevos(perfil["user_id"])

    return {"ok": True, "informe_estado": "entregado", "informe": informe}
