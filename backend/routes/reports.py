"""
Rutas de reportes: crear, listar, evolución.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid

from core.database import db
from core.security import get_current_user, get_admin_user, assert_client_access
from core.plan_access import plan_grants_feature
from core.series_cliente import anotar_peso
from core.sin_futuro import hasta_hoy
from core.tiempo import a_madrid, hoy_madrid
from models.common import ReportCreate, ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])

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
    from routes.report_cadence import compute_client_report_state, _fecha_es, _hora_es
    from routes.plans import _overrides_by_code
    from models.user import merged_catalog
    now = datetime.now(timezone.utc)
    state = compute_client_report_state(profile, merged_catalog(await _overrides_by_code()), now)
    if not state["due"]:
        raise HTTPException(status_code=403, detail="Esta semana no toca reporte. Te avisaremos cuando abra la ventana.")
    if now < state["window_open"]:
        # Decía «se rellena el fin de semana», que es verdad para el mensual y mentira para
        # el quincenal: ese se rellena el miércoles y el jueves.
        raise HTTPException(
            status_code=403,
            detail=f"Todavía no toca: se abre el {_fecha_es(state['window_open'])} "
                   f"a las {_hora_es(state['window_open'])} y lo tienes hasta el "
                   f"{_fecha_es(state['window_close'])} a las {_hora_es(state['window_close'])}.")
    if now > state["window_close"]:
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
    fotos = [f for f in (data.photos or []) if f]
    if not fotos:
        desde = state["window_open"].isoformat()
        fotos = [d["id"] async for d in db.client_photos.find(
            {"client_id": profile["id"], "uploaded_at": {"$gte": desde}},
            {"_id": 0, "id": 1}).sort("uploaded_at", -1).limit(6)]
        fotos.reverse()

    report_id = str(uuid.uuid4())
    report = {
        "id": report_id,
        "client_id": profile["id"],
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
        "dieta_dificultad": data.dieta_dificultad,
        "entreno": data.entreno.model_dump() if data.entreno else None,
        "lesiones": [l.model_dump() for l in data.lesiones] if data.lesiones else None,
        "lesion_nueva": (data.lesion_nueva or "").strip() or None,
        "cardio_proximo_mes": data.cardio_proximo_mes,
        "suplementacion": data.suplementacion.model_dump() if data.suplementacion else None,
        "energia_motivo": data.energia_motivo,
        "valoracion_resultado": data.valoracion_resultado,
        "motivacion": data.motivacion,
        "sugerencias": (data.sugerencias or "").strip() or None,
        "trainer_feedback": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.reports.insert_one(report)

    # El objetivo que marca el cliente MANDA sobre la fase del perfil: es lo que dispara el
    # cambio de fase, y sin esto un Nivel 1 no cambiaria de fase nunca (no tiene coach que se
    # la cambie). `fase_desde` guarda CUANDO empezo, que es lo que necesita el informe para
    # la foto de "inicio de fase".
    # `ultimo_reporte` va aqui a proposito duplicado (punto 29 del 07-08, ver
    # core/seguimiento.py): es lo que deja ordenar la lista de clientes por "quien lleva
    # mas sin que le toquen" sin recorrer los reportes de todos para pintar una tabla.
    set_perfil = {"ultimo_reporte": report["created_at"][:10]}
    # El peso NO se escribe aqui: va a la serie con la fecha del reporte, y el "actual"
    # sale de la serie (punto 30). Es lo que arregla los dos pesos distintos del punto 9.
    await anotar_peso(profile["id"], data.weight, report["created_at"][:10], origen="reporte")
    if data.proximo_objetivo in ("definicion", "volumen", "mantenimiento"):
        if profile.get("goal") != data.proximo_objetivo:
            set_perfil["goal"] = data.proximo_objetivo
            set_perfil["fase_desde"] = report["created_at"][:10]

    # LAS LESIONES SE QUEDAN EN EL PERFIL, NO SOLO EN EL REPORTE (T8, bloque 06).
    # Es lo que hace que el mes que viene salga "LO QUE YA ME CONTASTE" en vez de una
    # hoja en blanco. Las superadas se guardan igual, con su estado: así se sabe que se
    # cerró y no se le vuelve a preguntar (`lesiones_del_perfil` las filtra).
    if data.lesiones is not None:
        set_perfil["lesiones"] = [
            {"zona": l.zona, "desde": l.desde, "estado_mes": l.estado_mes,
             "ejercicios_vetados": l.ejercicios, "actualizado": report["created_at"][:10]}
            for l in data.lesiones
        ]
    await db.client_profiles.update_one({"id": profile["id"]}, {"$set": set_perfil})
    # Y el perfil que se lleva el informe es el de DESPUÉS: si acaba de cambiar de fase,
    # la foto de "inicio de fase" es la de ahora, no la de la fase que deja atrás.
    profile.update(set_perfil)

    # El aplazamiento se cierra al mandarlo: si ya está el reporte, no hay nada que correr.
    if profile.get("reporte_aplazado_hasta"):
        await db.client_profiles.update_one(
            {"id": profile["id"]},
            {"$unset": {"reporte_aplazado_hasta": "", "reporte_aplazado_tipo": ""}})

    await _avisar_de_lo_que_pidio(profile, user, data, report_id)

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
    respuesta["mensaje_envio"] = (
        "Antes del sábado tienes tu informe completo con mi feedback y tus ajustes. Te aviso por aquí."
        if lleva_feedback and report.get("tipo") == "mensual" else
        "Antes del viernes tienes tus ajustes nuevos. Te aviso por aquí.")
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
    if entreno.rutina_del_mes in ("basica", "avanzada"):
        modalidad = "básica" if entreno.rutina_del_mes == "basica" else "avanzada"
        # «Al marcar «Sí» autorizas el cargo en tu tarjeta»: se le cobra en la que ya tiene
        # guardada. Si no se puede, el reporte se manda igual y el equipo se entera de por
        # qué; lo que no se hace es dejar la petición sin cobrar y sin decirlo.
        from core.rutina_del_mes import PRECIO_EUR, cobrar
        cobro = await cobrar(profile, entreno.rutina_del_mes, report_id)

        if cobro["cobrado"]:
            estado = f"Cobrados {PRECIO_EUR:.0f} € en su tarjeta."
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
                   "importe_eur": PRECIO_EUR},
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

    report = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "weight": data.weight,
        "measurements": data.measurements,
        "photos": data.photos,
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
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.reports.insert_one(report)

    set_perfil = {"ultimo_reporte": str(report["created_at"])[:10]}
    if data.proximo_objetivo in ("definicion", "volumen", "mantenimiento"):
        if profile.get("goal") != data.proximo_objetivo:
            set_perfil["goal"] = data.proximo_objetivo
            set_perfil["fase_desde"] = str(report["created_at"])[:10]
    await db.client_profiles.update_one({"id": client_id}, {"$set": set_perfil})
    # El peso, a su serie con la fecha del reporte (punto 30).
    await anotar_peso(client_id, data.weight, str(report["created_at"])[:10], origen="reporte (lo metió el equipo)")

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
        from routes.report_cadence import compute_client_report_state
        from routes.plans import _overrides_by_code
        from models.user import merged_catalog
        estado = compute_client_report_state(
            perfil, merged_catalog(await _overrides_by_code()), datetime.now(timezone.utc))
        tipo = (estado["tipos"] or ["mensual"])[0]

    perfil_rep = perfil_de_reporte(hab)
    d0, d1 = _periodo_del_reporte(perfil, tipo)
    datos = await datos_del_reporte(perfil, tipo, d0, d1)

    bloques = bloques_del_mensual(perfil_rep) if tipo == "mensual" else [
        "entreno_previo", "peso", "molestias", "sensaciones", "libre"]
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
        "bloques": bloques,
        # Si su plan lleva alguien detrás que le escriba el informe. De esto depende lo
        # que se le promete al enviar: ajustes (viernes) o informe con feedback (sábado).
        "lleva_feedback": "quincenal" in reportes,
        "datos": datos,
        # Si ya lo aplazó este mes, para que la casilla salga marcada y no lo aplace dos veces.
        "aplazado_hasta": perfil.get("reporte_aplazado_hasta"),
    }


@router.post("/aplazar")
async def aplazar_reporte(user=Depends(get_current_user)):
    """"¿No has podido hacer el programa completo estas 3 semanas? Márcalo y te lo aplazo
    7 días." (doc 16-08, T8, cabecera de los tres).

    Guarda hasta cuándo se le corre la ventana en su perfil y deja el aviso de
    confirmación. La ventana de envío la sigue mandando `report_cadence`, que es quien
    tiene que leer este campo: aquí solo se escribe.

    Lo pide él, no se deduce de que no conteste un correo: es la diferencia entre
    organizarse y quedarse fuera.
    """
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    from routes.report_cadence import compute_client_report_state
    from routes.plans import _overrides_by_code
    from models.user import merged_catalog

    ahora = datetime.now(timezone.utc)
    estado = compute_client_report_state(
        perfil, merged_catalog(await _overrides_by_code()), ahora)
    if not estado["due"]:
        raise HTTPException(status_code=403,
                            detail="Esta semana no te toca reporte, así que no hay nada que aplazar.")

    # Siete días desde el cierre de SU ventana, no desde hoy: aplazarlo el viernes y
    # aplazarlo el domingo tienen que dejarle el mismo plazo nuevo.
    hasta = estado["window_close"] + timedelta(days=7)
    ya_aplazado = perfil.get("reporte_aplazado_hasta")
    if ya_aplazado and str(ya_aplazado) >= hasta.isoformat():
        # Ya lo aplazó: se le contesta con lo que tiene, sin correrle la fecha otra vez.
        hasta = datetime.fromisoformat(str(ya_aplazado).replace("Z", "+00:00"))
    else:
        await db.client_profiles.update_one(
            {"id": perfil["id"]},
            {"$set": {"reporte_aplazado_hasta": hasta.isoformat(),
                      # QUÉ reporte se aplazó, no solo hasta cuándo: la semana que viene
                      # puede que no le toque ninguno, y sin esto la ventana ampliada no
                      # sabría de qué reporte está hablando.
                      "reporte_aplazado_tipo": (estado["tipos"] or [None])[0],
                      "reporte_aplazado_at": ahora.isoformat()}},
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
    
    weight_data = [{"date": r["created_at"], "value": r["weight"]} for r in reports if r.get("weight")]
    
    measurements_data = {}
    for r in reports:
        if r.get("measurements"):
            for key, value in r["measurements"].items():
                if key not in measurements_data:
                    measurements_data[key] = []
                measurements_data[key].append({"date": r["created_at"], "value": value})
    
    return {
        "weight": weight_data,
        "measurements": measurements_data
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

    if not es_del_equipo and reporte.get("informe_estado") == "pendiente_revision":
        return {"generado": False, "motivo": "pendiente_revision",
                "mensaje": "Tu informe está en camino. Te aviso por aquí en cuanto esté."}

    # Ya montado y publicado: se devuelve tal cual se guardó. Un informe es la foto de un
    # momento, y recalcularlo meses después lo cambiaría con datos que entonces no había.
    if reporte.get("informe") and (es_del_equipo or reporte.get("informe_estado") == "entregado"):
        return reporte["informe"]

    return await _montar_informe_del_reporte(reporte, perfil)


async def _montar_informe_del_reporte(reporte: dict, perfil: dict) -> dict:
    """Junta de la base todo lo que necesita `montar_informe` y lo monta.

    Estaba dentro del GET, y desde T9 hace falta también al ENVIAR el reporte: el informe
    se genera solo en ese momento y se guarda con su estado, en vez de montarse cada vez
    que alguien abre la pantalla.
    """
    from core.informe_mensual import montar_informe

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

    return montar_informe(
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
