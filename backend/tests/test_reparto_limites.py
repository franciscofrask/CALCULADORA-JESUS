# -*- coding: utf-8 -*-
"""
Punto 5.4: los casos limite del reparto de macros.

El informe los leyo en el snapshot de marzo. Comprobado contra el codigo de hoy: 5.1, 5.2 y
5.3 ya estaban arreglados. Lo que quedaba eran los valores de entrada fuera de rango, y el
problema no era que reventaran -- `momento_entreno` ya se cae a 1 a proposito para no devolver
un 500 -- sino que se arreglaban EN SILENCIO. Un `num_comidas=5` recibia el reparto de cuatro
y la quinta comida se quedaba a cero, que en pantalla se ve como "todo sobra".

Aqui se fija que ningun valor raro tumbe el reparto Y que lo que salga siga cuadrando.
"""
import pytest

from macro_distribution import distribuir_macros

BASE = dict(p_entreno=150, h_entreno=100, g_entreno=50, p_peri=30, h_peri=30,
            p_descanso=150, h_descanso=100, g_descanso=50, tipo_dia="entrenamiento",
            num_comidas=4, momento_entreno=1, opcion_peri="intra_post")


def _reparto(**kw):
    r = distribuir_macros(**{**BASE, **kw})
    return r["comidas"], r["resumen"]


class TestNadaRevienta:
    @pytest.mark.parametrize("kw", [
        {"momento_entreno": 7}, {"momento_entreno": -1}, {"momento_entreno": None},
        {"momento_entreno": "dos"}, {"num_comidas": 5}, {"num_comidas": 0},
        {"num_comidas": 99}, {"num_comidas": None}, {"opcion_peri": "lo_que_sea"},
        {"tipo_dia": "lo_que_sea"},
    ])
    def test_no_lanza(self, kw):
        """Un 500 aqui deja la pantalla de Nutricion con todos los objetivos a cero."""
        comidas, _ = _reparto(**kw)
        assert comidas, f"{kw} devolvio un reparto vacio"


class TestLoQueSaleSigueCuadrando:
    def test_el_reparto_normal_suma_lo_que_hay(self):
        comidas, resumen = _reparto()
        assert abs(resumen["H_total"] - (100 + 30)) < 1.5

    @pytest.mark.parametrize("kw", [{"momento_entreno": 7}, {"num_comidas": 99}])
    def test_con_valores_raros_tampoco_se_inventa_comida(self, kw):
        comidas, _ = _reparto(**kw)
        h = sum(c["H"] for c in comidas.values())
        assert abs(h - 100) < 1.5, f"con {kw} reparte {h} y hay 100"


class TestNadaNegativo:
    def test_los_hidratos_negativos_no_se_reparten(self):
        """Con -50 devolvia -50 en una comida tan tranquilo, y de ahi salen objetivos
        negativos en la pantalla. Un macro negativo no es un macro pequeño: es un dato roto."""
        comidas, _ = _reparto(h_entreno=-50)
        for k, c in comidas.items():
            assert c["H"] >= 0, f"{k} tiene {c['H']} de hidratos"
            assert c["P"] >= 0 and c["G"] >= 0

    def test_todo_a_cero_no_rompe(self):
        comidas, resumen = _reparto(p_entreno=0, h_entreno=0, g_entreno=0, p_peri=0, h_peri=0)
        assert comidas
        assert resumen["H_total"] == 0


class TestLoQueYaEstabaBien:
    """5.1, 5.2 y 5.3 del informe: comprobado que el snapshot de marzo era viejo."""

    @pytest.mark.parametrize("h_total,momento,esperado", [
        (25, 1, [0, 25, 0, 0]),     # menos de 30: TODO al post
        (25, 2, [0, 0, 25, 0]),
        (40, 1, [10, 30, 0, 0]),    # 30-50: 10 a la de antes, el resto al post
        (40, 3, [0, 0, 10, 30]),
    ])
    def test_el_tramo_de_menos_de_30(self, h_total, momento, esperado):
        comidas, _ = _reparto(h_entreno=h_total, p_peri=0, h_peri=0,
                              momento_entreno=momento, opcion_peri="sin_peri")
        assert [comidas[k]["H"] for k in ("C1", "C2", "C3", "C4")] == esperado

    @pytest.mark.parametrize("h_total", [5, 8, 9])
    def test_con_menos_de_10_no_reparte_mas_de_lo_que_hay(self, h_total):
        comidas, _ = _reparto(h_entreno=h_total, p_peri=0, h_peri=0, opcion_peri="sin_peri")
        assert abs(sum(c["H"] for c in comidas.values()) - h_total) < 0.5

    @pytest.mark.parametrize("modo,esperado", [
        ("solo_post", [20, 20, 10, 10]),
        ("sin_peri", [35, 35, 10, 10]),
    ])
    def test_el_peri_entra_ANTES_de_elegir_el_escenario(self, modo, esperado):
        """El caso que midio Jesus en la app: 60 g de hidratos con peri 30/30.
        Sumar el peri DESPUES y a partes iguales daba 27,5 · 27,5 · 17,5 · 17,5."""
        comidas, _ = _reparto(h_entreno=60, p_peri=30, h_peri=30, opcion_peri=modo)
        assert [comidas[k]["H"] for k in ("C1", "C2", "C3", "C4")] == esperado
