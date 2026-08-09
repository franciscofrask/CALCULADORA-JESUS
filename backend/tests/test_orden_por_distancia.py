"""Puntos 76 y 78 del documento de Jesús (07-08-2026), los dos con el mismo arreglo.

**76.** *«Con 9,3 g de proteína pendientes y solo 6,2 g de grasa, el asistente propone
callos a la madrileña: 53 g de proteína y 60,8 g de grasa. Mira el macro que falta y no
mira lo que desajusta al meterlo.»* Reproducido con ese hueco exacto: salían en el puesto 6
un aislado de 89,9 g de proteína (distancia 86,8) y una tortita de maíz de 125 g de grasa
(distancia 133,6).

La fórmula que pedía -- Σ|ΔP| + |ΔH| + |ΔG| -- ya existía en el motor (`diferencia_de_macros`,
la `Ze()` de Calma) y la calculadora ya ordenaba por ella. El asistente no: ordenaba por lo
que más aportaba del macro que faltaba.

**78.** *«Tira de polvos antes que de comida real.»* Con el hueco de arriba salían **10 de
10** suplementos. No hizo falta penalizarlos: un aislado da 9 g de proteína y 0 de grasa
(distancia 6,5), unas brochetas de pollo dan 9,2 P **y** 6,2 G a la vez (distancia 0,1). La
comida real gana sola porque cubre los dos macros de un golpe.

Detalle que costó verlo: ordenar por distancia no bastaba, porque antes se acotaba el
universo por «lo que más aporta por 100 g» y ahí los primeros son siempre los concentrados
-- las brochetas ni llegaban a competir. Hay que mirar el catálogo entero; medido, cuesta
0,53 s dimensionar las 3.211 fichas y la búsqueda entera tarda ~355 ms.
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

# El hueco del ejemplo de Jesús.
HUECO = {"P": 9.3, "H": 0.0, "G": 6.2}
# Polvos y suplementos: las mismas categorías que ya usa el repo para el peri.
CATS_POLVO = ("4", "14", "18", "27", "28", "29", "30", "41")


def _buscar(para_macro, hueco=None, meal=None, limite=10, texto=""):
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        from agent_tools import AgentTools
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        bot = NutritionChatbot(f"dist_{para_macro}_{meal}_{texto}", db)
        bot.set_user_macros(MACROS)
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
        if meal:
            idx = [i + 1 for i, k in enumerate(bot.state["meal_order"]) if k == meal]
            if idx:
                bot.go_to_meal(idx[0])
        if hueco:
            bot.get_remaining_macros = lambda: dict(hueco)
        tools = await AgentTools.crear(bot)
        r = await tools.buscar_alimentos(texto=texto, para_macro=para_macro, limite=limite)
        return r["items"], tools
    return asyncio.run(_correr())


def _distancia(item, hueco):
    from calma_suggest import diferencia_de_macros
    m = item["macros"]
    return diferencia_de_macros(
        {"proteinas": m["P"], "hidratos": m["H"], "grasas": m["G"]},
        {"proteinas": hueco["P"], "hidratos": hueco["H"], "grasas": hueco["G"]})


@pytest.mark.parametrize("para_macro", ["P", "G"])
def test_no_ofrece_lo_que_desajusta_la_comida(para_macro):
    """Nada de lo que se enseña puede desviar la comida más que el propio hueco."""
    items, _ = _buscar(para_macro, hueco=HUECO)
    assert items, "no devuelve nada"
    peor = max(_distancia(i, HUECO) for i in items)
    assert peor <= 15, (
        f"pidiendo {para_macro} con {HUECO}, el peor de los {len(items)} desvía {peor:.0f} g "
        f"(antes del arreglo: 86,8 pidiendo proteína y 133,6 pidiendo grasa)")


@pytest.mark.parametrize("para_macro", ["P", "G"])
def test_la_comida_real_va_por_delante_de_los_polvos(para_macro):
    """Punto 78, sin penalizar nada: sale solo al ordenar por distancia."""
    from calculator import get_categorias, cat_in_list
    items, tools = _buscar(para_macro, hueco=HUECO)
    polvos = [i for i in items
              if i["id"] in tools.foods
              and any(cat_in_list(c, list(CATS_POLVO)) for c in get_categorias(tools.foods[i["id"]]))]
    assert len(polvos) <= len(items) // 3, (
        f"{len(polvos)} de {len(items)} son suplementos (antes eran 10 de 10): "
        f"{[i['nombre'] for i in polvos[:4]]}")


@pytest.mark.parametrize("meal,espera", [("Intra", True), ("Post", True)])
def test_en_el_peri_los_suplementos_siguen_saliendo(meal, espera):
    """«Salvo en el perientreno», dice el punto 78. Ahí la dextrosa y los aminoácidos son
    lo que toca, y su universo de categorías ya lo acota."""
    items, _ = _buscar("H", meal=meal, limite=6)
    assert items, f"el {meal} se queda sin opciones"


@pytest.mark.parametrize("texto,esperado", [
    ("pollo", "pollo"), ("lechuga", "lechuga"), ("avena", "avena"),
])
def test_con_texto_sigue_mandando_lo_que_pide_el_cliente(texto, esperado):
    """El orden por distancia es SOLO para cuando no hay texto. Si el cliente nombra un
    alimento, eso manda -- que es lo que se arregló el 08-08 y no puede romperse."""
    items, _ = _buscar("P", texto=texto, limite=4)
    assert items, f"«{texto}» no devuelve nada"
    assert esperado in items[0]["nombre"].lower(), f"«{texto}» -> {[i['nombre'] for i in items[:3]]}"


def test_sigue_habiendo_variedad():
    """Ordenar por distancia a secas haría ganar siempre al mismo. Se agrupa en escalones
    de 3 g y dentro se baraja, con la semilla por cliente-día-comida."""
    vistas = set()
    for s in ("A", "B", "C", "D"):
        async def _correr(sesion=s):
            from motor.motor_asyncio import AsyncIOMotorClient
            from chatbot import NutritionChatbot
            from agent_tools import AgentTools
            db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
            bot = NutritionChatbot(f"var_dist_{sesion}", db)
            bot.set_user_macros(MACROS)
            bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
            bot.get_remaining_macros = lambda: dict(HUECO)
            tools = await AgentTools.crear(bot)
            r = await tools.buscar_alimentos(para_macro="P", limite=6)
            return tuple(i["nombre"] for i in r["items"])
        vistas.add(asyncio.run(_correr()))
    assert len(vistas) >= 2, f"4 clientes y solo {len(vistas)} lista(s) distinta(s)"
