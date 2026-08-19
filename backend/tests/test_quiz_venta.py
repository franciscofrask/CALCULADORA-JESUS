"""
El quiz de venta (documento del test de nivel, 06-08-2026).

Seis preguntas y una recomendacion. Lo que se fija aqui es su cruce, frase a frase, y
las tres cosas que lo rodean:

  - "como mucho UNA subida de nivel, por lo que llegue antes",
  - el Nivel 3 se PROPONE con los tres precios delante, no se impone,
  - y el resultado se ve SIN dar el correo, asi que nada de esto puede depender de tener
    usuario.

Sustituye a la tabla de cuatro preguntas y siete combinaciones de la especificacion del
31-07: aquella daba el nivel por combinaciones de las tres primeras y la cuarta ni se
miraba.
"""
import pytest

from core.quiz_venta import FRASES, PREGUNTAS, recomendar, resultado_completo
from models.user import PLAN_CATALOG


# Respuestas que no mueven nada: sin fecha, y poco tiempo intentandolo.
NEUTRO = {1: "A", 2: "B", 3: "A", 4: "A", 6: "C"}


def resp(frase, tiempo="A", fecha="C"):
    """Las respuestas del test. `tiempo` es la P4 y `fecha` la P6: las dos que suben."""
    r = dict(NEUTRO)
    r[5] = frase
    r[4] = tiempo
    r[6] = fecha
    return r


class TestElCruceDelDocumento:
    """Su tabla: con cual se identifica -> que sale."""

    @pytest.mark.parametrize("frase,nivel", [
        ("A", 1),   # estoy en forma pero harto del proceso -> le falta libertad
        ("D", 1),   # voy bien, quiero dar un salto         -> sabe hacerlo, solo afina
        ("C", 2),   # hago las cosas bien y no veo resultados-> que alguien mire sus numeros
        ("F", 2),   # lo consigo y vuelvo atras             -> le falta sostenerlo
        ("E", 2),   # nunca he estado en forma              -> guia desde el principio
        ("B", 3),   # se lo que tendria que hacer y no lo hago -> que alguien este encima
    ])
    def test_cada_frase_coloca_su_producto(self, frase, nivel):
        assert recomendar(resp(frase))["nivel"] == nivel

    def test_las_seis_frases_estan_y_no_se_repiten(self):
        ids = [f["id"] for f in FRASES]
        assert len(ids) == 6 and len(set(ids)) == 6

    def test_hay_frases_de_los_tres_niveles(self):
        assert {f["nivel"] for f in FRASES} == {1, 2, 3}

    def test_el_orden_no_va_de_gravedad(self):
        """Suyo: de mejor a peor, la gente se para en la primera que le suena un poco."""
        niveles = [f["nivel"] for f in FRASES]
        assert niveles != sorted(niveles)
        assert niveles != sorted(niveles, reverse=True)


class TestUnaSubidaNoDos:
    """"Una, no dos": si se acumulan, el que parte de cero acaba en Nivel 3 sin haber
    entrenado nunca, y esa venta se cae en la llamada."""

    def test_la_fecha_sube_uno(self):
        assert recomendar(resp("A"))["nivel"] == 1
        assert recomendar(resp("A", fecha="A"))["nivel"] == 2

    @pytest.mark.parametrize("r4", ["C", "D"])   # mas de 5 años / toda la vida
    def test_el_tiempo_sube_uno(self, r4):
        assert recomendar(resp("A", tiempo=r4))["nivel"] == 2

    @pytest.mark.parametrize("r4", ["A", "B"])   # menos de un año / de 1 a 5
    def test_poco_tiempo_no_sube(self, r4):
        assert recomendar(resp("A", tiempo=r4))["nivel"] == 1

    def test_sin_fecha_fija_no_sube(self):
        assert recomendar(resp("A", fecha="B"))["nivel"] == 1

    def test_fecha_y_tiempo_juntos_suben_UNA_sola(self):
        r = recomendar(resp("A", tiempo="D", fecha="A"))
        assert r["nivel"] == 2, "acumuló las dos subidas"
        assert r["subida"] == "fecha"

    def test_el_de_nivel_1_con_las_dos_no_llega_al_3(self):
        """El caso que teme el documento: con las dos subidas acumuladas, alguien que
        solo necesitaba la herramienta acabaría en la llamada de 1.500 €."""
        assert recomendar(resp("A", tiempo="D", fecha="A"))["nivel"] == 2

    def test_el_que_parte_de_cero_con_fecha_SI_llega_al_3(self):
        """OJO, esto es consecuencia de las reglas tal como están escritas, no un fallo:
        "nunca he estado en forma" ya sale Nivel 2, y una sola subida lo pone en 3.

        O sea que el que no ha entrenado nunca y tiene una fecha acaba en la llamada de
        1.500 €, que es justo el perfil del que el documento dice que "esa venta se cae
        en la llamada". La regla de "una, no dos" no lo evita: solo evita que llegue ahí
        alguien que partía de Nivel 1.

        Se deja así porque es lo que dice el documento. Si Jesús quiere que las frases de
        Nivel 2 no pasen de 2 por subida, es un tope de una línea en recomendar()."""
        assert recomendar(resp("E", tiempo="D", fecha="A"))["nivel"] == 3
        assert recomendar(resp("E", fecha="A"))["nivel"] == 3

    def test_ninguna_combinacion_sube_dos(self):
        for frase in "ABCDEF":
            base = recomendar(resp(frase))["nivel"]
            for r4 in "ABCD":
                for r6 in "ABC":
                    n = recomendar(resp(frase, tiempo=r4, fecha=r6))["nivel"]
                    assert n - base <= 1, f"{frase} con 4={r4} y 6={r6} subió {n - base}"


