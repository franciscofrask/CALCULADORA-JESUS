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
    si no tiene                     -> se avisa a TODO el staff, para que lo coja alguien.

Un aviso que no se envia a nadie es peor que no tener avisos: hace creer que el circuito
funciona.
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

    Devuelve a cuanta gente se le ha dejado (0 solo si no hay ni entrenador ni staff,
    que en una base sana no pasa; quien llame puede registrarlo si le importa).
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

    enviados = 0
    async for u in db.users.find({"role": {"$in": ["admin", "trainer"]}}, {"_id": 0, "id": 1}):
        await db.notifications.insert_one({**base, "id": str(uuid.uuid4()), "user_id": u["id"]})
        enviados += 1
    return enviados
