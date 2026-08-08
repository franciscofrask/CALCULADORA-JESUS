"""Paridad del reparto por comida con la calculadora antigua (punto 1 del doc del 07-08).

El doc de Jesus del 07-08 dice que los escenarios de hidratos "no se estan aplicando" y da un
caso: 4 comidas, entreno tras la Comida 1, y en la app 19 / 19 / 14 / 14 donde deberia salir
22,5 / 22,5 / 10 / 10.

Lo que se comprobo:
  - Las tablas SI estaban bien. Este fichero las verifica una a una contra `pe()` del bundle
    de Calma (`_calma_ref/utils_.ac9d7b60.js`), reimplementada aqui como `pe_calma` desde el
    codigo original: las tablas z (proteinas y grasas), J (100-150 g) y W (>150 g), y los
    cinco tramos de hidratos.
  - Lo que deformaba el reparto era el presupuesto de perientreno de los modos `sin_peri` y
    `solo_intra` (que Calma no tiene): se sumaba a partes iguales DESPUES de repartir. Ahora
    entra en el total del dia ANTES, que es lo que reproduce el 22,5 / 22,5 / 10 / 10.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from macro_distribution import distribuir_macros


# ── `pe()` de Calma, portada literalmente desde el bundle ────────────────────
# z[a] = {proteinas, grasas} por momento de entreno; J = tramo 100-150 g; W = >150 g.
# Los arrays llevan un 0 delante porque Calma indexa las comidas de 1 a 4.
Z_CALMA = [
    {"proteinas": [0, .25, .25, .20, .30], "grasas": [0, .20, .25, .25, .30]},
    {"proteinas": [0, .25, .25, .20, .30], "grasas": [0, .20, .20, .30, .30]},
    {"proteinas": [0, .25, .20, .25, .30], "grasas": [0, .30, .20, .20, .30]},
    {"proteinas": [0, .30, .25, .20, .25], "grasas": [0, .30, .30, .20, .20]},
]
J_CALMA = [[0, .36, .18, .10, .36], [0, .36, .36, .18, .10],
           [0, .18, .36, .36, .10], [0, .10, .18, .36, .36]]
W_CALMA = [[0, .30, .20, .20, .30], [0, .30, .30, .20, .20],
           [0, .20, .30, .30, .20], [0, .20, .20, .30, .30]]


def pe_calma(p, h, g, momento, comida):
    """Macros de UNA comida segun `pe()` de Calma. `momento` 0-3, `comida` 1-4."""
    a, s = momento, comida
    out = {"P": p * Z_CALMA[a]["proteinas"][s], "G": g * Z_CALMA[a]["grasas"][s], "H": 0}
    if h < 30:
        if s == a + 1:
            out["H"] = h
    elif h < 50:
        if s % 4 == a:
            out["H"] = 10
        elif s == a + 1:
            out["H"] = h - 10
    elif h < 100:
        t = (s - a) % 4 if (s - a) >= 0 else (s - a)  # JS: el resto conserva el signo
        out["H"] = (h - 20) * 0.5 if t in (0, 1) else 10
    elif h <= 150:
        out["H"] = h * J_CALMA[a][s]
    else:
        out["H"] = h * W_CALMA[a][s]
    return out


def nuestro(p, h, g, momento, opcion_peri="intra_post", p_peri=0.0, h_peri=0.0):
    return distribuir_macros(
        p_entreno=p, h_entreno=h, g_entreno=g,
        p_peri=p_peri, h_peri=h_peri,
        p_descanso=p, h_descanso=h, g_descanso=g,
        tipo_dia="entrenamiento", num_comidas=4,
        momento_entreno=momento, opcion_peri=opcion_peri,
    )


# Un valor de hidratos dentro de cada uno de los cinco tramos, y las fronteras.
HIDRATOS = [0, 10, 25, 29, 30, 40, 49, 50, 65, 99, 100, 120, 150, 151, 200, 300]


class TestParidadConCalma:
    """Sin peri de por medio, cada comida tiene que dar lo que da `pe()` de Calma."""

    @pytest.mark.parametrize("h", HIDRATOS)
    @pytest.mark.parametrize("momento", [0, 1, 2, 3])
    def test_cada_comida_coincide(self, h, momento):
        comidas = nuestro(120, h, 50, momento)["comidas"]
        for i in (1, 2, 3, 4):
            esperado = pe_calma(120, h, 50, momento, i)
            obtenido = comidas[f"C{i}"]
            for macro in ("P", "H", "G"):
                assert obtenido[macro] == pytest.approx(esperado[macro], abs=0.05), (
                    f"H={h} momento={momento} C{i} {macro}")

    @pytest.mark.parametrize("h", HIDRATOS)
    @pytest.mark.parametrize("momento", [0, 1, 2, 3])
    def test_los_hidratos_del_dia_no_se_pierden(self, h, momento):
        comidas = nuestro(120, h, 50, momento)["comidas"]
        assert sum(c["H"] for c in comidas.values()) == pytest.approx(h, abs=0.2)

    def test_descanso_reparte_a_partes_iguales(self):
        # Calma: dia de descanso -> 0.25 de cada macro a cada comida.
        r = distribuir_macros(120, 60, 50, 35, 15, 120, 60, 50, "descanso", 4, 1, "intra_post")
        for c in r["comidas"].values():
            assert (c["P"], c["H"], c["G"]) == (30.0, 15.0, 12.5)

    def test_perientreno_20_30_y_80_70(self):
        peri = nuestro(120, 60, 50, 1, p_peri=40, h_peri=30)["periworkout"]
        assert (peri["Intra"]["P"], peri["Intra"]["H"]) == (8.0, 9.0)
        assert (peri["Post"]["P"], peri["Post"]["H"]) == (32.0, 21.0)


class TestLosCincoTramos:
    """Los cinco tramos del doc, con los numeros del propio doc."""

    def test_menos_de_30_todo_a_la_de_despues(self):
        h = [nuestro(120, 25, 50, 1)["comidas"][f"C{i}"]["H"] for i in (1, 2, 3, 4)]
        assert h == [0, 25.0, 0, 0]

    def test_de_30_a_50_diez_a_la_del_entreno(self):
        h = [nuestro(120, 40, 50, 1)["comidas"][f"C{i}"]["H"] for i in (1, 2, 3, 4)]
        assert h == [10, 30.0, 0, 0]

    def test_de_30_a_50_en_ayunas_los_diez_van_a_la_comida_4(self):
        # Confirmado por Jesus el 07-08: es intencionado (mealIndex % 4 == trainMoment).
        h = [nuestro(120, 40, 50, 0)["comidas"][f"C{i}"]["H"] for i in (1, 2, 3, 4)]
        assert h == [30.0, 0, 0, 10]

    def test_de_50_a_100_la_mitad_de_h_menos_20(self):
        h = [nuestro(120, 65, 50, 1)["comidas"][f"C{i}"]["H"] for i in (1, 2, 3, 4)]
        assert h == [22.5, 22.5, 10, 10]

    def test_de_100_a_150_tabla_a(self):
        h = [nuestro(120, 120, 50, 1)["comidas"][f"C{i}"]["H"] for i in (1, 2, 3, 4)]
        assert h == [43.2, 43.2, 21.6, 12.0]   # 36 / 36 / 18 / 10

    def test_mas_de_150_tabla_b(self):
        h = [nuestro(120, 200, 50, 1)["comidas"][f"C{i}"]["H"] for i in (1, 2, 3, 4)]
        assert h == [60.0, 60.0, 40.0, 40.0]   # 30 / 30 / 20 / 20


class TestElPeriNoDeformaElReparto:
    """El caso exacto del doc: 50 g de hidratos de entreno + 15 de peri, modo `sin_peri`.

    Antes el peri se sumaba a partes iguales despues de repartir -> 18,8 / 18,8 / 13,8 / 13,8
    (los 19 / 19 / 14 / 14 que vio Jesus). Ahora entra en el total del dia antes de repartir.
    """

    def test_caso_del_documento(self):
        c = nuestro(120, 50, 50, 1, opcion_peri="sin_peri", p_peri=35, h_peri=15)["comidas"]
        assert [c[f"C{i}"]["H"] for i in (1, 2, 3, 4)] == [22.5, 22.5, 10, 10]

    def test_no_vuelve_el_reparto_plano(self):
        c = nuestro(120, 50, 50, 1, opcion_peri="sin_peri", p_peri=35, h_peri=15)["comidas"]
        assert [round(c[f"C{i}"]["H"]) for i in (1, 2, 3, 4)] != [19, 19, 14, 14]

    @pytest.mark.parametrize("opcion", ["sin_peri", "solo_intra"])
    def test_el_dia_sigue_sumando_lo_mismo(self, opcion):
        # Cambia como se reparte, no cuanto come: 50 + 15 = 65 g de hidratos en total.
        r = nuestro(120, 50, 50, 1, opcion_peri=opcion, p_peri=35, h_peri=15)
        total_h = (sum(c["H"] for c in r["comidas"].values())
                   + sum(c["H"] for c in r["periworkout"].values()))
        assert total_h == pytest.approx(65.0, abs=0.2)

    def test_el_peri_en_bebida_no_entra_en_las_comidas(self):
        # Con intra_post el peri va aparte y las comidas solo reparten los 50 del entreno.
        c = nuestro(120, 50, 50, 1, opcion_peri="intra_post", p_peri=35, h_peri=15)["comidas"]
        assert [c[f"C{i}"]["H"] for i in (1, 2, 3, 4)] == [15.0, 15.0, 10, 10]


class TestNoSeGuardaEstadoEntreLlamadas:
    """Aviso 1 del doc del 07-08 sobre el codigo antiguo: alli `getMealsPortions` escribia
    encima del objeto de constantes, asi que una llamada se llevaba lo que habia dejado la
    anterior. Aqui las tablas son de solo lectura; estos tests lo dejan fijado."""

    def test_dos_llamadas_iguales_dan_lo_mismo(self):
        a = nuestro(120, 65, 50, 1)["comidas"]
        nuestro(180, 250, 65, 3, opcion_peri="sin_peri", p_peri=40, h_peri=30)  # llamada intercalada
        b = nuestro(120, 65, 50, 1)["comidas"]
        assert a == b

    def test_las_tablas_no_se_tocan(self):
        import copy as _copy
        import macro_distribution as md
        antes = _copy.deepcopy((md.DIST_E1, md.DIST_E2))
        for momento in (0, 1, 2, 3):
            for h in (25, 40, 65, 120, 200):
                nuestro(120, h, 50, momento, opcion_peri="sin_peri", p_peri=40, h_peri=30)
        assert (md.DIST_E1, md.DIST_E2) == antes

    @pytest.mark.parametrize("tabla", ["DIST_E1", "DIST_E2"])
    def test_las_tablas_suman_cien(self, tabla):
        # El otro aviso: en el codigo antiguo `defaultMealsPortions` sumaba 133 % de hidratos
        # y 80 % de grasas. Ninguna de las nuestras puede hacer eso.
        import macro_distribution as md
        for momento, reparto in getattr(md, tabla).items():
            for i, macro in enumerate(("P", "H", "G")):
                assert sum(v[i] for v in reparto.values()) == 100, f"{tabla} momento {momento} {macro}"


class TestUnMomentoRaroNoTumbaElDia:
    """El momento de entreno indexa las tablas: fuera de 0-3 daba KeyError -> 500 en
    /distribute -> la pantalla de Nutricion con todos los objetivos a cero."""

    @pytest.mark.parametrize("momento", [4, -1, 99, None, "x", 1.7])
    def test_cae_al_de_siempre(self, momento):
        r = distribuir_macros(120, 65, 50, 35, 15, 120, 65, 50,
                              "entrenamiento", 4, momento, "intra_post")
        assert [r["comidas"][f"C{i}"]["H"] for i in (1, 2, 3, 4)] == [22.5, 22.5, 10, 10]
        assert r["config"]["momento_entreno"] == 1  # el que se uso, no el que llego

    def test_un_numero_en_texto_se_entiende(self):
        r = distribuir_macros(120, 65, 50, 35, 15, 120, 65, 50,
                              "entrenamiento", 4, "2", "intra_post")
        assert [r["comidas"][f"C{i}"]["H"] for i in (1, 2, 3, 4)] == [10, 22.5, 22.5, 10]


# ── La tabla de prueba del propio documento (versión del 07-08 actualizada) ──
#
# Jesús la incluyó para que se pueda verificar la implementación: "si tu implementación da
# estos números, está bien". Son sus valores, no deducciones nuestras, así que es el mejor
# juez que hay. Incluye las filas de "en ayunas", que esa versión del documento confirma que
# la calculadora en producción SÍ aplica (lo que él leyó era una versión vieja del código).

TABLA_DEL_DOCUMENTO = [
    (25, 1, [0, 25, 0, 0]),
    (25, 2, [0, 0, 25, 0]),
    (40, 1, [10, 30, 0, 0]),
    (40, 3, [0, 0, 10, 30]),
    (60, 1, [20, 20, 10, 10]),
    (60, 2, [10, 20, 20, 10]),
    (65, 1, [22.5, 22.5, 10, 10]),
    (90, 1, [35, 35, 10, 10]),
    (120, 1, [43.2, 43.2, 21.6, 12]),
    (120, 3, [12, 21.6, 43.2, 43.2]),
    (200, 1, [60, 60, 40, 40]),
    (200, 2, [40, 60, 60, 40]),
]

TABLA_EN_AYUNAS = [
    (25, [25, 0, 0, 0]),
    (40, [30, 0, 0, 10]),
    (60, [20, 10, 10, 20]),
    (65, [22.5, 10, 10, 22.5]),
    (90, [35, 10, 10, 35]),
    (120, [43.2, 21.6, 12, 43.2]),
    (200, [60, 40, 40, 60]),
]


class TestLaTablaDePruebaDelDocumento:

    @pytest.mark.parametrize("h,momento,esperado", TABLA_DEL_DOCUMENTO)
    def test_fila(self, h, momento, esperado):
        c = nuestro(120, h, 50, momento)["comidas"]
        assert [c[f"C{i}"]["H"] for i in (1, 2, 3, 4)] == pytest.approx(esperado, abs=0.05)

    @pytest.mark.parametrize("h,esperado", TABLA_EN_AYUNAS)
    def test_fila_en_ayunas(self, h, esperado):
        """Con el entreno en ayunas las comidas cargadas son la 1 y la 4, que es lo que
        describen los clientes en las dudas frecuentes de la plataforma."""
        c = nuestro(120, h, 50, 0)["comidas"]
        assert [c[f"C{i}"]["H"] for i in (1, 2, 3, 4)] == pytest.approx(esperado, abs=0.05)

    @pytest.mark.parametrize("h", [40, 65, 120, 200])
    def test_el_dia_de_descanso_reparte_a_cuartos(self, h):
        """A partes iguales, con una tolerancia de un décimo de gramo: el reparto redondea
        cada comida a 0,1 g, así que con hidratos que no se dividen entre cuatro (65 ÷ 4 =
        16,25) se pierden hasta 0,2 g del día. No se toca por eso: lo que se le enseña al
        cliente va redondeado a múltiplos de 5 (punto 6), así que ni se ve."""
        r = distribuir_macros(120, h, 50, 0, 0, 120, h, 50, "descanso", 4, 1, "intra_post")
        assert [r["comidas"][f"C{i}"]["H"] for i in (1, 2, 3, 4)] == pytest.approx([h / 4] * 4, abs=0.1)


class TestConTresComidasNoHayEscenario:
    """Punto 2 del documento: los tramos son solo para 4 comidas. Con 3, cada comida se lleva
    un tercio de cada macro aunque sea día de entreno. El perientreno sí se aplica igual."""

    @pytest.mark.parametrize("h", [25, 65, 120, 200])
    @pytest.mark.parametrize("momento", [0, 1, 2, 3])
    def test_un_tercio_de_cada_macro(self, h, momento):
        r = distribuir_macros(180, h, 60, 40, 30, 180, h, 60,
                              "entrenamiento", 3, momento, "intra_post")
        c = r["comidas"]
        assert len(c) == 3
        for macro, total in (("P", 180), ("H", h), ("G", 60)):
            valores = [c[f"C{i}"][macro] for i in (1, 2, 3)]
            assert valores == pytest.approx([total / 3] * 3, abs=0.2), macro

    def test_el_perientreno_se_sigue_aplicando(self):
        r = distribuir_macros(180, 120, 60, 40, 30, 180, 120, 60,
                              "entrenamiento", 3, 1, "intra_post")
        assert r["periworkout"]["Intra"] == {"P": 8.0, "H": 9.0, "G": 0.0}
        assert r["periworkout"]["Post"] == {"P": 32.0, "H": 21.0, "G": 0.0}


class TestLosCuatroModosDePerientreno:
    """Punto 3 del documento, con su tabla."""

    BASE = dict(p_entreno=180, h_entreno=200, g_entreno=60, p_peri=40, h_peri=30,
                p_descanso=180, h_descanso=200, g_descanso=60,
                tipo_dia="entrenamiento", num_comidas=4, momento_entreno=1)

    def _r(self, modo):
        return distribuir_macros(opcion_peri=modo, **self.BASE)

    def test_intra_mas_post(self):
        p = self._r("intra_post")["periworkout"]
        assert (p["Intra"]["P"], p["Intra"]["H"]) == (8.0, 9.0)      # 20 % y 30 %
        assert (p["Post"]["P"], p["Post"]["H"]) == (32.0, 21.0)      # 80 % y 70 %

    def test_solo_post(self):
        p = self._r("solo_post")["periworkout"]
        assert "Intra" not in p
        assert (p["Post"]["P"], p["Post"]["H"]) == (40, 30)          # 100 % y 100 %

    def test_solo_intra(self):
        r = self._r("solo_intra")
        assert "Post" not in r["periworkout"]
        assert (r["periworkout"]["Intra"]["P"], r["periworkout"]["Intra"]["H"]) == (10.0, 10.5)
        # El resto (75 % y 65 %) se reparte entre las comidas.
        assert sum(c["P"] for c in r["comidas"].values()) == pytest.approx(180 + 30, abs=0.5)
        assert sum(c["H"] for c in r["comidas"].values()) == pytest.approx(200 + 19.5, abs=0.5)

    def test_sin_peri(self):
        r = self._r("sin_peri")
        assert r["periworkout"] == {}
        assert sum(c["P"] for c in r["comidas"].values()) == pytest.approx(220, abs=0.5)
        assert sum(c["H"] for c in r["comidas"].values()) == pytest.approx(230, abs=0.5)

    @pytest.mark.parametrize("modo", ["intra_post", "solo_post", "solo_intra"])
    def test_ni_el_intra_ni_el_post_llevan_grasa(self, modo):
        for comida in self._r(modo)["periworkout"].values():
            assert comida["G"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
