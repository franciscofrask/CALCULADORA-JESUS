"""La biblioteca de rutinas del equipo (17-08-2026).

Francisco: «deberíamos agregar la opción de crear rutinas en el panel de rutinas, y cuando
vas a la ficha poder elegir también de las creadas por entrenadores, poder editarlas y
borrarlas».

Aquí se comprueba la limpieza de los días, que es donde está la lógica: qué entra, qué se
descarta y cuándo un día es de descanso. Sin Mongo.
"""
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from routes.routines import _dias_limpios  # noqa: E402


def test_siempre_salen_los_siete_dias():
    """Aunque solo se escriba el lunes: una rutina es una semana entera."""
    dias = _dias_limpios([{"day": "Lunes", "exercises": [{"name": "Press banca"}]}])
    assert [d["day"] for d in dias] == ["Lunes", "Martes", "Miércoles", "Jueves",
                                        "Viernes", "Sábado", "Domingo"]


def test_un_dia_sin_ejercicios_es_descanso():
    """Sin tener que acordarse de marcar la casilla."""
    dias = _dias_limpios([{"day": "Lunes", "exercises": [{"name": "Press banca"}]}])
    porNombre = {d["day"]: d for d in dias}
    assert porNombre["Lunes"]["is_rest"] is False
    assert porNombre["Martes"]["is_rest"] is True


def test_un_ejercicio_sin_nombre_no_entra():
    """Se escapa al añadir una fila y no rellenarla; guardarla dejaría un hueco mudo."""
    dias = _dias_limpios([{"day": "Lunes", "exercises": [
        {"name": "Press banca", "sets": 4},
        {"name": "   ", "sets": 3},
        {"sets": 3},
    ]}])
    lunes = next(d for d in dias if d["day"] == "Lunes")
    assert [e["name"] for e in lunes["exercises"]] == ["Press banca"]


def test_la_ejecucion_se_guarda():
    """Es lo que distingue una rutina de una lista de nombres."""
    dias = _dias_limpios([{"day": "Lunes", "exercises": [
        {"name": "Press banca", "sets": 4, "reps": "8-10", "rest": '90"',
         "notes": "Escápulas retraídas, sin bloquear codos arriba."},
    ]}])
    ej = next(d for d in dias if d["day"] == "Lunes")["exercises"][0]
    assert ej["reps"] == "8-10" and ej["rest"] == '90"'
    assert "Escápulas" in ej["notes"]


def test_un_dia_que_no_existe_se_ignora():
    """«Lunes 1» o un dedazo no pueden crear un octavo día."""
    dias = _dias_limpios([{"day": "Lunes 1", "exercises": [{"name": "X"}]},
                          {"day": "", "exercises": [{"name": "Y"}]}])
    assert len(dias) == 7
    assert all(d["is_rest"] for d in dias)


def test_lo_que_no_es_un_dia_no_revienta():
    """A esta función también se le llamará desde la importación de las rutinas de Drive."""
    assert len(_dias_limpios(None)) == 7
    assert len(_dias_limpios(["Lunes", 42, None])) == 7


def test_el_dia_sin_tilde_es_el_mismo_dia():
    """«Miercoles» sin tilde perdia el dia ENTERO y en silencio: la plantilla se guardaba
    con un dia menos y nadie se enteraba. Pasa al llamar a la API a mano y va a pasar con
    la importacion de las rutinas de Drive."""
    dias = _dias_limpios([
        {"day": "miercoles", "exercises": [{"name": "Sentadilla", "sets": 4}]},
        {"day": "SÁBADO", "exercises": [{"name": "Remo", "sets": 3}]},
    ])
    porNombre = {d["day"]: d for d in dias}
    assert porNombre["Miércoles"]["exercises"][0]["name"] == "Sentadilla"
    assert porNombre["Sábado"]["exercises"][0]["name"] == "Remo"
    assert len(dias) == 7
