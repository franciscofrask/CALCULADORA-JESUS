# -*- coding: utf-8 -*-
"""Un plato que no está en el catálogo no se sustituye por sus ingredientes en silencio.

Francisco, viéndolo en producción el 15-08: pidió «pon tortillas de claras», el asistente
le metió 300 g de claras de huevo pasteurizadas y no dijo nada. «No debería cargarme lo que
quiera.» En el catálogo no hay ninguna tortilla de claras -- las tortillas que hay son de
patata, de trigo, de maíz y de avena --, y las claras son el ingrediente con el que se hace,
no el plato.

El aviso que ya existía solo miraba peticiones de UNA palabra. Estos casos fijan el de
varias, y sobre todo fijan que NO salte con los platos que sí existen: pedirle núcleo a
todas las palabras daba por inexistente medio catálogo, porque los adjetivos («arroz
BLANCO», «salmón AHUMADO») nunca están en el núcleo.
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


async def _buscar(texto):
    from motor.motor_asyncio import AsyncIOMotorClient
    from chatbot import NutritionChatbot
    from agent_tools import AgentTools
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    bot = NutritionChatbot("test_plato_que_no_existe", db)
    bot.set_user_macros(dict(MACROS))
    bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
    tools = await AgentTools.crear(bot)
    return await tools.buscar_alimentos(texto=texto, limite=4)


@pytest.mark.parametrize("texto", ["tortillas de claras", "tortilla de claras de huevo"])
def test_el_plato_que_no_existe_se_avisa(texto):
    r = correr(_buscar(texto))
    ojo = r.get("ojo") or ""
    assert "no hay ning" in ojo.lower(), f"no avisa de que '{texto}' no existe: {ojo[:120]}"
    assert "no lo añadas por tu cuenta" in ojo.lower(), "no le prohíbe plantarlo él solo"
    # Los ingredientes SÍ se devuelven: son lo que se le puede ofrecer para que elija.
    assert r.get("items"), "se queda sin nada que enseñarle"


@pytest.mark.parametrize("texto", [
    "pechuga de pollo",     # existe con ese nombre exacto
    "arroz blanco",         # el adjetivo no está en el núcleo, y aun así existe
    "salmon ahumado",       # igual, con acento de por medio
    "200 g de arroz",       # números y unidades no cuentan como palabras del plato
])
def test_lo_que_si_existe_no_dispara_el_aviso(texto):
    r = correr(_buscar(texto))
    ojo = r.get("ojo") or ""
    assert "no hay ning" not in ojo.lower(), (
        f"dice que '{texto}' no existe y sí está: {[i['nombre'] for i in r.get('items', [])][:3]}")
