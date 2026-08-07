# -*- coding: utf-8 -*-
"""La dieta que ya come MODULA, no manda.

Hasta el 06-08-2026, si el cliente declaraba su dieta y la confirmaba, sus hidratos
PISABAN el resultado: se tiraban la tabla y todos los modificadores. Jesus lo corrigio el
15 de julio -- "NO manda sobre todo, es un factor mas, el que mas pesa, pero no
determinante" -- y se quedo pendiente de rediseñar.

Ahora se queda a +-20 % de lo que dice la tabla ya modificada. Sigue siendo el factor que
mas pesa (ninguno de los otros llega solo a tanto: +10 activo, +20 deporte, +20 engordo),
pero ya no se lleva el calculo por delante.

Con UNA excepcion que se queda entera: quien viene comiendo menos de 75 g de hidratos en
definicion recibe el arranque minimo fijo. Eso es fisica, no criterio.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from macro_engine import TOPE_DIETA_REPORTADA, calcular_macros_v2   # noqa: E402


def _hc_entreno(r):
    """Los hidratos del dia de entreno: comidas + peri, que es como se comparan."""
    return r["macros"]["entreno"]["hidratos"] + r["macros"]["perientreno"]["hidratos"]


def _sin_dieta(**kw):
    return calcular_macros_v2(85, "hombre", 25, "definicion", **kw)


def _con_dieta(hc, como_va="bien", **kw):
    return calcular_macros_v2(85, "hombre", 25, "definicion", como_va=como_va,
                              dieta_reportada={"hc_entreno": hc, "grasa_entreno": None}, **kw)


def _paso(r, nombre):
    return next((p for p in r["desglose"] if p["paso"] == nombre), None)


class TestElTopeExiste:
    def test_es_del_20(self):
        assert TOPE_DIETA_REPORTADA == 0.20

    def test_una_dieta_enorme_no_se_lleva_el_calculo(self):
        """Alguien que dice comer 500 g de hidratos no acaba con 500."""
        base = _hc_entreno(_sin_dieta())
        r = _con_dieta(500)
        assert _hc_entreno(r) <= base * 1.2 + 5   # +5 por el redondeo a multiplo de 5
        assert _hc_entreno(r) < 500

    def test_y_deja_dicho_que_lo_recorto(self):
        assert _paso(_con_dieta(500), "tope_dieta") is not None

    def test_una_dieta_pequeña_tampoco(self):
        """Por debajo tambien hay suelo: 90 g estando la tabla en 160."""
        base = _hc_entreno(_sin_dieta())
        r = _con_dieta(90, como_va="mantengo")
        assert _hc_entreno(r) >= base * 0.8 - 5

    def test_dentro_del_margen_no_toca_nada(self):
        """Si su dieta ya esta cerca de la tabla, el tope no pinta nada."""
        base = _hc_entreno(_sin_dieta())
        r = _con_dieta(base * 1.05)
        assert _paso(r, "tope_dieta") is None


class TestSigueSiendoElQueMasPesa:
    def test_mueve_mas_que_cualquier_otro_modificador(self):
        base = _hc_entreno(_sin_dieta())
        solo_activo = _hc_entreno(_sin_dieta(actividad_diaria="muy_activo"))
        con_dieta_alta = _hc_entreno(_con_dieta(500))
        assert con_dieta_alta - base > solo_activo - base

    def test_su_dieta_sigue_moviendo_el_resultado(self):
        """Modular no es ignorar: comer mucho y comer poco no pueden dar lo mismo."""
        assert _hc_entreno(_con_dieta(500)) > _hc_entreno(_con_dieta(90, como_va="mantengo"))


class TestLaExcepcionSeQueda:
    def test_el_que_viene_en_las_ultimas_no_pasa_por_el_tope(self):
        """Menos de 75 g en definicion: arranque minimo fijo, sin acotar."""
        r = _con_dieta(60)
        assert _paso(r, "dieta_reportada")["rama"] == "def_ultimas"
        assert _paso(r, "tope_dieta") is None

    def test_y_le_da_el_arranque_del_documento(self):
        r = _con_dieta(60)
        assert r["macros"]["entreno"]["hidratos"] == 60
        assert r["macros"]["perientreno"]["hidratos"] == 15


class TestLoQueNoDebeCambiar:
    def test_sin_dieta_declarada_todo_igual(self):
        """Quien no declara dieta no puede notar este cambio."""
        r = _sin_dieta(actividad_diaria="muy_activo", facilidad_engordar="casi_no")
        assert _paso(r, "tope_dieta") is None
        assert _paso(r, "dieta_reportada") is None

    def test_la_proteina_no_se_toca(self):
        assert _con_dieta(500)["macros"]["entreno"]["proteina"] == _sin_dieta()["macros"]["entreno"]["proteina"]

    def test_el_descanso_nunca_supera_al_entreno(self):
        for hc in [90, 150, 200, 300, 500]:
            r = _con_dieta(hc)
            assert r["macros"]["descanso"]["hidratos"] <= r["macros"]["entreno"]["hidratos"], hc

    def test_los_suelos_siguen_mandando(self):
        r = _con_dieta(90, como_va="mantengo")
        assert r["macros"]["entreno"]["hidratos"] >= 60
        assert r["macros"]["descanso"]["hidratos"] >= 50

    def test_en_volumen_tambien_se_acota(self):
        base = calcular_macros_v2(85, "hombre", 15, "volumen")
        alto = calcular_macros_v2(85, "hombre", 15, "volumen", como_va="bien",
                                  dieta_reportada={"hc_entreno": 700, "grasa_entreno": None})
        assert _hc_entreno(alto) <= _hc_entreno(base) * 1.2 + 5
