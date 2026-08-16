"""
Las ventanas de envío, en hora de España (doc 16-08, regla 1 y criterios de T7 y T8).

El doc lo dice con hora y con día: el quincenal va de miércoles 09:00 a jueves 20:00 y el
mensual de viernes a lunes 18:00. Antes todos compartían la misma ventana y en UTC, que es
de donde salían las dos quejas: el quincenal cerraba el lunes cuando al cliente se le
prometía el jueves a las 20:00, y la hora bailaba según la época del año.

Se comprueba en las DOS estaciones a propósito: el desfase con UTC es de dos horas en
verano y de una en invierno, así que una ventana escrita a mano en UTC solo puede acertar
media año.
"""
from datetime import datetime, timedelta, timezone

from core.tiempo import a_madrid
from routes.report_cadence import _submission_window

VERANO = datetime(2026, 8, 17, tzinfo=timezone.utc)     # lunes de agosto
INVIERNO = datetime(2026, 1, 12, tzinfo=timezone.utc)   # lunes de enero


def _local(dt):
    d = a_madrid(dt)
    return d.weekday(), d.hour, d.minute


def test_el_quincenal_abre_el_miercoles_a_las_nueve_y_cierra_el_jueves_a_las_ocho():
    for semana in (VERANO, INVIERNO):
        abre, cierra = _submission_window(semana, "quincenal")
        assert _local(abre) == (2, 9, 0), "el quincenal no abre el miércoles a las 09:00"
        assert _local(cierra) == (3, 20, 0), "el quincenal no cierra el jueves a las 20:00"


def test_el_mensual_va_del_viernes_al_lunes_a_las_seis_de_la_tarde():
    for semana in (VERANO, INVIERNO):
        abre, cierra = _submission_window(semana, "mensual")
        assert _local(abre) == (4, 0, 0), "el mensual no abre el viernes a las 00:00"
        assert _local(cierra) == (0, 18, 0), "el mensual no cierra el lunes a las 18:00"


def test_el_semanal_se_queda_como_estaba():
    """El doc no lo cubre (es del plan con llamadas): no se le cambia el horario, solo se
    dice en su hora."""
    abre, cierra = _submission_window(VERANO, "semanal")
    assert _local(abre) == (4, 0, 0)
    assert _local(cierra) == (0, 6, 0)


def test_en_invierno_y_en_verano_la_hora_de_espana_es_la_misma():
    """La prueba de que no hay una hora escrita a mano: en UTC estas dos ventanas NO
    coinciden (una hora de diferencia), y para el cliente sí."""
    _, cierra_verano = _submission_window(VERANO, "mensual")
    _, cierra_invierno = _submission_window(INVIERNO, "mensual")
    assert cierra_verano.hour != cierra_invierno.hour        # en UTC, distintas
    assert a_madrid(cierra_verano).hour == a_madrid(cierra_invierno).hour == 18


def test_la_ventana_del_quincenal_cae_antes_que_la_del_mensual():
    """Ordenarlas mal dejaría al Gold enviando el quincenal después del mensual de esa
    misma semana."""
    abre_q, cierra_q = _submission_window(VERANO, "quincenal")
    abre_m, _ = _submission_window(VERANO, "mensual")
    assert cierra_q < abre_m
    assert abre_q < abre_m
    assert cierra_q - abre_q == timedelta(days=1, hours=11)


# ── Lo que se le DICE al cliente ─────────────────────────────────────────────

def test_la_etiqueta_dice_el_dia_que_el_cliente_vive():
    """El mensual abre el viernes 00:00 de Madrid, que en UTC son las 22:00 del JUEVES.
    Sacar el nombre del día del datetime en UTC le prometía al cliente un día que no era:
    «tu reporte abre el jueves» cuando abre el viernes."""
    from routes.report_cadence import _fecha_es, _hora_es

    abre, cierra = _submission_window(VERANO, "mensual")
    assert _fecha_es(abre).startswith("viernes")
    assert _fecha_es(cierra).startswith("lunes")
    assert _hora_es(cierra) == "18:00"


def test_la_etiqueta_del_quincenal_tambien():
    from routes.report_cadence import _fecha_es, _hora_es

    abre, cierra = _submission_window(VERANO, "quincenal")
    assert _fecha_es(abre).startswith("miércoles")
    assert _fecha_es(cierra).startswith("jueves")
    assert _hora_es(cierra) == "20:00"


def test_la_hora_de_cierre_ya_no_esta_escrita_a_mano():
    """Decía «a las 6:00» fijo, que era la hora UTC de la ventana única de antes."""
    import os
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "routes", "report_cadence.py")
    with open(ruta, encoding="utf-8") as f:
        assert 'a las 6:00"' not in f.read()
