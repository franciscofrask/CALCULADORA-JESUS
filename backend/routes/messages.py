"""
Rutas de mensajes: inbox del chat.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from core.database import db
from core.security import get_current_user, get_admin_user
from models.common import MessageCreate, MessageResponse

router = APIRouter(prefix="/messages", tags=["messages"])


async def _resolve_receiver(user: dict, receiver_id: Optional[str]) -> str:
    """Traduce el destinatario 'support' (o vacio) a una persona real:
    el coach del cliente si tiene, o el primer admin como soporte."""
    if receiver_id and receiver_id != "support":
        return receiver_id
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "trainer_id": 1})
    if profile and profile.get("trainer_id"):
        return profile["trainer_id"]
    admin_user = await db.users.find_one(
        {"role": "admin", "deleted_at": None}, {"_id": 0, "id": 1}, sort=[("created_at", 1)]
    )
    if not admin_user:
        raise HTTPException(status_code=500, detail="No hay ningún admin para recibir el mensaje")
    return admin_user["id"]


@router.post("", response_model=MessageResponse)
async def send_message(data: MessageCreate, user = Depends(get_current_user)):
    """Enviar un mensaje."""
    receiver_id = await _resolve_receiver(user, data.receiver_id)
    message_id = str(uuid.uuid4())
    message = {
        "id": message_id,
        "sender_id": user["id"],
        "receiver_id": receiver_id,
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
        if with_user == "support":
            with_user = await _resolve_receiver(user, "support")
        query = {
            "$or": [
                {"sender_id": user["id"], "receiver_id": with_user},
                {"sender_id": with_user, "receiver_id": user["id"]}
            ]
        }

    messages = await db.messages.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [MessageResponse(**m) for m in messages]


@router.get("/conversations")
async def get_conversations(user = Depends(get_admin_user)):
    """Bandeja del staff: una entrada por persona con la que hay conversación,
    con último mensaje y cuántos están sin leer."""
    msgs = await db.messages.find(
        {"$or": [{"sender_id": user["id"]}, {"receiver_id": user["id"]}]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(5000)

    convs = {}
    for m in msgs:
        other = m["receiver_id"] if m["sender_id"] == user["id"] else m["sender_id"]
        c = convs.setdefault(other, {"user_id": other, "last_message": m, "unread": 0})
        if m["receiver_id"] == user["id"] and not m.get("read"):
            c["unread"] += 1

    users = await db.users.find(
        {"id": {"$in": list(convs.keys())}}, {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1}
    ).to_list(1000)
    umap = {u["id"]: u for u in users}
    out = [{**c, "user": umap.get(uid, {"id": uid, "name": "Usuario eliminado", "email": ""})}
           for uid, c in convs.items()]
    out.sort(key=lambda c: c["last_message"]["created_at"], reverse=True)
    return out


@router.put("/read-all")
async def mark_conversation_read(with_user: str, user = Depends(get_current_user)):
    """Marca como leídos todos los mensajes recibidos de un usuario."""
    result = await db.messages.update_many(
        {"sender_id": with_user, "receiver_id": user["id"], "read": False},
        {"$set": {"read": True}}
    )
    return {"ok": True, "marked": result.modified_count}

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
