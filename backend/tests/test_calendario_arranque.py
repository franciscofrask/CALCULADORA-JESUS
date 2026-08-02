"""
El calendario de arranque (especificacion 31-07-2026, parte 2).

Todos arrancan en lunes, pague el dia que pague, y si al pagar quedan menos de 48 horas
para ese lunes se va al siguiente: en los niveles 2 y 3 el equipo necesita ese margen
para validar los macros, y sin el se arrancaria sin ellos.

Lo que se fija aqui es sobre todo que el ANCLA de facturacion cae en el lunes y no el
dia del pago. De eso depende que el cobro del ciclo siguiente llegue antes de ponerse a
preparar el trabajo: si no, se prepara para alguien que igual no ha renovado.
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.calendario_arranque import (
    HORAS_MINIMAS_ANTES_DEL_LUNES,
    lunes_de_arranque,
    mensaje_de_arranque,
    plan_de_arranque,
    proximo_lunes,
)


def utc(a, m, d, h=12, mi=0):
    return datetime(a, m, d, h, mi, tzinfo=timezone.utc)


# Agosto de 2026: el 3 es lunes, el 10 el siguiente, el 17 el otro.
LUNES_3 = utc(2026, 8, 3, 0, 0)
LUNES_10 = utc(2026, 8, 10, 0, 0)
LUNES_17 = utc(2026, 8, 17, 0, 0)


class TestSiempreEnLunes:
    @pytest.mark.parametrize("dia,hora", [(28, 12), (29, 9), (30, 18), (31, 10)])
    def test_pague_el_dia_que_pague_arranca_en_lunes(self, dia, hora):
        arranque = lunes_de_arranque(utc(2026, 7, dia, hora))
        assert arranque.weekday() == 0, "tiene que ser lunes"

    def test_un_martes_con_margen_arranca_el_lunes_de_esa_semana(self):
        # Martes 28 de julio: quedan casi 6 dias para el lunes 3.
        assert lunes_de_arranque(utc(2026, 7, 28, 12)) == LUNES_3

    def test_el_que_paga_un_lunes_no_arranca_ese_mismo_lunes(self):
        """Ya ha empezado la semana: se va al siguiente."""
        assert lunes_de_arranque(utc(2026, 8, 3, 10)) == LUNES_10


class TestLaReglaDeLas48Horas:
    def test_con_mas_de_48_horas_entra_en_el_lunes_de_esa_semana(self):
        # Viernes 31 a las 10:00 -> quedan ~62 h para el lunes 3.
        assert lunes_de_arranque(utc(2026, 7, 31, 10)) == LUNES_3

    def test_con_menos_de_48_horas_se_va_al_siguiente(self):
        # Sabado 1 a las 12:00 -> quedan 36 h. No da tiempo a validar macros.
        assert lunes_de_arranque(utc(2026, 8, 1, 12)) == LUNES_10

    def test_el_domingo_siempre_se_va_al_siguiente(self):
        assert lunes_de_arranque(utc(2026, 8, 2, 9)) == LUNES_10

    def test_justo_en_el_limite_de_las_48_horas(self):
        justo = LUNES_3 - timedelta(hours=HORAS_MINIMAS_ANTES_DEL_LUNES)
        assert lunes_de_arranque(justo) == LUNES_3, "48 h exactas todavia valen"
        assert lunes_de_arranque(justo + timedelta(minutes=1)) == LUNES_10


class TestElAnclaDeFacturacion:
    """Lo que de verdad arregla esto: el siguiente cobro cae a los 84 dias del LUNES."""

    def test_el_ancla_es_el_lunes_no_el_dia_del_pago(self):
        p = plan_de_arranque(utc(2026, 7, 29, 15))     # miercoles
        assert p["arranque"] == LUNES_3
        assert p["anchor_timestamp"] == int(LUNES_3.timestamp())

    def test_el_ciclo_acaba_12_semanas_despues_del_lunes(self):
        p = plan_de_arranque(utc(2026, 7, 29, 15), semanas_ciclo=12)
        assert p["fin_de_ciclo"] == LUNES_3 + timedelta(weeks=12)
        assert (p["fin_de_ciclo"] - p["arranque"]).days == 84

    def test_el_cobro_del_ciclo_siguiente_llega_antes_de_preparar_nada(self):
        """El ciclo acaba el mismo dia que Stripe cobra: por eso se ancla."""
        p = plan_de_arranque(utc(2026, 7, 29, 15))
        cobro = datetime.fromtimestamp(p["anchor_timestamp"], timezone.utc) + timedelta(weeks=12)
        assert cobro == p["fin_de_ciclo"]

    def test_dos_personas_de_la_misma_semana_comparten_ancla(self):
        """Es lo que permite dimensionar el trabajo de la semana."""
        martes = plan_de_arranque(utc(2026, 7, 28, 9))
        jueves = plan_de_arranque(utc(2026, 7, 30, 20))
        assert martes["anchor_timestamp"] == jueves["anchor_timestamp"]


class TestLaSemanaCero:
    def test_cuenta_los_dias_que_se_le_regalan(self):
        p = plan_de_arranque(utc(2026, 7, 29, 15))    # miercoles -> lunes 3
        assert p["dias_semana_cero"] == 5

    def test_al_que_se_le_va_al_lunes_siguiente_se_le_puede_avisar(self):
        p = plan_de_arranque(utc(2026, 8, 2, 9))      # domingo -> lunes 10
        assert p["salta_al_siguiente"] is True
        assert p["dias_semana_cero"] == 8

    def test_al_que_entra_con_margen_no_se_le_avisa_de_nada(self):
        assert plan_de_arranque(utc(2026, 7, 28, 12))["salta_al_siguiente"] is False


class TestLoQueSeLeDice:
    def test_le_dice_el_lunes_exacto(self):
        m = mensaje_de_arranque(plan_de_arranque(utc(2026, 7, 29, 15)))
        assert "lunes 3 de agosto" in m

    def test_y_para_que_sirven_esos_dias(self):
        """La Semana 0 es puesta a punto, no espera."""
        m = mensaje_de_arranque(plan_de_arranque(utc(2026, 7, 29, 15)))
        for pista in ("macros", "fotos", "dietas"):
            assert pista in m


class TestBordes:
    def test_cambio_de_mes(self):
        p = plan_de_arranque(utc(2026, 7, 30, 10))
        assert p["arranque"].month == 8 and p["arranque"].day == 3

    def test_cambio_de_año(self):
        # 31 de diciembre de 2026 es jueves; el lunes siguiente es el 4 de enero.
        a = lunes_de_arranque(utc(2026, 12, 31, 10))
        assert (a.year, a.month, a.day) == (2027, 1, 4)

    def test_una_fecha_sin_zona_horaria_se_trata_como_utc(self):
        sin_zona = datetime(2026, 7, 29, 15)
        assert lunes_de_arranque(sin_zona) == LUNES_3

    def test_proximo_lunes_de_un_lunes_es_el_mismo_dia(self):
        assert proximo_lunes(utc(2026, 8, 3, 15)) == LUNES_3
