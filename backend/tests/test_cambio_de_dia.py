"""Cambiar de día lo decide el asistente, no un regex del front.

Francisco, 08-08-2026: escribió «hoy es día de descanso» y no pasó nada de lo que pedía.
El front miraba el mensaje con `/^(hoy|manana|pasado manana)\\b/` antes de mandarlo al
backend; como empezaba por «hoy», lo leía como «vete al día de hoy», recargaba ese día
y se dejaba por el camino lo de descanso. El mensaje ni siquiera llegaba al asistente.

El mismo regex se tragaba «esto lo dejo para mañana, ponme atún» (por `\\bpara mañana\\b`),
que no pide cambiar de día en absoluto.

Es el mismo hardcodeo que ya se quitó para la configuración del día en F3: adivinar la
intención con una lista de palabras, cuando hay un modelo delante que entiende la frase.
Ahora hay una herramienta `cambiar_de_dia` y el front solo obedece lo que venga en
`state.fecha_pedida`.

Los casos de lenguaje van contra el agente real (necesitan OPENAI_API_KEY); la validación
de la herramienta no.
"""
import asyncio
import os
import sys
from datetime import date, timedelta

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

# El .env va aquí arriba a propósito: el skipif se evalúa al importar el módulo, y si se
# carga más tarde (dentro del test) los casos se saltan en silencio y parece que pasan.
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_RAIZ, ".env"))

MONGO_URL = os.environ.get("MONGO_URL")
MACROS = {"p_entreno": 160, "h_entreno": 120, "g_entreno": 40,
          "p_peri": 35, "h_peri": 15,
          "p_descanso": 140, "h_descanso": 40, "g_descanso": 40}


async def _bot():
    from dotenv import load_dotenv
    from motor.motor_asyncio import AsyncIOMotorClient
    from chatbot import NutritionChatbot
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(raiz, ".env"))
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
    bot = NutritionChatbot("test_cambio_dia", db)
    bot.set_user_macros(MACROS)
    bot.state["fecha_objetivo"] = date.today().isoformat()
    bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
    return bot


# --------------------------------------------------------- validación (sin LLM)
class TestLaHerramienta:
    def test_exige_fecha_real(self):
        async def t():
            from agent_tools import AgentTools
            tools = await AgentTools.crear(await _bot())
            return [tools.cambiar_de_dia(f) for f in (None, "", "mañana", "2026-13-45", "8/8/2026")]
        for r in asyncio.run(t()):
            assert not r["ok"], f"ha tragado una fecha que no lo es: {r}"

    def test_apunta_la_fecha_pedida(self):
        async def t():
            from agent_tools import AgentTools
            bot = await _bot()
            tools = await AgentTools.crear(bot)
            r = tools.cambiar_de_dia("2026-08-09")
            return r, bot.state.get("fecha_pedida")
        r, apuntada = asyncio.run(t())
        assert r["ok"] and apuntada == "2026-08-09"


# ------------------------------------------------------ el lenguaje (con LLM)
pytestmark_llm = pytest.mark.skipif(
    not (MONGO_URL and os.environ.get("OPENAI_API_KEY")),
    reason="necesita Mongo y OPENAI_API_KEY: test de integración con el agente real")

HOY = date.today().isoformat()
MANANA = (date.today() + timedelta(days=1)).isoformat()


async def _hablar(mensaje):
    from agent_loop import AgentLoop
    bot = await _bot()
    loop = await AgentLoop.crear(bot)
    await loop.procesar(mensaje)
    return bot.state.get("fecha_pedida"), bot.state.get("tipo_dia")


@pytestmark_llm
@pytest.mark.parametrize("mensaje,fecha_esperada,tipo_esperado", [
    # El caso de Francisco: DOS peticiones en una frase, hay que atender las dos.
    ("hoy es dia de descanso", None, "descanso"),
    ("mañana descanso", MANANA, "descanso"),
    ("vamos a montar el de mañana", MANANA, "entrenamiento"),
    # Y estos NO piden cambiar de día por mucho que digan "mañana".
    ("esto lo dejo para mañana, ponme atun", None, "entrenamiento"),
    ("quiero pollo con arroz", None, "entrenamiento"),
])
def test_lo_que_pide_el_cliente_llega_entero(mensaje, fecha_esperada, tipo_esperado):
    fecha, tipo = asyncio.run(_hablar(mensaje))
    assert tipo == tipo_esperado, f"«{mensaje}»: el tipo de día quedó en {tipo}"
    if fecha_esperada is None:
        assert fecha in (None, HOY), f"«{mensaje}» ha cambiado de día sin que se lo pidieran: {fecha}"
    else:
        assert fecha == fecha_esperada, f"«{mensaje}»: esperaba {fecha_esperada} y llegó {fecha}"
