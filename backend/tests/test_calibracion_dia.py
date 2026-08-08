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


class TestElTercioVaAntesDeCalibrar:
    """Punto 3 del doc de Jesus del 07-08: "la regla del tercio va ANTES de calibrar".

    El tercio (P > H/3 en cereales y panes, P > G/3 en frutos secos) se decide sobre los
    macros POR 100 g del alimento, que no dependen del tramo. Solo despues se aplica el
    0 / 50 / 100 % del acumulado del dia.

    Si se hiciera al reves -- calibrar primero y mirar el tercio sobre el valor ya
    reducido -- un alimento que pasa el filtro al 100 % dejaria de pasarlo al 50 %, y su
    proteina caeria a cero en vez de a la mitad. Los numeros de estos tests son justo esa
    diferencia.
    """

    def test_cereal_al_50_da_la_mitad_no_cero(self):
        # CEREAL: P25 / H55, con H/3 = 18,33. Pasa el tercio (25 > 18,33).
        # Al derecho: 25 x 0,5 = 12,5. Al reves: 12,5 > 18,33 es falso -> 0.
        m = macros_item_calibrados(CEREAL, 100, 0.5, 0)
        assert abs(m["P"] - 12.5) < 0.05

    def test_fruto_seco_al_50_da_la_mitad_no_cero(self):
        # ALMENDRAS: P21 / G54, con G/3 = 18. Pasa el tercio (21 > 18).
        # Al derecho: 21 x 0,5 = 10,5. Al reves: 10,5 > 18 es falso -> 0.
        m = macros_item_calibrados(ALMENDRAS, 100, 0, 0.5)
        assert abs(m["P"] - 10.5) < 0.05

    @pytest.mark.parametrize("pct,esperado", [(0.0, 0.0), (0.5, 12.5), (1.0, 25.0)])
    def test_el_tramo_solo_escala_lo_que_ya_paso_el_filtro(self, pct, esperado):
        # La proteina es proporcional al tramo: el filtro no se re-evalua en cada uno.
        m = macros_item_calibrados(CEREAL, 100, pct, 0)
        assert abs(m["P"] - esperado) < 0.05

    @pytest.mark.parametrize("pct", [0.0, 0.5, 1.0])
    def test_el_que_no_pasa_el_filtro_no_cuenta_en_ningun_tramo(self, pct):
        # AVENA: P13 / H60, con H/3 = 20. No pasa (13 < 20): cero en los tres tramos.
        assert macros_item_calibrados(AVENA, 100, pct, 0)["P"] == 0

    def test_da_igual_que_el_alimento_llegue_ya_regulado(self):
        """El otro modo de invertir el orden: pasarle a la calibracion un alimento por el
        que ya paso `aplicar_regla_macros`. A las almendras esa regla les pone la proteina
        a cero (su criterio es otro), asi que el tercio la habria dado por inexistente y
        se perdian 21 g. Ahora se leen los macros de etiqueta guardados, y sale lo mismo."""
        import copy as _copy
        from calma_suggest import aplicar_regla_macros
        for alimento in (ALMENDRAS, CEREAL, AVENA, NUECES):
            crudo = macros_item_calibrados(_copy.deepcopy(alimento), 100, 1.0, 1.0)
            regulado = _copy.deepcopy(alimento)
            aplicar_regla_macros(regulado)
            assert macros_item_calibrados(regulado, 100, 1.0, 1.0) == crudo, alimento["nombre"]

    def test_la_cantidad_no_cambia_si_pasa_el_filtro(self):
        # El tercio se mide por 100 g, asi que comer 20 g o 200 g no altera SI cuenta,
        # solo CUANTO. (El tramo lo decide el acumulado, que es otra cosa.)
        poco = macros_item_calibrados(ALMENDRAS, 20, 0, 1.0)["P"]
        mucho = macros_item_calibrados(ALMENDRAS, 200, 0, 1.0)["P"]
        assert abs(poco - 21 * 0.2) < 0.05
        assert abs(mucho - 21 * 2.0) < 0.05


