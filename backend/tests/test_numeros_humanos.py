# -*- coding: utf-8 -*-
"""Los números que el asistente escribe, tal y como los lee el cliente.

El estado le llega al modelo como «P=50.2 H=30 G=10» y el modelo lo copia. Se corrige a la
salida, en `_numeros_humanos`, que es donde no falla. Estos casos salieron todos de la
pantalla, no de la imaginación.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_loop import _numeros_humanos   # noqa: E402


def test_las_iniciales_se_dicen_con_palabras():
    assert _numeros_humanos("P=47.5") == "47,5 g de proteína"
    assert _numeros_humanos("H = 51") == "51 g de hidratos"


def test_tres_seguidas_no_se_pegan():
    r"""«50,2 g de proteína30 g de hidratos10 g de grasa», visto en producción el 15-08.

    El `\s*` del final se comía el espacio de separación aunque no hubiera ninguna «g».
    """
    assert _numeros_humanos("P=50.2 H=30 G=10") == (
        "50,2 g de proteína 30 g de hidratos 10 g de grasa")


def test_y_de_rebote_los_ceros_de_relleno_se_van():
    """Pegado al texto anterior no había frontera de palabra y «51,0» se quedaba."""
    assert _numeros_humanos("P=47.5 H=51.0 G=12.0") == (
        "47,5 g de proteína 51 g de hidratos 12 g de grasa")


def test_la_g_se_come_solo_si_esta():
    assert _numeros_humanos("quedan P=12 g y H=3 g") == (
        "quedan 12 g de proteína y 3 g de hidratos")


def test_el_punto_decimal_se_vuelve_coma():
    assert _numeros_humanos("te pasas 9.4 g") == "te pasas 9,4 g"
    assert _numeros_humanos("te pasas 9.0 g") == "te pasas 9 g"


def test_lo_que_no_es_un_numero_no_se_toca():
    assert _numeros_humanos("") == ""
    assert _numeros_humanos(None) is None
    assert _numeros_humanos("Pan de molde") == "Pan de molde"
