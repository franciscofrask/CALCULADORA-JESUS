"""
Las ventanas de envío, en hora de España, con el RELOJ del doc del 19-08.

El reloj lo dice con hora y con día: el quincenal va de miércoles 10:00 a jueves 20:00 y
el mensual de viernes 10:00 a lunes 18:00. (El del 16-08 decía miércoles 09:00 y el
mensual sin hora; manda el del 19-08.) Antes de todo eso compartían la misma ventana y en
UTC, que es de donde salían las dos quejas: el quincenal cerraba el lunes cuando al
cliente se le prometía el jueves a las 20:00, y la hora bailaba según la época del año.

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


def test_el_quincenal_abre_el_miercoles_a_las_diez_y_cierra_el_jueves_a_las_ocho():
    for semana in (VERANO, INVIERNO):
        abre, cierra = _submission_window(semana, "quincenal")
        assert _local(abre) == (2, 10, 0), "el quincenal no abre el miércoles a las 10:00"
        assert _local(cierra) == (3, 20, 0), "el quincenal no cierra el jueves a las 20:00"


def test_el_mensual_va_del_viernes_a_las_diez_al_lunes_a_las_seis_de_la_tarde():
    for semana in (VERANO, INVIERNO):
        abre, cierra = _submission_window(semana, "mensual")
        assert _local(abre) == (4, 10, 0), "el mensual no abre el viernes a las 10:00"
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
    assert cierra_q - abre_q == timedelta(days=1, hours=10)


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


# ── La semana de ciclo también es la de España ───────────────────────────────

def test_la_semana_de_ciclo_cambia_a_medianoche_en_madrid():
    """A las 00:30 del lunes en Madrid son las 22:30 del domingo en UTC. Contando en UTC, el
    cliente seguía en la semana anterior: se le anunciaba el plazo de una ventana que ya
    había vencido y el reporte que le tocaba era el de la semana pasada."""
    from core.cycle import compute_cycle

    perfil = {"plan": "gold", "cycle_start": "2026-08-03T00:00:00+00:00"}
    # Domingo 16 a las 22:30 UTC = lunes 17 a las 00:30 en Madrid: ya es la semana 3.
    medianoche_larga = datetime(2026, 8, 16, 22, 30, tzinfo=timezone.utc)
    assert compute_cycle(perfil, medianoche_larga)["week"] == 3

    # Y por la tarde del domingo, cuando aquí y allí es el mismo día, sigue siendo la 2.
    domingo = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    assert compute_cycle(perfil, domingo)["week"] == 2


def test_la_ventana_se_calcula_sobre_la_semana_en_curso():
    from routes.report_cadence import _week_window_start

    perfil = {"plan": "gold", "cycle_start": "2026-08-03T00:00:00+00:00"}
    inicio = _week_window_start(perfil, datetime(2026, 8, 16, 22, 30, tzinfo=timezone.utc))
    abre, _ = _submission_window(inicio, "quincenal")
    # El miércoles de SU semana (17-23), no el de la anterior.
    assert a_madrid(abre).day == 19
