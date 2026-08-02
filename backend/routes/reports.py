"""
Rutas de reportes: crear, listar, evolución.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid

from core.database import db
from core.security import get_current_user, get_admin_user
from core.plan_access import plan_grants_feature
from models.common import ReportCreate, ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])

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
            {"client_id": profile["id"]}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)]
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
        "trainer_feedback": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.reports.insert_one(report)
    
    # Update client profile weight
    await db.client_profiles.update_one(
        {"id": profile["id"]},
        {"$set": {"weight": data.weight}}
    )
    
    return ReportResponse(**report)

@router.get("", response_model=List[ReportResponse])
async def get_reports(skip: int = 0, limit: int = 50, user = Depends(get_current_user)):
    """Obtener reportes del cliente (paginado con skip/limit para 'cargar más')."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    reports = await db.reports.find(
        {"client_id": profile["id"]},
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
    prev = await db.reports.find_one(
        {"client_id": profile["id"]},
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
    
    reports = await db.reports.find(
        {"client_id": profile["id"]},
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
        {"_id": 0, "photos": 1}, sort=[("created_at", 1)],
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
