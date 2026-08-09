"""«3 claras» no son 300 g.

Salió en la auditoría del asistente con agentes de navegador (08-08-2026). Pedir tres
claras metía **300 g** en la comida: en un desayuno de 47 g de proteína, el triple de lo
que toca, y el descuadre se arrastra al resto del día.

Eran dos fallos encadenados:

1. `set_food_quantity` convertía unidades a gramos multiplicando por `racion`, que es la
   cantidad de referencia con la que están escritos los macros de la ficha -- 100 g para
   casi todo --, no el peso de una unidad. Con los huevos no se notaba porque ahí `racion`
   (63) sí es lo que pesa uno. Y las claras, además, tienen `unidades=False`: en el método
   NO se miden por piezas, se miden en gramos (comprobado en las dietas reales: las
   cantidades son 200, 150, 100, 250... múltiplos de 50, no de 33).

2. Al rechazar la conversión, saltaba un respaldo de `editar_comida` pensado para cuando
   NO SE ENCUENTRA el alimento, que llamaba a `add_food_by_id` sin cantidad y dejaba que el
   motor dimensionase. Volvían los 300 g por la puerta de atrás, y «2 huevos» se quedaba
   en 1 ud.
"""
import asyncio
import os
import sys

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_RAIZ, ".env"))

pytestmark = pytest.mark.skipif(not os.environ.get("MONGO_URL"),
                                reason="sin MONGO_URL: test de integración")

MACROS = {"p_entreno": 160, "h_entreno": 120, "g_entreno": 40,
          "p_peri": 35, "h_peri": 15,
          "p_descanso": 140, "h_descanso": 40, "g_descanso": 40}


def _poner(nombre, cantidad, unidad):
    """Lo que acaba en la comida al pedir esa cantidad."""
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        bot = NutritionChatbot(f"uni_{nombre}_{cantidad}{unidad}", db)
        bot.set_user_macros(MACROS)
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
        r = await bot.add_foods([{"nombre": nombre, "cantidad": cantidad,
                                  "unidad": unidad, "sumar": False}])
        puestos = [(a["nombre"], a["cantidad_display"]) for a in r.get("foods_added", [])]
        avisos = [f.get("razon", "") for f in r.get("foods_not_found", [])]
        return puestos, avisos
    return asyncio.run(_correr())


def test_las_claras_no_se_multiplican_por_cien():
    """Van por gramos: pedirlas en piezas se avisa, no se inventa."""
    puestos, avisos = _poner("claras de huevo pasteurizadas", 3, "ud")
    assert not puestos, f"ha metido {puestos} al pedir 3 unidades de algo que va por gramos"
    assert avisos and "gramos" in avisos[0].lower(), avisos


def test_en_gramos_entran_tal_cual():
    puestos, _ = _poner("claras de huevo pasteurizadas", 200, "g")
    assert puestos and puestos[0][1] == "200g", puestos


@pytest.mark.parametrize("nombre,cantidad,esperado", [
    ("huevos enteros L", 2, "2 ud"),
    ("plátano pequeño", 1, "1 ud"),
])
def test_lo_que_si_va_por_unidades_sigue_bien(nombre, cantidad, esperado):
    """El arreglo no puede romper lo que ya funcionaba: cuando la ficha dice que el
    alimento va por piezas, se respeta el número que ha pedido el cliente."""
    puestos, avisos = _poner(nombre, cantidad, "ud")
    assert puestos, f"«{cantidad} ud de {nombre}» no entra: {avisos}"
    assert puestos[0][1] == esperado, puestos


# -------------------------------------------------------------- con el agente real
@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="necesita OPENAI_API_KEY")
@pytest.mark.parametrize("mensaje,nombre,maximo", [
    ("ponme 3 claras de huevo", "claras", 150),      # 3 x 33 g, nunca 300
    ("ponme 2 huevos enteros L", "huevos", None),
])
def test_de_punta_a_punta(mensaje, nombre, maximo):
    """El respaldo semántico de `editar_comida` devolvía los 300 g por otro camino, así
    que el caso hay que verlo entero, no solo en la función que convierte."""
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        from agent_loop import AgentLoop
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        bot = NutritionChatbot(f"e2e_{mensaje[:12]}", db)
        bot.set_user_macros(MACROS)
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
        loop = await AgentLoop.crear(bot)
        await loop.procesar(mensaje)
        return (bot.state["comidas_completadas"].get("C1") or {}).get("alimentos", [])
    puestos = asyncio.run(_correr())
    assert puestos, f"«{mensaje}» no pone nada"
    coincide = [a for a in puestos if nombre in a["nombre"].lower()]
    assert coincide, f"«{mensaje}» -> {[a['nombre'] for a in puestos]}"
    if maximo is not None:
        gramos = coincide[0].get("cantidad_g", 0)
        assert gramos <= maximo, f"«{mensaje}» mete {gramos} g (el tope razonable es {maximo})"
