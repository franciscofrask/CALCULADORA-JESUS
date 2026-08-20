# -*- coding: utf-8 -*-
"""El bloque 10 del doc 19-08: los avisos de la tabla que faltaban y sus reglas.

- «Configura lo que comes» a los 3 días sin preferencias, en todos los planes.
- «¿Volvemos?» al mes en Mantenimiento, una sola vez.
- «Tu ciclo ha terminado» al vencer sin renovar (solo planes de ciclo cerrado: el flag
  llega ya decidido).
- «Te hemos mandado el correo de novedades» los viernes desde mediodía.
- Los avisos leen las habilitaciones: sin ajuste en el plan, no hay «llevas N semanas
  con los mismos macros».
"""
from datetime import datetime, timezone

from core.avisos_cliente import avisos_condicionados, avisos_de_calendario_doc
from core.tiempo import MADRID

AHORA = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)

_es = lambda *a: datetime(*a, tzinfo=MADRID)


class TestConfiguraLoQueComes:
    def test_dos_dias_no(self):
        assert avisos_condicionados(ahora=AHORA, dias_sin_preferencias=2) == []

    def test_tres_dias_si(self):
        avisos = avisos_condicionados(ahora=AHORA, dias_sin_preferencias=3)
        assert len(avisos) == 1
        assert avisos[0]["variantes"][0]["titulo"] == "Configura lo que comes"

    def test_con_preferencias_marcadas_nunca(self):
        # El caller manda None cuando ya las tiene: no hay nada que pedirle.
        assert avisos_condicionados(ahora=AHORA, dias_sin_preferencias=None) == []


class TestVolvemos:
    def test_a_los_29_dias_no(self):
        assert avisos_condicionados(ahora=AHORA, dias_en_mantenimiento=29) == []

    def test_al_mes_si_y_una_sola_vez(self):
        avisos = avisos_condicionados(ahora=AHORA, dias_en_mantenimiento=30)
        assert avisos[0]["variantes"][0]["titulo"] == "¿Volvemos?"
        # La clave no lleva la semana: no vuelve a salir a la siguiente.
        assert avisos[0]["clave"] == "volvemos:mantenimiento"


class TestLasHabilitacionesMandan:
    def test_sin_ajuste_en_el_plan_no_hay_aviso_de_semanas_sin_ajustar(self):
        # «Hoy al de Mantenimiento le llega "llevas 4 semanas con los mismos macros" y su
        # plan no incluye ajuste» (doc 19-08).
        assert avisos_condicionados(ahora=AHORA, semanas_sin_ajustar=6, con_ajuste=False) == []

    def test_con_ajuste_si(self):
        assert len(avisos_condicionados(ahora=AHORA, semanas_sin_ajustar=6, con_ajuste=True)) == 1


class TestCicloTerminado:
    def test_al_vencer_sale_y_lleva_a_la_renovacion(self):
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 19, 10), cliente_id="c1",
                                          ciclo_vencido=True, con_correo_de_novedades=False)
        assert len(avisos) == 1
        a = avisos[0]
        assert a["variantes"][0]["titulo"] == "Tu ciclo ha terminado"
        assert a["link"] == "/renovacion"
        assert a["calendario"] is True, "es de entrega: no caduca ni gasta el cupo"
        assert a["clave"] == "ciclo_terminado:c1", "una vez por vencimiento, no una al día"

    def test_sin_vencer_no(self):
        assert avisos_de_calendario_doc(ahora_es=_es(2026, 8, 19, 10), cliente_id="c1",
                                        ciclo_vencido=False, con_correo_de_novedades=False) == []


class TestCorreoDelViernes:
    def test_el_viernes_desde_mediodia_si(self):
        # El 21-08-2026 es viernes.
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 21, 12))
        assert any(a["familia"] == "correo_viernes" for a in avisos)

    def test_el_viernes_por_la_manana_todavia_no(self):
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 21, 9))
        assert not any(a["familia"] == "correo_viernes" for a in avisos)

    def test_el_jueves_no(self):
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 20, 13))
        assert not any(a["familia"] == "correo_viernes" for a in avisos)

    def test_la_clave_lleva_el_dia_para_volver_el_viernes_siguiente(self):
        de_este = [a for a in avisos_de_calendario_doc(ahora_es=_es(2026, 8, 21, 13))
                   if a["familia"] == "correo_viernes"][0]["clave"]
        del_siguiente = [a for a in avisos_de_calendario_doc(ahora_es=_es(2026, 8, 28, 13))
                         if a["familia"] == "correo_viernes"][0]["clave"]
        assert de_este != del_siguiente
