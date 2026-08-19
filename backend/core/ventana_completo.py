"""
La ventana del CUESTIONARIO LARGO (el reloj del doc del 19-08, apartado 02).

    «Viernes · 10:00  Se abre el reporte mensual a quien le toque, y el cuestionario
     largo al que se está dando de alta.
     Lunes · 18:00 hora de España  Cierra el mensual y cierra el cuestionario largo.»

Y el porqué, en el mismo documento: «El cliente que se apunta hoy usa la calculadora
desde el primer día con unos macros provisionales. El viernes se le abre el cuestionario
largo, cierra el lunes, el miércoles tiene sus macros, el jueves su rutina, y el lunes
siguiente empieza su programa con todo hecho.» Las 48 horas entre el cierre del lunes y
la entrega del miércoles son el margen del equipo para trabajar.

Hasta hoy el cuestionario largo estaba SIEMPRE abierto («Hoy están siempre abiertos o
siempre cerrados», punto 1 de lo que hay que construir). La ventana se repite CADA
semana mientras el cliente lo tenga pendiente: el que deja pasar la suya no se queda
fuera para siempre, entra en el tren del viernes siguiente.

LO QUE ESTA VENTANA NO CIERRA: el básico (el alta de todo el mundo), el cuestionario de
ajuste (`?ajustar=1`), el completar-huecos de los que ya estaban (`?completar=1`) y el
modo revisión del equipo (`?ver=`). Solo cierra la ENTRADA al completo; el envío del que
lo terminó se acepta siempre — rechazar veinte pantallas contestadas porque el reloj
marca las 18:05 sería castigar justo al que lo hizo.

Cálculo puro, en hora de España, sin base ni HTTP.
"""
from datetime import datetime, timedelta
from typing import Any, Dict

from core.tiempo import MADRID, a_madrid

ABRE_DIA, ABRE_HORA = 4, 10      # viernes 10:00
CIERRA_DIA, CIERRA_HORA = 0, 18  # lunes 18:00 (el de después de ese viernes)


def _viernes_a_las_10(dia) -> datetime:
    """El viernes a las 10:00 de la semana del día que se le pase (en hora de España)."""
    viernes = dia + timedelta(days=(ABRE_DIA - dia.weekday()) % 7)
    return datetime(viernes.year, viernes.month, viernes.day, ABRE_HORA, tzinfo=MADRID)


def ventana_del_completo(ahora) -> Dict[str, Any]:
    """{abierta, abre, cierra} de la ventana del cuestionario largo que aplica AHORA.

    Abierta: entre el viernes 10:00 y el lunes 18:00 siguientes. Cerrada: `abre` trae el
    próximo viernes 10:00, que es lo que hay que decirle al cliente.
    """
    ahora_es = a_madrid(ahora) or ahora

    # La ventana que podría estar en curso es la que abrió el viernes PASADO (o hoy, si
    # es viernes): se mira esa primero y, si ya cerró, la siguiente.
    ultima_apertura = _viernes_a_las_10(ahora_es.date() - timedelta(days=(ahora_es.weekday() - ABRE_DIA) % 7))
    cierre = ultima_apertura + timedelta(days=3)
    cierre = cierre.replace(hour=CIERRA_HORA)

    if ultima_apertura <= ahora_es <= cierre:
        return {"abierta": True, "abre": ultima_apertura, "cierra": cierre}

    proxima = ultima_apertura if ahora_es < ultima_apertura \
        else _viernes_a_las_10(ahora_es.date() + timedelta(days=1))
    return {"abierta": False, "abre": proxima,
            "cierra": proxima.replace(hour=CIERRA_HORA) + timedelta(days=3)}
