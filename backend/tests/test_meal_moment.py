# -*- coding: utf-8 -*-
"""El momento de cada comida (desayuno / almuerzo / merienda / cena / peri).

Regla acordada el 06-08-2026: por POSICIÓN, sin excepciones. El momento del entreno no
renombra ninguna comida.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meal_moment import (  # noqa: E402
    COMIDA, DESAYUNO, MERIENDA, CENA, PERI,
    momento_de_comida, etiqueta_momento, describe_comida, entreno_antes_de,
)


class TestRepartoPorPosicion:
    def test_tres_comidas(self):
        assert momento_de_comida("C1", 3) == DESAYUNO
        assert momento_de_comida("C2", 3) == COMIDA
        assert momento_de_comida("C3", 3) == CENA

    def test_cuatro_comidas(self):
        assert momento_de_comida("C1", 4) == DESAYUNO
        assert momento_de_comida("C2", 4) == COMIDA
        assert momento_de_comida("C3", 4) == MERIENDA
        assert momento_de_comida("C4", 4) == CENA

    def test_bloque_unico_es_comida(self):
        assert momento_de_comida("C1", 1, single_meal=True) == COMIDA

    def test_cinco_comidas_no_revienta(self):
        # La app ofrece 3 o 4, pero una preferencia guardada rara no puede romper nada.
        assert momento_de_comida("C1", 5) == DESAYUNO
        assert momento_de_comida("C2", 5) == COMIDA
        assert momento_de_comida("C5", 5) == CENA


class TestPeri:
    def test_intra_y_post_son_peri(self):
        assert momento_de_comida("Intra", 4) == PERI
        assert momento_de_comida("Post", 4) == PERI

    def test_el_peri_no_ocupa_posicion(self):
        # Con Intra y Post intercalados, la C2 sigue siendo el almuerzo.
        assert momento_de_comida("C2", 4) == COMIDA


class TestElEntrenoNoRenombra:
    """Lo que se decidió el 06-08: entrenar en ayunas NO convierte el desayuno en comida."""

    def test_en_ayunas_la_c1_sigue_siendo_desayuno(self):
        assert momento_de_comida("C1", 4) == DESAYUNO   # momento_entreno no entra ni como argumento

    def test_entreno_a_mediodia_no_cambia_nada(self):
        assert momento_de_comida("C3", 4) == MERIENDA


class TestEntrenoComoContexto:
    ORDER_AYUNAS = ["Intra", "Post", "C1", "C2", "C3", "C4"]
    ORDER_TRAS_C1 = ["C1", "Intra", "Post", "C2", "C3", "C4"]
    ORDER_MEDIODIA = ["C1", "C2", "Intra", "Post", "C3", "C4"]

    def test_en_ayunas_todas_van_despues(self):
        assert entreno_antes_de("C1", 0, self.ORDER_AYUNAS) is True
        assert entreno_antes_de("C4", 0, self.ORDER_AYUNAS) is True

    def test_entreno_tras_la_primera(self):
        assert entreno_antes_de("C1", 1, self.ORDER_TRAS_C1) is False
        assert entreno_antes_de("C2", 1, self.ORDER_TRAS_C1) is True

    def test_entreno_a_mediodia(self):
        assert entreno_antes_de("C2", 2, self.ORDER_MEDIODIA) is False
        assert entreno_antes_de("C3", 2, self.ORDER_MEDIODIA) is True

    def test_dia_sin_peri(self):
        assert entreno_antes_de("C2", 1, ["C1", "C2", "C3"]) is False

    def test_post_cuenta_como_despues_del_entreno(self):
        assert entreno_antes_de("Post", 1, self.ORDER_TRAS_C1) is True
        assert entreno_antes_de("Intra", 1, self.ORDER_TRAS_C1) is False


class TestEtiquetas:
    def test_comida_se_le_dice_almuerzo(self):
        assert etiqueta_momento(COMIDA) == "almuerzo"

    def test_describe_lleva_el_momento(self):
        assert describe_comida("C2", 4, meal_label="Comida 2") == "Comida 2 (almuerzo)"
        assert describe_comida("C1", 3, meal_label="Comida 1") == "Comida 1 (desayuno)"

    def test_el_peri_no_se_duplica(self):
        assert describe_comida("Post", 4, meal_label="Post-entreno") == "Post-entreno"


class TestEntradasRaras:
    def test_clave_desconocida(self):
        assert momento_de_comida("", 4) == COMIDA
        assert momento_de_comida("Cx", 4) == COMIDA

    def test_comida_fuera_del_reparto(self):
        # Reconfigurar de 4 a 3 comidas a mitad de sesión deja claves huérfanas.
        assert momento_de_comida("C4", 3) == CENA
