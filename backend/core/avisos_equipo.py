"""
Los avisos que le llegan al EQUIPO por la campanita (los del cliente estan en
avisos_cliente.py).

Existe por un fallo que estuvo meses en pie: el cuestionario avisaba al coach del
cliente... dentro de un `if profile.get("trainer_id")`. Como nada asigna entrenador al
registrarse ni al pagar, en produccion habia 168 cuestionarios completados y CERO avisos.
El cliente leia "tus datos ya estan con tu coach" y no habia ni coach ni dato que mirar.

La regla, que es la que ya usaba el pago de la revision suelta y que aqui se centraliza
para que no vuelva a haber dos versiones de lo mismo:

    si el cliente tiene entrenador  -> se avisa a su entrenador,
    si no tiene                     -> se avisa a los ADMINISTRADORES, que son los que
                                       reparten, para que se lo asignen a alguien.

Un aviso que no se envia a nadie es peor que no tener avisos: hace creer que el circuito
funciona.

CADA ENTRENADOR SOLO OYE LO DE SUS CLIENTES (14-08-2026). Antes, el cliente sin entrenador
avisaba a TODO el staff -- administradores y entrenadores --, y como en produccion casi nadie
tiene entrenador puesto, en la practica cada entrenador recibia los avisos de todos los
clientes de la casa. Un buzon con cosas que no son tuyas se deja de mirar, y entonces el dia
que llega la tuya tampoco la ves.

Ver la ficha de cualquier cliente y tocarla se sigue pudiendo, que es otra cosa: eso es un
permiso y esto es a quien se le da un toque.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


async def avisar_al_equipo(
    db,
    *,
    tipo: str,
    titulo: str,
    mensaje: str,
    client_id: Optional[str] = None,
    trainer_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> int:
    """Deja el aviso en la campanita de quien tenga que verlo.

    Devuelve a cuanta gente se le ha dejado (0 solo si no hay ni entrenador ni
    administradores, que en una base sana no pasa; quien llame puede registrarlo si le
    importa).
    """
    base = {
        "type": tipo,
        "title": titulo,
        "message": mensaje,
        "client_id": client_id,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }

    if trainer_id:
        await db.notifications.insert_one({**base, "id": str(uuid.uuid4()), "user_id": trainer_id})
        return 1

    # Sin entrenador asignado el aviso es de quien reparte, no de todos.
    enviados = 0
    async for u in db.users.find({"role": "admin"}, {"_id": 0, "id": 1}):
        await db.notifications.insert_one({**base, "id": str(uuid.uuid4()), "user_id": u["id"]})
        enviados += 1
    return enviados