class TestLoQueNoPasaElFiltroSigueGastandoCupo:
    """Regla del documento del 07-08 (versión actualizada), en negrita y con aviso:

        "El alimento SIGUE SUMANDO AL ACUMULADO del día aunque no pase el filtro. Un pan que
        aporta cero de proteína sí gasta cupo y empuja a los siguientes hacia el 50 % o el
        100 %."
    """

    # P10 con H40: 10 no supera 40/3 = 13,3, así que su proteína no cuenta nunca.
    PAN_QUE_NO_PASA = _f("Pan que no pasa el filtro", "8.1", 10, 40, 2)

    def test_su_proteina_no_cuenta(self):
        macros, _ = calibrar_dia([("C1", [(self.PAN_QUE_NO_PASA, 60)])])
        assert macros["C1"][0]["P"] == 0

    def test_pero_gasta_cupo_y_empuja_al_siguiente(self):
        """60 g de ese pan + 100 g de cereal: el cereal llega con 160 g acumulados y cobra el
        100 %. Sin el pan delante se habría quedado en el 50 %."""
        macros, pcts = calibrar_dia([("C1", [(self.PAN_QUE_NO_PASA, 60)]),
                                     ("C2", [(CEREAL, 100)])])
        assert pcts["C1"]["acum_cp"] == 60
        assert pcts["C2"]["acum_cp"] == 160
        assert pcts["C2"]["pct_cp"] == 1.0
        assert macros["C2"][0]["P"] == 25.0

        solo, p = calibrar_dia([("C2", [(CEREAL, 100)])])
        assert p["C2"]["pct_cp"] == 0.5, "sin el pan delante se queda a medias"
        assert solo["C2"][0]["P"] == 12.5


class TestEnDobleCategoriaGanaLaMasPermisiva:
    """Otra regla nueva del 07-08: si el alimento es de un bloque calibrado pero ADEMÁS es
    proteína en polvo (4) o vegetal (28), su proteína cuenta entera. No es la proteína
    incidental de un cereal: es la que le han puesto a propósito."""

    PAN_CON_PROTEINA_VEGETAL = _f("Pan sin gluten con chía", "8.6 | 28", 12, 40, 5)
    CEREAL_CON_PROTEINA_POLVO = _f("Cereal con proteína", "7.1 | 4", 20, 50, 2)
    CREMA_CON_PROTEINA = _f("Crema de frutos secos con proteína", "17.2.1 | 28", 30, 10, 45)

    @pytest.mark.parametrize("alimento", [PAN_CON_PROTEINA_VEGETAL,
                                          CEREAL_CON_PROTEINA_POLVO,
                                          CREMA_CON_PROTEINA])
    def test_cuenta_entera_aunque_el_acumulado_este_a_cero(self, alimento):
        macros, _ = calibrar_dia([("C1", [(alimento, 30)])])
        assert macros["C1"][0]["P"] == pytest.approx(alimento["proteinas"] * 0.3, abs=0.05)

    def test_el_mismo_pan_sin_la_segunda_categoria_si_calibra(self):
        pan_normal = _f("Pan sin gluten", "8.6", 12, 40, 5)
        macros, _ = calibrar_dia([("C1", [(pan_normal, 30)])])
        assert macros["C1"][0]["P"] == 0, "12 no supera 40/3, y encima el acumulado está a cero"

    def test_sigue_sumando_al_acumulado(self):
        """Saltarse la calibración no le quita el cupo que gasta."""
        _, pcts = calibrar_dia([("C1", [(self.PAN_CON_PROTEINA_VEGETAL, 80)])])
        assert pcts["C1"]["acum_cp"] == 80


if __name__ == "__main__":
    import pytest as _p
    raise SystemExit(_p.main([__file__, "-q"]))
