"""
Rutas de mensajes: inbox del chat.
"""
from fastapi import APIRouter, HTTPException, Depends, File, Response, UploadFile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from bson import Binary

from core import fotos as fotos_core
from core.config import SUPPORT_EMAILS
from core.database import db
from core.security import get_current_user, get_admin_user
from models.common import MessageCreate, MessageResponse
from routes.notifications import notify

router = APIRouter(prefix="/messages", tags=["messages"])

# ADJUNTOS DEL CHAT: SOLO IMÁGENES (Francisco, 25-08: «ambos chats deben permitir la carga
# de imágenes adjuntas»).
#
# Los mismos tipos y el mismo tope que las fotos de progreso (routes/checkins), y por lo
# mismo: es lo que sale de la cámara de un móvil. Deliberadamente NO se aceptan PDF ni
# ficheros sueltos: lo que se ha pedido son imágenes, y un buzón de archivos hay que
# vigilarlo (qué se guarda, cuánto ocupa, quién lo borra) y eso no está construido.
TIPOS_DE_IMAGEN = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif",
}
MAX_ADJUNTO_BYTES = 4 * 1024 * 1024  # 4 MB


async def _ids_de_soporte(excluir: Optional[str] = None) -> List[str]:
    """Las cuentas de soporte que existen de verdad, en el orden de `SUPPORT_EMAILS`.

    El mensaje se guarda a nombre de UNA -- la primera --, porque una conversación tiene
    dos partes; pero el aviso va a todas (ver `send_message`). La bandeja del equipo es
    común desde el 11-08, así que cualquiera de ellas puede abrirla y contestar.
    """
    ids: List[str] = []
    for email in SUPPORT_EMAILS:
        u = await db.users.find_one(
            {"email": email, "deleted_at": None, "id": {"$ne": excluir}},
            {"_id": 0, "id": 1},
        )
        if u and u["id"] not in ids:
            ids.append(u["id"])
    return ids


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
    soporte = await _ids_de_soporte(excluir=user["id"])
    if soporte:
        return soporte[0]
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


@router.post("/adjunto")
async def subir_adjunto(
    file: UploadFile = File(..., description="Imagen del chat (JPEG, PNG, WebP, HEIC). Máx 4 MB."),
    user = Depends(get_current_user),
):
    """Sube la imagen ANTES de mandar el mensaje y devuelve su id.

    En dos pasos a propósito: así el que escribe ve la miniatura y puede quitarla o
    cambiarla antes de enviar, y el mensaje sigue siendo JSON como siempre. El id que
    devuelve viaja luego en `adjunto_id` al crear el mensaje.

    Mientras no se mande el mensaje, la imagen queda huérfana y solo la ve quien la subió:
    no está enganchada a ninguna conversación.
    """
    content_type = (file.content_type or "").lower()
    if content_type not in TIPOS_DE_IMAGEN:
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden adjuntar imágenes (JPEG, PNG, WebP o HEIC).")

    contenido = await file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(contenido) > MAX_ADJUNTO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"La imagen pesa {len(contenido) // 1024} KB y el máximo son "
                   f"{MAX_ADJUNTO_BYTES // (1024 * 1024)} MB.")

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "filename": file.filename or "imagen.jpg",
        "content_type": content_type,
        "size": len(contenido),
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Se rellena al mandarlo: hasta entonces no pertenece a ninguna conversación.
        "message_id": None,
    }
    # MISMO CAMINO QUE LAS FOTOS DE PROGRESO: a R2 si hay credenciales, y si no el binario
    # en Mongo. Sin esto los adjuntos engordarían la base igual que engordaron las fotos
    # (906 MB antes de moverlas), y con la ventaja de que la caída ya está probada.
    clave = await fotos_core.subir_foto_nueva(
        user_id=user["id"], client_id=user["id"], photo_id=doc["id"],
        contenido=contenido, content_type=content_type)
    if clave:
        doc["en_r2"] = True
        doc["r2_key"] = clave
    else:
        doc["data"] = Binary(contenido)
    await db.message_files.insert_one(doc)
    return {"id": doc["id"], "filename": doc["filename"],
            "content_type": doc["content_type"], "size": doc["size"]}


