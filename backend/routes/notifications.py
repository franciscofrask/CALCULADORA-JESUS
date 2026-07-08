"""
Notificaciones in-app del cliente ("campanita"): eventos que el coach genera y el
cliente debe conocer (rutina nueva, macros, feedback, suplementos, cambio de coach).
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from typing import Optional
import uuid

from core.database import db
from core.security import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def notify(user_id: str, type: str, title: str, link: Optional[str] = None):
    """Crea una notificación para un usuario. Falla en silencio: un aviso nunca
    debe romper la operación principal (asignar coach, guardar macros...)."""
    if not user_id:
        return
    try:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": type,
            "title": title,
            "link": link,
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


@router.get("")
async def list_notifications(user = Depends(get_current_user)):
    """Últimas notificaciones del usuario actual."""
    items = await db.notifications.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(30)
    return {"notifications": items}


@router.get("/unread-count")
async def unread_count(user = Depends(get_current_user)):
    count = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"count": count}


@router.put("/read-all")
async def mark_all_read(user = Depends(get_current_user)):
    result = await db.notifications.update_many(
        {"user_id": user["id"], "read": False}, {"$set": {"read": True}}
    )
    return {"ok": True, "marked": result.modified_count}
