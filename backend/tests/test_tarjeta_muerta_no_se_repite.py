# -*- coding: utf-8 -*-
"""La tarjeta muerta no se repite (flecos del 21-08, punto 4).

`componer_menu` rescata como máximo UNA opción no aplicable por llamada («por arriba el
método no la da por buena», `no_aplicable=True`; el front la pinta «Solo de referencia»,
sin botón). Pero tres llamadas seguidas eran tres tarjetas muertas iguales: el cliente
pedía otra vez y recibía otra vez lo mismo que no puede elegir.

La regla: si en ESTA comida una ronda anterior ya salió entera «solo de referencia», no
se rescata otra. Se devuelve el camino `sin_resultados_porque` que ya existía, para que
el asistente proponga bajar el objetivo o cambiar de pieza. Una por comida y
conversación basta.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

MONGO_URL = os.environ.get("MONGO_URL")
pytestmark = pytest.mark.skipif(not MONGO_URL, reason="sin MONGO_URL: test de integración")

MACROS = {"p_entreno": 201, "h_entreno": 80, "g_entreno": 50, "p_peri": 50, "h_peri": 70,
          "p_descanso": 300, "h_descanso": 200, "g_descanso": 80}


def correr(coro):
    return asyncio.run(coro)


async def _bot_y_tools(nombre):
    from motor.motor_asyncio import AsyncIOMotorClient
    from chatbot import NutritionChatbot
    from agent_tools import AgentTools
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    bot = NutritionChatbot(nombre, db)
    bot.set_user_macros(dict(MACROS))
    bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
    tools = await AgentTools.crear(bot)
    return bot, tools


def test_con_la_marca_puesta_no_sale_otra_tarjeta_muerta():
    """El candado en sí: con el rescate ya consumido en esta comida, ninguna ronda
    posterior puede volver a enseñar una opción `no_aplicable`. O trae opciones con
    botón, o trae `sin_resultados_porque` para que el asistente proponga otra salida."""
    async def go():
        bot, tools = await _bot_y_tools("test_tarjeta_muerta_candado")
        bot.state.setdefault("rescate_muerto", {})[bot.current_meal_key()] = True
        # «tortilla de patata» es el estilo que dispara el rescate de las pasadas de
        # grasa (mismo caso que test_no_se_pasa_por_arriba).
        return await tools.componer_menu(estilo="tortilla de patata", n=3)
    r = correr(go())
    muertas = [b for b in r.get("borradores", []) if b.get("no_aplicable")]
    assert not muertas, "con el rescate ya consumido ha vuelto a salir una tarjeta muerta"
    if not r.get("borradores"):
        assert r.get("sin_resultados_porque"), (
            "sin borradores tiene que venir sin_resultados_porque, que es lo que le da "
            "al asistente el porqué para proponer bajar el objetivo o cambiar de pieza")


def test_dos_rondas_seguidas_no_repiten_la_tarjeta_muerta():
    """El circuito completo: si la primera ronda sale entera «solo de referencia», la
    marca queda puesta y la segunda ronda del MISMO estilo ya no repite la tarjeta."""
    async def go():
        bot, tools = await _bot_y_tools("test_tarjeta_muerta_rondas")
        r1 = await tools.componer_menu(estilo="tortilla de patata", n=3)
        r2 = await tools.componer_menu(estilo="tortilla de patata", n=3)
        return bot, r1, r2
    bot, r1, r2 = correr(go())
    b1 = r1.get("borradores", [])
    if not (b1 and all(b.get("no_aplicable") for b in b1)):
        pytest.skip("con el catálogo actual la primera ronda no acaba en rescate muerto; "
                    "el candado lo cubre el test de arriba")
    assert bot.state.get("rescate_muerto", {}).get(bot.current_meal_key()), (
        "la ronda salió entera solo de referencia y la marca no se apuntó")
    muertas2 = [b for b in r2.get("borradores", []) if b.get("no_aplicable")]
    assert not muertas2, "la segunda ronda volvió a enseñar la tarjeta muerta"
    if not r2.get("borradores"):
        assert r2.get("sin_resultados_porque")


def test_una_ronda_con_opciones_de_verdad_no_apunta_la_marca():
    """La marca es SOLO para las rondas que salen enteras de referencia: una ronda con
    opciones aplicables no puede gastar el rescate de la comida."""
    async def go():
        bot, tools = await _bot_y_tools("test_tarjeta_muerta_no_marca")
        r = await tools.componer_menu(estilo="pollo con arroz", n=3)
        return bot, r
    bot, r = correr(go())
    aplicables = [b for b in r.get("borradores", []) if not b.get("no_aplicable")]
    if not aplicables:
        pytest.skip("el catálogo no dio opciones aplicables para un pollo con arroz")
    assert not bot.state.get("rescate_muerto", {}).get(bot.current_meal_key()), (
        "una ronda con opciones aplicables ha dejado apuntado el rescate como gastado")
