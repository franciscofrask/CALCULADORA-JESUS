"""
La semana de RUTINA, separada de la semana de plan (doc del 19-08, apartado 02).

    «El quincenal se abre en la semana 2 de la rutina, no de su ciclo. Son dos contadores
     distintos y hoy solo hay uno.»

Lo que se fija aquí: cómo cuenta el contador nuevo (arranca el lunes, 0 antes de empezar,
None sin rutina) y que el estado del reporte lo usa cuando hay rutina y cae al ciclo
cuando no la hay — que es la red que evita dejar sin reporte a los ~180 sin rutina cargada.
"""
from datetime import date, datetime, timezone

from core.semana_rutina import lunes_de_arranque, lunes_de_la_semana, semana_de_rutina
from core.tiempo import a_madrid
from routes.report_cadence import compute_client_report_state

# Una rutina entregada el jueves 6 de agosto de 2026: su lunes de arranque es el 10.
RUTINA = {"created_at": "2026-08-06T14:00:00+00:00"}


class TestElContador:
    def test_entregada_el_jueves_arranca_el_lunes(self):
        assert lunes_de_arranque(RUTINA["created_at"]) == date(2026, 8, 10)

    def test_creada_en_lunes_arranca_ese_mismo_lunes(self):
        assert lunes_de_arranque("2026-08-10T09:00:00+00:00") == date(2026, 8, 10)

    def test_antes_de_su_lunes_es_semana_cero(self):
        """Entregada pero sin empezar: con 0 el patrón no matchea y no se abre nada."""
        assert semana_de_rutina(RUTINA, date(2026, 8, 8)) == 0

    def test_su_primer_lunes_es_la_semana_uno(self):
        assert semana_de_rutina(RUTINA, date(2026, 8, 10)) == 1
        assert semana_de_rutina(RUTINA, date(2026, 8, 16)) == 1

    def test_el_lunes_siguiente_es_la_dos(self):
        assert semana_de_rutina(RUTINA, date(2026, 8, 17)) == 2
        assert semana_de_rutina(RUTINA, date(2026, 8, 19)) == 2

    def test_sin_rutina_no_hay_contador(self):
        assert semana_de_rutina(None, date(2026, 8, 19)) is None
        assert semana_de_rutina({}, date(2026, 8, 19)) is None
        assert semana_de_rutina({"created_at": "no es una fecha"}, date(2026, 8, 19)) is None

    def test_el_lunes_de_cada_semana(self):
        assert lunes_de_la_semana(RUTINA, 1) == date(2026, 8, 10)
        assert lunes_de_la_semana(RUTINA, 2) == date(2026, 8, 17)

    def test_la_fecha_se_cuenta_en_dia_de_espana(self):
        """Creada el domingo a las 22:30 UTC, que en Madrid ya es lunes: arranca ese lunes,
        no el siguiente. Es la misma trampa horaria que ya mordió tres veces."""
        assert lunes_de_arranque("2026-08-09T22:30:00+00:00") == date(2026, 8, 10)


# Un catálogo mínimo con un plan tipo Gold: quincenal en la semana 2, mensual en la 3.
CATALOGO = {"gold": {"code": "gold", "habilitaciones": {"reportes": ["quincenal", "mensual"]},
                     "ciclo": {"semanas": 12}}}


class TestElEstadoDelReporte:
    def test_con_rutina_manda_su_semana(self):
        """Cliente en semana 5 de ciclo pero semana 2 de rutina: le toca el QUINCENAL de
        la semana 2 de rutina, no lo que dijera el ciclo."""
        perfil = {"id": "c1", "plan": "gold", "cycle_start": "2026-07-15T00:00:00+00:00"}
        # Miércoles 19-08 a las 12:00 en Madrid.
        ahora = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)
        estado = compute_client_report_state(perfil, CATALOGO, ahora, rutina=RUTINA)
        assert estado["semana_rutina"] == 2
        assert estado["tipos"] == ["quincenal"]
        # Y su ventana es la de ESA semana: abre el miércoles 19 a las 10:00 de España.
        abre = a_madrid(estado["window_open"])
        assert (abre.day, abre.hour) == (19, 10)

    def test_sin_rutina_cae_al_ciclo(self):
        """La red de seguridad: sin rutina se cuenta como siempre y nadie pierde su
        reporte."""
        perfil = {"id": "c1", "plan": "gold", "cycle_start": "2026-08-10T00:00:00+00:00"}
        ahora = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)   # su semana 2 de ciclo
        estado = compute_client_report_state(perfil, CATALOGO, ahora, rutina=None)
        assert estado["semana_rutina"] is None
        assert estado["semana_reporte"] == estado["cycle"]["week"] == 2
        assert estado["tipos"] == ["quincenal"]

    def test_rutina_entregada_sin_empezar_no_abre_nada(self):
        """Semana 0 de rutina: el patrón no matchea y no se le pide reporte de una rutina
        que todavía no ha empezado, aunque su ciclo fuera semana par."""
        perfil = {"id": "c1", "plan": "gold", "cycle_start": "2026-08-03T00:00:00+00:00"}
        rutina = {"created_at": "2026-08-13T10:00:00+00:00"}   # arranca el lunes 17
        ahora = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)  # viernes 14: aún no
        estado = compute_client_report_state(perfil, CATALOGO, ahora, rutina=rutina)
        assert estado["semana_rutina"] == 0
        assert estado["tipos"] == []
