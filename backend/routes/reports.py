"""
Rutas de reportes: crear, listar, evolución.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List
import uuid

from core.database import db
from core.security import get_current_user, get_admin_user
from models.common import ReportCreate, ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])

@router.post("", response_model=ReportResponse)
async def create_report(data: ReportCreate, user = Depends(get_current_user)):
    """Crear un reporte de seguimiento."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
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
