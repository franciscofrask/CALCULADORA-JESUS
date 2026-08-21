"""
Rutas de mensajes: inbox del chat.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from core.config import SUPPORT_EMAILS
from core.database import db
from core.security import get_current_user, get_admin_user
from models.common import MessageCreate, MessageResponse
from routes.notifications import notify

router = APIRouter(prefix="/messages", tags=["messages"])


async def _resolve_receiver(user: dict, receiver_id: Optional[str]) -> str:
    """Traduce el destinatario 'support' (o vacio) a una persona real:
    el coach del cliente si tiene, o el primer admin como soporte.
    Nunca se resuelve a uno mismo: un admin probando en modo cliente acababa
    chateando consigo y todos los mensajes salían en el mismo lado."""
    if receiver_id and receiver_id != "support":
        return receiver_id
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "trainer_id": 1})
    if profile and profile.get("trainer_id") and profile["trainer_id"] != user["id"]:
        return profile["trainer_id"]
    for email in SUPPORT_EMAILS:
        support_user = await db.users.find_one(
            {"email": email, "deleted_at": None, "id": {"$ne": user["id"]}},
            {"_id": 0, "id": 1},
        )
        if support_user:
            return support_user["id"]
    admin_user = await db.users.find_one(
        {"role": "admin", "deleted_at": None, "id": {"$ne": user["id"]}},
        {"_id": 0, "id": 1}, sort=[("created_at", 1)]
    )
    if not admin_user:
        admin_user = await db.users.find_one(
            {"role": "trainer", "deleted_at": None, "id": {"$ne": user["id"]}},
            {"_id": 0, "id": 1}, sort=[("created_at", 1)]
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
    # El canal del mensaje (doc 21-08): por cuál de las dos entradas del Chat entró.
    # Solo los dos valores conocidos; cualquier otra cosa se ignora y el mensaje queda
    # como los de siempre, que es lo que son los mensajes viejos y los del staff.
    if data.canal in ("suscripcion", "tecnico"):
        message["canal"] = data.canal
    await db.messages.insert_one(message)

    # Avisar a quien lo recibe. Hasta hoy el mensaje se guardaba y ya: le escribías a un
    # cliente de 897 o de 1.500 y se enteraba SI entraba por su cuenta. Y ese es el canal
    # por el que se le acompaña.
    #
    # Se avisa en las dos direcciones: al cliente cuando le escribe su coach, y al coach
    # cuando le escribe un cliente, que es el que no puede quedarse sin contestar.
    quien = (user.get("name") or "").strip()
    de_staff = user.get("role") in ("admin", "trainer")
    titulo = (f"{quien} te ha escrito" if quien else "Tienes un mensaje nuevo" if de_staff
              else f"{quien or 'Un cliente'} te ha escrito")
    # El propio mensaje va en el cuerpo, recortado: se lee en la campana sin tener que
    # entrar, y si es largo se entra.
    texto = (data.content or "").strip()
    # El enlace es el del que RECIBE: si escribe el coach, el cliente va a su panel de
    # mensajes; si escribe el cliente, el coach va al suyo, que es otra pantalla.
    destino = "/dashboard/messages" if de_staff else "/admin/messages"
    await notify(receiver_id, "mensaje", titulo, destino,
                 body=(texto[:140] + "…") if len(texto) > 140 else texto)

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
    """Bandeja del staff: una entrada por cliente con el que hay conversación, con el
    último mensaje, cuántos están sin leer y si se quedó esperando respuesta.

    LA BANDEJA ENSEÑABA UNA SOLA CONVERSACIÓN.

    Jesús, 11-08: *«la bandeja tiene una sola conversación con más de 228 clientes»*. No es
    que nadie escriba -- en la base hay cien conversaciones abiertas --: es que esta
    consulta solo traía aquellas en las que el que mira es una de las dos partes, y el
    equipo ve a todos los clientes desde el 21-07. Así que cada uno entraba y veía las
    suyas, y las de los demás no las veía nadie.

    Ahora se trae la bandeja del equipo entera y se dice quién contestó por última vez.
    """
    staff_ids = set(await db.users.distinct("id", {"role": {"$in": ["admin", "trainer"]}}))
    msgs = await db.messages.find(
        {"$or": [{"sender_id": {"$in": list(staff_ids)}},
                 {"receiver_id": {"$in": list(staff_ids)}}]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20000)

    convs: Dict[str, Any] = {}
    for m in msgs:
        emisor, receptor = m["sender_id"], m["receiver_id"]
        # La conversación se archiva por el cliente. Entre dos del equipo, por el otro.
        if emisor in staff_ids and receptor in staff_ids:
            otro = receptor if emisor == user["id"] else emisor
        else:
            otro = receptor if emisor in staff_ids else emisor
        if otro == user["id"]:
            continue
        c = convs.get(otro)
        if c is None:
            # Los mensajes vienen del más nuevo al más viejo, así que el primero que se ve
            # de cada conversación es el último que se escribió.
            c = convs[otro] = {
                "user_id": otro, "last_message": m, "unread": 0,
                # EL QUE SE PIERDE ES EL QUE NADIE VE: si el último en hablar fue el
                # cliente, esa conversación está esperando a alguien.
                "sin_respuesta": emisor not in staff_ids,
                "ultimo_de": "cliente" if emisor not in staff_ids else "equipo",
            }
        if receptor == user["id"] and not m.get("read"):
            c["unread"] += 1

    users = await db.users.find(
        {"id": {"$in": list(convs.keys())}}, {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1}
    ).to_list(2000)
    umap = {u["id"]: u for u in users}
    # Las conversaciones con gente que ya no existe se quedaban en la bandeja como
    # "Usuario eliminado" -- en dev son tres, restos del simulador --. No se les puede
    # contestar, así que no son bandeja de entrada: son ruido delante de las que sí.
    out = [{**c, "user": umap[uid]} for uid, c in convs.items() if uid in umap]
    # Las que esperan respuesta, arriba; dentro de cada grupo, la más reciente primero.
    # En dos pasadas porque el orden de Python es estable: la segunda respeta la primera.
    out.sort(key=lambda c: c["last_message"]["created_at"] or "", reverse=True)
    out.sort(key=lambda c: not c["sin_respuesta"])
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
