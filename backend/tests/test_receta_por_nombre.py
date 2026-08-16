# -*- coding: utf-8 -*-
"""Una receta del recetario se puede pedir por su nombre, y lo prometido se cumple.

Francisco, 15-08-2026: «esa avena que le pido es una receta y no la puso en el segundo, ni
siquiera tiene avena». Pedía la «Avena Fusion Cake» -- receta de desayuno de Jesús, nueve
ingredientes -- y le salían tres opciones sin avena. La receta estaba: lo que no había era
ninguna forma de buscarla por su nombre, porque el recetario solo entraba filtrado por
momento y macros.

Y en el mismo transcript, el segundo fallo: «¿Te monto la Comida 1 con avena de base?» --
«dale» -- y las tres opciones sin avena. Prometer y no cumplir obliga al cliente a repetirse.
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

MACROS = {"p_entreno": 150, "h_entreno": 120, "g_entreno": 50, "p_peri": 50, "h_peri": 70,
          "p_descanso": 300, "h_descanso": 200, "g_descanso": 80}


def correr(coro):
    return asyncio.run(coro)


async def _tools(sesion):
    from motor.motor_asyncio import AsyncIOMotorClient
    from chatbot import NutritionChatbot
    from agent_tools import AgentTools
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    bot = NutritionChatbot(sesion, db)
    bot.set_user_macros(dict(MACROS))
    bot.configure_day("entrenamiento", 4, momento_entreno=2, opcion_peri="intra_post")
    return await AgentTools.crear(bot), bot


# ------------------------------------------------------------------ el nombre se reconoce
async def _detectar(frase):
    t, _ = await _tools("test_receta_detecta")
    return await t.receta_nombrada(frase)


@pytest.mark.parametrize("frase", [
    "quiero la avena fusion cake",
    "montame el avena fusion cake en la comida 1",
    "avena fusion cake",
])
def test_la_receta_nombrada_se_encuentra(frase):
    r = correr(_detectar(frase))
    assert r and "fusion cake" in (r.get("nombre") or "").lower()


@pytest.mark.parametrize("frase", [
    "montame pollo con arroz",        # ingredientes sueltos: manda «solo lo pedido»
    "quiero pollo, arroz y aceite",
    "dame opciones para el desayuno",
    "ponme 200 g de pechuga de pollo",
])
def test_pedir_ingredientes_no_es_pedir_una_receta(frase):
    assert correr(_detectar(frase)) is None


# ------------------------------------------------------------------ y se monta esa, entera
async def _montar(nombre):
    t, bot = await _tools("test_receta_monta")
    return await t.componer_menu(receta=nombre), bot


def test_la_receta_sale_con_sus_ingredientes():
    r, _ = correr(_montar("Avena Fusion Cake"))
    bs = r.get("borradores") or []
    assert len(bs) == 1, r.get("sin_resultados_porque")
    b = bs[0]
    assert b["nombre"] == "Avena Fusion Cake"
    assert b["origen"] == "recetario"
    assert b.get("receta_pedida") == "Avena Fusion Cake"
    nombres = " ".join(i["nombre"].lower() for i in b["items"])
    assert "avena" in nombres, nombres
    # Nueve ingredientes tiene la receta: se enseña entera, no una versión recortada.
    assert len(b["items"]) >= 8, [i["nombre"] for i in b["items"]]
    # Y con cantidades servibles, no a cero.
    assert all(i["cantidad_g"] > 0 for i in b["items"])


def test_una_receta_que_no_existe_se_dice_sin_inventar_otra():
    r, _ = correr(_montar("Tarta galáctica de zanahoria"))
    assert not r.get("borradores")
    assert any("no hay ninguna receta" in x for x in (r.get("sin_resultados_porque") or []))


# ------------------------------------------------------- lo prometido entra en la comida
async def _promesa_y_si():
    from agent_loop import AgentLoop
    t, bot = await _tools("test_receta_promesa")
    loop = AgentLoop(bot, t)
    avena = next((f for f in t.foods.values()
                  if (f.get("nombre") or "").lower().startswith("copos de avena")), None)
    assert avena, "no hay copos de avena en el catálogo de pruebas"
    # Turno 1: el asistente miró la avena y cerró preguntando si monta la comida con ella.
    loop._vistos_del_turno = {int(avena["id"]): avena["nombre"]}
    loop._apuntar_promesa("¿Te monto la Comida 1 con avena de base?", [])
    apuntada = bot.state.get("promesa_alimentos")
    # Turno 2: un «dale» pelado, y el modelo compone sin pasar la avena.
    loop._prometidos = list((apuntada or {}).get("ids") or [])
    r = await loop._despachar("componer_menu", {"n": 2})
    return apuntada, r, int(avena["id"])


def test_lo_que_prometio_entra_cuando_el_cliente_dice_que_si():
    apuntada, r, avena_id = correr(_promesa_y_si())
    assert apuntada and apuntada["ids"] == [avena_id]
    bs = r.get("borradores") or []
    assert bs, r.get("sin_resultados_porque")
    for b in bs:
        assert any(i["id"] == avena_id for i in b["items"]), \
            f"la opción «{b['nombre']}» no lleva lo prometido: {[i['nombre'] for i in b['items']]}"


async def _promesa_sin_pregunta():
    from agent_loop import AgentLoop
    t, bot = await _tools("test_receta_promesa2")
    loop = AgentLoop(bot, t)
    avena = next(iter(t.foods.values()))
    loop._vistos_del_turno = {int(avena["id"]): avena["nombre"]}
    # Sin pregunta no hay promesa; con tarjetas delante tampoco (el «sí» va a las tarjetas).
    loop._apuntar_promesa(f"Te he puesto {avena['nombre']} en la comida.", [])
    sin_pregunta = bot.state.get("promesa_alimentos")
    loop._apuntar_promesa(f"¿Te monto la comida con {avena['nombre']}?", [{"id": "b1"}])
    con_tarjetas = bot.state.get("promesa_alimentos")
    return sin_pregunta, con_tarjetas


def test_no_se_apunta_promesa_donde_no_la_hay():
    sin_pregunta, con_tarjetas = correr(_promesa_sin_pregunta())
    assert sin_pregunta is None
    assert con_tarjetas is None
