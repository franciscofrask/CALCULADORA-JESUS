# -*- coding: utf-8 -*-
"""EL NOMBRE DEL SUPLEMENTO QUE VE EL CLIENTE (video de Jesus del 27-08).

«El solamente ve Aceite de krill. NO tiene que ver Aceite de krill, tres perlas.» Y: «ve el
nombre del suplemento, pero no ve lo de hombre o lo de mujer».

Los nombres de aqui son LITERALES de produccion: los 53 que la gente tiene delante hoy. La
mitad de este fichero prueba lo que se corta y la otra mitad, con la misma insistencia, lo que
NO se corta -- que es donde de verdad se puede hacer dano.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from core.nombre_del_suplemento import nombre_para_el_cliente  # noqa: E402


@pytest.mark.parametrize("guardado,ve_el_cliente", [
    # «No ve lo de hombre o lo de mujer»: 97 y 13 lineas.
    ("Omega 3 hombre", "Omega 3"),
    ("Omega 3 mujer", "Omega 3"),
    ("Creatina hombre", "Creatina"),
    ("Creatina mujer", "Creatina"),

    # Su propio ejemplo del video.
    ("Aceite de krill 3 perlas", "Aceite de krill"),
    ("Aceite de krill 4 perlas", "Aceite de krill"),
    ("Vitamina D3 + K2 4 perlas", "Vitamina D3 + K2"),

    # El mes del protocolo, con y sin la explicacion detras.
    ("Fat burner hardcore mes 3", "Fat burner hardcore"),
    ("Sinefrina con termogénico mes 1 (1 cápsula primeras 2 semanas y a partir de la "
     "semana 3 sube a 1 y 1)", "Sinefrina con termogénico"),
    ("Sinefrina con cafeína mes 5 (10 días con 1)", "Sinefrina con cafeína"),
    ("Cafeína anhidra mes 1 protocolo light", "Cafeína anhidra"),
    ("MONACOLINA PROTOCOLO 2", "MONACOLINA"),

    # Capsulas, tomas y dosis.
    ("Selenio 1 cápsula", "Selenio"),
    ("Selenio 2 cápsulas", "Selenio"),
    ("SAME + Betaína 3 Cap", "SAME + Betaína"),
    ("Ursobilane 500 mg 2 tomas", "Ursobilane 500 mg"),
    ("Total electrolitos 2 tomas", "Total electrolitos"),
    ("Pre-workout 3 dosis", "Pre-workout"),

    # Gramos pegados al final.
    ("Hydropeptides o MAP 15g", "Hydropeptides o MAP"),
    ("Hydropeptides o MAP 10g", "Hydropeptides o MAP"),

    # Y las dos coletillas sueltas que tiene.
    ("Cafeína anhidra 200 mg suelta", "Cafeína anhidra 200 mg"),
    ("CBD 40% CON DOSIS MARCADA", "CBD 40%"),
])
def test_lo_que_se_corta(guardado, ve_el_cliente):
    assert nombre_para_el_cliente(guardado) == ve_el_cliente


@pytest.mark.parametrize("nombre", [
    # Ya limpios: no se les puede tocar ni una letra.
    "Whey Isolate + crema de arroz",
    "Hydropeptides o MAP",
    "Ciclodextrina",
    "NAC",
    "Total electrolitos",
    "Sport Vitamin Premium",
    "Crema RELIEF EFFECT",
    "Glicerol",
    "Monohidrato de creatina",
    "Omega 3",
    "Bebida intraentreno adicional",

    # EL PARENTESIS SE QUEDA cuando dice algo: aqui le esta diciendo CUANDO se lo toma.
    "Whey Isolate + crema de arroz (post-entreno)",
    "Café (bien cargado) o Monster light",
    "Niacina Flush Free (subir HDL, 2 meses)",

    # LA DOSIS DE EN MEDIO NO SE TOCA. Son cuatro bebidas distintas y lo unico que las
    # distingue son esos gramos: recortarlas dejaria cuatro «Bebida intra» iguales.
    "Bebida intra 15 g ciclo + 15 g de hydro",
    "Bebida intra 20 g ciclo + 15 g de hydro",
    "Bebida intra 15 g ciclo + 20 g de hydro",
    "Bebida intra 20 g ciclo + 20 g de hydro",
])
def test_lo_que_NO_se_toca(nombre):
    assert nombre_para_el_cliente(nombre) == nombre


def test_los_miligramos_no_son_gramos():
    """«Cafeína anhidra 200 mg»: los 200 mg son la capsula que compra, no lo que le pauta.
    Si se cortaran, el cliente iria a la tienda a por la cafeina equivocada."""
    assert nombre_para_el_cliente("Cafeína anhidra 200 mg") == "Cafeína anhidra 200 mg"
    assert nombre_para_el_cliente("Ursobilane 300 mg") == "Ursobilane 300 mg"


def test_no_se_queda_nunca_sin_nombre():
    """Si de un nombre solo quedara la cola, se devuelve el original: mas vale un nombre feo
    que una ficha sin nombre."""
    assert nombre_para_el_cliente("3 perlas") == "3 perlas"
    assert nombre_para_el_cliente("hombre") == "hombre"


def test_aguanta_lo_vacio():
    assert nombre_para_el_cliente(None) == ""
    assert nombre_para_el_cliente("   ") == ""


def test_se_corta_todo_lo_que_haya_que_cortar():
    """Un nombre puede llevar dos colas seguidas."""
    assert nombre_para_el_cliente("Omega 3 2 perlas hombre") == "Omega 3"
