"""
El quiz de venta (especificacion 31-07-2026, partes 3 y 4).

Cuatro preguntas y una recomendacion. Lo que se fija aqui es la tabla del documento,
fila a fila, y las dos cosas que la rodean:

  - "en caso de duda, se recomienda el nivel mayor",
  - y que el resultado se ve SIN dar el correo (parte 10), asi que la funcion no puede
    depender de tener usuario.
"""
import pytest

from core.quiz_venta import PREGUNTAS, recomendar, resultado_completo
from models.user import PLAN_CATALOG


def resp(r1, r2, r3, r4="A"):
    return {1: r1, 2: r2, 3: r3, 4: r4}


class TestLaTablaDelDocumento:
    """Cada fila de la tabla, tal cual."""

    def test_1D_recomienda_el_3(self):
        assert recomendar(resp("D", "B", "B"))["nivel"] == 3

    def test_1B_mas_2A_recomienda_el_3(self):
        assert recomendar(resp("B", "A", "B"))["nivel"] == 3

    def test_3C_con_cualquier_otra_recomienda_el_3(self):
        for r1 in "ABCD":
            for r2 in "ABCD":
                assert recomendar(resp(r1, r2, "C"))["nivel"] == 3, f"{r1}{r2}C"

    @pytest.mark.parametrize("r2", ["A", "B"])
    def test_1A_mas_2A_o_2B_mas_3A_recomienda_el_2(self, r2):
        assert recomendar(resp("A", r2, "A"))["nivel"] == 2

    def test_1C_2B_3D_recomienda_el_2(self):
        assert recomendar(resp("C", "B", "D"))["nivel"] == 2

    def test_1A_2D_3B_recomienda_el_1(self):
        assert recomendar(resp("A", "D", "B"))["nivel"] == 1

    def test_1A_2C_3B_recomienda_el_1(self):
        assert recomendar(resp("A", "C", "B"))["nivel"] == 1


class TestEnCasoDeDuda:
    """"En caso de duda, se recomienda el nivel mayor"."""

    def test_si_encajan_dos_reglas_gana_la_mayor(self):
        # 1A+2C+3B daria 1... pero si ademas fuera 3C, manda el 3.
        r = recomendar(resp("A", "C", "C"))
        assert r["nivel"] == 3

    def test_1D_con_una_regla_de_nivel_1_sigue_dando_3(self):
        """1D manda siempre: nunca ha entrenado en serio."""
        assert recomendar(resp("D", "C", "B"))["nivel"] == 3

    def test_cuando_encajan_varias_se_nota(self):
        assert recomendar(resp("D", "A", "C"))["reglas_aplicadas"] >= 2

    def test_lo_que_no_esta_en_la_tabla_cae_en_el_intermedio(self):
        """Decision de desarrollo, no del documento: la tabla no cubre las 256
        combinaciones y poner 1.497 EUR delante del que se sale de ella es demasiado."""
        r = recomendar(resp("A", "A", "D"))
        assert r["nivel"] == 2 and r["reglas_aplicadas"] == 0


class TestSiempreRecomiendaAlgo:
    def test_todas_las_combinaciones_dan_un_nivel_valido(self):
        for r1 in "ABCD":
            for r2 in "ABCD":
                for r3 in "ABCD":
                    for r4 in "ABCD":
                        n = recomendar(resp(r1, r2, r3, r4))["nivel"]
                        assert n in (1, 2, 3), f"{r1}{r2}{r3}{r4} -> {n}"

    def test_sin_respuestas_no_revienta(self):
        assert recomendar({})["nivel"] in (1, 2, 3)

    def test_respuestas_a_medias_tampoco(self):
        assert recomendar({1: "A"})["nivel"] in (1, 2, 3)

    def test_tolera_minusculas_y_claves_de_texto(self):
        assert recomendar({"1": "d", "2": "b", "3": "b"})["nivel"] == 3

    def test_siempre_explica_por_que(self):
        for r1 in "ABCD":
            r = recomendar(resp(r1, "B", "B"))
            assert r["por_que"] and len(r["por_que"]) > 20


class TestElResultadoQueSeLeEnseña:
    def _resultado(self, *args):
        return resultado_completo(resp(*args), PLAN_CATALOG)

    def test_enseña_los_tres_niveles_no_solo_el_recomendado(self):
        """"los otros dos visibles debajo, y puede elegir otro"."""
        r = self._resultado("D", "B", "B")
        assert len(r["niveles"]) == 3
        assert sum(1 for n in r["niveles"] if n["recomendado"]) == 1

    def test_el_recomendado_va_marcado(self):
        r = self._resultado("A", "D", "B")
        assert r["recomendado"] == "nivel1"
        assert next(n for n in r["niveles"] if n["recomendado"])["plan"] == "nivel1"

    def test_trae_los_precios_del_catalogo(self):
        precios = {n["plan"]: n["precio"] for n in self._resultado("A", "A", "A")["niveles"]}
        assert precios == {"nivel1": 297.0, "nivel2": 897.0, "nivel3": 1497.0}

    def test_el_nivel_3_va_marcado_como_por_llamada(self):
        """No lleva a un pago: "como se compra: por llamada"."""
        tres = next(n for n in self._resultado("A", "A", "A")["niveles"] if n["plan"] == "nivel3")
        assert tres["por_llamada"] is True

    def test_los_otros_dos_no(self):
        for n in self._resultado("A", "A", "A")["niveles"]:
            if n["plan"] != "nivel3":
                assert n["por_llamada"] is False


class TestLasPreguntas:
    def test_son_cuatro(self):
        assert len(PREGUNTAS) == 4

    def test_cada_una_tiene_sus_cuatro_opciones(self):
        for p in PREGUNTAS:
            assert len(p["opciones"]) == 4
            assert [o["id"] for o in p["opciones"]] == ["A", "B", "C", "D"]

    def test_los_textos_son_los_del_documento(self):
        assert PREGUNTAS[0]["texto"] == "¿Entrenas ahora mismo?"
        assert PREGUNTAS[3]["texto"] == "¿Cuánto tiempo llevas intentándolo?"