@router.get("/adjunto/{adjunto_id}")
async def ver_adjunto(adjunto_id: str, user = Depends(get_current_user)):
    """Sirve la imagen. Solo el que la subió, el que la recibe, o el equipo.

    El equipo entra porque la bandeja es común desde el 11-08 y el hilo desde el 24-08: si
    cualquiera del equipo puede LEER la conversación, esconderle la foto que va dentro
    dejaría el mensaje a medias. Un cliente solo ve las de sus propias conversaciones.
    """
    doc = await db.message_files.find_one({"id": adjunto_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="No encontramos esa imagen.")

    permitido = doc.get("user_id") == user["id"]
    if not permitido and user.get("role") in ("admin", "trainer"):
        permitido = True
    if not permitido and doc.get("message_id"):
        # El destinatario del mensaje al que va pegada.
        msg = await db.messages.find_one({"id": doc["message_id"]},
                                         {"_id": 0, "sender_id": 1, "receiver_id": 1})
        permitido = bool(msg) and user["id"] in (msg.get("sender_id"), msg.get("receiver_id"))
    if not permitido:
        raise HTTPException(status_code=403, detail="Esta imagen no es de una conversación tuya.")

    data, content_type = await fotos_core.leer_binario_de_foto_app(doc)
    return Response(
        content=data, media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600",
                 "Content-Disposition": f'inline; filename="{doc.get("filename") or "imagen"}"'},
    )


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

    # LA IMAGEN QUE SE SUBIÓ ANTES. Solo se engancha si es SUYA y todavía está suelta: sin
    # esas dos comprobaciones, mandar un id ajeno colaría la foto de otra conversación
    # dentro de la propia, y reenviar un id ya usado la movería de sitio.
    if data.adjunto_id:
        adj = await db.message_files.find_one(
            {"id": data.adjunto_id, "user_id": user["id"], "message_id": None},
            {"_id": 0, "id": 1, "filename": 1, "content_type": 1, "size": 1})
        if not adj:
            raise HTTPException(
                status_code=400,
                detail="Esa imagen ya no está disponible. Vuelve a adjuntarla.")
        message["adjunto"] = {"id": adj["id"], "filename": adj.get("filename"),
                              "content_type": adj.get("content_type"),
                              "size": adj.get("size")}

    await db.messages.insert_one(message)
    if message.get("adjunto"):
        await db.message_files.update_one({"id": message["adjunto"]["id"]},
                                          {"$set": {"message_id": message_id}})

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
    # entrar, y si es largo se entra. Una imagen sola no tiene texto que enseñar, así que
    # se dice lo que es: «Sin texto» en la campana no cuenta nada.
    texto = (data.content or "").strip()
    if not texto and message.get("adjunto"):
        texto = "📷 Te ha enviado una imagen"
    # El enlace es el del que RECIBE: si escribe el coach, el cliente va a su panel de
    # mensajes; si escribe el cliente, el coach va al suyo, que es otra pantalla.
    destino = "/dashboard/messages" if de_staff else "/admin/messages"
    # SI VA A SOPORTE, LES SUENA A LAS TRES (Francisco, 25-08). El mensaje se guarda a
    # nombre de una sola -- una conversación tiene dos partes --, pero avisar solo a esa
    # dejaba el soporte colgando de una persona: si ese día no entra, nadie se entera. La
    # bandeja del equipo es común, así que la que lo vea primero contesta.
    soporte = await _ids_de_soporte(excluir=user["id"])
    a_quienes = soporte if receiver_id in soporte else [receiver_id]
    cuerpo = (texto[:140] + "…") if len(texto) > 140 else texto
    for uid in a_quienes:
        await notify(uid, "mensaje", titulo, destino, body=cuerpo)

    return MessageResponse(**message)

@router.get("", response_model=List[MessageResponse])
async def get_messages(with_user: Optional[str] = None, user = Depends(get_current_user)):
    """Obtener mensajes."""
    query = {"$or": [{"sender_id": user["id"]}, {"receiver_id": user["id"]}]}

    if with_user:
        if with_user == "support":
            with_user = await _resolve_receiver(user, "support")

        # SI LA BANDEJA ES COMPARTIDA, EL HILO TAMBIÉN (24-08).
        #
        # `GET /messages/conversations` trae la bandeja del equipo ENTERO desde el 11-08,
        # pero este hilo seguía filtrando por quien mira. Resultado: alguien del equipo
        # abría una conversación de la lista -- normalmente de otro compañero, porque al
        # cliente sin coach se le resuelve al primer admin -- y leía «Sin mensajes con
        # este cliente», con el botón de responder al lado. Se podía contestar sin haber
        # podido leer lo que el cliente escribió.
        #
        # Se ensancha SOLO cuando el que mira es del equipo y el otro NO lo es: entre dos
        # del equipo la conversación sigue siendo de los dos, y un cliente nunca ve nada
        # que no sea suyo.
        del_equipo = set(await db.users.distinct("id", {"role": {"$in": ["admin", "trainer"]}}))
        if user["id"] in del_equipo and with_user not in del_equipo:
            query = {
                "$or": [
                    {"sender_id": with_user, "receiver_id": {"$in": list(del_equipo)}},
                    {"sender_id": {"$in": list(del_equipo)}, "receiver_id": with_user},
                ]
            }
        else:
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

    # ¿ESTA CONVERSACIÓN ES DE SOPORTE O ES DE ALGUIEN? (Francisco, 25-08: «si es un chat
    # de soporte, ¿hay algún diferenciador?». No lo había.)
    #
    # La bandeja es común para los quince del equipo y todas las conversaciones se veían
    # iguales. Con el soporte repartido entre tres personas eso deja de valer: hace falta
    # saber de un vistazo cuáles son «de nadie» -- cliente sin entrenador, o sea de la
    # cola de soporte -- y cuáles son de un compañero, para no contestar encima suyo.
    #
    # El chip `canal` que ya existía no responde a esto: dice de qué va la consulta
    # («Mi suscripción», «Algo no funciona»), no de quién es la conversación.
    perfiles = await db.client_profiles.find(
        {"user_id": {"$in": list(convs.keys())}},
        {"_id": 0, "user_id": 1, "trainer_id": 1},
    ).to_list(3000)
    entrenador_de = {p["user_id"]: p.get("trainer_id") for p in perfiles}
    nombres_staff = {u["id"]: u.get("name") for u in await db.users.find(
        {"id": {"$in": [t for t in entrenador_de.values() if t]}},
        {"_id": 0, "id": 1, "name": 1}).to_list(200)}

    # Las conversaciones con gente que ya no existe se quedaban en la bandeja como
    # "Usuario eliminado" -- en dev son tres, restos del simulador --. No se les puede
    # contestar, así que no son bandeja de entrada: son ruido delante de las que sí.
    out = []
    for uid, c in convs.items():
        if uid not in umap:
            continue
        entrenador = entrenador_de.get(uid)
        out.append({
            **c,
            "user": umap[uid],
            # Sin entrenador asignado, la conversación es de la cola de soporte. Es la
            # misma cuenta que hace `_resolve_receiver` al mandar el mensaje.
            "es_soporte": not entrenador,
            "entrenador_nombre": nombres_staff.get(entrenador) if entrenador else None,
        })
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
