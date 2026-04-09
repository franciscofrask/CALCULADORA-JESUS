"""
Rutas de mensajes: inbox del chat.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from core.database import db
from core.security import get_current_user
from models.common import MessageCreate, MessageResponse

router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("", response_model=MessageResponse)
async def send_message(data: MessageCreate, user = Depends(get_current_user)):
    """Enviar un mensaje."""
    message_id = str(uuid.uuid4())
    message = {
        "id": message_id,
        "sender_id": user["id"],
        "receiver_id": data.receiver_id,
        "content": data.content,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(message)
    return MessageResponse(**message)

@router.get("", response_model=List[MessageResponse])
async def get_messages(with_user: Optional[str] = None, user = Depends(get_current_user)):
    """Obtener mensajes."""
    query = {"$or": [{"sender_id": user["id"]}, {"receiver_id": user["id"]}]}
    
    if with_user:
        query = {
            "$or": [
                {"sender_id": user["id"], "receiver_id": with_user},
                {"sender_id": with_user, "receiver_id": user["id"]}
            ]
        }
    
    messages = await db.messages.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [MessageResponse(**m) for m in messages]

@router.put("/{message_id}/read")
async def mark_message_read(message_id: str, user = Depends(get_current_user)):
    """Marcar mensaje como leído."""
    await db.messages.update_one(
        {"id": message_id, "receiver_id": user["id"]},
        {"$set": {"read": True}}
    )
    return {"success": True}

@router.get("/unread-count")
async def get_unread_count(user = Depends(get_current_user)):
    """Obtener cantidad de mensajes no leídos."""
    count = await db.messages.count_documents({"receiver_id": user["id"], "read": False})
    return {"count": count}
