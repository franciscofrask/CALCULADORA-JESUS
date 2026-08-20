# -*- coding: utf-8 -*-
"""El bloque 12 del doc 19-08: los cuatro paneles. Las reglas de dinero y de semana.

Los endpoints son de agregación y se prueban en vivo; aquí van las reglas puras que no
pueden torcerse sin que nadie lo note: la cascada del importe de renovación, el estado
confirmado/por confirmar/a mano, la normalización a euros al mes y la semana de negocio.
"""
from datetime import date

from routes.paneles import (_estado_renovacion, _eur_mes, _importe_renovacion,
                            _semana_es)


class TestImporteDeRenovacion:
    def test_manda_el_puesto_a_mano(self):
        p = {"renovacion_importe_prevision": 450}
        assert _importe_renovacion(p, {"precio": 847}, {"importe": 900}) == (450.0, True)

    def test_luego_el_ultimo_cobro_real(self):
        assert _importe_renovacion({}, {"precio": 847}, {"importe": 450}) == (450.0, False)

    def test_un_cobro_a_cero_no_vale(self):
        assert _importe_renovacion({}, {"precio": 847}, {"importe": 0}) == (847.0, False)

    def test_sin_nada_el_precio_de_tarifa(self):
        assert _importe_renovacion({}, {"precio": 247}, None) == (247.0, False)

    def test_true_no_es_un_importe(self):
        # bool es subclase de int: sin el candado, un True guardado por error valdría 1 €.
        p = {"renovacion_importe_prevision": True}
        assert _importe_renovacion(p, {"precio": 97}, None) == (97.0, False)


class TestEstadoDeRenovacion:
    def test_a_mano_manda(self):
        assert _estado_renovacion({}, {"renovacion": {"automatica": True}}, True) == "a_mano"

    def test_stripe_activo_confirma(self):
        p = {"stripe_subscription_id": "sub_1", "subscription_status": "active"}
        assert _estado_renovacion(p, {}, False) == "confirmado"

    def test_stripe_impagado_no_confirma(self):
        p = {"stripe_subscription_id": "sub_1", "subscription_status": "incomplete"}
        assert _estado_renovacion(p, {"renovacion": {}}, False) == "por_confirmar"

    def test_plan_automatico_confirma(self):
        assert _estado_renovacion({}, {"renovacion": {"automatica": True}}, False) == "confirmado"


class TestEurosAlMes:
    def test_trimestral_por_semanas_de_cobro(self):
        # 847 cada 12 semanas -> 847 * 4.345 / 12
        assert round(_eur_mes(847, {"billing_cycle_weeks": 12}), 2) == round(847 * 4.345 / 12, 2)

    def test_mensual_se_queda_igual(self):
        assert _eur_mes(97, {"billing_cycle_weeks": 4}) > 97  # 4 semanas no es un mes justo
        assert _eur_mes(97, {}) == 97

    def test_anual_dividido_entre_doce(self):
        assert _eur_mes(800, {"precios": [{"periodo": "año"}]}) == 800 / 12.0


class TestSemanaDeNegocio:
    def test_de_lunes_a_domingo(self):
        desde, hasta = _semana_es(date(2026, 8, 20))  # jueves
        assert desde == date(2026, 8, 17) and hasta == date(2026, 8, 23)
        assert desde.weekday() == 0 and hasta.weekday() == 6

    def test_el_lunes_ya_es_su_semana(self):
        desde, _ = _semana_es(date(2026, 8, 17))
        assert desde == date(2026, 8, 17)
