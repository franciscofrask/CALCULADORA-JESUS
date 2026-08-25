# -*- coding: utf-8 -*-
"""El bloque 12 del doc 19-08: los cuatro paneles. Las reglas de dinero y de semana.

Los endpoints son de agregación y se prueban en vivo; aquí van las reglas puras que no
pueden torcerse sin que nadie lo note: la cascada del importe de renovación, el estado
confirmado/por confirmar/a mano, la normalización a euros al mes y la semana de negocio.
"""
from datetime import date

from routes.admin import euros_al_mes, importe_de_ciclo
from routes.paneles import _estado_renovacion, _semana_es

# EL CATÁLOGO DE PRUEBA. Desde el punto 46 (24-08) la cuenta del dinero es una sola y vive
# en routes/admin.py, así que se prueba con perfiles y catálogo, no con importes sueltos:
# el fallo que costó 11.000 € fue precisamente que cada pantalla resolvía el precio por su
# cuenta antes de normalizarlo.
CAT = {
    "gold": {"ciclo": {"tipo": "trimestral", "semanas": 12}, "billing_cycle_weeks": 12,
             "precio": 847},
    "elm": {"ciclo": {"tipo": "mensual", "semanas": None}, "billing_cycle_weeks": 4,
            "precio": 97},
    "raro": {"precio": 800, "precios": [{"periodo": "año"}]},
}


class TestImporteDeCiclo:
    def test_manda_el_puesto_a_mano(self):
        p = {"plan": "gold", "renovacion_importe_prevision": 450}
        assert importe_de_ciclo(p, CAT, {"importe": 900}) == (450.0, "a_mano")

    def test_luego_el_ultimo_cobro_real(self):
        assert importe_de_ciclo({"plan": "gold"}, CAT, {"importe": 450}) == (450.0, "cobro_real")

    def test_un_cobro_a_cero_no_vale(self):
        assert importe_de_ciclo({"plan": "gold"}, CAT, {"importe": 0}) == (847.0, "ficha")

    def test_sin_nada_el_precio_de_tarifa(self):
        assert importe_de_ciclo({"plan": "elm"}, CAT, None) == (97.0, "ficha")

    def test_el_precio_congelado_de_la_ficha_manda_sobre_la_tarifa(self):
        # Jesús, 24-08: los clientes del sistema anterior conservan su precio congelado. Al
        # que nunca pagó por la app no se le pone la tarifa nueva de su plan.
        assert importe_de_ciclo({"plan": "elm", "price": 60.5}, CAT, None) == (60.5, "ficha")

    def test_la_cortesia_no_paga_aunque_pagara_el_ano_pasado(self):
        p = {"plan": "gold", "comp_plan": True}
        assert importe_de_ciclo(p, CAT, {"importe": 847}) == (0.0, "cortesia")

    def test_true_no_es_un_importe(self):
        # bool es subclase de int: sin el candado, un True guardado por error valdría 1 €.
        p = {"plan": "elm", "renovacion_importe_prevision": True}
        assert importe_de_ciclo(p, CAT, None) == (97.0, "ficha")


class TestEstadoDeRenovacion:
    def test_a_mano_manda(self):
        assert _estado_renovacion({}, {"renovacion": {"automatica": True}}, "a_mano") == "a_mano"

    def test_la_cortesia_se_dice(self):
        assert _estado_renovacion({}, {"renovacion": {"automatica": True}}, "cortesia") == "cortesia"

    def test_stripe_activo_confirma(self):
        p = {"stripe_subscription_id": "sub_1", "subscription_status": "active"}
        assert _estado_renovacion(p, {}, "cobro_real") == "confirmado"

    def test_stripe_impagado_no_confirma(self):
        p = {"stripe_subscription_id": "sub_1", "subscription_status": "incomplete"}
        assert _estado_renovacion(p, {"renovacion": {}}, "cobro_real") == "por_confirmar"

    def test_plan_automatico_confirma(self):
        assert _estado_renovacion({}, {"renovacion": {"automatica": True}}, "ficha") == "confirmado"


class TestEurosAlMes:
    def test_trimestral_por_semanas_de_cobro(self):
        # 847 cada 12 semanas -> 847 * 4.345 / 12. Stripe cobra cada 84 días, no cada 3
        # meses de calendario: dividir entre 3 se dejaba un cobro cada tres años.
        p = {"plan": "gold"}
        assert round(euros_al_mes(p, CAT, {"importe": 847}), 2) == round(847 * 4.345 / 12, 2)

    def test_el_mensual_no_lleva_recargo(self):
        # El catálogo le pone `billing_cycle_weeks: 4` al mensual, que es una aproximación
        # del mes. Multiplicar por 4,345/4 le inventaba un 8,6 % de más -- 13 pagos al año
        # donde su factura dice «at 60.50 € / month» (punto 46 del 24-08).
        assert euros_al_mes({"plan": "elm"}, CAT, {"importe": 97}) == 97
        assert euros_al_mes({"plan": "no_esta_en_el_catalogo", "price": 97}, CAT, None) == 97

    def test_un_ciclo_que_la_casa_no_conoce_se_cuenta_como_mensual(self):
        # El nombre de este test decía «anual dividido entre doce» y comprobaba justo lo
        # contrario: «anual» no está en `_MESES_DE_CICLO` y esos 800 € cuentan enteros
        # cada mes. Se deja escrito lo que HACE, que un test que miente es peor que no
        # tenerlo. Hoy no muerde -- los 24 planes del catálogo declaran
        # `billing_cycle_weeks` y ninguno es anual --, y el día que se añada uno hay que
        # meterle las semanas de su ciclo, no fiarse de la palabra.
        assert euros_al_mes({"plan": "raro"}, {**CAT, "raro": {
            "ciclo": {"tipo": "anual"}, "precio": 800}}, {"importe": 800}) == 800
        # Con las semanas puestas sí se reparte.
        anual = {"ciclo": {"tipo": "anual"}, "billing_cycle_weeks": 52, "precio": 800}
        assert round(euros_al_mes({"plan": "raro"}, {**CAT, "raro": anual},
                                  {"importe": 800}), 2) == round(800 * 4.345 / 52, 2)

    def test_las_dos_pantallas_dan_lo_mismo(self):
        # El punto 46 en una línea: el Inicio del panel y Dirección llaman a la MISMA
        # función, así que con el mismo cliente y el mismo cobro no pueden discrepar.
        from routes.admin import precio_mensual
        p = {"plan": "gold", "price": 900}
        assert precio_mensual(p, CAT, {"importe": 450}) == euros_al_mes(p, CAT, {"importe": 450})


class TestSemanaDeNegocio:
    def test_de_lunes_a_domingo(self):
        desde, hasta = _semana_es(date(2026, 8, 20))  # jueves
        assert desde == date(2026, 8, 17) and hasta == date(2026, 8, 23)
        assert desde.weekday() == 0 and hasta.weekday() == 6

    def test_el_lunes_ya_es_su_semana(self):
        desde, _ = _semana_es(date(2026, 8, 17))
        assert desde == date(2026, 8, 17)
