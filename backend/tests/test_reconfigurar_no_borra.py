"""Cambiar la configuración del día no puede tragarse lo que el cliente ya montó.

Francisco, 08-08-2026: tenía el post-entreno montado, pasó el día a descanso y el post
desapareció. Sin aviso. Y al preguntarle al asistente dónde estaba, le contestó que "lo
del post lo tienes metido en la Comida 2" -- que era mentira: tampoco él se había
enterado, porque nadie se lo contaba.

Era intencionado a medias: el intra y el post no existen en un día de descanso, así que
se caían del recorrido para no colarse en la dieta guardada. Pero caerse del recorrido no
es lo mismo que borrarse. Ahora los alimentos se traspasan a la comida principal más
cercana y el traspaso se cuenta -- al usuario y al agente.

Pasa igual bajando de 4 comidas a 3 (se cae la Comida 4) o quitando el peri.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MACROS = {"p_entreno": 150, "h_entreno": 120, "g_entreno": 45,
          "p_peri": 35, "h_peri": 15,
          "p_descanso": 140, "h_descanso": 40, "g_descanso": 40}

DEXTROSA = {"id": 9001, "nombre": "Dextrosa", "racion": 100, "categorias": ["10"],
            "proteinas": 0, "carbohidratos": 100, "grasas": 0}
POLLO = {"id": 9002, "nombre": "Pechuga de pollo", "racion": 100, "categorias": ["1"],
         "proteinas": 23, "carbohidratos": 0, "grasas": 2}


def _bot():
    """Sin Mongo: lo que se prueba es el reparto del estado, no el catálogo."""
    from chatbot import NutritionChatbot
    bot = NutritionChatbot.__new__(NutritionChatbot)
    NutritionChatbot.__init__(bot, "test_reconf", None)
    bot.set_user_macros(MACROS)
    return bot


def _poner(bot, key, alimento, gramos):
    bot._append_food(key, alimento, gramos, bot._macros_at(alimento, gramos))


def _nombres(bot, key):
    return [f["nombre"] for f in (bot.state["comidas_completadas"].get(key) or {}).get("alimentos", [])]


def _gramos(bot, key, nombre):
    for f in (bot.state["comidas_completadas"].get(key) or {}).get("alimentos", []):
        if f["nombre"] == nombre:
            return f["cantidad_g"]
    return 0


def test_pasar_a_descanso_no_borra_el_intra():
    bot = _bot()
    bot.configure_day("entrenamiento", 3, momento_entreno=1, opcion_peri="intra_post")
    assert bot.state["meal_order"] == ["C1", "Intra", "Post", "C2", "C3"]
    _poner(bot, "C1", POLLO, 200)
    _poner(bot, "Intra", DEXTROSA, 40)

    bot.configure_day("descanso", 3, momento_entreno=0, opcion_peri="sin_peri")

    assert "Intra" not in bot.state["meal_order"], "el intra no pinta en un día de descanso"
    assert "Dextrosa" in _nombres(bot, "C1"), (
        f"la dextrosa del intra se ha perdido: C1={_nombres(bot, 'C1')}")
    assert _gramos(bot, "C1", "Dextrosa") == 40, "se ha traspasado con otra cantidad"
    assert "Pechuga de pollo" in _nombres(bot, "C1"), "de paso se ha cargado lo que ya había"


def test_el_traspaso_se_cuenta():
    """Lo importante no es solo no borrar: es DECIRLO. Sin esto el agente se lo inventa."""
    bot = _bot()
    bot.configure_day("entrenamiento", 3, momento_entreno=1, opcion_peri="intra_post")
    _poner(bot, "Intra", DEXTROSA, 40)
    bot.configure_day("descanso", 3, momento_entreno=0, opcion_peri="sin_peri")

    reubicado = bot.state.get("reubicado_al_reconfigurar")
    assert reubicado, "se ha movido comida y no lo cuenta"
    r = reubicado[0]
    assert r["desde"] == "Intra" and r["hacia"] == "C1"
    assert r["nombre"] == "Dextrosa" and r["cantidad_g"] == 40
    assert r["desde_nombre"] and r["hacia_nombre"], "sin nombres legibles no hay aviso que dar"


def test_bajar_de_comidas_no_borra_la_ultima():
    bot = _bot()
    bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="sin_peri")
    _poner(bot, "C4", POLLO, 150)
    bot.configure_day("entrenamiento", 3, momento_entreno=1, opcion_peri="sin_peri")

    assert "C4" not in bot.state["meal_order"]
    assert "Pechuga de pollo" in _nombres(bot, "C3"), (
        f"la Comida 4 se ha perdido al bajar a 3: C3={_nombres(bot, 'C3')}")


def test_el_mismo_alimento_se_fusiona_no_se_duplica():
    """Si el destino ya llevaba lo mismo, suma gramos: nada de dos líneas de dextrosa."""
    bot = _bot()
    bot.configure_day("entrenamiento", 3, momento_entreno=1, opcion_peri="intra_post")
    _poner(bot, "C1", DEXTROSA, 20)
    _poner(bot, "Intra", DEXTROSA, 40)
    bot.configure_day("descanso", 3, momento_entreno=0, opcion_peri="sin_peri")

    assert _nombres(bot, "C1").count("Dextrosa") == 1, "línea duplicada"
    assert _gramos(bot, "C1", "Dextrosa") == 60


def test_sin_nada_montado_no_inventa_avisos():
    bot = _bot()
    bot.configure_day("entrenamiento", 3, momento_entreno=1, opcion_peri="intra_post")
    bot.configure_day("descanso", 3, momento_entreno=0, opcion_peri="sin_peri")
    assert not bot.state.get("reubicado_al_reconfigurar")


def test_los_macros_del_destino_incluyen_lo_traspasado():
    """Traspasar y no recontar sería peor que borrar: el cliente vería un cuadre falso."""
    bot = _bot()
    bot.configure_day("entrenamiento", 3, momento_entreno=1, opcion_peri="intra_post")
    _poner(bot, "Intra", DEXTROSA, 40)
    antes = dict(bot.state["comidas_completadas"]["Intra"]["macros"])
    bot.configure_day("descanso", 3, momento_entreno=0, opcion_peri="sin_peri")
    despues = bot.state["comidas_completadas"]["C1"]["macros"]
    for m in ("P", "H", "G"):
        assert abs(despues[m] - antes[m]) < 0.5, (
            f"los macros no han viajado con el alimento: {m} {antes[m]} -> {despues[m]}")
