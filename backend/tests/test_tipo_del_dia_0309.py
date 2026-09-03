# -*- coding: utf-8 -*-
"""«LOS DIAS SABADO Y DOMINGO POR DEFECTO SON DE DESCANSO» (Francisco, 3-09-2026).

La regla que quedo pendiente el 09-08, cuando se midio que de las 14.027 dietas de
produccion 14.025 decian «entrenamiento»: nadie marcaba el tipo, asi que casi todo el mundo
comia de dia de entreno tambien los fines de semana.

Es un VALOR POR DEFECTO, solo para el dia que nadie ha configurado.
"""
import os
import sys
from datetime import date

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from core.tipo_del_dia import tipo_por_defecto  # noqa: E402

# Una semana entera, del lunes al domingo.
LUNES = date(2026, 8, 31)
SEMANA = {"lunes": LUNES, "martes": date(2026, 9, 1), "miercoles": date(2026, 9, 2),
          "jueves": date(2026, 9, 3), "viernes": date(2026, 9, 4),
          "sabado": date(2026, 9, 5), "domingo": date(2026, 9, 6)}


def test_el_sabado_y_el_domingo_abren_en_descanso():
    assert tipo_por_defecto(SEMANA["sabado"]) == "descanso"
    assert tipo_por_defecto(SEMANA["domingo"]) == "descanso"


def test_de_lunes_a_viernes_siguen_abriendo_en_entreno():
    for dia in ("lunes", "martes", "miercoles", "jueves", "viernes"):
        assert tipo_por_defecto(SEMANA[dia]) == "entrenamiento", dia


def test_da_igual_que_venga_como_texto_o_como_fecha():
    """La pantalla manda «AAAA-MM-DD» y el asistente a veces un `date`."""
    assert tipo_por_defecto("2026-09-05") == "descanso"
    assert tipo_por_defecto("2026-09-05T10:00:00") == "descanso"
    assert tipo_por_defecto("2026-09-04") == "entrenamiento"


def test_sin_fecha_o_con_una_rara_se_queda_como_estaba():
    """Un dato roto no puede cambiarle la dieta a nadie: se cae al valor de siempre."""
    for mala in (None, "", "manana", "2026-13-45", 12345):
        assert tipo_por_defecto(mala) == "entrenamiento", mala
