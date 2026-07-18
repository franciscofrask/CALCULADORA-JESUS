"""Tests de la calibración progresiva por acumulado del DÍA (spec 17-07-2026).

Cubren los dos ejemplos literales de la spec, la asignación de la comida entera
al tramo tras añadirla, la regla de edición (recalcular esa comida y las
posteriores, nunca las anteriores), las excepciones proteicas y los gates.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calibracion_dia import calibrar_dia, pcts_por_comida, macros_item_calibrados, clasificar_bloque


def _f(nombre, cat, p, h, g, racion=100, unidades=False):
    return {"nombre": nombre, "categorias": cat, "proteinas": p, "hidratos": h,
            "grasas": g, "racion": racion, "unidades": unidades}


CEREAL = _f("Cereal test", "7.1.1", 25, 55, 0)          # P25/H55: P > H/3 -> calibra
PAN = _f("Pan test", "8.1", 25, 55, 0)                   # mismo perfil, cat 8
AVENA = _f("Avena", "7.1.1", 13, 60, 7)                  # P13 < 60/3=20 -> P nunca
CEREAL_PROTEICO = _f("Cereal proteico", "7.1.3", 25, 55, 0)
PAN_PROTEICO = _f("Pan proteico", "8.8", 22, 30, 0)
ALMENDRAS = _f("Almendras", "17.2.1", 21, 4, 54)         # P>18 sí; H=4<18 no
ANACARDOS = _f("Anacardos", "17.2.1", 18, 27, 44)        # P y H > 44/3=14.7: ambos calibran
CACAHUETE_DESG = _f("Cacahuete desgrasado", "17.2.6", 50, 12, 11)
NUECES = _f("Nueces", "17.2.3", 15, 7, 65)               # P=15 < 65/3=21.7 -> P nunca
POLLO = _f("Pechuga de pollo", "2.2.1", 22, 0, 1.5)


class TestEjemploSpecCereales:
    """Ejemplo literal de la spec: cereal P25/H55, comidas de 40/30(pan)/40 g."""

    def test_tres_comidas(self):
        meals = [
            ("C1", [(CEREAL, 40)]),
            ("C2", [(PAN, 30)]),
            ("C3", [(CEREAL, 40)]),
        ]
        macros, pcts = calibrar_dia(meals)
        # C1: acumulado 40 (0-50) -> 0 %
        assert pcts["C1"]["pct_cp"] == 0.0
        assert macros["C1"][0]["P"] == 0
        assert abs(macros["C1"][0]["H"] - 22.0) < 0.1
        # C2: acumulado 70 (50-100) -> 50 %
        assert pcts["C2"]["pct_cp"] == 0.5
        assert abs(macros["C2"][0]["P"] - 3.75) < 0.05
        assert abs(macros["C2"][0]["H"] - 16.5) < 0.1
        # C3: acumulado 110 (>100) -> 100 %
        assert pcts["C3"]["pct_cp"] == 1.0
        assert abs(macros["C3"][0]["P"] - 10.0) < 0.05
        assert abs(macros["C3"][0]["H"] - 22.0) < 0.1

    def test_no_recalcula_hacia_atras(self):
        """C1 queda al 0 % aunque el día acabe >100 g (por construcción: su pct
        solo depende de las comidas anteriores y de ella misma)."""
        macros, _ = calibrar_dia([("C1", [(CEREAL, 40)]), ("C2", [(CEREAL, 200)])])
        assert macros["C1"][0]["P"] == 0

    def test_editar_recalcula_esa_y_posteriores(self):
        """Regla 4: subir C1 de 40->60 g cambia C1 (cruza tramo) y las
        posteriores; con C1 intacta, C1 no cambia aunque cambien C2/C3."""
        antes, _ = calibrar_dia([("C1", [(CEREAL, 40)]), ("C2", [(CEREAL, 20)])])
        editado, _ = calibrar_dia([("C1", [(CEREAL, 60)]), ("C2", [(CEREAL, 20)])])
        assert antes["C1"][0]["P"] == 0            # 40 g -> tramo 0 %
        assert abs(editado["C1"][0]["P"] - 25 * 0.6 * 0.5) < 0.05  # 60 g -> 50 %
        # C2 pasa de acum 60 (50 %) a acum 80 (50 %): mismo tramo, y C1 nunca
        # depende de C2 (cambiar C2 no toca C1)
        solo_c2, _ = calibrar_dia([("C1", [(CEREAL, 40)]), ("C2", [(CEREAL, 300)])])
        assert solo_c2["C1"][0]["P"] == antes["C1"][0]["P"]

    def test_comida_entera_al_tramo_tras_anadirla(self):
        """Una comida que cruza el umbral se asigna ENTERA al tramo final:
        dos cereales de 40 g en la misma comida -> acumulado 80 -> ambos al 50 %."""
        macros, pcts = calibrar_dia([("C1", [(CEREAL, 40), (PAN, 40)])])
        assert pcts["C1"]["pct_cp"] == 0.5
        assert abs(macros["C1"][0]["P"] - 25 * 0.4 * 0.5) < 0.05
        assert abs(macros["C1"][1]["P"] - 25 * 0.4 * 0.5) < 0.05

    def test_gate_p_sobre_h3(self):
        """Avena P13/H60 no pasa P > H/3: su P no cuenta nunca, ni con acumulado alto."""
        macros, _ = calibrar_dia([("C1", [(CEREAL, 150)]), ("C2", [(AVENA, 100)])])
        assert macros["C2"][0]["P"] == 0
        assert abs(macros["C2"][0]["H"] - 60.0) < 0.1

    def test_excepciones_proteicas(self):
        """7.1.3 y 8.8: P siempre al 100 % aunque el acumulado sea 0."""
        macros, _ = calibrar_dia([("C1", [(CEREAL_PROTEICO, 40), (PAN_PROTEICO, 50)])])
        assert abs(macros["C1"][0]["P"] - 10.0) < 0.05   # 25*0.4
        assert abs(macros["C1"][1]["P"] - 11.0) < 0.05   # 22*0.5

    def test_acumulado_conjunto_7_y_8(self):
        """Cereal y pan suman al MISMO acumulado."""
        _, pcts = calibrar_dia([("C1", [(CEREAL, 30)]), ("C2", [(PAN, 30)])])
        assert pcts["C2"]["acum_cp"] == 60
        assert pcts["C2"]["pct_cp"] == 0.5


class TestEjemploSpecFrutosSecos:
    """Ejemplo literal de la spec: almendras P21/H4/G54, comidas de 15/10/20 g."""

    def test_tres_comidas(self):
        meals = [("C1", [(ALMENDRAS, 15)]), ("C2", [(ALMENDRAS, 10)]), ("C3", [(ALMENDRAS, 20)])]
        macros, pcts = calibrar_dia(meals)
        # C1: acum 15 -> 0 %: solo grasa
        assert macros["C1"][0]["P"] == 0 and macros["C1"][0]["H"] == 0
        assert abs(macros["C1"][0]["G"] - 8.1) < 0.1
        # C2: acum 25 -> 50 %
        assert pcts["C2"]["pct_fs"] == 0.5
        assert abs(macros["C2"][0]["P"] - 1.05) < 0.05
        assert abs(macros["C2"][0]["G"] - 5.4) < 0.1
        # C3: acum 45 -> 100 %
        assert abs(macros["C3"][0]["P"] - 4.2) < 0.05
        assert abs(macros["C3"][0]["G"] - 10.8) < 0.1

    def test_hidratos_tambien_calibran(self):
        """Anacardos: P y H pasan el gate G/3 y calibran juntos por tramo."""
        macros, _ = calibrar_dia([("C1", [(ANACARDOS, 15)]), ("C2", [(ANACARDOS, 10)])])
        assert macros["C1"][0]["P"] == 0 and macros["C1"][0]["H"] == 0
        assert abs(macros["C2"][0]["P"] - 18 * 0.1 * 0.5) < 0.05
        assert abs(macros["C2"][0]["H"] - 27 * 0.1 * 0.5) < 0.05

    def test_gate_g3_por_alimento(self):
        """Nueces P15 < G65/3: su P no cuenta nunca, pero SÍ suman al acumulado."""
        macros, pcts = calibrar_dia([("C1", [(NUECES, 25)]), ("C2", [(ALMENDRAS, 10)])])
        assert macros["C1"][0]["P"] == 0
        assert pcts["C2"]["acum_fs"] == 35          # 25 de nueces + 10 de almendras
        assert abs(macros["C2"][0]["P"] - 21 * 0.1 * 0.5) < 0.05  # tramo 50 %

    def test_17_2_6_es_fruto_seco(self):
        macros, pcts = calibrar_dia([("C1", [(CACAHUETE_DESG, 15)]), ("C2", [(CACAHUETE_DESG, 30)])])
        assert macros["C1"][0]["P"] == 0
        assert pcts["C2"]["pct_fs"] == 1.0          # acum 45 -> 100 %
        assert abs(macros["C2"][0]["P"] - 50 * 0.3) < 0.05

    def test_acumuladores_independientes(self):
        """Cereal no suma al de frutos secos ni al revés."""
        _, pcts = calibrar_dia([("C1", [(CEREAL, 90), (ALMENDRAS, 15)])])
        assert pcts["C1"]["acum_cp"] == 90 and pcts["C1"]["pct_cp"] == 0.5
        assert pcts["C1"]["acum_fs"] == 15 and pcts["C1"]["pct_fs"] == 0.0


class TestFueraDeBloques:
    def test_alimento_normal_intacto(self):
        """El pollo (ni cereal ni fruto seco) va por el motor de siempre."""
        assert clasificar_bloque(POLLO) is None
        macros, _ = calibrar_dia([("C1", [(POLLO, 200)])])
        assert abs(macros["C1"][0]["P"] - 44.0) < 0.1
        assert macros["C1"][0]["G"] == 0            # G<3: no cuenta (regla de categoría)

    def test_unidades_suman_gramos_reales(self):
        """Alimentos por unidad: gramos = unidades x ración (regla 1 de la spec)."""
        pan_ud = _f("Pan unidad", "8.1", 25, 55, 0, racion=60, unidades=True)
        # 60 g por unidad y macros POR UNIDAD en la BD (per100: P25/H55 con racion 60
        # significa por unidad P25... aquí los macros son por ración=unidad)
        _, pcts = calibrar_dia([("C1", [(pan_ud, 120)])])   # 2 ud = 120 g
        assert pcts["C1"]["acum_cp"] == 120
        assert pcts["C1"]["pct_cp"] == 1.0


if __name__ == "__main__":
    import pytest as _p
    raise SystemExit(_p.main([__file__, "-q"]))
