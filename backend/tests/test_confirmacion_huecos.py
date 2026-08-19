"""
La confirmacion de huecos (especificacion 31-07-2026, partes 6 y 7).

Lo que se fija aqui es la idea de fondo: el cumplimiento sale del registro, no de que el
cliente se puntue. Un deslizador mide una opinion; los dias sin registrar son un hecho, y
lo unico que no sabemos es si no lo hizo o si lo hizo sin apuntarlo.
"""
import pytest

from core.confirmacion_huecos import (
    NO_LO_HICE, SI_PERO_NO_APUNTE,
    huecos_del_periodo, cumplimiento, limpiar_respuestas,
)


class TestLaPregunta:
    def test_es_la_del_documento(self):
        e = huecos_del_periodo(dias_periodo=14, dias_con_dieta=10, dias_con_entreno=0)
        assert e["huecos"][0]["pregunta"] == (
            "No registraste la dieta 4 días de los últimos 14. "
            "¿Es porque no la hiciste, o porque sí la hiciste y no la apuntaste?"
        )

    def test_un_solo_dia_va_en_singular(self):
        e = huecos_del_periodo(14, 13, 0)
        assert "1 día de los últimos 14" in e["huecos"][0]["pregunta"]

    def test_si_lo_registro_todo_no_se_pregunta_nada(self):
        e = huecos_del_periodo(14, 14, 0)
        assert e["huecos"] == [] and e["hay_que_preguntar"] is False


class TestElEntrenamiento:
    """APAGADO POR EL PUNTO 41 (doc del 19-08).

    «Quita ese dato del reporte. Decirle a alguien que no ha entrenado cuando sí ha
    entrenado es peor que no decirle nada. Cuando exista dónde marcarlo, se vuelve a
    encender.»

    Los previstos son una multiplicación y los hechos salen de los días que cerró, así
    que el hueco acusaba al que entrena y no cierra el día. Lo que se fija aquí es que NO
    sale por ninguna vía, ni siquiera pasándole los previstos.
    """

    def test_no_se_pregunta_si_no_sabemos_cuantos_tocaban(self):
        """Contar los días de descanso como entrenos fallados sería acusarle en falso."""
        e = huecos_del_periodo(14, 14, 2, entrenos_previstos=None)
        assert not any(h["tipo"] == "entrenamiento" for h in e["huecos"])

    def test_tampoco_se_pregunta_aunque_sepamos_cuantos_tocaban(self):
        e = huecos_del_periodo(14, 14, 4, entrenos_previstos=8)
        assert not any(h["tipo"] == "entrenamiento" for h in e["huecos"])

    def test_el_de_la_dieta_sigue_saliendo(self):
        """Apagar el del entreno no puede llevarse por delante el que sí es un hecho."""
        e = huecos_del_periodo(14, 10, 4, entrenos_previstos=8)
        assert [h["tipo"] for h in e["huecos"]] == ["dieta"]

    def test_los_previstos_se_siguen_devolviendo(self):
        """El dato no se pierde: deja de convertirse en una pregunta, nada más."""
        e = huecos_del_periodo(14, 14, 4, entrenos_previstos=8)
        assert e["entrenos_previstos"] == 8 and e["dias_con_entreno"] == 4

    def test_si_hizo_todos_los_previstos_no_hay_hueco(self):
        e = huecos_del_periodo(14, 14, 8, entrenos_previstos=8)
        assert e["huecos"] == []


class TestElCumplimiento:
    def test_lo_que_hizo_sin_apuntar_cuenta_como_hecho(self):
        e = huecos_del_periodo(14, 10, 0)
        c = cumplimiento(e, {"dieta": SI_PERO_NO_APUNTE})
        assert c["dieta_dias"] == 14 and c["dieta_pct"] == 100

    def test_lo_que_no_hizo_no_cuenta(self):
        e = huecos_del_periodo(14, 10, 0)
        c = cumplimiento(e, {"dieta": NO_LO_HICE})
        assert c["dieta_dias"] == 10 and c["dieta_pct"] == 71

    def test_sin_contestar_cuenta_como_no_hecho(self):
        """Es lo único que consta. No se le regala cumplimiento por callar."""
        e = huecos_del_periodo(14, 10, 0)
        assert cumplimiento(e, {})["dieta_pct"] == 71

    def test_no_sale_de_una_opinion_y_se_dice(self):
        c = cumplimiento(huecos_del_periodo(14, 10, 0), {})
        assert c["origen"] == "registro"

    def test_el_entreno_no_da_porcentaje_mientras_este_apagado(self):
        """Punto 41: sin hueco no hay «lo hice y no lo apunté», así que el porcentaje
        sería siempre el de los días que casualmente cerró. No sale ninguno."""
        assert "entreno_pct" not in cumplimiento(huecos_del_periodo(14, 14, 3), {})
        c = cumplimiento(huecos_del_periodo(14, 14, 3, entrenos_previstos=8),
                         {"entrenamiento": SI_PERO_NO_APUNTE})
        assert "entreno_pct" not in c

    def test_periodo_vacio_no_revienta(self):
        c = cumplimiento(huecos_del_periodo(0, 0, 0), {})
        assert c["dieta_pct"] == 0


class TestQueNoEntreBasura:
    @pytest.mark.parametrize("v", [None, [], "si", {"dieta": "quiza"}, {"otra": NO_LO_HICE}])
    def test_solo_pasan_respuestas_validas(self, v):
        assert limpiar_respuestas(v) == {}

    def test_las_buenas_pasan(self):
        assert limpiar_respuestas({"dieta": NO_LO_HICE, "entrenamiento": SI_PERO_NO_APUNTE}) == {
            "dieta": NO_LO_HICE, "entrenamiento": SI_PERO_NO_APUNTE}

    def test_mas_dias_con_dieta_que_dias_del_periodo_se_recorta(self):
        e = huecos_del_periodo(14, 20, 0)
        assert e["dias_con_dieta"] == 14 and e["huecos"] == []
