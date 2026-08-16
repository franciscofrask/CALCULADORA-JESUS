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
    # Lo que el cliente ha escrito, que es lo que convierte esto en «lo que pide él»: desde
    # el 16-08 la regla solo se aplica a los alimentos que salen de SUS palabras, porque el
    # modelo se puso a meter en `incluir_ids` alimentos elegidos por su cuenta y la comida
    # salía siendo solo eso (dos aceites como desayuno entero).
    bot.mensaje_en_curso = "ponme " + ", ".join(nombres)
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


# ------------------------------------------------- los gramos que dice el cliente
class TestLosGramosQueDiceElCliente:
    """«La opción 3 pero añádele 30 gramos de almendras» -> 30, y el menú entero.

    Salió en producción el 15-08: puso 5 g de almendras en vez de 30, borró las claras y el
    fiambre de pavo, y subió el queso de 50 a 150 g. Un menú que el cliente había elegido,
    deshecho para que los números cuadraran. Iba TODO al recuadre y este hacía lo que quería.
    """

    def test_respeta_los_gramos_y_no_pierde_ingredientes(self):
        async def t():
            from motor.motor_asyncio import AsyncIOMotorClient
            from chatbot import NutritionChatbot
            from agent_tools import AgentTools
            db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
            bot = NutritionChatbot("test_gramos_cliente", db)
            bot.set_user_macros(dict(MACROS))
            bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
            tools = await AgentTools.crear(bot)
            r = await tools.componer_menu(n=3)
            bs = r.get("borradores") or []
            if not bs:
                pytest.skip("el compositor no dio ninguna opción con la que probar")
            b = bs[-1]
            antes = {i["nombre"] for i in b["items"]}
            alm = next(x for x in tools.foods.values() if x.get("nombre") == "Almendras")
            await tools.editar_borrador(b["id"], [{"op": "añadir",
                                                   "alimento_id": int(alm["id"]),
                                                   "cantidad": 30}])
            return (bot.state.get("borradores") or {}).get(b["id"]), antes

        b2, antes = correr(t())
        ahora = {i["nombre"]: i.get("cantidad_g") for i in b2["items"]}
        assert ahora.get("Almendras") == 30, (
            f"le cambió los gramos: pidió 30 y puso {ahora.get('Almendras')}")
        perdidos = antes - set(ahora)
        assert not perdidos, f"se llevó por delante ingredientes que él no quitó: {perdidos}"
        # Y como los gramos los ha puesto él, la opción no se le bloquea al elegirla.
        assert b2.get("solo_lo_pedido"), "se le bloquearía al aplicarla"


def test_lo_que_elige_el_modelo_no_es_lo_que_pide_el_cliente():
    """«Añádele algo de grasa» no puede acabar en una comida de dos aceites y nada más.

    Francisco, 16-08-2026, en producción: pidió la opción anterior «con algo de grasa», el
    modelo eligió por su cuenta aceite de coco y aceite de oliva, los pasó como si fueran
    suyos, y salió un desayuno de 0 g de proteína, 0 de hidratos y 10 de grasa con su botón
    de aplicar. La regla de «solo lo que pides» es para respetar al cliente, no para que el
    modelo se salte el compositor.
    """
    async def _probar():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        from agent_tools import AgentTools
        db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
        bot = NutritionChatbot("test_no_lo_pidio_el", db)
        bot.set_user_macros(dict(MACROS))
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="solo_post")
        tools = await AgentTools.crear(bot)
        aceite = next((f for f in tools.foods.values()
                       if (f.get("nombre") or "").startswith("Aceite de coco")), None)
        assert aceite, "no hay aceite de coco en el catálogo de pruebas"
        bot.mensaje_en_curso = "la anterior con algo de grasa"
        return await tools.componer_menu(incluir_ids=[int(aceite["id"])])
    r = correr(_probar())
    b = (r.get("borradores") or [None])[0]
    assert b, r.get("sin_resultados_porque")
    assert len(b["items"]) > 1, [i["nombre"] for i in b["items"]]
    assert b["macros_totales"]["P"] > 10, b["macros_totales"]
