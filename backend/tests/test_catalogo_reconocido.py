"""¿Funciona con CUALQUIER alimento, o solo con los que se probaron?

Francisco, 08-08-2026: «¿funciona con pimienta y cualquier alimento que no exista?».
Pregunta justa: el filtro que decide si un alimento ES lo que el cliente ha pedido se
había probado con 45 casos, y el catálogo tiene 3.211 fichas. Así que se barre entero.

Son dos riesgos opuestos y hay que medir los dos:

  - **Rechazar de más**: que alguien pida un alimento que SÍ está y se le diga que no.
    Es el peligroso, porque rompe el uso normal.
  - **Colar de menos**: que alguien pida algo que NO está y se le meta un parecido.
    Es el que motivó todo esto (sal -> frutos secos, pimienta -> chorizo).

El barrido destapó un fallo que los tests de casos concretos no veían: `_en_nucleo`
emparejaba por PREFIJO, heredado de la búsqueda, y así «sal» colaba por «Lomo de SALmón»
y «SALchichas». Para decidir si un alimento es lo pedido hace falta la palabra entera (o
la misma en otro género o número).
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

from chatbot import NutritionChatbot as C  # noqa: E402

# Alimentos y condimentos de una palabra que NO están en el catálogo de Jesús.
# «canela» queda fuera a propósito: existe un «Sirope de canela», que sí es de canela.
NO_ESTAN = [
    "sal", "pimienta", "oregano", "curry", "comino", "azafran", "romero", "tomillo",
    "perejil", "laurel", "jengibre", "cilantro", "eneldo", "ron", "whisky", "ginebra",
    "vodka", "unicornio", "dragon", "chuchurrumia",
]
# Los que la primera palabra de su nombre no es un alimento que nadie vaya a pedir:
# «T-Bone de ternera», «My Fitness Carrot», «Oh my waffle», y el «Té con agua» al que se
# le corta el nombre por el «con».
NI_SE_PIDEN = {"bone", "fitness", "waffle", "con"}


@pytest.fixture(scope="module")
def catalogo():
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        return await db.foods.find({}, {"_id": 0, "nombre": 1, "url": 1}).to_list(None)
    return asyncio.run(_correr())


def _reconoce(termino, nombres):
    return any(C._en_nucleo(termino, n) for n in nombres)


def test_reconoce_casi_todo_el_catalogo_por_su_nombre(catalogo):
    """Se le pide a cada ficha por la primera palabra de su nombre, que es como lo diría
    cualquiera, y tiene que reconocerse."""
    nombres = [f["nombre"] for f in catalogo]
    terminos = {}
    for f in catalogo:
        n = C._norm_text(f["nombre"].split("(")[0])
        palabras = [w for w in n.replace(",", " ").replace("-", " ").split()
                    if len(w) > 2 and w.isalpha()]
        if palabras:
            terminos.setdefault(palabras[0], f["nombre"])

    fallan = [(t, ej) for t, ej in terminos.items()
              if t not in NI_SE_PIDEN and not _reconoce(t, nombres)]
    assert not fallan, (
        f"{len(fallan)} de {len(terminos)} nombres del catálogo no se reconocerían: "
        f"{fallan[:10]}")


def test_ninguna_palabra_de_un_generico_se_pierde(catalogo):
    """Los genéricos son los que se piden por su nombre a diario. Cualquier palabra suya
    de 4+ letras que sea un alimento tiene que reconocerse; los adjetivos y los
    complementos («moreno», «entera», «sopera») no, y eso es lo correcto."""
    nombres = [f["nombre"] for f in catalogo]
    genericos = [f for f in catalogo if not f.get("url")]
    # La PRIMERA palabra de un genérico sí es siempre el alimento.
    fallan = []
    for f in genericos:
        n = C._norm_text(f["nombre"].split("(")[0])
        palabras = [w for w in n.replace(",", " ").replace("-", " ").split() if w.isalpha()]
        if palabras and palabras[0] not in NI_SE_PIDEN and not _reconoce(palabras[0], nombres):
            fallan.append((palabras[0], f["nombre"]))
    assert not fallan, f"genéricos que no se reconocerían por su nombre: {fallan[:10]}"


@pytest.mark.parametrize("termino", NO_ESTAN)
def test_lo_que_no_esta_no_se_confunde_con_otra_cosa(termino, catalogo):
    nombres = [f["nombre"] for f in catalogo]
    if _reconoce(termino, nombres):
        cuales = [n for n in nombres if C._en_nucleo(termino, n)][:3]
        pytest.fail(f"«{termino}» no está en el catálogo y se confunde con {cuales}")
