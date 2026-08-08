"""Buscar «col» no puede devolver chocolate.

Francisco, 08-08-2026, sobre el asistente: la búsqueda emparejaba por TROZOS de palabra.
Los regex iban contra `nombre` sin exigir que la coincidencia empezara una palabra:

    col  -> Barrita proteica doble CHOCOLATE       (cho-COL-ate)
    te   -> ACEITE de oliva virgen extra           (acei-TE)
    ajo  -> Atún al natural BAJO en sal            (b-AJO)
    pan  -> Filete de pechuga de pollo emPANado
    ron  -> MacaRRONes integrales

Medido sobre las 3.211 fichas: de los 1.048 candidatos de «te», 962 eran ruido; de los
353 de «col», 278. Y como cada consulta a Mongo se corta en 50 EN ORDEN NATURAL, el ruido
no solo ensuciaba la lista: podía dejar fuera lo que se buscaba.

El `\\b` que ya había en `_regex_raiz` no servía de nada por dos motivos: `\\b` no ve una
frontera en mitad de «chocolate», y el regex de Mongo NO normaliza acentos, así que
`\\bcafe\\b` no encontraba «Café». Ahora `_regex_termino` exige que delante no haya letra
ni número y tolera los acentos del catálogo.

No se exige final de palabra a propósito: «tostad» tiene que seguir llegando a «tostadas».
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


def _buscar(termino, limite=8):
    """Cliente dentro del asyncio.run: Motor se ata al bucle en el que nace."""
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        bot = NutritionChatbot("test_busqueda", db)
        bot.set_user_macros(MACROS)
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
        return [f.get("nombre", "") for f in await bot.search_foods(termino, limit=limite)]
    return asyncio.run(_correr())


# ------------------------------------------------------- el fallo, tal cual salió
@pytest.mark.parametrize("termino,intruso", [
    ("col", "chocolate"),
    ("te", "aceite"),
    ("ajo", "bajo en"),
    ("pan", "empanado"),
    ("ron", "macarrones"),
])
def test_no_empareja_en_mitad_de_otra_palabra(termino, intruso):
    nombres = [n.lower() for n in _buscar(termino)]
    colados = [n for n in nombres if intruso in n]
    assert not colados, f"pedí «{termino}» y me cuela {colados}"


# --------------------------------------------------------- y sigue encontrando
@pytest.mark.parametrize("termino,esperado", [
    ("cafe", "café"),        # sin tilde tiene que llegar al catálogo con tilde
    ("café", "café"),
    ("col", "col"),          # coliflor, coles, col lombarda: todas valen
    ("pan", "pan"),
    ("arroz", "arroz"),
    ("avena", "avena"),
    ("tostadas", "tostad"),  # variante de género y número
    ("queso batido", "queso fresco batido"),
    ("pechuga de pollo", "pechuga de pollo"),
])
def test_sigue_encontrando_lo_que_encontraba(termino, esperado):
    nombres = [n.lower() for n in _buscar(termino)]
    assert nombres, f"«{termino}» no devuelve nada"
    assert any(esperado in n for n in nombres), f"«{termino}» -> {nombres[:4]}"


def test_lo_pedido_va_primero():
    """Cuando existe la ficha con ese nombre, encabeza la lista."""
    for termino, empieza in [("cafe", "café"), ("arroz", "arroz"), ("miel", "miel"),
                             ("uva", "uva"), ("avena", "avena")]:
        primero = _buscar(termino, limite=3)[0].lower()
        assert primero.startswith(empieza), f"«{termino}» devuelve «{primero}» el primero"


# ------------------------------------------ y avisa cuando NO tiene lo que le piden
def _parcial(termino):
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        bot = NutritionChatbot("test_busqueda_parcial", db)
        bot.set_user_macros(MACROS)
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
        r = await bot.search_foods(termino, limit=4)
        return bool(r) and bool(r[0].get("_match_parcial"))
    return asyncio.run(_correr())


@pytest.mark.parametrize("termino", ["sal", "ron"])
def test_marca_parcial_lo_que_no_tiene(termino):
    """La sal y el ron no están en el catálogo de Jesús. Hasta el 08-08 quien pedía sal se
    llevaba «Frutos secos cocktail tostado sin sal» METIDO en la comida, sin preguntar y
    sin avisar: la red de `_match_parcial` solo se tendía con dos palabras o más, y por ahí
    se colaba todo lo de una."""
    assert _parcial(termino), f"«{termino}» no está en el catálogo y no lo dice"


@pytest.mark.parametrize("termino", ["arroz", "pan", "col", "miel", "huevos", "atun",
                                     "yogur", "platano", "nueces", "leche", "cafe",
                                     "avena", "pavo",
                                     # «Pechuga DE pollo» va de pollo; «Pipas CON sal» no
                                     # va de sal. Por eso el nexo cuenta y la posición sola
                                     # no basta.
                                     "pollo"])
def test_lo_que_existe_no_se_marca(termino):
    assert not _parcial(termino), f"«{termino}» sí está en el catálogo y lo da por dudoso"


def test_avisa_si_no_existe_lo_pedido():
    """La sal y el té solos no están en el catálogo de Jesús. Devolver «pistachos
    tostados con sal» sin decir nada es lo que hacía que pareciera que sí."""
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        from agent_tools import AgentTools
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        bot = NutritionChatbot("test_busqueda_ojo", db)
        bot.set_user_macros(MACROS)
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
        tools = await AgentTools.crear(bot)
        return (await tools.buscar_alimentos(texto="sal", limite=6),
                await tools.buscar_alimentos(texto="arroz", limite=6))
    sal, arroz = asyncio.run(_correr())
    if sal["items"]:
        assert sal.get("ojo"), "devuelve sucedáneos de la sal y no dice que no la tiene"
    assert not arroz.get("ojo"), "el arroz SÍ existe: no hay nada que avisar"
