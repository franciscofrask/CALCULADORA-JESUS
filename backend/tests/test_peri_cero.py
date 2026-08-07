"""Tests del perientreno a 0 (descuadre del dia de entreno, 31-07-2026).

Caso real que lo destapo: un cliente con 190 P / 240 H / 50 G de entreno, peri a 0 y opcion
`sin_peri`, 4 comidas, momento 1. El dia salia con 226 P y 256 H en vez de 190 y 240.

La causa no era el reparto (las tablas suman 100%) sino lo que entraba en el: las rutas leian
el peri con `peri.get("protein") or peri.get("proteinas") or 35`, y como en Python el 0 cuenta
como vacio, un peri a 0 se sustituia por 35 P / 15 H. En modo `sin_peri` ese peri fantasma se
repartia entre las comidas (+8,8 P y +3,8 H en cada una) sin aparecer en ninguna parte.

Unitarios y en local (sin HTTP): importan macro_distribution directamente.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from macro_distribution import distribuir_macros, leer_macro, leer_peri


# Los macros del caso real y el peri tal y como esta guardado en el perfil.
ENTRENO = {"protein": 190.0, "carbs": 240.0, "fat": 50.0,
           "proteinas": 190.0, "hidratos": 240.0, "grasas": 50.0}
PERI_CERO = {"protein": 0.0, "carbs": 0.0, "proteinas": 0.0, "hidratos": 0.0}


def reparto(peri, opcion_peri="sin_peri", momento=1):
    """Distribuye el caso real leyendo el peri como lo hacen las rutas."""
    p_peri, h_peri = leer_peri(peri, opcion_peri)
    return distribuir_macros(
        p_entreno=leer_macro(ENTRENO, "protein", "proteinas"),
        h_entreno=leer_macro(ENTRENO, "carbs", "hidratos"),
        g_entreno=leer_macro(ENTRENO, "fat", "grasas"),
        p_peri=p_peri,
        h_peri=h_peri,
        p_descanso=leer_macro(ENTRENO, "protein", "proteinas"),
        h_descanso=leer_macro(ENTRENO, "carbs", "hidratos"),
        g_descanso=leer_macro(ENTRENO, "fat", "grasas"),
        tipo_dia="entrenamiento", num_comidas=4,
        momento_entreno=momento, opcion_peri=opcion_peri,
    )


def totales(res):
    """Lo que suman las comidas + el peri, que es lo que se come en el dia."""
    p = sum(c["P"] for c in res["comidas"].values())
    h = sum(c["H"] for c in res["comidas"].values())
    g = sum(c["G"] for c in res["comidas"].values())
    for comida in res["periworkout"].values():
        p += comida["P"]
        h += comida["H"]
    return (round(p, 1), round(h, 1), round(g, 1))


class TestLeerMacro:
    """El 0 es un valor, no un hueco."""

    def test_cero_se_respeta(self):
        assert leer_macro(PERI_CERO, "protein", "proteinas", default=35) == 0.0
        assert leer_macro(PERI_CERO, "carbs", "hidratos", default=15) == 0.0

    def test_sin_peri_asignado_cae_al_default(self):
        assert leer_macro({}, "protein", "proteinas", default=35) == 35.0
        assert leer_macro(None, "carbs", "hidratos", default=15) == 15.0

    def test_cae_a_la_clave_alternativa(self):
        # Formato del chatbot (proteinas/hidratos) cuando no esta el ingles.
        assert leer_macro({"proteinas": 40.0}, "protein", "proteinas", default=35) == 40.0

    def test_valor_normal(self):
        assert leer_macro({"protein": 45.0}, "protein", "proteinas", default=35) == 45.0


class TestPeriCeroNoInflaElDia:
    """Con el peri a 0 el dia tiene que dar EXACTAMENTE los macros introducidos."""

    def test_sin_peri_cuadra_con_lo_introducido(self):
        assert totales(reparto(PERI_CERO)) == (190.0, 240.0, 50.0)

    def test_sin_peri_reparto_del_caso_real(self):
        # 25/25/20/30 de P y 30/30/20/20 de H (momento 1), sin gramos de mas.
        comidas = reparto(PERI_CERO)["comidas"]
        assert [comidas[c]["P"] for c in ("C1", "C2", "C3", "C4")] == [47.5, 47.5, 38.0, 57.0]
        assert [comidas[c]["H"] for c in ("C1", "C2", "C3", "C4")] == [72.0, 72.0, 48.0, 48.0]

    def test_sin_peri_no_crea_intra_ni_post(self):
        assert reparto(PERI_CERO)["periworkout"] == {}

    @pytest.mark.parametrize("opcion", ["intra_post", "solo_post", "solo_intra", "sin_peri"])
    def test_peri_cero_cuadra_en_los_cuatro_modos(self, opcion):
        # El peri a 0 no puede inventar gramos en ningun modo. Con intra_post y solo_post
        # antes aparecian ademas un Intra y un Post fantasma de la nada.
        assert totales(reparto(PERI_CERO, opcion_peri=opcion)) == (190.0, 240.0, 50.0)

    @pytest.mark.parametrize("momento", [0, 1, 2, 3])
    def test_peri_cero_cuadra_en_los_cuatro_momentos(self, momento):
        assert totales(reparto(PERI_CERO, momento=momento)) == (190.0, 240.0, 50.0)

    def test_regresion_no_vuelven_los_226(self):
        p, h, _ = totales(reparto(PERI_CERO))
        assert (p, h) != (225.2, 255.2), "vuelve el peri fantasma de 35 P / 15 H"


class TestPeriAsignadoSigueIgual:
    """El arreglo no toca el metodo: con peri de verdad, el peri sigue yendo aparte."""

    def test_peri_real_se_suma_al_dia(self):
        # Doc de Jesus (29-07): el peri va aparte de las comidas del dia de entreno.
        peri = {"protein": 40.0, "carbs": 30.0}
        assert totales(reparto(peri, opcion_peri="intra_post")) == (230.0, 270.0, 50.0)

    def test_peri_real_reparte_intra_y_post(self):
        res = reparto({"protein": 40.0, "carbs": 30.0}, opcion_peri="intra_post")
        assert res["periworkout"]["Intra"] == {"P": 8.0, "H": 9.0, "G": 0.0}
        assert res["periworkout"]["Post"] == {"P": 32.0, "H": 21.0, "G": 0.0}

    def test_sin_peri_configurado_mantiene_el_default(self):
        # Cliente sin peri en el perfil y en un modo que SI lleva peri: se sigue asumiendo
        # 35/15 como hasta ahora.
        assert totales(reparto({}, opcion_peri="intra_post")) == (225.0, 255.0, 50.0)


class TestArranqueNoAplicaEnSinPeri:
    """Si no hay peri configurado Y el cliente ha dicho que no toma peri, no hay presupuesto.

    El 35/15 es el arranque para "todavia no le han asignado peri", no para "no toma peri".
    Inventarlo en modo `sin_peri` metia en las comidas gramos que nadie habia asignado.
    """

    @pytest.mark.parametrize("peri", [{}, None, {"protein": None, "carbs": None}])
    def test_sin_campo_y_sin_peri_no_inventa_nada(self, peri):
        assert leer_peri(peri, "sin_peri") == (0.0, 0.0)
        assert totales(reparto(peri, opcion_peri="sin_peri")) == (190.0, 240.0, 50.0)

    @pytest.mark.parametrize("opcion", ["intra_post", "solo_post", "solo_intra"])
    def test_el_arranque_sigue_vivo_en_los_demas_modos(self, opcion):
        assert leer_peri({}, opcion) == (35.0, 15.0)

    def test_peri_configurado_manda_sobre_el_arranque(self):
        # Con peri de verdad, el modo no cambia el presupuesto: solo cambia el vehiculo.
        assert leer_peri({"protein": 40.0, "carbs": 30.0}, "sin_peri") == (40.0, 30.0)
        assert leer_peri({"protein": 40.0, "carbs": 30.0}, "intra_post") == (40.0, 30.0)

    def test_peri_configurado_con_sin_peri_se_reparte_en_las_comidas(self):
        # Quitar la bebida no le quita los gramos del dia: se los come en solido. Confirmado
        # por el doc de Jesus del 07-08, que ademas fija COMO se reparten (entran en el total
        # del dia y pasan por las tablas, no a partes iguales; ver test_reparto_calma_paridad).
        assert totales(reparto({"protein": 40.0, "carbs": 30.0},
                               opcion_peri="sin_peri")) == (230.0, 270.0, 50.0)


class TestDescansoNoMiraElPeri:
    """El dia de descanso siempre cuadro, y tiene que seguir cuadrando."""

    def test_descanso_ignora_el_peri(self):
        res = distribuir_macros(
            p_entreno=190, h_entreno=240, g_entreno=50,
            p_peri=35, h_peri=15,
            p_descanso=190, h_descanso=240, g_descanso=50,
            tipo_dia="descanso", num_comidas=4,
            momento_entreno=1, opcion_peri="sin_peri",
        )
        assert totales(res) == (190.0, 240.0, 50.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
