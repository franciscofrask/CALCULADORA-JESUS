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
from typing import Any, Dict, List, Optional


# EL CATALOGO DE LO QUE SE LE PUEDE AVISAR AL EQUIPO.
#
# Existe porque los avisos del equipo y los del cliente comparten coleccion
# (`db.notifications`) y solo se distinguen por el `type`. Sin esta lista, la campanita del
# panel tendria que adivinar cuales son suyos, y el dia que alguien anada un aviso nuevo se
# quedaria fuera sin que nadie se entere.
#
# `dinero` marca los que son una venta: o el cliente esta pidiendo comprar algo, o ya ha
# pagado y falta darselo. Esos se pintan aparte y arriba del todo. Perder uno no es perder
# un recordatorio, es perder un cobro.
TIPOS_EQUIPO: Dict[str, Dict[str, Any]] = {
    "rutina_del_mes": {"etiqueta": "Quiere comprar la rutina del mes", "dinero": True},
    "interes_plan": {"etiqueta": "Quiere que le cuentes el plan de arriba", "dinero": True},
    "revision_suelta_pagada": {"etiqueta": "Revisión de macros pagada", "dinero": True},
    "lead_pagado": {"etiqueta": "Lead que ha pagado", "dinero": True},
    "macros_propuestos": {"etiqueta": "Macros propuestos por el cuestionario", "dinero": False},
    "perfil_completo": {"etiqueta": "Cuestionario largo relleno", "dinero": False},
}

# Los que hay que mirar antes que nada, en el orden en que se pintan.
TIPOS_DE_DINERO: List[str] = [t for t, d in TIPOS_EQUIPO.items() if d["dinero"]]


def es_de_dinero(tipo: Optional[str]) -> bool:
    """¿Este aviso es una venta esperando a que alguien la atienda?"""
    return bool(TIPOS_EQUIPO.get(tipo or "", {}).get("dinero"))


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
        # La marca de que esto es del EQUIPO y no del cliente. El `type` ya lo dice (ver
        # TIPOS_EQUIPO), pero un tipo nuevo que alguien anada sin acordarse de apuntarlo
        # arriba se quedaria fuera de la campanita del panel y nadie lo notaria: con la
        # marca puesta aqui, cualquier aviso que salga de esta funcion se pinta si o si.
        # Los que ya estaban escritos antes de que existiera la marca entran por el `type`.
        "equipo": True,
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
