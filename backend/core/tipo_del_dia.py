# -*- coding: utf-8 -*-
"""ENTRENO O DESCANSO, CUANDO NADIE LO HA DICHO TODAVIA.

    «Los dias sabado y domingo por defecto son de descanso» (Francisco, 3-09-2026).

Es la regla que quedo pendiente el 09-08, cuando se midio que de las 14.027 dietas de
produccion **14.025 decian «entrenamiento» y 2 «descanso»**: nadie lo marcaba, asi que casi
todo el mundo comia de dia de entreno tambien los domingos, con sus 60 g de hidratos y sus
45 de perientreno de mas.

ES SOLO UN VALOR POR DEFECTO. El selector de Entreno/Descanso sigue mandando, y a un dia ya
configurado no se le toca el tipo.

EL GEMELO DE LA PANTALLA es `frontend/src/lib/tipoDelDia.js`. Si cambia la regla, los dos.
"""
from datetime import date
from typing import Optional, Union

#: Los dias que se abren en descanso. `weekday()`: 0 lunes ... 5 sabado, 6 domingo.
DIAS_QUE_ABREN_EN_DESCANSO = (5, 6)


def tipo_por_defecto(fecha: Optional[Union[str, date]]) -> str:
    """El tipo con el que abrir una fecha, sea «AAAA-MM-DD» o un `date`.

    Sin fecha o con una que no se entiende, «entrenamiento»: es lo que habia antes de esta
    regla y no conviene que un dato raro cambie de dieta a nadie.
    """
    if isinstance(fecha, date):
        dia = fecha
    else:
        try:
            dia = date.fromisoformat(str(fecha)[:10])
        except (TypeError, ValueError):
            return "entrenamiento"
    return "descanso" if dia.weekday() in DIAS_QUE_ABREN_EN_DESCANSO else "entrenamiento"
