"""
Revision de macros por entrenador comprada suelta (seccion 6 del doc del 29-07).

Un cliente que se autogestiona calcula sus macros solo y nadie se los mira. Esto le deja pagar
una vez para que un entrenador se los revise, sin cambiar de plan. Es una puerta de entrada:
prueba lo que se siente teniendo a alguien detras, y si sube de plan en los 30 dias siguientes
se le descuenta lo que pago.

"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

# ── PRECIO ────────────────────────────────────────────────────────────────────
# 147 EUR, cerrado en la especificacion del 31-07-2026 (parte 1). Antes era un 29
# provisional puesto para poder probar el circuito de cobro.
# Subirlo no toca a quien ya compro: el importe que se le cobro se guarda en su perfil
# (`revision_suelta.importe_eur`) y el descuento posterior sale de ahi, no de aqui.
PRECIO_EUR = 147.0
DIAS_PARA_DESCONTAR = 30
NOMBRE_PRODUCTO = "Revisión de macros por entrenador"


def importe_centimos() -> int:
    return int(round(PRECIO_EUR * 100))


async def activar_tras_pago(profile: Dict, importe_eur: Optional[float] = None) -> bool:
    """
    El pago ha entrado: se le busca entrenador y se le deja la revision pendiente, con sus macros
    de ahora y las respuestas que dio. Es el mismo circuito que el del plan con coach, solo que
    disparado por una compra.

    Devuelve si se ha creado (False si ya estaba activa, para no duplicar por un webhook repetido).
    """
    import uuid

    from core.database import db
    from core.avisos_equipo import avisar_al_equipo

    actual = profile.get("revision_suelta") or {}
    if actual.get("estado") in ("pendiente", "hecha"):
        return False

    # Si no tiene entrenador asignado, la revision queda sin dueño y la coge cualquiera del equipo:
    # es mejor eso que dejarla esperando a una asignacion que quiza no llega.
    coach_id = profile.get("trainer_id")
    ahora = datetime.now(timezone.utc).isoformat()
    client_id = profile.get("id")

    await db.macro_sugerencias.insert_one({
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "user_id": profile.get("user_id"),
        "origen": "revision_suelta",
        "estado": "pendiente",
        "actuales": {
            "macros_training": profile.get("macros_training"),
            "macros_rest": profile.get("macros_rest"),
            "macros_periworkout": profile.get("macros_periworkout"),
        },
        "respuestas": profile.get("ajustes_macros"),
        "created_at": ahora,
    })

    # Con coach, a su coach; sin coach, a todo el staff. La regla vivía aquí y ahora está
    # en core/avisos_equipo.py, compartida con los avisos del cuestionario.
    await avisar_al_equipo(
        db,
        tipo="revision_suelta_pagada",
        titulo="Revisión de macros pagada",
        mensaje=f"{profile.get('name') or 'Un cliente'} ha pagado una revisión de sus macros. "
                f"Revísalos y aplícaselos.",
        client_id=client_id,
        trainer_id=coach_id,
    )

    await db.client_profiles.update_one(
        {"id": client_id},
        {"$set": {"revision_suelta": {
            **actual,
            "estado": "pendiente",
            "importe_eur": float(importe_eur if importe_eur is not None else PRECIO_EUR),
            "pagada_at": ahora,
            "descuento_aplicado": False,
        }}},
    )
    return True


def descuento_vigente(profile: Dict, ahora: Optional[datetime] = None) -> Optional[Dict]:
    """
    Si compro una revision hace menos de 30 dias y todavia no se le ha descontado, devuelve
    cuanto le corresponde descontar al subir de plan. None si no le toca nada.
    """
    compra = (profile or {}).get("revision_suelta") or {}
    if not compra.get("pagada_at") or compra.get("descuento_aplicado"):
        return None
    try:
        pagada = datetime.fromisoformat(str(compra["pagada_at"]).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if pagada.tzinfo is None:
        pagada = pagada.replace(tzinfo=timezone.utc)

    ahora = ahora or datetime.now(timezone.utc)
    caduca = pagada + timedelta(days=DIAS_PARA_DESCONTAR)
    if ahora > caduca:
        return None
    return {
        "importe_eur": float(compra.get("importe_eur") or PRECIO_EUR),
        "caduca": caduca.strftime("%Y-%m-%d"),
        "dias_restantes": max(0, (caduca - ahora).days),
    }
