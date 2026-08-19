"""
La semana de RUTINA, separada de la semana de plan (doc del 19-08, apartado 02).

    «La semana de rutina, separada de la semana de plan. El quincenal se abre en la
     semana 2 de la rutina, no de su ciclo. Son dos contadores distintos y hoy solo hay
     uno.»

El ciclo cuenta desde que el cliente paga; la rutina, desde que su rutina arranca. Se
parecen la primera vez y se separan en cuanto la rutina se renueva a mitad de ciclo o
llega tarde: el reporte pregunta por LA RUTINA («¿cómo va la semana 2 de este entreno?»),
así que es su contador el que decide cuándo se abre la ventana.

CÓMO SE CUENTA. La rutina se entrega el jueves y «empiezas el lunes» (el reloj del doc):
su semana 1 arranca el primer lunes DESPUÉS de crearla -- si se crea en lunes, ese mismo
día -- y cada lunes siguiente suma una. Entre la entrega y su primer lunes la semana es 0:
todavía no ha empezado, y con 0 el patrón de reportes no matchea nada, que es lo que toca
(a nadie se le abre el quincenal de una rutina que aún no ha empezado).

SI NO HAY RUTINA, NO HAY CONTADOR y devuelve None: el que llama cae a la semana de ciclo,
que es lo que la app hacía hasta hoy. Es la red de seguridad para los ~180 clientes sin
rutina cargada en la app -- sin ella, separar los contadores los dejaba a todos sin
reporte de golpe.

Cálculo puro: ni base ni HTTP, para poder probarlo entero.
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from core.tiempo import a_madrid


def lunes_de_arranque(creada: Optional[str]) -> Optional[date]:
    """El lunes en que ARRANCA una rutina creada en esa fecha (en día de España).

    Creada en lunes, arranca ese mismo lunes; cualquier otro día, el lunes siguiente.
    """
    if not creada:
        return None
    try:
        d = datetime.fromisoformat(str(creada).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    dia = (a_madrid(d) or d).date()
    return dia + timedelta(days=(7 - dia.weekday()) % 7)


def semana_de_rutina(rutina: Optional[Dict[str, Any]], hoy_es: date) -> Optional[int]:
    """En qué semana de SU RUTINA está el cliente hoy (`hoy_es` en día de España).

    None sin rutina o sin fecha (no hay contador: manda el ciclo). 0 si la rutina está
    entregada pero su lunes no ha llegado. 1, 2, 3... a partir de su lunes de arranque.
    """
    if not rutina:
        return None
    arranque = lunes_de_arranque(rutina.get("created_at"))
    if not arranque:
        return None
    if hoy_es < arranque:
        return 0
    return (hoy_es - arranque).days // 7 + 1


def lunes_de_la_semana(rutina: Dict[str, Any], semana: int) -> Optional[date]:
    """El lunes en que empieza la semana `semana` (1-based) de esta rutina."""
    arranque = lunes_de_arranque((rutina or {}).get("created_at"))
    if not arranque or semana < 1:
        return None
    return arranque + timedelta(days=7 * (semana - 1))
