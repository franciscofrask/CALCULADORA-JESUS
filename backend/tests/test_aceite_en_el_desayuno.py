# -*- coding: utf-8 -*-
"""En un desayuno no sale aceite. En una cena, sí.

Regla de Francisco del 15-08-2026, viéndolo en la app: «aceite no quiero que salga en un
desayuno». Los aceites ya eran «no sugeribles» por condimento, pero el rescate de
`_acompana_a_algo` los dejaba entrar en cuanto había con qué acompañarlos, y así salió un
desayuno de flan proteico + aceite + acelgas.

Lo que NO cambia: en el resto de comidas se queda como estaba («dejalo como esta al
aceite»), y pedirlo por su nombre sigue funcionando en todas.
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

MACROS = {"p_entreno": 190, "h_entreno": 110, "g_entreno": 50,
          "p_peri": 45, "h_peri": 20,
          "p_descanso": 220, "h_descanso": 90, "g_descanso": 50}


def correr(coro):
    return asyncio.run(coro)


async def _tools_en(comida: str):
    from motor.motor_asyncio import AsyncIOMotorClient
    from chatbot import NutritionChatbot
    from agent_tools import AgentTools
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    bot = NutritionChatbot("test_aceite_desayuno", db)
    bot.set_user_macros(dict(MACROS))
    bot.configure_day(tipo_dia="entrenamiento", num_comidas=4, momento_entreno=1,
                      opcion_peri="intra_post")
    tools = await AgentTools.crear(bot)
    tools.navegar(comida)
    return tools


def _aceites(items):
    from calculator import cat_in_list
    from calma_engine import parse_categories
    return [i["nombre"] for i in items
            if any(cat_in_list(c, ["17.1"])
                   for c in parse_categories((i.get("alimento") or {}).get("categorias", "")))]


class TestElAceiteYElDesayuno:
    def test_el_compositor_no_pone_aceite_en_el_desayuno(self):
        async def t():
            tools = await _tools_en("1")
            assert tools._momento_actual() == "desayuno", "la Comida 1 de 4 debería ser desayuno"
            r = await tools.componer_menu(n=3)
            for b in r.get("borradores", []):
                assert not _aceites(b["items"]), (
                    f"aceite en un desayuno: {[i['nombre'] for i in b['items']]}")
        correr(t())

    def test_las_sugerencias_del_desayuno_tampoco(self):
        async def t():
            tools = await _tools_en("1")
            r = await tools.buscar_alimentos(para_macro="G", limite=10)
            assert not _aceites(r.get("items", [])), "el buscador ofrece aceite de desayuno"
        correr(t())

    def test_pedirlo_por_su_nombre_sigue_valiendo(self):
        """No es una prohibición: es que no se propone solo. Quien lo pide, lo tiene."""
        async def t():
            tools = await _tools_en("1")
            r = await tools.buscar_alimentos(texto="aceite de oliva", limite=5)
            nombres = [i["nombre"].lower() for i in r.get("items", [])]
            assert any("aceite" in n for n in nombres), (
                f"pide aceite por su nombre y no se lo da: {nombres}")
        correr(t())

    def test_en_la_cena_se_queda_como_estaba(self):
        """La regla es del desayuno. En la cena el aceite sigue siendo una grasa válida."""
        async def t():
            tools = await _tools_en("4")
            assert tools._momento_actual() == "cena"
            r = await tools.buscar_alimentos(texto="aceite de oliva", limite=5)
            assert any("aceite" in i["nombre"].lower() for i in r.get("items", [])), (
                "en la cena el aceite tiene que seguir estando")
        correr(t())
