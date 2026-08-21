# -*- coding: utf-8 -*-
"""El contador de comidas descuenta el peri, como ya hacían los macros (tarea 1.3, 21-08).

`total_meals()` cuenta `meal_order` con Intra y Post dentro, así que la cabecera del chat
decía «Día: 2 de 6 comidas» en un día de 4 comidas con peri completo, mientras Nutrición
dice «de 4». Los macros ya llevaban el peri aparte (`objetivo_comidas`); era el contador
el que se quedó atrás. `get_day_overview` expone ahora el par de las comidas PRINCIPALES
(`completas_principales` / `total_comidas_principales`) y el del peri por separado, y
`ver_estado('dia')` se lo cuenta al modelo en `contador_comidas`.

Sin Mongo y sin OpenAI: es estado puro del bot.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_tools import AgentTools  # noqa: E402
from chatbot import NutritionChatbot  # noqa: E402


def _bot(opcion_peri="intra_post", num_comidas=4, single_meal=False,
         tipo_dia="entrenamiento"):
    bot = NutritionChatbot("test_contador", None)
    bot.configure_day(tipo_dia=tipo_dia, num_comidas=num_comidas, momento_entreno=1,
                      opcion_peri=opcion_peri, single_meal=single_meal)
    return bot


def test_dia_con_peri_cuenta_4_no_6():
    bot = _bot()
    assert bot.state["meal_order"] == ["C1", "Intra", "Post", "C2", "C3", "C4"]
    v = bot.get_day_overview()
    assert v["total_comidas_principales"] == 4, v
    assert v["total_peri"] == 2, v
    # Los campos de siempre no cambian: son el total y hay quien los lee.
    assert v["total_comidas"] == 6, v


def test_el_peri_guardado_no_infla_las_hechas():
    bot = _bot()
    bot.state["saved_meals"] = ["C1", "Post"]
    v = bot.get_day_overview()
    assert v["completas_principales"] == 1, v
    assert v["completas_peri"] == 1, v
    assert v["completas"] == 2, v          # el total, como estaba


def test_dia_de_descanso_no_tiene_peri():
    v = _bot(tipo_dia="descanso").get_day_overview()
    assert v["total_comidas_principales"] == 4
    assert v["total_peri"] == 0
    assert v["total_comidas"] == 4


def test_bloque_unico_es_una_comida():
    bot = _bot(single_meal=True, num_comidas=1)
    v = bot.get_day_overview()
    assert v["total_comidas_principales"] == 1, v
    assert v["total_peri"] == 2, v


def test_ver_estado_dia_le_da_al_modelo_el_contador_sin_peri():
    bot = _bot()
    bot.state["saved_meals"] = ["C1", "Intra", "Post"]
    tools = AgentTools.__new__(AgentTools)   # ver_estado no toca el catálogo
    tools.bot = bot
    dia = tools.ver_estado("dia")
    contador = dia.get("contador_comidas")
    assert contador, "ver_estado('dia') no trae contador_comidas"
    assert contador["hechas"] == 1, contador
    assert contador["total"] == 4, contador
    assert "principales" in contador.get("nota", ""), contador
