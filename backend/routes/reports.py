"""
Rutas de reportes: crear, listar, evolución.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
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

    report_id = str(uuid.uuid4())
    report = {
        "id": report_id,
        "client_id": profile["id"],
        "weight": data.weight,
        "measurements": data.measurements,
        "photos": data.photos,
        "training_compliance": data.training_compliance,
        "nutrition_compliance": data.nutrition_compliance,
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
