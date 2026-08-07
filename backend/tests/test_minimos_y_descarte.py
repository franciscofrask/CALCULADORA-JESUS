"""Cantidades mínimas por categoría y descarte por debajo del mínimo (punto 5, doc 07-08).

La regla: cada categoría tiene una cantidad más pequeña con la que tiene sentido ponerla en
un plato (5 g de aceite, 50 de verdura, 100 de bebida vegetal, media lata de atún). Si lo que
cabe en la comida no llega a ese mínimo, el alimento **se descarta**; no entra a cero.

Lo que se veía antes: "Queso Havarti · 0 ud" y "Huevos enteros M · 0 ud" ocupando línea en la
comida. El motor devolvía 0 para decir "no cabe" y la ruta lo entregaba como si 0 fuese una
cantidad; la pantalla, al ver un alimento con los tres macros a cero, lo tomaba por un
alimento libre (konjac, salsas zero) y lo dejaba entrar igual.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calma_suggest import (Z_MIN, MINIMOS_JESUS, CANTIDAD_MINIMA_GRANEL, cantidad_minima,
                           ajustar_cantidad, aplicar_regla_macros)


def _f(nombre, cat, unidades=False, racion=100, **macros):
    base = {"nombre": nombre, "categorias": cat, "unidades": unidades, "racion": racion,
            "proteinas": 0, "hidratos": 0, "grasas": 0}
    base.update(macros)
    return base


class TestElMapaDeMinimos:
    """Ya estaba portado de la calculadora antigua; esto fija lo que el doc da por bueno."""

    def test_estan_las_categorias_del_mapa_antiguo(self):
        assert len(Z_MIN) >= 56

    @pytest.mark.parametrize("cat,esperado,que_es", [
        ("17.1.1", 5, "aceites"),
        ("13.1", 50, "verduras"),
        ("24", 100, "bebidas vegetales"),
        ("17.2.1", 10, "frutos secos"),
    ])
    def test_los_cuatro_minimos_que_nombra_el_documento(self, cat, esperado, que_es):
        assert cantidad_minima(_f(que_es, cat)) == esperado

    def test_los_frutos_secos_son_decision_de_jesus(self):
        # En el mapa antiguo heredaban el 5 de la categoría 17; el doc del 07-08 pide 10, y
        # ese cambio vive aparte para que se vea que es suyo y no heredado.
        assert MINIMOS_JESUS["17.2"] == 10

    def test_lo_que_no_esta_en_el_mapa_cae_al_por_defecto(self):
        assert cantidad_minima(_f("Algo raro", "99.9")) == CANTIDAD_MINIMA_GRANEL

    def test_el_minimo_propio_del_alimento_manda(self):
        f = _f("Con minimo propio", "13.1")
        f["minimo"] = 30
        assert cantidad_minima(f) == 30


class TestSeDescartaNoSeQuedaACero:
    """El motor devuelve 0 para decir "no cabe ni a su cantidad mínima"."""

    def test_lo_que_no_llega_al_minimo_devuelve_cero(self):
        # Queso: mínimo 20 g (cat 5.3) y sitio para muy poco.
        queso = _f("Queso", "5.3", proteinas=25, grasas=20)
        aplicar_regla_macros(queso)
        assert ajustar_cantidad(queso, {"proteinas": 2, "hidratos": 1, "grasas": 1}) == 0.0

    def test_con_hueco_de_sobra_si_sale_cantidad(self):
        queso = _f("Queso", "5.3", proteinas=25, grasas=20)
        aplicar_regla_macros(queso)
        assert ajustar_cantidad(queso, {"proteinas": 40, "hidratos": 20, "grasas": 25}) > 0

    def test_un_alimento_libre_no_se_descarta_nunca(self):
        # Konjac: sin macros que gasten hueco, siempre cabe. No puede confundirse con un
        # "no cabe" solo porque sus macros sean cero.
        konjac = _f("Konjac", "16.4")
        aplicar_regla_macros(konjac)
        assert ajustar_cantidad(konjac, {"proteinas": 2, "hidratos": 1, "grasas": 1}) > 0


class TestLaRutaDeAnadirNoDevuelveCantidadCero:
    """`/adjust` tiene que decir que no cabe, en vez de entregar un 0 como si fuera cantidad."""

    def test_el_contrato_de_la_respuesta(self):
        # Se comprueba la forma, no la ruta entera (necesitaría base de datos): cuando no
        # cabe, `cabe` es False y viaja el mínimo para poder explicárselo al cliente.
        from routes.calculator import _minimo_en_gramos
        assert _minimo_en_gramos(_f("Huevo", "1.2.1", unidades=True, racion=53)) == 53.0
        assert _minimo_en_gramos(_f("Queso loncha", "5.3", unidades=True, racion=25)) == 25.0
        assert _minimo_en_gramos(_f("Aceite", "17.1.1")) == 5.0


class TestLaParidadNoSeRompe:
    """Cambiar el mínimo de los frutos secos no puede tocar el resto del motor."""

    @pytest.mark.parametrize("cat", ["2.2.1", "13.1", "8.1", "4.1.1", "21.1", "5.3"])
    def test_los_demas_minimos_siguen_siendo_los_del_mapa_antiguo(self, cat):
        esperado = {"2.2.1": 50, "13.1": 50, "8.1": 25, "4.1.1": 5, "21.1": 25, "5.3": 20}
        assert cantidad_minima(_f("x", cat)) == esperado[cat]

    def test_solo_hay_un_ajuste_sobre_el_mapa_antiguo(self):
        # Si alguien añade más, que sea a sabiendas y actualizando este test.
        assert MINIMOS_JESUS == {"17.2": 10}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
