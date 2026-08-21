# -*- coding: utf-8 -*-
"""`editar_comida` op='cuadrar': cuadrar la comida VIVA, no solo el borrador (1.3, 21-08).

«Sí, ajústamela» tras un sustituir no tenía herramienta: cuadrar solo existía sobre el
borrador (`editar_borrador` op='cuadrar'), y el sustituir de `editar_comida` mete la
pieza nueva con la cantidad que decida el motor sin recuadrar el resto. El modelo, sin
op, o ajustaba a ojo o contestaba que ya estaba, y la comida se quedaba descuadrada.

Mismo motor que el borrador (`_recuadrar_a_hoy`): reajusta las cantidades de lo que la
comida ya lleva, remata con UNA pieza solo si falta un macro, y nunca la deja peor.

Necesita Mongo (el catálogo y `meal_builder`), no OpenAI.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

MONGO_URL = os.environ.get("MONGO_URL")
pytestmark = pytest.mark.skipif(not MONGO_URL, reason="sin MONGO_URL: test de integración")

MACROS = {"p_entreno": 120, "h_entreno": 60, "g_entreno": 40, "p_peri": 50, "h_peri": 70,
          "p_descanso": 300, "h_descanso": 200, "g_descanso": 80}


def correr(coro):
    return asyncio.run(coro)


async def _bot_y_tools(sesion):
    from motor.motor_asyncio import AsyncIOMotorClient
    from agent_tools import AgentTools
    from chatbot import NutritionChatbot
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    bot = NutritionChatbot(sesion, db)
    bot.set_user_macros(dict(MACROS))
    bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="solo_post")
    tools = await AgentTools.crear(bot)
    tools.navegar("2")
    return bot, tools


def _id_de(tools, nombre):
    f = next((x for x in tools.foods.values()
              if (x.get("nombre") or "").lower() == nombre.lower()), None)
    assert f, f"'{nombre}' no está en el catálogo de pruebas"
    return int(f["id"])


def _desvio(bot):
    return sum(abs(v) for v in bot.get_remaining_macros().values())


def test_cuadrar_reajusta_sin_perder_lo_que_habia():
    async def t():
        bot, tools = await _bot_y_tools("test_cuadrar_viva")
        # Una comida claramente descuadrada: cantidades enanas puestas a mano.
        await bot.add_food_by_id(_id_de(tools, "Pollo asado"), 30)
        await bot.add_food_by_id(_id_de(tools, "Arroz blanco"), 20)
        antes = _desvio(bot)
        r = await tools.editar_comida([{"op": "cuadrar"}])
        return bot, r, antes
    bot, r, antes = correr(t())
    assert r.get("ok"), r
    assert r.get("hechos"), r
    despues = _desvio(bot)
    assert despues < antes, f"no ha mejorado: antes {antes}, después {despues}"
    nombres = {a.get("nombre") for a in
               bot.state["comidas_completadas"]["C2"]["alimentos"]}
    assert "Pollo asado" in nombres and "Arroz blanco" in nombres, \
        f"cuadrar ha perdido piezas: {nombres}"
    detalle = r["hechos"][0]["detalle"]
    assert detalle.get("cambios"), "no cuenta qué ha cambiado"
    assert "falta_ahora" in detalle, "no dice cómo queda"


def test_cuadrar_una_comida_vacia_no_hace_nada_y_lo_dice():
    async def t():
        _, tools = await _bot_y_tools("test_cuadrar_vacia")
        return await tools.editar_comida([{"op": "cuadrar"}])
    r = correr(t())
    assert not r.get("ok"), r
    assert "vacía" in str(r.get("fallos")), r


def test_cuadrar_una_comida_volcada_mantiene_la_marca_de_guardada():
    """La comida se reescribe entera (clear + add) y `clear_meal` suelta la marca de
    `saved_meals`; sin reponerla, el bucle del agente no re-sincroniza con Nutrición y
    el plan se queda con las cantidades viejas."""
    async def t():
        bot, tools = await _bot_y_tools("test_cuadrar_guardada")
        await bot.add_food_by_id(_id_de(tools, "Pollo asado"), 30)
        await bot.add_food_by_id(_id_de(tools, "Arroz blanco"), 20)
        bot.state.setdefault("saved_meals", []).append("C2")
        r = await tools.editar_comida([{"op": "cuadrar"}])
        return bot, r
    bot, r = correr(t())
    assert r.get("ok"), r
    assert "C2" in (bot.state.get("saved_meals") or []), \
        "cuadrar le quitó la marca de guardada y el plan no se re-sincronizaría"
