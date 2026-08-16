"""
«Día cuadrado» se dice de UNA sola forma: ±4 g, y la proteína cuenta cubierta.

Había dos cuentas distintas sobre los mismos datos: el calendario de Nutrición guardaba
`is_cuadrado` con tolerancia CERO y el reporte del mes contaba con el margen de la
calculadora, así que «cuadraste los macros 19 días» podía no coincidir con los días verdes
que el cliente ve. Manda el ±4 (Francisco, 16-08) y la proteína cuenta como hecha en cuanto
está cubierta (Jesús, 13-08: pasarse de proteína no es un fallo).

Se fija la regla del reporte, que es la que sale por escrito en el mensual.
"""
import pytest

from calma_suggest import MARGEN_VALIDO


def cuadra(objetivo, total):
    """La misma regla que aplica `core/datos_reporte.dieta_del_periodo`."""
    proteina_hecha = total["P"] - objetivo["P"] >= -MARGEN_VALIDO
    resto = all(abs(objetivo[r] - total[r]) <= MARGEN_VALIDO for r in ("H", "G"))
    return proteina_hecha and resto


OBJETIVO = {"P": 200, "H": 220, "G": 60}


def test_el_margen_es_de_cuatro_gramos():
    assert MARGEN_VALIDO == 4


def test_clavado_cuadra():
    assert cuadra(OBJETIVO, {"P": 200, "H": 220, "G": 60})


def test_por_dos_gramos_no_se_le_quita_el_dia():
    """Es el caso que rompía: 219,8 de 220 con tolerancia cero contaba como NO cuadrado."""
    assert cuadra(OBJETIVO, {"P": 198, "H": 218, "G": 61.5})


def test_pasarse_de_proteina_no_estropea_el_dia():
    """Decisión de Jesús del 13-08. Si no es un fallo en la comida, tampoco puede serlo
    en el recuento del mes."""
    assert cuadra(OBJETIVO, {"P": 240, "H": 220, "G": 60})


def test_pasarse_de_hidratos_si_lo_estropea():
    assert not cuadra(OBJETIVO, {"P": 200, "H": 240, "G": 60})


def test_quedarse_corto_de_proteina_no_cuadra():
    assert not cuadra(OBJETIVO, {"P": 150, "H": 220, "G": 60})


@pytest.mark.parametrize("desvio,esperado", [(0, True), (4, True), (4.1, False), (10, False)])
def test_el_borde_de_los_cuatro_gramos(desvio, esperado):
    assert cuadra(OBJETIVO, {**OBJETIVO, "H": 220 + desvio}) is esperado


def test_la_regla_del_front_es_la_misma():
    """El espejo: si alguien cambia el margen en Nutrición, esto avisa. La cuenta del
    reporte y los días verdes del calendario tienen que salir del mismo número."""
    import os
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(raiz, "frontend", "src", "lib", "exceso.js"), encoding="utf-8") as f:
        assert f"export const MARGEN = {MARGEN_VALIDO};" in f.read(), (
            "el margen del front ya no es el mismo que el del backend")
    with open(os.path.join(raiz, "frontend", "src", "pages", "NutritionPage.jsx"), encoding="utf-8") as f:
        nutricion = f.read()
    assert "const margin = MARGEN;" in nutricion, (
        "el estado del día en Nutrición ha vuelto a llevar un margen escrito a mano")
