"""La red de VARIAS palabras, barrida sobre el catálogo entero.

Francisco pidió medir también esto, después de que el barrido de una palabra destapara
que «sal» se colaba por «salmón». La sospecha era razonable: la cobertura de varias
palabras usa `w in nombre` -- subcadena en cualquier posición --, que es exactamente el
fallo que hubo que corregir en los regex y en `_en_nucleo`.

**Medido, no lo tiene.** Sobre las 3.211 fichas:

  - las 2.997 de dos o más palabras se reconocen a sí mismas por su propio nombre;
  - de 15 peticiones inventadas de 2-3 palabras, solo dos encuentran algo, y las mismas
    dos con el criterio por palabra;
  - en 12 peticiones reales, cambiar a criterio por palabra solo cambia una («leche
    desnatada», que dejaría fuera las semidesnatadas) y para peor.

El motivo es que exigir que estén TODAS las palabras (o todas menos una si son 3+) ya es
un filtro fuerte por sí solo: que dos palabras coincidan por casualidad como subcadena es
rarísimo. Con una sola palabra no había nada de eso, y por eso allí sí hacía falta.

Así que aquí no se cambió nada. Este test fija la medida, para que si alguien toca la
cobertura se vea sobre el catálogo entero.
"""
import asyncio
import os
import sys
import unicodedata

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_RAIZ, ".env"))

pytestmark = pytest.mark.skipif(not os.environ.get("MONGO_URL"),
                                reason="sin MONGO_URL: test de integración")

_STOP = {"de", "del", "la", "el", "los", "las", "con", "sin", "al", "a",
         "en", "un", "una", "unos", "unas", "y", "o", "u", "por", "para"}

# Peticiones de 2-3 palabras que no existen. Las dos últimas encuentran algo a propósito y
# se anotan aparte: «Solomillo de salmón» y «Focaccia queso, romero y tomillo» llevan de
# verdad las palabras pedidas. Nadie va a pedir eso, pero conviene que quede escrito.
INVENTADAS = [
    "filete de unicornio", "pechuga de dragon", "arroz de canela",
    "crema de chuchurrumia", "pan de pimienta", "yogur de oregano",
    "tortilla de curry", "batido de laurel", "pechuga de romero",
    "leche de azafran", "hamburguesa de comino", "zumo de perejil",
    "tarta de unicornio",
]


def _norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower())
                   if unicodedata.category(c) != "Mn")


def _sig(q):
    return [w for w in _norm(q).split() if w not in _STOP and len(w) > 1]


def _cubre(palabras, nombre):
    """El criterio de cobertura de search_foods, tal cual."""
    n = _norm(nombre)
    necesarias = len(palabras) if len(palabras) == 2 else len(palabras) - 1
    return sum(1 for w in palabras if w in n) >= necesarias


@pytest.fixture(scope="module")
def nombres():
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        fichas = await db.foods.find({}, {"_id": 0, "nombre": 1}).to_list(None)
        return [f["nombre"] for f in fichas]
    return asyncio.run(_correr())


def test_cada_ficha_se_reconoce_por_su_propio_nombre(nombres):
    """El riesgo de rechazar de más: pedir algo que sí está y no encontrarlo."""
    fallan, consultas = [], 0
    for nombre in nombres:
        palabras = _sig(nombre.split("(")[0])
        if len(palabras) < 2:
            continue
        consultas += 1
        if not _cubre(palabras, nombre):
            fallan.append(nombre)
    assert consultas > 2000, f"solo {consultas} fichas de 2+ palabras: ¿catálogo incompleto?"
    assert not fallan, f"{len(fallan)} fichas no se reconocen por su nombre: {fallan[:8]}"


@pytest.mark.parametrize("peticion", INVENTADAS)
def test_lo_que_no_existe_no_encuentra_nada(peticion, nombres):
    """El riesgo de colar de menos: pedir algo que no está y que cuele un parecido."""
    palabras = _sig(peticion)
    cubren = [n for n in nombres if _cubre(palabras, n)]
    assert not cubren, f"«{peticion}» no existe y encuentra {cubren[:3]}"


@pytest.mark.parametrize("peticion,esperado", [
    ("pechuga de pollo", "pechuga de pollo"),
    ("queso batido", "queso fresco batido"),
    ("crema de cacahuete", "crema de cacahuete"),
    ("aceite de oliva", "aceite de oliva"),
    ("claras de huevo", "claras de huevo"),
    ("copos de avena", "copos de avena"),
    ("pan de molde", "pan de molde"),
    ("yogur griego", "yogur griego"),
])
def test_las_peticiones_normales_siguen_encontrando(peticion, esperado, nombres):
    palabras = _sig(peticion)
    cubren = [n.lower() for n in nombres if _cubre(palabras, n)]
    assert cubren, f"«{peticion}» no encuentra nada"
    assert any(esperado in n for n in cubren), f"«{peticion}» -> {cubren[:4]}"
