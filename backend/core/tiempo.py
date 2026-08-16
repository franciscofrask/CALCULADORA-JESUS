"""
La hora de España, en un solo sitio (doc 16-08, regla 1: "Todo en hora de España.
Nada en UTC").

Mongo sigue guardando UTC; aquí se convierte en los bordes: las ventanas de los
reportes, los avisos con hora fija y los textos tipo "a las 18:00 h España". El
desfase con UTC no es constante (una hora en invierno, dos en verano), así que
nada de sumar horas a mano: siempre por la zona.
"""
from datetime import date, datetime, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")


def ahora_madrid() -> datetime:
    """El ahora en hora de España, con zona."""
    return datetime.now(MADRID)


def hoy_madrid() -> date:
    """El día de hoy PARA EL CLIENTE. A las 23:30 de Madrid en UTC ya es mañana:
    todo lo que corte por día (el cierre del día, "te quedan 2 días") usa esto."""
    return ahora_madrid().date()


def a_madrid(valor: Union[datetime, str, None]) -> Optional[datetime]:
    """Convierte un datetime o un ISO (lo que guarda Mongo) a hora de España.

    Sin zona se asume UTC, que es como escribe todo el backend. Devuelve None si
    no hay valor o no se entiende: quien pinta una hora ya sabe vivir sin ella.
    """
    if valor is None:
        return None
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(MADRID)


def a_utc(valor: datetime) -> datetime:
    """El camino de vuelta: de hora de España (o cualquier zona) a UTC para guardar."""
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=MADRID)
    return valor.astimezone(timezone.utc)
