"""Lo que el cliente pide por su nombre no se cambia por otra cosa.

Francisco, 08-08-2026: pidió «pollo lechuga huevos y jugo» y el asistente le devolvió
tres opciones de huevos con manzana. Ni pollo ni lechuga. Y el propio asistente lo
decía en su respuesta -- «ni llevan pollo ni lechuga, además» -- y las enseñaba igual.

La Lechuga existe (id 363). Lo que pasaba es que TRES filtros distintos, todos pensados
para no proponer tonterías por iniciativa propia, se cargaban también lo que el cliente
había pedido a propósito, y ninguno lo decía:

  1. `para_macro`: el agente buscaba `texto="lechuga", para_macro="H"`, la lechuga no
     aporta hidratos y se descartaba. Salían sus vecinos semánticos, que sí aportan:
     calabaza, puerro.
  2. La coherencia con el momento: lechuga en la Comida 1 es «atípica para un
     desayuno», así que fuera. Y el aviso de «vetados por atípicos» solo aparece
     cuando no queda NINGÚN resultado -- y vecinos había --, así que se iba en silencio.
  3. `componer_menu` recibía `incluir_ids` como «obligatorios», los pasaba a nombres y
     dejaba que `build_meal` decidiera qué cabía. Los que no cabían desaparecían sin
     que nadie los contase.

Nada de esto es de la lechuga: pasa con cualquier alimento que aporte poco (pepino,
apio, café, especias, agua) o que sea atípico para la comida en la que estés. Por eso
el test va con varios y no con uno.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _db():
    """El cliente se crea DENTRO de cada asyncio.run: Motor se ata al event loop en el
    que nace, y compartirlo entre tests daba «Event loop is closed» y resultados
    fantasma (un test veía peras al buscar pepino)."""
    from dotenv import load_dotenv
    from motor.motor_asyncio import AsyncIOMotorClient
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]


async def _tools(db, restante):
    """Las herramientas del agente sobre una comida con esos macros restantes."""
    import chatbot as cb
    from agent_tools import AgentTools

    bot = cb.NutritionChatbot.__new__(cb.NutritionChatbot)
    bot.db = db
    bot.state = {"comida_actual": 1, "num_comidas": 4, "single_meal": False,
                 "meal_order": ["C1", "Intra", "Post", "C2", "C3", "C4"],
                 "avoided_categories": [], "avoided_keywords": [], "borradores": {}}
    bot.get_remaining_macros = lambda: dict(restante)
    return await AgentTools.crear(bot)


@pytest.mark.parametrize("pedido,esperado", [
    ("lechuga", "Lechuga"),
    ("pepino", "Pepino"),
    ("calabacin", "Calabacín"),
])
def test_lo_pedido_por_su_nombre_sale_el_primero(pedido, esperado):
    """Aunque no aporte el macro que el agente supone, y aunque sea raro a esa hora."""
    async def _correr():
        tools = await _tools(_db(), {"P": 47.5, "H": 72.0, "G": 12.0})
        # `para_macro="H"` es justo lo que hacía el agente con la lechuga: pedir una
        # verdura como si fuera una fuente de hidratos.
        return await tools.buscar_alimentos(texto=pedido, para_macro="H", limite=8)
    res = asyncio.run(_correr())
    nombres = [i["nombre"] for i in res["items"]]
    assert nombres, f"«{pedido}» no devuelve nada: {res.get('sin_resultados_porque')}"
    assert any(esperado.lower() in n.lower() for n in nombres), (
        f"pedí «{pedido}» y me devuelve {nombres[:4]}")
    assert esperado.lower() in nombres[0].lower(), (
        f"«{esperado}» sale, pero no el primero: {nombres[:4]}")


def test_sin_texto_el_macro_sigue_filtrando():
    """El arreglo no puede cargarse el caso legítimo: «dame algo con proteína» sin
    texto SÍ debe descartar lo que no aporta proteína."""
    async def _correr():
        tools = await _tools(_db(), {"P": 47.5, "H": 72.0, "G": 12.0})
        return await tools.buscar_alimentos(texto="", para_macro="P", limite=8)
    res = asyncio.run(_correr())
    assert res["items"], "sin texto no devuelve nada"
    for i in res["items"]:
        assert i["macros"]["P"] > 0, f"{i['nombre']} no aporta proteína y la pedía"


def test_componer_menu_no_pierde_lo_pedido():
    """`incluir_ids` son obligatorios de verdad: o están en la opción, o no hay opción."""
    LECHUGA, HUEVOS_L, POLLO = 363, 321, 498
    async def _correr():
        tools = await _tools(_db(), {"P": 47.5, "H": 72.0, "G": 12.0})
        return await tools.componer_menu(incluir_ids=[LECHUGA, HUEVOS_L, POLLO], n=2)
    res = asyncio.run(_correr())
    borradores = res.get("borradores") or []
    if not borradores:
        # Puede no salir ninguna que cuadre, y es una respuesta legítima -- pero
        # entonces hay que explicarlo, no devolver una lista vacía y ya.
        assert res.get("sin_resultados_porque"), "no salen menús y no dice por qué"
        return
    for b in borradores:
        ids = {i["id"] for i in b["items"]}
        for pedido in (LECHUGA, HUEVOS_L, POLLO):
            assert pedido in ids, (
                f"la opción no lleva el alimento {pedido} que era obligatorio: "
                f"{[i['nombre'] for i in b['items']]}")
