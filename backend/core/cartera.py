"""
Las cuentas de la pestaña de Clientes (doc del 19-08, apartado 04).

Dos columnas que hoy no existen y sin las que «no se puede llevar la cartera»:

    SEMANAS SIN REPORTE   «Contando desde el lunes, que es cuando recojo.» No son días
                          partidos por siete: son recogidas del lunes que han pasado sin
                          que haya reporte nuevo. El que mandó el viernes está al día
                          aunque hayan pasado tres días.
    REPORTES SIN RESPONDER  Cuántos le TOCABAN según el calendario de su plan y no ha
                          mandado, seguidos, desde el último que sí mandó. No es lo mismo
                          que las semanas: al de reporte mensual le pasan cuatro lunes
                          entre reporte y reporte sin deber ninguno.

Cálculo puro: ni base ni HTTP. Las fechas llegan como ISO y se cuentan en día de España
(quien llama ya se lo pasa así o son fechas a secas).
"""
from datetime import date, timedelta
from typing import Any, Dict, Optional

from core.calendario_reportes import reporte_de_la_semana


def _fecha(v) -> Optional[date]:
    try:
        return date.fromisoformat(str(v)[:10])
    except (ValueError, TypeError):
        return None


def _lunes_pasados(desde: date, hasta: date) -> int:
    """Cuántos lunes hay en (desde, hasta]: las recogidas que han ocurrido después."""
    if hasta <= desde:
        return 0
    primero = desde + timedelta(days=(7 - desde.weekday()) % 7 or 7)   # el lunes SIGUIENTE
    if primero > hasta:
        return 0
    return (hasta - primero).days // 7 + 1


def semanas_sin_reporte(ultimo_reporte, arranque, hoy: date) -> Optional[int]:
    """Recogidas del lunes que han pasado sin reporte nuevo.

    Con reporte: la primera recogida después de mandarlo lo incluyó, así que esa no
    cuenta; las siguientes sí. Sin reporte nunca: todas las recogidas desde que arrancó.
    None si no hay ni reporte ni arranque (no hay desde dónde contar).
    """
    d_reporte = _fecha(ultimo_reporte)
    if d_reporte:
        return max(0, _lunes_pasados(d_reporte, hoy) - 1)
    d_arranque = _fecha(arranque)
    if d_arranque:
        return _lunes_pasados(d_arranque, hoy)
    return None


def reportes_sin_responder(cal: Dict[str, Any], semana_actual: Optional[int],
                           ultimo_reporte, hoy: date, tope: int = 12) -> Optional[int]:
    """Cuántos reportes le tocaban y no mandó, seguidos, hasta la semana pasada.

    `cal` es su calendario (patrón del plan/contrato) y `semana_actual` la semana que
    manda (la de rutina si la tiene, la de ciclo si no). La semana en curso no se cuenta:
    su ventana puede no haber cerrado todavía y deberla a medias no es deberla.

    `tope` corta el paseo: a partir de doce seguidos el número exacto ya no cambia nada.
    """
    if not semana_actual or semana_actual < 1 or not (cal.get("patron") or []):
        return None
    d_reporte = _fecha(ultimo_reporte)
    if d_reporte:
        # En qué semana cayó su último reporte, contada hacia atrás por lunes: cada lunes
        # pasado desde entonces es una semana más de programa.
        semana_del_reporte = semana_actual - _lunes_pasados(d_reporte, hoy)
        desde = max(1, semana_del_reporte + 1)
    else:
        desde = 1
    perdidos = 0
    for s in range(desde, semana_actual):        # la semana en curso, fuera
        if reporte_de_la_semana(cal, s):
            perdidos += 1
            if perdidos >= tope:
                break
    return perdidos
