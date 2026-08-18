"""El ajuste a medida de 87 EUR (bloque 6 del doc del cuestionario, 18-08).

Es la oferta que se le hace al final del alta a quien NO lleva entrenador:

    «Puedes continuar con tu plan actual... o puedes solicitar tus macros personalizados y
    recibir tu ajuste a medida. Esta segunda opcion no esta incluida en tu plan, tiene un
    coste adicional e incluye tambien tu plan personalizado de suplementacion.»

Las tres decisiones que faltaban las cierra Francisco el 18-08:

    SE COBRA POR STRIPE .......... aqui mismo, en el momento, como la revision suelta.
    ENTRA EN LA COLA DE LOS LUNES  el equipo lo prepara para el lunes que le toca, con la
                                   misma regla de las 48 horas que el alta.
    SE PUEDE REPETIR ............. no es una compra de una sola vez en la vida. Lo que no
                                   se puede es tener dos pendientes a la vez.

QUE ABRE, ADEMAS DEL COBRO: `ajuste_a_medida.cobrado` es lo que le abre el cuestionario
completo, «exactamente igual que un Gold» (regla que ordena el documento).

NO SE LE ASIGNA ENTRENADOR AUTOMATICAMENTE: eso no lo decidio nadie, y el aviso al equipo
va a su coach si lo tiene y a todo el staff si no, que es como funciona la revision suelta.
"""
from datetime import datetime, timezone
from typing import Dict, Optional

# 87 EUR, el precio que dice el texto de la propia pantalla. Si cambia, cambia aqui: lo que
# se le cobro a cada uno queda guardado en su perfil, asi que subirlo no toca a los de antes.
PRECIO_EUR = 87.0
NOMBRE_PRODUCTO = "Ajuste a medida de tus macros"
DESCRIPCION = "Tus macros personalizados por un entrenador y tu plan de suplementación."


def importe_centimos() -> int:
    return int(round(PRECIO_EUR * 100))


def hay_uno_pendiente(profile: Dict) -> bool:
    """Si ya tiene uno pagado y sin entregar. Repetir si, dos a la vez no."""
    a = (profile or {}).get("ajuste_a_medida") or {}
    return bool(a.get("cobrado")) and a.get("estado") not in ("entregado", "cancelado")


async def activar_tras_pago(profile: Dict, importe_eur: Optional[float] = None) -> bool:
    """El pago ha entrado: entra en la cola del lunes y el equipo se entera.

    Devuelve si se ha activado (False si ya estaba, para que un webhook repetido no lo
    duplique ni le mueva la fecha de la cola).
    """
    import uuid

    from core.avisos_equipo import avisar_al_equipo
    from core.calendario_arranque import lunes_de_arranque
    from core.database import db

    if hay_uno_pendiente(profile):
        return False

    ahora = datetime.now(timezone.utc)
    lunes = lunes_de_arranque(ahora)
    client_id = profile.get("id")

    # La cola del equipo es la misma que la de la revision suelta: una sugerencia pendiente
    # con los macros de ahora y lo que contesto. Asi el ajuste a medida no inventa un
    # circuito nuevo, entra por donde ya se trabaja.
    await db.macro_sugerencias.insert_one({
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "user_id": profile.get("user_id"),
        "origen": "ajuste_a_medida",
        "estado": "pendiente",
        "para_el_lunes": lunes.date().isoformat(),
        "actuales": {
            "macros_training": profile.get("macros_training"),
            "macros_rest": profile.get("macros_rest"),
            "macros_periworkout": profile.get("macros_periworkout"),
        },
        "respuestas": profile.get("ajustes_macros"),
        "created_at": ahora.isoformat(),
    })

    await avisar_al_equipo(
        db,
        tipo="ajuste_a_medida_pagado",
        titulo="Ajuste a medida pagado",
        mensaje=f"{profile.get('name') or 'Un cliente'} ha pagado su ajuste a medida "
                f"({PRECIO_EUR:.0f} €). Entra en la cola del lunes "
                f"{lunes.strftime('%d/%m')}: macros y suplementación.",
        client_id=client_id,
        trainer_id=profile.get("trainer_id"),
    )

    anterior = (profile.get("ajuste_a_medida") or {})
    await db.client_profiles.update_one(
        {"id": client_id},
        {"$set": {"ajuste_a_medida": {
            **anterior,
            "quiere": True,
            "cobrado": True,
            "estado": "pendiente",
            "importe_eur": float(importe_eur if importe_eur is not None else PRECIO_EUR),
            "pagado_at": ahora.isoformat(),
            "para_el_lunes": lunes.date().isoformat(),
            # Cuantos lleva comprados: se puede repetir, y saber si va por el primero o por
            # el cuarto cambia lo que se le escribe.
            "veces": int(anterior.get("veces") or 0) + 1,
        }}},
    )
    return True
