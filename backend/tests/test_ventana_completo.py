"""
La ventana del cuestionario largo (el reloj del doc del 19-08).

    «Viernes 10:00: se abre el cuestionario largo al que se está dando de alta.
     Lunes 18:00 hora de España: cierra el cuestionario largo.»

Se prueba en verano y en invierno, como todas las ventanas: una hora escrita en UTC solo
acierta medio año.
"""
from datetime import datetime, timezone

from core.tiempo import a_madrid
from core.ventana_completo import ventana_del_completo


def _es(y, m, d, h, minuto=0):
    """Un instante dado EN HORA DE ESPAÑA, pasado a UTC (que es como llega `ahora`)."""
    from core.tiempo import MADRID
    return datetime(y, m, d, h, minuto, tzinfo=MADRID).astimezone(timezone.utc)


class TestCuandoAbre:
    def test_el_miercoles_esta_cerrada_y_abre_el_viernes(self):
        v = ventana_del_completo(_es(2026, 8, 19, 12))     # miércoles
        assert v["abierta"] is False
        assert (v["abre"].weekday(), v["abre"].day, v["abre"].hour) == (4, 21, 10)

    def test_el_viernes_antes_de_las_diez_sigue_cerrada(self):
        v = ventana_del_completo(_es(2026, 8, 21, 9, 59))
        assert v["abierta"] is False
        assert v["abre"].day == 21    # abre HOY, no el viernes siguiente

    def test_el_viernes_a_las_diez_abre(self):
        assert ventana_del_completo(_es(2026, 8, 21, 10))["abierta"] is True

    def test_el_fin_de_semana_esta_abierta(self):
        assert ventana_del_completo(_es(2026, 8, 22, 23))["abierta"] is True   # sábado
        assert ventana_del_completo(_es(2026, 8, 23, 8))["abierta"] is True    # domingo

    def test_el_lunes_hasta_las_seis_de_la_tarde(self):
        assert ventana_del_completo(_es(2026, 8, 24, 17, 59))["abierta"] is True
        v = ventana_del_completo(_es(2026, 8, 24, 18, 1))
        assert v["abierta"] is False
        assert (v["abre"].weekday(), v["abre"].day) == (4, 28)   # el viernes siguiente

    def test_el_cierre_que_se_anuncia_es_el_lunes_a_las_seis(self):
        v = ventana_del_completo(_es(2026, 8, 19, 12))
        assert (v["cierra"].weekday(), v["cierra"].hour) == (0, 18)

    def test_en_invierno_la_hora_de_espana_es_la_misma(self):
        """La prueba de que no hay una hora en UTC escondida."""
        invierno = ventana_del_completo(_es(2026, 1, 14, 12))    # miércoles de enero
        verano = ventana_del_completo(_es(2026, 8, 19, 12))
        assert a_madrid(invierno["abre"]).hour == a_madrid(verano["abre"]).hour == 10
