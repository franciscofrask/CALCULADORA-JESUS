"""
Check-ins de seguimiento (portado de calmajp).

Tres niveles:
  - daily:   ánimo/energía/entrenó/nutrición (10 segundos)
  - weekly:  peso + cumplimiento + sueño + estrés
  - monthly: peso + %graso + medidas + progreso/retos

Incluye health score (rojo/amarillo/verde) y fotos de progreso (binario en
colección dedicada `client_photos` para no inflar los documentos de check-in).
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Response
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import uuid

from bson import Binary

from core.database import db
from core.security import get_current_user, get_admin_user
from models.common import CheckInCreate, CheckInResponse

router = APIRouter(tags=["checkins"])

VALID_CHECKIN_TYPES = {"daily", "weekly", "monthly"}


# ==================== HEALTH SCORE ====================

def _compute_health_score(checkins: List[dict], profile: dict) -> dict:
    """Score rojo/amarillo/verde a partir de los check-ins recientes y el estado del perfil.

    Reglas:
      - red:    sin check-in 14+ días, baja_automatica, o adherencia reciente < 50%
      - yellow: sin check-in 7-14 días, pago past_due, o adherencia 50-75%
      - green:  actividad reciente y adherencia >= 75%
    """
    now = datetime.now(timezone.utc)
    factors: list[str] = []
    level = "green"

    last_checkin_date: Optional[datetime] = None
    for c in checkins:
        try:
            dt = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
            if last_checkin_date is None or dt > last_checkin_date:
                last_checkin_date = dt
        except Exception:
            continue

    days_since = (now - last_checkin_date).days if last_checkin_date else 999

    if profile.get("status") == "baja_automatica":
        level = "red"
        factors.append("Baja automatica por fallos de pago")
    elif days_since >= 14:
        level = "red"
        factors.append(f"Sin check-in hace {days_since} dias")
    elif days_since >= 7:
        level = "yellow"
        factors.append(f"Ultimo check-in hace {days_since} dias")

    weekly = [c for c in checkins if c.get("type") == "weekly"][:4]
    if weekly:
        train_vals = [c.get("training_compliance") for c in weekly if c.get("training_compliance") is not None]
        nutr_vals = [c.get("nutrition_compliance") for c in weekly if c.get("nutrition_compliance") is not None]
        all_vals = train_vals + nutr_vals
        if all_vals:
            avg = sum(all_vals) / len(all_vals)
            if avg < 50:
                level = "red"
                factors.append(f"Adherencia media baja ({avg:.0f}%)")
            elif avg < 75 and level != "red":
                level = "yellow"
                factors.append(f"Adherencia media regular ({avg:.0f}%)")

    if profile.get("subscription_status") == "past_due" and level == "green":
        level = "yellow"
        factors.append("Pago atrasado")

    if (profile.get("payment_failure_count") or 0) >= 1 and level == "green":
        level = "yellow"
        factors.append(f"{profile['payment_failure_count']} intento(s) de cobro fallido(s)")

    return {
        "score": level,
        "factors": factors,
        "last_checkin": last_checkin_date.isoformat() if last_checkin_date else None,
        "days_since_checkin": days_since if last_checkin_date else None,
    }


# ==================== CHECK-INS ====================

@router.post("/checkins", response_model=CheckInResponse)
async def create_checkin(data: CheckInCreate, user = Depends(get_current_user)):
    if data.type not in VALID_CHECKIN_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo invalido. Usa uno de: {VALID_CHECKIN_TYPES}")
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    checkin = {
        "id": str(uuid.uuid4()),
        "client_id": profile["id"],
        **data.model_dump(exclude_none=True),
        "trainer_feedback": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.checkins.insert_one(checkin)

    # Sync de peso al perfil si lo aporta (weekly/monthly).
    if data.weight is not None:
        await db.client_profiles.update_one(
            {"id": profile["id"]},
            {"$set": {"weight": data.weight}},
        )

    return CheckInResponse(**checkin)


@router.get("/checkins", response_model=List[CheckInResponse])
async def get_my_checkins(type: Optional[str] = None, limit: int = 30, skip: int = 0, user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    query: Dict[str, Any] = {"client_id": profile["id"]}
    if type:
        if type not in VALID_CHECKIN_TYPES:
            raise HTTPException(status_code=400, detail="Tipo invalido")
        query["type"] = type

    checkins = await db.checkins.find(query, {"_id": 0}).sort("created_at", -1).skip(max(0, skip)).to_list(min(limit, 100))
    return [CheckInResponse(**c) for c in checkins]


@router.get("/admin/clients/{client_id}/checkins", response_model=List[CheckInResponse])
async def admin_get_client_checkins(client_id: str, type: Optional[str] = None, limit: int = 60, user = Depends(get_admin_user)):
    query: Dict[str, Any] = {"client_id": client_id}
    if type:
        if type not in VALID_CHECKIN_TYPES:
            raise HTTPException(status_code=400, detail="Tipo invalido")
        query["type"] = type
    checkins = await db.checkins.find(query, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 200))
    return [CheckInResponse(**c) for c in checkins]


@router.post("/admin/clients/{client_id}/checkins/{checkin_id}/feedback")
async def admin_set_checkin_feedback(client_id: str, checkin_id: str, data: dict, user = Depends(get_admin_user)):
    feedback = (data or {}).get("feedback", "")
    result = await db.checkins.update_one(
        {"id": checkin_id, "client_id": client_id},
        {"$set": {"trainer_feedback": feedback}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Check-in no encontrado")

    if feedback.strip():
        profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0, "user_id": 1})
        if profile:
            from routes.notifications import notify
            await notify(profile["user_id"], "feedback", "Tu coach ha comentado tu check-in", "/dashboard/checkins")

    return {"success": True}


@router.get("/admin/clients/{client_id}/health-score")
async def admin_get_health_score(client_id: str, user = Depends(get_admin_user)):
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    checkins = await db.checkins.find(
        {"client_id": client_id, "created_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(60)
    return _compute_health_score(checkins, profile)


@router.get("/health-score")
async def get_my_health_score(user = Depends(get_current_user)):
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    checkins = await db.checkins.find(
        {"client_id": profile["id"], "created_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(60)
    return _compute_health_score(checkins, profile)


# ==================== FOTOS DE PROGRESO ====================
#
# Guardadas como bson.Binary en colección dedicada `client_photos` para no
# inflar los documentos de check-in (límite Mongo 16MB).

MAX_PHOTO_BYTES = 4 * 1024 * 1024  # 4 MB
ALLOWED_PHOTO_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif",
}


def _photo_meta(doc: dict) -> dict:
    """Quita el binario del documento - para respuestas de listado."""
    return {
        "id":           doc.get("id"),
        "client_id":    doc.get("client_id"),
        "user_id":      doc.get("user_id"),
        "filename":     doc.get("filename"),
        "content_type": doc.get("content_type"),
        "size":         doc.get("size"),
        "taken_at":     doc.get("taken_at"),
        "uploaded_at":  doc.get("uploaded_at"),
    }


async def _resolve_client_id_for_user(user: dict) -> Optional[str]:
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    return profile["id"] if profile else None


@router.post("/reports/photos")
async def upload_progress_photo(
    file: UploadFile = File(..., description="Foto de progreso (JPEG, PNG, WebP, HEIC). Máx 4 MB."),
    taken_at: Optional[str] = Query(None, description="Fecha ISO de la foto (por defecto ahora)."),
    user = Depends(get_current_user),
):
    """El cliente sube una foto de progreso. Guardada en `client_photos`. Devuelve metadatos."""
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: {content_type or 'desconocido'}. Sube JPEG, PNG, WebP o HEIC.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(contents) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"La foto pesa {len(contents) // 1024} KB; el máximo permitido es {MAX_PHOTO_BYTES // (1024 * 1024)} MB.",
        )

    client_id = await _resolve_client_id_for_user(user)
    if not client_id:
        raise HTTPException(status_code=400, detail="No se encontró el perfil de cliente.")

    now_iso = datetime.now(timezone.utc).isoformat()
    if taken_at:
        try:
            datetime.fromisoformat(taken_at.replace("Z", "+00:00"))
        except Exception:
            taken_at = None

    doc = {
        "id":           str(uuid.uuid4()),
        "client_id":    client_id,
        "user_id":      user["id"],
        "filename":     file.filename or "photo.jpg",
        "content_type": content_type,
        "size":         len(contents),
        "taken_at":     taken_at or now_iso,
        "uploaded_at":  now_iso,
        "data":         Binary(contents),
    }
    await db.client_photos.insert_one(doc)
    return _photo_meta(doc)


@router.get("/reports/photos")
async def list_my_photos(user = Depends(get_current_user)):
    """Lista las fotos propias del cliente (más recientes primero), solo metadatos."""
    cursor = db.client_photos.find({"user_id": user["id"]}, {"_id": 0, "data": 0}).sort("taken_at", -1)
    photos = await cursor.to_list(length=200)
    return {"photos": photos, "count": len(photos)}


@router.get("/reports/photos/{photo_id}")
async def get_photo(photo_id: str, user = Depends(get_current_user)):
    """Sirve el binario de la foto. El llamante debe ser el dueño o staff."""
    photo = await db.client_photos.find_one({"id": photo_id}, {"_id": 0})
    if not photo:
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    is_owner = photo.get("user_id") == user["id"]
    is_staff = user.get("role") in ("admin", "trainer")
    if not (is_owner or is_staff):
        raise HTTPException(status_code=403, detail="Sin permiso para ver esta foto")

    data = photo.get("data")
    if not data:
        raise HTTPException(status_code=404, detail="Foto sin datos")

    return Response(
        content=bytes(data),
        media_type=photo.get("content_type") or "application/octet-stream",
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'inline; filename="{photo.get("filename") or "photo"}"',
        },
    )


@router.delete("/reports/photos/{photo_id}")
async def delete_photo(photo_id: str, user = Depends(get_current_user)):
    """El dueño o staff borra una foto."""
    photo = await db.client_photos.find_one({"id": photo_id}, {"_id": 0, "user_id": 1, "client_id": 1})
    if not photo:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    is_owner = photo.get("user_id") == user["id"]
    is_staff = user.get("role") in ("admin", "trainer")
    if not (is_owner or is_staff):
        raise HTTPException(status_code=403, detail="Sin permiso para borrar esta foto")
    await db.client_photos.delete_one({"id": photo_id})
    return {"ok": True}


@router.get("/admin/clients/{client_id}/photos")
async def admin_list_client_photos(client_id: str, user = Depends(get_admin_user)):
    """Admin: lista las fotos de un cliente (metadatos, más recientes primero)."""
    cursor = db.client_photos.find({"client_id": client_id}, {"_id": 0, "data": 0}).sort("taken_at", -1)
    photos = await cursor.to_list(length=500)
    return {"photos": photos, "count": len(photos)}
