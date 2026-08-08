# -*- coding: utf-8 -*-
"""PerfilMomento: la matemática de coherencia y sus respaldos, con datos sintéticos."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from moment_profile import PerfilMomento, cat2_de  # noqa: E402

# Reparto general uniforme: 100 usos por momento -> el ratio es directamente la
# proporción del alimento en ese momento por 4.
BASE = {"tipo": "_base", "clave": "_base", "total": 400,
        "conteos": {"desayuno": 100, "comida": 100, "merienda": 100, "cena": 100}}

AVENA = {"tipo": "alimento", "clave": "10", "total": 100,
         "conteos": {"desayuno": 80, "comida": 10, "merienda": 5, "cena": 5}}
POCOS = {"tipo": "alimento", "clave": "11", "total": 5,      # sin evidencia suficiente
         "conteos": {"cena": 5}}
CAT_PESCADO = {"tipo": "categoria", "clave": "3.1", "total": 200,
               "conteos": {"desayuno": 0, "comida": 60, "merienda": 20, "cena": 120}}


def perfil():
    return PerfilMomento(
        alimentos={"10": AVENA, "11": POCOS},
        categorias={"3.1": CAT_PESCADO},
        base=BASE,
    )


class TestCoherencia:
    def test_tipico_puntua_alto(self):
        # 80% de sus usos en desayuno frente a un 25% general -> 3.2
        assert perfil().coherencia({"id": 10, "categorias": "7.2"}, "desayuno") == 3.2

    def test_atipico_puntua_bajo(self):
        assert perfil().coherencia({"id": 10, "categorias": "7.2"}, "cena") == 0.2

    def test_sin_evidencia_hereda_de_la_categoria(self):
        # id 11 solo tiene 5 usos (< mínimo): cae a la categoría 3.1
        f = {"id": 11, "categorias": "3.1.4 | CGE"}
        assert perfil().coherencia(f, "cena") == 2.4      # 120/200 frente a 25%
        assert perfil().coherencia(f, "desayuno") == 0.0  # el pescado no desayuna

    def test_sin_nada_es_neutro(self):
        assert perfil().coherencia({"id": 999, "categorias": "51"}, "desayuno") == 1.0

    def test_peri_es_neutro(self):
        # El peri no tiene perfil: sus categorías permitidas ya lo acotan.
        assert perfil().coherencia({"id": 10, "categorias": "7.2"}, "peri") == 1.0

    def test_sin_base_es_neutro(self):
        p = PerfilMomento(alimentos={"10": AVENA}, categorias={}, base=None)
        assert p.coherencia({"id": 10, "categorias": "7.2"}, "desayuno") == 1.0


class TestTieneDatos:
    def test_con_evidencia_directa(self):
        assert perfil().tiene_datos({"id": 10, "categorias": "7.2"}) is True

    def test_poca_evidencia_sin_categoria(self):
        assert perfil().tiene_datos({"id": 11, "categorias": "9"}) is False


class TestCat2:
    def test_ignora_etiquetas_transversales(self):
        assert cat2_de({"categorias": "YA | 2.2.1 | 42"}) == "2.2"

    def test_sin_categoria_numerica(self):
        assert cat2_de({"categorias": "YA"}) == "?"
        assert cat2_de({}) == "?"
