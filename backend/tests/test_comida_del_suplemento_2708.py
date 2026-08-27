# -*- coding: utf-8 -*-
"""CON QUE COMIDA SALE CADA SUPLEMENTO (punto 174 del artifact del 27-08).

«+ Creatina debajo de los macros de la comida 3. + Omega 3 · NAC en la 4. El intra y el post no
llevan: ellos son el suplemento, y ponerles otro debajo confunde.»

Manda lo que elija el coach en la ficha y, si no ha elegido, el texto del «¿Cuando?» (la
opcion C, decidida el 27-08). Los textos de aqui son LITERALES de produccion: son los 23 que
hay vivos, asi que esto no prueba casos inventados sino el catalogo entero.

No hace falta backend: es una funcion.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from core.comida_del_suplemento import comidas_del_suplemento, deducir_del_cuando  # noqa: E402


# ── Lo que dice el texto, cuando nadie ha elegido nada ──────────────────────

@pytest.mark.parametrize("cuando,esperado", [
    # Los que SI caen en una comida (206 lineas de las 528 vivas el 27-08).
    ("Todos los días, con el desayuno (entrenes o no)", ["primera"]),
    ("Todos los días, en el desayuno", ["primera"]),
    ("Con el desayuno", ["primera"]),
    ("Todos los días, en dos tomas (desayuno y cena)", ["primera", "ultima"]),

    # EL INTRA Y EL POST NO LLEVAN NADA DEBAJO: son sus palabras en el mismo punto.
    ("Durante el entreno", []),
    ("Durante el entrenamiento, diluido en la bebida intraentreno", []),
    ("Justo después de entrenar", []),
    ("Especialmente recomendable después de entrenar, pero también lo puedes emplear "
     "en cualquier momento del día", []),

    # Alrededor del entreno, que tampoco es una comida.
    ("Inmediatamente antes de entrenar", []),
    ("Unos 30 minutos antes de empezar a entrenar", []),
    ("Solamente los días que entrenes fuerza, unos 30 minutos antes de empezar", []),
    ("Después del ejercicio, en la zona que hayas entrenado o que sientas dolorida", []),

    # Y los que no dicen ninguna comida. NO SE INVENTA UNA: se queda sin salir, que es lo
    # que el coach corrige con el desplegable si quiere.
    ("Todos los días, en dos tomas (haciéndolas coincidir con el termogénico)", []),
    ("Todos los días, en una sola toma (al despertar).", []),
    ("En dos tomas, al despertar y antes de acostar", []),
    ("Todos los días, aproximadamente 1 hora antes de acostarte", []),
    ("En cualquier momento del día, como una comida más", []),
    ("", []),
])
def test_lo_que_dice_el_cuando(cuando, esperado):
    assert deducir_del_cuando(cuando) == esperado


def test_las_tildes_y_las_mayusculas_no_deciden_nada():
    """El coach escribe «Desayuno», «desayuno» y «DESAYUNO» sin criterio fijo."""
    for t in ("Con el DESAYUNO", "con el desayuno", "Con el Desayuno"):
        assert deducir_del_cuando(t) == ["primera"]


def test_una_palabra_dentro_de_otra_no_cuenta():
    """«desayunos» o «cenar» no son la palabra, y un suplemento no puede cambiar de comida
    porque el texto lleve una palabra parecida."""
    assert deducir_del_cuando("Antes de cenar no, mejor por la mañana") == []


# ── Quien manda sobre quien ─────────────────────────────────────────────────

FICHA = {"cuando": "Todos los días, con el desayuno (entrenes o no)"}


def test_sin_elegir_nada_manda_el_texto():
    assert comidas_del_suplemento({"cuando": FICHA["cuando"]}) == ["primera"]


def test_la_ficha_del_catalogo_pisa_al_texto():
    """El coach lo elige UNA vez en la ficha y vale para todos sus clientes."""
    item = {"cuando": FICHA["cuando"]}
    ficha = {**FICHA, "comida": "ultima"}
    assert comidas_del_suplemento(item, ficha) == ["ultima"]


def test_la_linea_del_cliente_pisa_a_la_ficha():
    """Y si a UNO le toca en otra comida, se le cambia a el sin mover la ficha de los demas."""
    item = {"cuando": FICHA["cuando"], "comida": "C3"}
    ficha = {**FICHA, "comida": "ultima"}
    assert comidas_del_suplemento(item, ficha) == ["C3"]


def test_ninguna_es_una_respuesta_y_no_un_hueco_vacio():
    """«En ninguna comida» tiene que poder elegirse: hay 87 lineas en produccion cuyo texto no
    dice comida, y el coach puede querer que sigan sin salir aunque manana reescriba el
    «¿Cuando?». Si «ninguna» se leyera como «no has elegido», el texto volveria a mandar."""
    item = {"cuando": FICHA["cuando"], "comida": "ninguna"}
    assert comidas_del_suplemento(item) == []
    assert comidas_del_suplemento({"cuando": FICHA["cuando"]}, {**FICHA, "comida": "ninguna"}) == []


def test_el_cuando_del_cliente_manda_sobre_el_de_la_ficha():
    """La linea del cliente es una copia editable: si el coach le cambio el texto a el, es el
    suyo el que dice cuando se lo toma."""
    item = {"cuando": "Todos los días, en dos tomas (desayuno y cena)"}
    assert comidas_del_suplemento(item, FICHA) == ["primera", "ultima"]


def test_una_linea_sin_nada_no_revienta():
    assert comidas_del_suplemento({}) == []
    assert comidas_del_suplemento(None, None) == []
