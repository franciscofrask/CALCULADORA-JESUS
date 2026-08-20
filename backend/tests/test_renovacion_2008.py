# -*- coding: utf-8 -*-
"""Las decisiones de Francisco del 20-08 sobre la renovación.

1. Ningún plan renueva automáticamente: todo el catálogo con automatica=False y los
   planes que se venden en pago único (ninguna venta nueva crea suscripción).
2. Todos los legacy renovables por los suyos: al que tiene un Gold antiguo, al vencer
   le sale «Seguir igual» con su precio congelado.
3. El aviso de «tu ciclo acaba en una semana» va POR FECHA cuando se sabe cuándo vence
   (también al mensual, que no tiene semanas de ciclo) y lleva a /renovacion.
"""
from datetime import date, datetime

from core.avisos_cliente import avisos_de_calendario_doc
from core.tiempo import MADRID
from models.user import PLAN_CATALOG, PLAN_TYPES, opciones_de_renovacion

_es = lambda *a: datetime(*a, tzinfo=MADRID)


class TestNadaRenuevaSolo:
    def test_ningun_plan_del_catalogo_renueva_automaticamente(self):
        con_auto = [c for c, p in PLAN_CATALOG.items()
                    if (p.get("renovacion") or {}).get("automatica")]
        assert con_auto == []

    def test_lo_que_se_vende_es_pago_unico(self):
        # Ninguna venta nueva puede crear una suscripción que cobre sola.
        for plan in ("nivel1", "nivel2", "nivel3", "elm", "mantenimiento"):
            assert PLAN_TYPES[plan]["one_time"] is True, plan


class TestLegacyRenovable:
    def test_todos_los_legacy_son_renovables_por_los_suyos(self):
        for c, p in PLAN_CATALOG.items():
            if p.get("estado") == "legacy":
                assert p.get("renovable_por_los_suyos") is True, c

    def test_al_gold_viejo_le_sale_seguir_igual_con_su_precio(self):
        op = opciones_de_renovacion("gold")
        assert op["puede_seguir_igual"] is True
        assert op["renovacion_legacy"] is True, "su cobro va por checkout, no por Stripe solo"
        assert op["mantiene_precio"] is True

    def test_el_legacy_sigue_sin_venderse_a_nadie_nuevo(self):
        # Renovable por los suyos NO es volver a la tienda.
        op = opciones_de_renovacion("gold")
        assert "gold" not in op["opciones"]


class TestAvisoDeFinDeCicloPorFecha:
    def test_a_siete_dias_sale_y_lleva_a_renovar(self):
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 20, 10), cliente_id="c1",
                                          fin_de_ciclo=date(2026, 8, 27))
        fin = [a for a in avisos if a["familia"] == "fin_ciclo"]
        assert len(fin) == 1
        assert fin[0]["link"] == "/renovacion"
        assert fin[0]["clave"] == "fin_ciclo:c1:2026-08-27", "una vez por vencimiento"

    def test_a_ocho_dias_todavia_no(self):
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 20, 10), cliente_id="c1",
                                          fin_de_ciclo=date(2026, 8, 28))
        assert not any(a["familia"] == "fin_ciclo" for a in avisos)

    def test_ya_vencido_no_es_este_aviso(self):
        # El vencido tiene el suyo («Tu ciclo ha terminado»); este es el de antes de vencer.
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 20, 10), cliente_id="c1",
                                          fin_de_ciclo=date(2026, 8, 19))
        assert not any(a["familia"] == "fin_ciclo" for a in avisos)

    def test_sin_fecha_manda_la_penultima_semana_como_antes(self):
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 20, 10), cliente_id="c1",
                                          semana=11, semanas_ciclo=12)
        assert any(a["familia"] == "fin_ciclo" for a in avisos)
