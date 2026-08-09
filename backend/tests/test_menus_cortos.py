"""Un menú al que le faltan 73 g no es una comida a la que le falta un remate.

De la auditoría del asistente (08-08-2026): la puerta de calidad de `componer_menu` solo
miraba el EXCESO. El déficit pasaba entero, con el argumento de que era «trabajo pendiente»
que el agente remataría o que el revisor señalaría.

Medido sobre 38 borradores de diez estilos distintos y dos comidas: **el 37 % salía con más
de 30 g sin cubrir**, y el peor con 73 -- le faltaban 40 g de proteína y 33 de hidratos.
Eso no lo remata nadie: se le enseña al cliente y lo acepta creyendo que cuadra.

Ahora el déficit se corta con el mismo listón que el exceso. La diferencia entre los dos
sigue estando: un menú corto se puede completar y uno pasado no, así que si al final no
queda NINGUNA opción, la menos corta se rescata con su aviso en vez de dejar al cliente sin
nada. Tras el cambio: 11 % por encima de 30 g, ninguna escena sin opciones, y todas las que
se quedan cortas llevan aviso.
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

ESTILOS = ["", "pollo", "algo con avena", "tostadas", "ensalada",
           "pescado", "algo dulce", "batido", "algo rapido", "huevos"]


@pytest.fixture(scope="module")
def borradores():
    """Todos los menús de diez estilos y dos comidas, en una sola pasada: cada
    `asyncio.run` contra Atlas cuesta, y repetirlo por test hacía el fichero eterno."""
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        from agent_tools import AgentTools
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        salida = []
        for estilo in ESTILOS:
            for comida in (1, 4):
                bot = NutritionChatbot(f"cortos_{estilo}_{comida}", db)
                bot.set_user_macros(MACROS)
                bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
                if comida > 1:
                    idx = [i + 1 for i, k in enumerate(bot.state["meal_order"]) if k == f"C{comida}"]
                    if idx:
                        bot.go_to_meal(idx[0])
                tools = await AgentTools.crear(bot)
                r = await tools.componer_menu(estilo=estilo, n=2)
                salida.append((estilo or "(sin estilo)", comida, r.get("borradores") or []))
        return salida
    return asyncio.run(_correr())


def _deficit(b):
    return sum(-v for v in b["desvio"].values() if v < 0)


def test_casi_ninguno_se_queda_muy_corto(borradores):
    todos = [b for _, _, bs in borradores for b in bs]
    assert todos, "no se ha generado ningún menú"
    malos = [b for b in todos if _deficit(b) > 30]
    proporcion = len(malos) / len(todos)
    assert proporcion <= 0.20, (
        f"{len(malos)} de {len(todos)} menús ({100*proporcion:.0f} %) se quedan a más de "
        f"30 g; antes del arreglo era el 37 %")


def test_el_que_se_queda_corto_lo_dice(borradores):
    """Rescatar sin avisar sería volver al principio: el cliente lo daría por bueno."""
    mudos = [(e, c, b["desvio"]) for e, c, bs in borradores for b in bs
             if _deficit(b) > 24 and not b.get("avisos")]
    assert not mudos, f"menús cortos que no avisan: {mudos[:3]}"


def test_nadie_se_queda_sin_opciones(borradores):
    """El corte no puede dejar al cliente con la pantalla vacía."""
    vacias = [(e, c) for e, c, bs in borradores if not bs]
    assert not vacias, f"escenas sin ninguna opción que ofrecer: {vacias}"


def test_el_exceso_sigue_bloqueado(borradores):
    """Lo que ya funcionaba: un menú que se pasa de largo no sale."""
    pasados = [(e, c, b["desvio"]) for e, c, bs in borradores for b in bs
               if sum(max(v, 0) for v in b["desvio"].values()) > 30]
    assert not pasados, f"menús que se pasan y salen igual: {pasados[:3]}"
