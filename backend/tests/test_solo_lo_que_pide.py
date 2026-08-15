# -*- coding: utf-8 -*-
"""Si el cliente nombra alimentos, van esos y SOLO esos.

Francisco, 15-08-2026: «si yo le pido pollo solo debe poner pollo, si le pido dos alimentos
solo debe poner los dos que le pido, porque quizá yo quiero ir cargando uno a uno; luego
quizá le pida alguna sugerencia para completar los macros, pero yo se lo voy a pedir, no lo
va a inventar».

Antes el compositor cogía sus alimentos como semilla y seguía rellenando hasta cuadrar: a
«pollo con arroz» le añadió pan de barra, y a «pollo, pan, huevos y ensalada» -- cinco
piezas ya puestas -- le metió carne picada de ternera. Los macros salían y la comida no era
la suya.
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

MACROS = {"p_entreno": 120, "h_entreno": 60, "g_entreno": 40, "p_peri": 50, "h_peri": 70,
          "p_descanso": 300, "h_descanso": 200, "g_descanso": 80}


def correr(coro):
    return asyncio.run(coro)


async def _componer(nombres, comida="2"):
    from motor.motor_asyncio import AsyncIOMotorClient
    from chatbot import NutritionChatbot
    from agent_tools import AgentTools
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    bot = NutritionChatbot("test_solo_lo_que_pide", db)
    bot.set_user_macros(dict(MACROS))
    bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="solo_post")
    tools = await AgentTools.crear(bot)
    tools.navegar(comida)
    ids = []
    for n in nombres:
        f = next((x for x in tools.foods.values()
                  if (x.get("nombre") or "").lower() == n.lower()), None)
        assert f, f"'{n}' no está en el catálogo de pruebas"
        ids.append(int(f["id"]))
    return await tools.componer_menu(incluir_ids=ids, n=3), set(ids)


@pytest.mark.parametrize("nombres", [
    ["Pollo asado"],                                        # uno solo: uno solo
    ["Pollo asado", "Arroz blanco"],                        # el caso del pan de barra
    ["Pollo asado", "Pan de barra", "Huevos enteros L", "Lechuga", "Tomate"],
])
def test_no_entra_nada_que_no_haya_pedido(nombres):
    r, ids = correr(_componer(nombres))
    assert r.get("borradores"), f"no le da nada con {nombres}: {r.get('sin_resultados_porque')}"
    for b in r["borradores"]:
        dentro = {int(i["id"]) for i in b["items"]}
        colados = [i["nombre"] for i in b["items"] if int(i["id"]) not in ids]
        assert not colados, f"metió sin pedirlo: {colados}"
        assert ids <= dentro, f"se dejó fuera algo pedido: {ids - dentro}"


def test_lo_suyo_se_enseña_aunque_no_cuadre_y_con_el_desvio_escrito():
    """Pollo y huevos traen 14 g de grasa y el hueco son 8: no cuadra, y da igual. Es su
    comida, se le enseña y se le dice cuánto se pasa."""
    r, _ = correr(_componer(["Pollo asado", "Pan de barra", "Huevos enteros L",
                             "Lechuga", "Tomate"]))
    b = r["borradores"][0]
    assert not b.get("no_aplicable"), "le esconde su propia comida"
    assert b.get("avisos"), "no le dice que se pasa"
    assert "has pedido" in b["avisos"][0]


def test_sin_alimentos_nombrados_el_compositor_trabaja_como_siempre():
    """La regla es para lo que él nombra. Pedir opciones a secas sigue trayendo comidas
    completas de las fuentes de siempre."""
    async def t():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        from agent_tools import AgentTools
        db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
        bot = NutritionChatbot("test_sin_pedidos", db)
        bot.set_user_macros(dict(MACROS))
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="solo_post")
        tools = await AgentTools.crear(bot)
        tools.navegar("2")
        return await tools.componer_menu(n=3)
    r = correr(t())
    assert r.get("borradores"), "se ha quedado sin componer nada"
    assert any(len(b["items"]) >= 3 for b in r["borradores"]), "solo trae medias comidas"
