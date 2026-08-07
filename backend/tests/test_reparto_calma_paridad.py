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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
