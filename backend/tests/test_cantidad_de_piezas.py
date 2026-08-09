# -*- coding: utf-8 -*-
"""
Punto 4.5: «Atun al natural lata, 0 ud, 0,6 g proteina».

En las dietas de Calma los alimentos por unidades guardan el CONTEO de piezas en el campo de
gramos. Leido como gramos, un huevo de 53 g vale 1 g. La regla de conversion tiene que ser
estrecha: solo cuando leerlo como gramos es imposible, no cuando es raro.
"""
import pytest

from core.cantidad_de_dieta import gramos, normalizar_dieta, parece_un_conteo

HUEVO = {"por_unidad": True, "peso_unidad": 53}
LATA = {"por_unidad": True, "peso_unidad": 60}
LONCHA = {"por_unidad": True, "peso_unidad": 25}
ARROZ = {"por_unidad": False, "peso_unidad": 0}


class TestCuandoSeConvierte:
    def test_el_caso_de_jesus(self):
        """3 en una lata de 60 g son tres latas, no tres gramos de atun."""
        assert parece_un_conteo(3, **LATA)
        assert gramos(3, LATA) == 180

    def test_un_huevo(self):
        assert gramos(1, HUEVO) == 53

    def test_dos_huevos(self):
        assert gramos(2, HUEVO) == 106


class TestCuandoNO:
    def test_una_cantidad_normal_se_queda(self):
        """150 g de atun son 150 g, aunque el atun vaya por latas."""
        assert not parece_un_conteo(150, **LATA)
        assert gramos(150, LATA) == 150

    def test_lo_que_puede_ser_una_pesada_no_se_toca(self):
        """40 en una loncha de 25 g puede ser 40 gramos de queso. Se deja."""
        assert not parece_un_conteo(40, **LONCHA)
        assert gramos(40, LONCHA) == 40

    def test_lo_que_va_a_granel_nunca(self):
        assert not parece_un_conteo(3, **ARROZ)
        assert gramos(3, ARROZ) == 3

    def test_los_decimales_no_son_un_conteo(self):
        """Nadie se pone 2,5 latas escribiendo 2.5 en el campo de gramos."""
        assert not parece_un_conteo(2.5, **LATA)

    def test_un_numero_grande_no_es_un_conteo(self):
        assert not parece_un_conteo(20, **LATA)

    def test_sin_peso_de_unidad_no_se_adivina(self):
        assert not parece_un_conteo(3, por_unidad=True, peso_unidad=0)

    def test_cerca_de_una_pieza_no_se_toca(self):
        """25 en una loncha de 25 g es exactamente una loncha pesada. Se deja."""
        assert not parece_un_conteo(25, **LONCHA)


class TestLaDietaEntera:
    def test_convierte_solo_lo_que_toca_y_tira_los_macros_malos(self):
        """La comida real del cliente 577f920f, tal cual esta en produccion."""
        diet = {"comidas": {"C1": {"alimentos": [
            {"alimento_id": 1, "nombre": "Pan de barra", "cantidad_g": 20},
            {"alimento_id": 2, "nombre": "Tomate rallado", "cantidad_g": 30},
            {"alimento_id": 3, "nombre": "Huevos enteros M", "cantidad_g": 1,
             "macros_efectivos": {"P": 0.1, "H": 0, "G": 0.1}},
            {"alimento_id": 4, "nombre": "Queso Havarti loncha", "cantidad_g": 1,
             "macros_efectivos": {"P": 0.3, "H": 0, "G": 0.2}},
        ]}}}
        cfgs = {1: ARROZ, 2: ARROZ, 3: HUEVO, 4: LONCHA}
        n = normalizar_dieta(diet, lambda aid, item: cfgs.get(aid))

        items = diet["comidas"]["C1"]["alimentos"]
        assert n == 2, "solo el huevo y la loncha"
        assert items[0]["cantidad_g"] == 20, "el pan estaba bien y no se toca"
        assert items[1]["cantidad_g"] == 30
        assert items[2]["cantidad_g"] == 53, "un huevo son 53 g"
        assert items[3]["cantidad_g"] == 25, "una loncha son 25 g"
        # Los macros calculados sobre el numero malo se van: 0,1 de proteina no es un dato
        # incompleto, es un dato falso.
        assert "macros_efectivos" not in items[2]
        assert "macros_efectivos" not in items[3]

    def test_queda_dicho_de_donde_sale_el_numero(self):
        diet = {"comidas": {"C1": {"alimentos": [
            {"alimento_id": 3, "nombre": "Huevos enteros M", "cantidad_g": 2}]}}}
        normalizar_dieta(diet, lambda aid, item: HUEVO)
        item = diet["comidas"]["C1"]["alimentos"][0]
        assert item["cantidad_g"] == 106
        assert item["cantidad_convertida"]["de"] == 2
        assert item["cantidad_convertida"]["peso_unidad"] == 53

    def test_una_dieta_sana_no_cambia_nada(self):
        diet = {"comidas": {"C1": {"alimentos": [
            {"alimento_id": 1, "cantidad_g": 150, "macros_efectivos": {"P": 30}}]}}}
        assert normalizar_dieta(diet, lambda aid, item: ARROZ) == 0
        assert diet["comidas"]["C1"]["alimentos"][0]["macros_efectivos"] == {"P": 30}

    def test_aguanta_una_dieta_con_forma_rara(self):
        for raro in ({"comidas": None}, {"comidas": 3}, {}, {"comidas": {"C1": None}},
                     {"comidas": {"C1": {"alimentos": [None, 3, "x"]}}}):
            assert normalizar_dieta(raro, lambda aid, item: HUEVO) == 0

    def test_un_nan_no_tumba_la_pantalla(self):
        """Hay dietas guardadas con cantidad_g NaN. Esto corre al LEER: un NaN sin controlar
        devolvia un 500 y dejaba al cliente sin poder abrir su dia."""
        nan = float("nan")
        assert parece_un_conteo(nan, **HUEVO) is False
        assert gramos(nan, HUEVO) is None
        diet = {"comidas": {"C1": {"alimentos": [
            {"alimento_id": 3, "cantidad_g": nan},
            {"alimento_id": 3, "cantidad_g": 2},
        ]}}}
        assert normalizar_dieta(diet, lambda aid, item: HUEVO) == 1
        assert diet["comidas"]["C1"]["alimentos"][1]["cantidad_g"] == 106
