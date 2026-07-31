"""Un solo motor de conteo para toda la app (unificación 31-07-2026).

Hasta ahora convivían dos motores y el mismo alimento contaba distinto según por dónde
entrase el cliente:

  - `calma_suggest` (port fiel de la función ye() del bundle de Calma): buscador, añadir
    a mano, sugeridor.
  - `calma_engine` (reimplementación por categorías): chat, generador de menús, biblioteca.

Contrastados contra el bundle real de Calma (`utils_.ac9d7b60.js` /
`group-home-utils.e5bc7415.js`), `calma_suggest` coincidía en los 3.196 alimentos del
catálogo y `calma_engine` fallaba en 233 (sin contar los de calibración progresiva).
Ahora todos los caminos van por `calma_suggest.macros_efectivos`.

Los valores esperados de este test salen de ejecutar la función ye() ORIGINAL de Calma
sobre esos mismos alimentos, no de nuestra implementación.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calma_suggest import macros_efectivos
from calibracion_dia import macros_item_por_acumulado
from meal_builder import get_effective_macros_per_100g


# Alimentos reales del catálogo. `esperado` = lo que cuenta Calma a esa cantidad.
CASOS = [
    # (nombre, alimento, cantidad_g, (P, H, G) segun Calma)
    ("seitán: Calma cuenta H y G; el motor viejo los anulaba",
     {"nombre": "Seitán", "proteinas": 22.4, "hidratos": 1.8, "grasas": 1.7,
      "racion": 100, "categorias": "28", "unidades": False},
     150, (33.6, 2.7, 2.55)),

    ("acelgas: los hidratos de la verdura cuentan (13.1 con H >= 4)",
     {"nombre": "Acelgas", "proteinas": 2, "hidratos": 4, "grasas": 0,
      "racion": 100, "categorias": "13.1", "unidades": False},
     200, (0.0, 8.0, 0.0)),

    ("crema de tofu: 6.2 cuenta hidratos",
     {"nombre": "Crema de tofu", "proteinas": 5.4, "hidratos": 2.0, "grasas": 15.2,
      "racion": 100, "categorias": "6.2 | 28", "unidades": False},
     150, (8.1, 3.0, 22.8)),

    ("granel con racion != 100: Calma IGNORA la racion, los macros ya son por 100 g",
     {"nombre": "Pechuga de pollo exprés", "proteinas": 13.52, "hidratos": 0,
      "grasas": 0.52, "racion": 52, "categorias": "2.2.3", "unidades": False},
     150, (20.28, 0.0, 0.0)),

    ("pollo normal: la grasa por debajo de 3 g no cuenta (cat 2)",
     {"nombre": "Pechuga de pollo", "proteinas": 23, "hidratos": 0, "grasas": 1.5,
      "racion": 100, "categorias": "2.2.1", "unidades": False},
     200, (46.0, 0.0, 0.0)),
]


def aprox(a, b, tol=0.05):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class TestFidelidadACalma:
    """El conteo tiene que ser el de la calculadora original."""

    @pytest.mark.parametrize("titulo,food,cant,esperado", CASOS,
                             ids=[c[0][:40] for c in CASOS])
    def test_cuenta_como_calma(self, titulo, food, cant, esperado):
        m = macros_efectivos(food, cant)
        assert aprox((m["P"], m["H"], m["G"]), esperado), titulo

    def test_granel_no_divide_por_racion(self):
        # El fallo concreto del motor viejo: dividía SIEMPRE por `racion`, así que un
        # plato preparado a granel con racion 52 salía con el doble de proteína.
        food = {"nombre": "x", "proteinas": 13.52, "hidratos": 0, "grasas": 0.52,
                "racion": 52, "categorias": "2.2.3", "unidades": False}
        assert macros_efectivos(food, 100)["P"] == pytest.approx(13.52, abs=0.05)

    def test_unidades_si_dividen_por_racion(self):
        # En los alimentos por unidades los macros son POR UNIDAD y `racion` son los
        # gramos que pesa una: 2 huevos de 60 g = 120 g -> 2 x 6,4 g de proteína.
        food = {"nombre": "Huevo", "proteinas": 6.4, "hidratos": 0.3, "grasas": 4.8,
                "racion": 60, "categorias": "1.2.1", "unidades": True}
        m = macros_efectivos(food, 120)
        assert m["P"] == pytest.approx(12.8, abs=0.05)


class TestTodosLosCaminosCuentanIgual:
    """Buscador, chat y generador de menús deben dar el mismo número."""

    @pytest.mark.parametrize("titulo,food,cant,esperado", CASOS,
                             ids=[c[0][:40] for c in CASOS])
    def test_chat_igual_que_buscador(self, titulo, food, cant, esperado):
        a = macros_efectivos(food, cant)
        b = macros_item_por_acumulado(food, cant)
        assert aprox((a["P"], a["H"], a["G"]), (b["P"], b["H"], b["G"]))

    @pytest.mark.parametrize("titulo,food,cant,esperado", CASOS,
                             ids=[c[0][:40] for c in CASOS])
    def test_menus_igual_que_buscador(self, titulo, food, cant, esperado):
        a = macros_efectivos(food, 100.0)
        b = get_effective_macros_per_100g(food)
        assert aprox((a["P"], a["H"], a["G"]), (b["P"], b["H"], b["G"]))


class TestCalibracionProgresivaIntacta:
    """La unificación no puede llevarse por delante la calibración del 17-07."""

    ALMENDRAS = {"nombre": "Almendras", "proteinas": 23, "hidratos": 4.8, "grasas": 53.1,
                 "racion": 100, "categorias": "17.2.1", "unidades": False}

    def test_tramos_de_frutos_secos(self):
        # 30 g con el día a 0 -> acumulado 30 (tramo 20-40) -> 50 % de la proteína.
        assert macros_item_por_acumulado(self.ALMENDRAS, 30, acum_fs=0)["P"] == pytest.approx(3.45, abs=0.05)
        # con 30 g ya comidos -> acumulado 60 (>40) -> 100 %.
        assert macros_item_por_acumulado(self.ALMENDRAS, 30, acum_fs=30)["P"] == pytest.approx(6.9, abs=0.05)
        # la grasa no se calibra nunca
        assert macros_item_por_acumulado(self.ALMENDRAS, 30, acum_fs=0)["G"] == pytest.approx(15.93, abs=0.05)

    def test_cereales_y_panes(self):
        # Pan proteico: pasa el ratio P > H/3 (20 > 10), así que su proteína entra en la
        # calibración. Un pan normal (P 9 / H 50) no lo pasa y su P no cuenta nunca.
        pan = {"nombre": "Pan proteico", "proteinas": 20, "hidratos": 30, "grasas": 3,
               "racion": 100, "categorias": "8", "unidades": False}
        # 40 g con el día a 0 -> acumulado 40 (<=50) -> 0 % de la proteína
        assert macros_item_por_acumulado(pan, 40, acum_cp=0)["P"] == 0.0
        # con 80 g ya comidos -> acumulado 120 (>100) -> 100 %
        assert macros_item_por_acumulado(pan, 40, acum_cp=80)["P"] == pytest.approx(8.0, abs=0.05)
        # los hidratos del pan cuentan siempre
        assert macros_item_por_acumulado(pan, 40, acum_cp=0)["H"] == pytest.approx(12.0, abs=0.05)

    def test_pan_normal_no_pasa_el_ratio(self):
        pan = {"nombre": "Pan", "proteinas": 9, "hidratos": 50, "grasas": 1.5,
               "racion": 100, "categorias": "8", "unidades": False}
        # P 9 vs H/3 = 16,7 -> su proteína no cuenta por mucho pan que lleve el día
        assert macros_item_por_acumulado(pan, 40, acum_cp=200)["P"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
