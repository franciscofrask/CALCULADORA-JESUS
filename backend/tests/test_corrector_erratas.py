# -*- coding: utf-8 -*-
"""CorrectorErratas (food_semantic): las erratas reales de clientes, sin listas a mano.

Hereda los casos que motivaron arreglos en el sistema anterior (test_chatbot_cantidades,
borrado en F3 junto con los regex que probaba): el cliente del 02-08 que escribió "sumo"
por "zumo" y las erratas fonéticas que antes vivían hardcodeadas en la tabla de sinónimos.
"""
import os
import sys
from collections import Counter

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from food_semantic import CorrectorErratas, clave_fonetica  # noqa: E402


def corrector():
    # Vocabulario mínimo de catálogo, con frecuencias realistas.
    return CorrectorErratas(Counter({
        "zumo": 8, "pollo": 30, "queso": 25, "huevos": 40, "avena": 12,
        "arroz": 20, "batido": 10, "naranja": 9, "cocido": 6,
    }))


class TestFonetica:
    def test_seseo_sumo_zumo(self):
        # El caso real del 02-08: "la cantidad de sumo que sea la mitad".
        assert corrector().corregir("sumo") == "zumo"

    def test_wevos_huevos(self):
        assert corrector().corregir("wevos") == "huevos"

    def test_poyo_pollo(self):
        assert corrector().corregir("poyo") == "pollo"

    def test_keso_queso(self):
        assert corrector().corregir("keso") == "queso"

    def test_abena_avena(self):
        assert corrector().corregir("abena") == "avena"


class TestNoToca:
    def test_lo_bien_escrito_no_se_corrige(self):
        assert corrector().corregir("pollo con arroz") == "pollo con arroz"

    def test_palabras_cortas_en_paz(self):
        # "iso" o "sal" no llegan al mínimo de 4 letras: no se inventa nada.
        assert corrector().corregir("sal") == "sal"

    def test_frase_entera_solo_toca_la_errata(self):
        assert corrector().corregir("batido de sumo de naranja") == "batido de zumo de naranja"


class TestClaveFonetica:
    def test_pliegues(self):
        assert clave_fonetica("wevos") == clave_fonetica("huevos")
        assert clave_fonetica("cosido") == clave_fonetica("cocido")
        assert clave_fonetica("aceyte") == clave_fonetica("aceite")