class TestTopeYBordes:
    def test_el_nivel_3_no_sube_mas(self):
        assert recomendar(resp("B", tiempo="D", fecha="A"))["nivel"] == 3

    def test_sin_la_frase_cae_en_el_intermedio(self):
        r = recomendar({1: "A", 2: "B", 3: "A", 4: "A", 6: "C"})
        assert r["nivel"] == 2 and r["subida"] is None

    def test_frase_desconocida_cae_en_el_intermedio(self):
        assert recomendar(resp("Z"))["nivel"] == 2

    def test_sin_respuestas_no_revienta(self):
        assert recomendar({})["nivel"] in (1, 2, 3)

    def test_tolera_minusculas_y_claves_de_texto(self):
        assert recomendar({"5": "b", "4": "a", "6": "c"})["nivel"] == 3

    def test_todas_las_combinaciones_dan_un_nivel_valido(self):
        for frase in "ABCDEF":
            for r4 in "ABCD":
                for r6 in "ABC":
                    n = recomendar(resp(frase, tiempo=r4, fecha=r6))["nivel"]
                    assert n in (1, 2, 3)

    def test_siempre_explica_por_que(self):
        for frase in "ABCDEF":
            assert len(recomendar(resp(frase))["por_que"]) > 20


class TestElResultadoQueSeLeEnsena:
    def _resultado(self, frase, **kw):
        return resultado_completo(resp(frase, **kw), PLAN_CATALOG)

    def test_ensena_los_tres_niveles_no_solo_el_recomendado(self):
        r = self._resultado("C")
        assert len(r["niveles"]) == 3
        assert sum(1 for n in r["niveles"] if n["recomendado"]) == 1

    def test_el_recomendado_va_marcado(self):
        r = self._resultado("A")
        assert r["recomendado"] == "nivel1"
        assert next(n for n in r["niveles"] if n["recomendado"])["plan"] == "nivel1"

    def test_trae_los_precios_del_catalogo(self):
        precios = {n["plan"]: n["precio"] for n in self._resultado("C")["niveles"]}
        assert precios == {"nivel1": 247.0, "nivel2": 847.0, "nivel3": 1500.0}

    def test_el_nivel_3_se_propone_con_los_tres_precios_delante(self):
        """Va a llamada: se propone y lo elige el, viendo los otros dos."""
        r = self._resultado("B")
        assert r["recomendado"] == "nivel3"
        assert all(n["precio"] for n in r["niveles"]), "los tres precios tienen que verse"
        tres = next(n for n in r["niveles"] if n["plan"] == "nivel3")
        assert tres["por_llamada"] is True

    def test_los_otros_dos_no_van_por_llamada(self):
        for n in self._resultado("C")["niveles"]:
            if n["plan"] != "nivel3":
                assert n["por_llamada"] is False


class TestLasPreguntas:
    def test_son_seis(self):
        assert len(PREGUNTAS) == 6

    def test_la_del_tiempo_ya_decide(self):
        """Antes se guardaba y no movia el nivel: se leia y no entraba en ninguna regla."""
        assert recomendar(resp("C", tiempo="A"))["nivel"] == 2
        assert recomendar(resp("C", tiempo="D"))["nivel"] == 3

    def test_la_de_las_frases_ofrece_las_seis(self):
        p5 = next(p for p in PREGUNTAS if p["id"] == 5)
        assert len(p5["opciones"]) == 6

    def test_ninguna_pregunta_se_queda_sin_opciones(self):
        for p in PREGUNTAS:
            assert p["opciones"]
            assert all(o["id"] and o["texto"] for o in p["opciones"])

    def test_los_textos_son_los_del_documento(self):
        assert PREGUNTAS[0]["texto"] == "¿Entrenas ahora mismo?"
        assert PREGUNTAS[3]["texto"] == "¿Cuánto tiempo llevas intentándolo?"
        assert PREGUNTAS[4]["texto"] == "¿Con cuál de estas te identificas más?"
        assert PREGUNTAS[5]["texto"] == "¿Tienes una fecha?"
