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
from models.common import ReportCreate, ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])
# Rutas del equipo sobre el reporte de un cliente (punto 45): meterlo en su nombre.
admin_router = APIRouter(prefix="/admin", tags=["admin-reports"])

@router.post("", response_model=ReportResponse)
async def create_report(data: ReportCreate, user = Depends(get_current_user)):
    """Crear un reporte de seguimiento."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    if not plan_grants_feature(profile.get("plan"), "reportes"):
        raise HTTPException(status_code=403, detail="Tu plan no incluye reportes de seguimiento.")

    # Ventana de envío (viernes 00:00 -> lunes 06:00): fuera de ella se bloquea.
    from routes.report_cadence import compute_client_report_state, _fecha_es
    from routes.plans import _overrides_by_code
    from models.user import merged_catalog
    now = datetime.now(timezone.utc)
    state = compute_client_report_state(profile, merged_catalog(await _overrides_by_code()), now)
    if not state["due"]:
        raise HTTPException(status_code=403, detail="Esta semana no toca reporte. Te avisaremos cuando abra la ventana.")
    if now < state["window_open"]:
        raise HTTPException(status_code=403, detail=f"Tu reporte se rellena el fin de semana. La ventana abre el {_fecha_es(state['window_open'])}.")
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

    report_id = str(uuid.uuid4())
    report = {
        "id": report_id,
        "client_id": profile["id"],
        "weight": data.weight,
        "measurements": data.measurements,
        "photos": data.photos,
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
    await db.client_profiles.update_one({"id": profile["id"]}, {"$set": set_perfil})

    return ReportResponse(**report)

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
    prev = await db.reports.find_one(
        {"client_id": profile["id"]}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)]
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
            {"client_id": p["id"], "weight": {"$ne": None}},
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
    """
    from core.informe_mensual import montar_informe
    from core.plan_access import plan_grants_feature  # noqa: F401  (mismo modulo que arriba)

    reporte = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    perfil = await db.client_profiles.find_one({"id": reporte["client_id"]}, {"_id": 0})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    # El cliente ve el suyo; el staff, el de cualquiera de sus clientes.
    if perfil.get("user_id") != user["id"] and user.get("role") not in ("admin", "trainer"):
        raise HTTPException(status_code=403, detail="Este informe no es tuyo")

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

    ultimos_macros = await db.macro_history.find_one(
        {"client_id": reporte["client_id"]}, {"_id": 0}, sort=[("created_at", -1)])

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
                        "fecha": ultimos_macros.get("created_at")} if ultimos_macros else None),
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
    """El coach escribe (o edita) el feedback de un reporte del cliente."""
    feedback = (data.get("feedback") or "").strip()
    report = await db.reports.find_one({"id": report_id}, {"_id": 0, "client_id": 1})
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    await db.reports.update_one(
        {"id": report_id}, {"$set": {"trainer_feedback": feedback or None}}
    )

    if feedback:
        profile = await db.client_profiles.find_one({"id": report["client_id"]}, {"_id": 0, "user_id": 1})
        if profile:
            from routes.notifications import notify
            await notify(profile["user_id"], "feedback", "Tu coach ha comentado tu reporte", "/dashboard/reports")

    return {"ok": True}
