# -*- coding: utf-8 -*-
"""El +20 % de "casi no engordo" en mujeres, que hasta hoy no se ejecutaba nunca.

Estaba apagado con la nota "n=11, sin validar", y esa nota engañaba: no es que fallara
con once casos, es que NO SE EJECUTO NI UNA VEZ. Dos barreras a la vez:

  1. APLICAR_ENGORDA_EN_MUJERES = False, que cortaba antes de mirar el % de grasa.
  2. El umbral del 20 %, cuando la tabla de mujeres EMPIEZA en el 20: habia que estar en
     el extremo exacto para cobrarlo.

Documento del 06-08-2026: el umbral sube al 30 % en mujeres (el mismo punto del recorrido
que el 20 % en hombres) y se enciende, para poder aplicarlo y validarlo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest                                                      # noqa: E402
from macro_engine import (BF_MAX_NO_ENGORDA, APLICAR_ENGORDA_EN_MUJERES,  # noqa: E402
                          calcular_macros_v2)


def _paso(r, nombre):
    return next((p for p in r["desglose"] if p["paso"] == nombre), None)


class TestElUmbralEsDistintoPorSexo:
    def test_los_dos_umbrales(self):
        assert BF_MAX_NO_ENGORDA["hombre"] == 20.0
        assert BF_MAX_NO_ENGORDA["mujer"] == 30.0

    def test_esta_encendido(self):
        assert APLICAR_ENGORDA_EN_MUJERES is True, "vuelve a estar muerto"


class TestEnMujeres:
    @pytest.mark.parametrize("bf", [20, 25, 30])
    def test_se_aplica_hasta_el_30(self, bf):
        r = calcular_macros_v2(70, "mujer", bf, "definicion", facilidad_engordar="casi_no")
        assert _paso(r, "no_engorda")["estado"] == "aplicado"

    @pytest.mark.parametrize("bf", [35, 40, 45])
    def test_por_encima_del_30_no(self, bf):
        r = calcular_macros_v2(70, "mujer", bf, "definicion", facilidad_engordar="casi_no")
        assert _paso(r, "no_engorda")["estado"] == "no_aplica_bf"

    def test_sube_los_hidratos_de_verdad(self):
        """Que se marque "aplicado" no basta: los números tienen que moverse."""
        con = calcular_macros_v2(70, "mujer", 25, "definicion", facilidad_engordar="casi_no")
        sin = calcular_macros_v2(70, "mujer", 25, "definicion", facilidad_engordar="enseguida")
        assert con["macros"]["entreno"]["hidratos"] > sin["macros"]["entreno"]["hidratos"]
        assert con["macros"]["descanso"]["hidratos"] > sin["macros"]["descanso"]["hidratos"]

    def test_no_toca_ni_proteina_ni_grasa(self):
        con = calcular_macros_v2(70, "mujer", 25, "definicion", facilidad_engordar="casi_no")
        sin = calcular_macros_v2(70, "mujer", 25, "definicion", facilidad_engordar="enseguida")
        assert con["macros"]["entreno"]["proteina"] == sin["macros"]["entreno"]["proteina"]
        assert con["macros"]["entreno"]["grasa"] == sin["macros"]["entreno"]["grasa"]

    def test_el_veto_sigue_mandando(self):
        """"Engordo enseguida" anula, y eso vale para los dos sexos."""
        r = calcular_macros_v2(70, "mujer", 25, "definicion",
                               facilidad_engordar="enseguida", actividad_diaria="muy_activo")
        assert _paso(r, "veto_engorda_enseguida") is not None


class TestEnHombresNoCambiaNada:
    def test_sigue_en_el_20(self):
        r = calcular_macros_v2(85, "hombre", 20, "definicion", facilidad_engordar="casi_no")
        assert _paso(r, "no_engorda")["estado"] == "aplicado"

    def test_al_25_no_se_aplica(self):
        r = calcular_macros_v2(85, "hombre", 25, "definicion", facilidad_engordar="casi_no")
        assert _paso(r, "no_engorda")["estado"] == "no_aplica_bf"

    def test_el_umbral_de_ella_no_se_le_aplica_a_el(self):
        """Si se hubiera puesto el 30 para todos, un hombre al 30 % lo cobraría."""
        r = calcular_macros_v2(85, "hombre", 30, "definicion", facilidad_engordar="casi_no")
        assert _paso(r, "no_engorda")["estado"] == "no_aplica_bf"
