# -*- coding: utf-8 -*-
"""El +20 % de "casi no engordo" y su umbral de grasa, tras el documento del 07-08.

Historia del umbral, para leer los asserts sin sustos:
  - Hasta el 06-08 estaba en 20 % para todos y en mujeres NO SE EJECUTO NI UNA VEZ
    (su tabla empieza justo en el 20: once respuestas guardadas, cero aplicaciones).
  - El doc del 06-08 lo subio al 30 % en ellas para poder activarlo y validarlo.
  - El doc del 07-08 (punto 11) dice "grasa <= 20 %" SIN distinguir sexo, y suplanta
    a todo lo anterior (decision de Francisco del 07-08). Vuelve el 20 para todos,
    con su consecuencia asumida: en mujeres solo lo cobra quien este en el arranque.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest                                                      # noqa: E402
from macro_engine import (BF_MAX_NO_ENGORDA, APLICAR_ENGORDA_EN_MUJERES,  # noqa: E402
                          calcular_macros_v2)


def _paso(r, nombre):
    return next((p for p in r["desglose"] if p["paso"] == nombre), None)


class TestElUmbralDelDoc0708:
    def test_veinte_para_todos(self):
        assert BF_MAX_NO_ENGORDA["hombre"] == 20.0
        assert BF_MAX_NO_ENGORDA["mujer"] == 20.0

    def test_sigue_encendido_en_mujeres(self):
        assert APLICAR_ENGORDA_EN_MUJERES is True, "vuelve a estar muerto"


class TestEnMujeres:
    def test_en_el_arranque_de_su_tabla_si(self):
        r = calcular_macros_v2(70, "mujer", 20, "definicion", facilidad_engordar="casi_no")
        assert _paso(r, "no_engorda")["estado"] == "aplicado"

    @pytest.mark.parametrize("bf", [25, 30, 35])
    def test_por_encima_del_20_no(self, bf):
        """Con el doc del 06-08 el 25 y el 30 cobraban; el doc del 07-08 los quita."""
        r = calcular_macros_v2(70, "mujer", bf, "definicion", facilidad_engordar="casi_no")
        assert _paso(r, "no_engorda")["estado"] == "no_aplica_bf"

    def test_sube_los_hidratos_de_verdad(self):
        """Que se marque "aplicado" no basta: los números tienen que moverse."""
        con = calcular_macros_v2(70, "mujer", 20, "definicion", facilidad_engordar="casi_no")
        sin = calcular_macros_v2(70, "mujer", 20, "definicion", facilidad_engordar="enseguida")
        assert con["macros"]["entreno"]["hidratos"] > sin["macros"]["entreno"]["hidratos"]
        assert con["macros"]["descanso"]["hidratos"] > sin["macros"]["descanso"]["hidratos"]

    def test_no_toca_ni_proteina_ni_grasa(self):
        con = calcular_macros_v2(70, "mujer", 20, "definicion", facilidad_engordar="casi_no")
        sin = calcular_macros_v2(70, "mujer", 20, "definicion", facilidad_engordar="enseguida")
        assert con["macros"]["entreno"]["proteina"] == sin["macros"]["entreno"]["proteina"]
        assert con["macros"]["entreno"]["grasa"] == sin["macros"]["entreno"]["grasa"]

    def test_el_veto_sigue_mandando(self):
        """"Engordo enseguida" anula, y eso vale para los dos sexos."""
        r = calcular_macros_v2(70, "mujer", 20, "definicion",
                               facilidad_engordar="enseguida", actividad_diaria="muy_activo")
        assert _paso(r, "veto_engorda_enseguida") is not None


class TestEnHombresNoCambiaNada:
    def test_sigue_en_el_20(self):
        r = calcular_macros_v2(85, "hombre", 20, "definicion", facilidad_engordar="casi_no")
        assert _paso(r, "no_engorda")["estado"] == "aplicado"

    def test_al_25_no_se_aplica(self):
        r = calcular_macros_v2(85, "hombre", 25, "definicion", facilidad_engordar="casi_no")
        assert _paso(r, "no_engorda")["estado"] == "no_aplica_bf"


class TestSoloCasiNoLoNoto:
    """Doc del 07-08: "engordo lo normal" deja de cobrar el +20 % (lo cobraba por el 29-07)."""

    @pytest.mark.parametrize("sexo,bf", [("hombre", 20), ("mujer", 20)])
    def test_normal_ya_no_sube(self, sexo, bf):
        peso = 85 if sexo == "hombre" else 70
        r = calcular_macros_v2(peso, sexo, bf, "definicion", facilidad_engordar="normal")
        paso = _paso(r, "no_engorda")
        assert paso is None or paso["estado"] != "aplicado"

    def test_normal_y_casi_no_ya_no_son_iguales(self):
        normal = calcular_macros_v2(85, "hombre", 20, "definicion", facilidad_engordar="normal")
        casi_no = calcular_macros_v2(85, "hombre", 20, "definicion", facilidad_engordar="casi_no")
        assert casi_no["macros"]["entreno"]["hidratos"] > normal["macros"]["entreno"]["hidratos"]
