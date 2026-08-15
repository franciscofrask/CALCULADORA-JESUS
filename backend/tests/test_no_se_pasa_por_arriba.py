# -*- coding: utf-8 -*-
"""El compositor no ofrece menús que se pasan de hidratos o de grasa.

«Por abajo se ajusta, por arriba no se pasa» (Jesús, 13-08). El corte que había sumaba el
exceso de los TRES macros y lo comparaba con 24 g, así que una opción con 22,5 g de grasa
sobre un objetivo de 10 -- «tortilla de patata» ofrecida a quien pidió tortilla de huevo --
pasaba con 12,5 de exceso y salía con su botón de elegir (Francisco, en producción el
15-08). Sumar los tres esconde justo el caso que importa: un macro reventado y los otros
dos clavados.

La proteína es otra cosa y sigue exenta: pasarse de proteína el método lo tolera.
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


async def _menus(estilo):
    from motor.motor_asyncio import AsyncIOMotorClient
    from chatbot import NutritionChatbot
    from agent_tools import AgentTools
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    bot = NutritionChatbot("test_no_se_pasa", db)
    bot.set_user_macros(dict(MACROS))
    bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
    tools = await AgentTools.crear(bot)
    return await tools.componer_menu(estilo=estilo, n=3), bot


@pytest.mark.parametrize("estilo", ["tortilla de huevo", "algo con queso", "pizza"])
def test_ninguna_opcion_aplicable_se_pasa_de_hidratos_ni_de_grasa(estilo):
    r, bot = correr(_menus(estilo))
    for b in r.get("borradores", []):
        if b.get("no_aplicable"):
            continue                      # esas se enseñan a propósito, y sin botón
        for m in ("H", "G"):
            tope = 2 * bot.margen_de(b["objetivo"].get(m, 0))
            assert b["desvio"][m] <= tope, (
                f"«{estilo}» ofrece una opción aplicable con {b['desvio'][m]:.1f} g de más "
                f"en {m} (tope {tope:.1f}): {[i['nombre'] for i in b['items']]}")


def test_la_que_se_pasa_y_se_rescata_sale_sin_boton():
    """Nadie se queda sin ver nada, pero un menú pasado no se puede rematar: no se aplica."""
    r, _ = correr(_menus("tortilla de patata"))
    for b in r.get("borradores", []):
        if any("se pasa" in (a or "") for a in (b.get("avisos") or [])):
            assert b.get("no_aplicable"), "una opción pasada sale con su botón de elegir"


def test_pasarse_de_proteina_sigue_permitido():
    """La regla es de hidratos y grasa. Que la proteína suba no puede tirar una opción."""
    r, bot = correr(_menus("mucha proteina"))
    aplicables = [b for b in r.get("borradores", []) if not b.get("no_aplicable")]
    assert aplicables, "se ha quedado sin ninguna opción aplicable"
