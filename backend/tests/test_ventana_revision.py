"""
La ventana del boton «Revisar» de Mis macros (tarea 7.3 del 21-08).

Se prueba la funcion pura por sus tres rutas -- autogestion, ciclo con coach y
sin ajuste -- con las fechas en la mano, sin base y sin servidor. La regla entera
vive en core/ventana_revision.
"""
from datetime import date

from core.calendario_reportes import calendario_del_plan
from core.ventana_revision import (
    un_mes_despues,
    ventana_autogestion,
    ventana_por_ciclo,
    ventana_sin_ajuste,
)

# ── El mes siguiente ─────────────────────────────────────────────────────────

def test_un_mes_despues_es_el_mismo_dia_del_mes_siguiente():
    assert un_mes_despues(date(2026, 8, 15)) == date(2026, 9, 15)


def test_un_mes_despues_recorta_los_dias_que_no_existen():
    assert un_mes_despues(date(2026, 1, 31)) == date(2026, 2, 28)
    assert un_mes_despues(date(2024, 1, 31)) == date(2024, 2, 29)   # bisiesto


def test_un_mes_despues_cruza_el_ano():
    assert un_mes_despues(date(2026, 12, 5)) == date(2027, 1, 5)


# ── Autogestion: una vez al mes ──────────────────────────────────────────────

def test_autogestion_sin_ningun_quiz_esta_abierta():
    """El primer ajuste no tiene mes que esperar: es el del alta."""
    v = ventana_autogestion(None, date(2026, 8, 21))
    assert v["abierta"] is True
    assert v["se_abre"] is None


def test_autogestion_con_el_quiz_reciente_esta_cerrada_y_dice_cuando():
    v = ventana_autogestion(date(2026, 8, 1), date(2026, 8, 21))
    assert v["abierta"] is False
    assert v["se_abre"] == "2026-09-01"
    assert v["motivo"]


def test_autogestion_al_mes_justo_se_abre():
    """El dia que se cumple el mes ya cuenta: hoy >= se_abre."""
    v = ventana_autogestion(date(2026, 7, 21), date(2026, 8, 21))
    assert v["abierta"] is True


def test_autogestion_pasado_el_mes_sigue_abierta():
    v = ventana_autogestion(date(2026, 3, 2), date(2026, 8, 21))
    assert v["abierta"] is True


# ── Con coach: cuando toca su ciclo ──────────────────────────────────────────
#
# El calendario sale del MISMO modulo que los reportes (calendario_del_plan), con los
# patrones reales del catalogo: Gold ["", "quincenal", "mensual", "quincenal"] y
# Silver/Bronze ["", "", "mensual", ""]. El mensual cae en la semana 3 de cada vuelta.

def _cal(tipos, duracion=12):
    cal = calendario_del_plan({"habilitaciones": {"reportes": tipos}})
    cal["duracion_semanas"] = duracion
    cal["semana_de_entrada"] = None
    return cal


INICIO = date(2026, 8, 3)   # un lunes: semana 1 = 3 al 9 de agosto


def test_ciclo_en_la_semana_del_mensual_esta_abierta():
    # Semana 3 del ciclo: del 17 al 23 de agosto.
    v = ventana_por_ciclo(_cal(["quincenal", "mensual"]), INICIO, date(2026, 8, 19))
    assert v["abierta"] is True


def test_ciclo_fuera_de_la_semana_del_mensual_esta_cerrada_y_da_la_fecha():
    # Semana 1: el mensual llega en la semana 3, que empieza el 17 de agosto.
    v = ventana_por_ciclo(_cal(["quincenal", "mensual"]), INICIO, date(2026, 8, 4))
    assert v["abierta"] is False
    assert v["se_abre"] == "2026-08-17"


def test_ciclo_pasada_la_semana_del_mensual_apunta_a_la_vuelta_siguiente():
    # Semana 4 (24-30 de agosto): el proximo mensual es la semana 7, el 14 de septiembre.
    v = ventana_por_ciclo(_cal(["quincenal", "mensual"]), INICIO, date(2026, 8, 25))
    assert v["abierta"] is False
    assert v["se_abre"] == "2026-09-14"


def test_ciclo_de_silver_solo_mensual_se_comporta_igual():
    v = ventana_por_ciclo(_cal(["mensual"]), INICIO, date(2026, 8, 19))
    assert v["abierta"] is True
    v = ventana_por_ciclo(_cal(["mensual"]), INICIO, date(2026, 8, 25))
    assert v["se_abre"] == "2026-09-14"


def test_ciclo_envuelve_al_terminar_las_doce_semanas():
    # Semana 13 de calendario = semana 1 del segundo ciclo (26 de octubre); su mensual
    # es la semana 3 de esa vuelta, el 9 de noviembre.
    v = ventana_por_ciclo(_cal(["mensual"]), INICIO, date(2026, 10, 27))
    assert v["abierta"] is False
    assert v["se_abre"] == "2026-11-09"


def test_ciclo_sin_mensual_en_el_patron_queda_cerrada_sin_fecha():
    """ANOTADO en el modulo: sin «mensual» no hay fecha de ciclo que dar."""
    v = ventana_por_ciclo(_cal([]), INICIO, date(2026, 8, 19))
    assert v["abierta"] is False
    assert v["se_abre"] is None
    assert v["motivo"]


# ── Sin ajuste: cerrada siempre ──────────────────────────────────────────────

def test_sin_ajuste_esta_cerrada_con_motivo():
    v = ventana_sin_ajuste()
    assert v["abierta"] is False
    assert v["se_abre"] is None
    assert "no incluye" in v["motivo"]
