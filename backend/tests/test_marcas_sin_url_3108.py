# -*- coding: utf-8 -*-
"""NINGUNA MARCA SE CUELA EN EL FILTRO «GENERICO» (Francisco, 31-08-2026).

El chip «Generico» decide con `calculator.es_generico`, que mira la URL de la ficha: sin URL
= generico. La regla es buena --contrastada con la marca entre parentesis del nombre, las dos
senales coinciden en 3.146 de 3.211-- pero NO se sostiene sola, y esto lo cazo Francisco:

    «pero hay marcas que no tienen url»

Tenia razon. Habia seis fichas de marca a las que nadie les habia rellenado la URL
(Nutrisport x2, 7 Hermanos, Sol Natural, Esgir y un Hacendado), y con la regla de la URL se
colaban en «Generico». Se marcaron a mano con `es_marca: true`.

Esta prueba es lo que impide que vuelva a pasar sin que nadie se entere. Busca alimentos con
algo entre parentesis al final del nombre, sin URL y sin `es_marca`, y solo tolera los que
sabemos que son genericos con una aclaracion --«(corte magro)», «(mas del 85 %)», «(sin
cascara)»--. El dia que alguien de de alta «Yogur proteico (Milbona)» sin URL, salta aqui.

Si salta: mirar el nombre. Si el parentesis es una MARCA, ponerle `es_marca: true` a esa
ficha (o la URL de verdad). Si es una ACLARACION, anadir su id a ACLARACIONES.

NUNCA se inventa una URL para callar esto: una URL falsa acaba siendo un enlace que se le
ensena a un cliente.
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

MONGO_URL = os.environ.get("MONGO_URL")
pytestmark = pytest.mark.skipif(not MONGO_URL, reason="sin MONGO_URL: test de integracion")

PARENTESIS_FINAL = re.compile(r"\([^()]+\)\s*$")

# Genericos cuyo parentesis es una aclaracion, no una marca. Revisados uno a uno el 31-08.
ACLARACIONES = {
    123,    # Filete de ternera (corte magro)
    1652,   # Fiambre de pechuga de pavo de buena calidad (mas del 85 %)
    1653,   # Jamon cocido de buena calidad (mas del 85 %)
    1730,   # Chuleton de ternera - lomo alto (corte graso)
    1731,   # Chuleton de ternera - lomo alto (corte magro)
    1732,   # T-Bone de ternera (corte graso)
    1733,   # T-Bone de ternera (corte magro)
    2519,   # Fiambre de pechuga de pavo de baja calidad (menos del 85 %)
    2520,   # Jamon cocido de baja calidad (menos del 85 %)
    2528,   # Pipas de girasol (con cascara)
    2529,   # Pipas de girasol (sin cascara)
    2968,   # Fiambre de pechuga de pollo de buena calidad (mas del 85 %)
}


def _sospechosos(db):
    import asyncio

    async def _mirar():
        fuera = []
        cursor = db.foods.find(
            {"$or": [{"url": {"$in": [None, ""]}}, {"url": {"$exists": False}}]},
            {"_id": 0, "id": 1, "nombre": 1, "es_marca": 1},
        )
        async for f in cursor:
            nombre = f.get("nombre") or ""
            if f.get("es_marca") is True:
                continue
            # Los alimentos que dejan sembrados otras baterias no son catalogo: en la base
            # local hay ocho «Alimento de prueba caso 37 (con categoria)» y no dicen nada
            # sobre marcas ni sobre genericos.
            if "alimento de prueba" in nombre.lower():
                continue
            if not PARENTESIS_FINAL.search(nombre):
                continue
            if f.get("id") in ACLARACIONES:
                continue
            fuera.append((f.get("id"), nombre))
        return fuera

    return asyncio.run(_mirar())


def test_ninguna_marca_sin_url_se_cuela_en_genericos():
    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    fuera = _sospechosos(db)
    assert not fuera, (
        "Hay alimentos con algo entre parentesis al final, sin URL y sin `es_marca`. "
        "Si el parentesis es una marca, ponles `es_marca: true`; si es una aclaracion, "
        "anade su id a ACLARACIONES de este fichero:\n  "
        + "\n  ".join(f"{i}  {n}" for i, n in fuera))


def test_es_generico_respeta_la_marca_puesta_a_mano():
    """La regla es la URL, pero `es_marca` manda sobre ella: es lo que tapa el hueco."""
    from calculator import es_generico
    assert es_generico({"nombre": "Pechuga de pollo"}) is True
    assert es_generico({"nombre": "Aquarius", "url": "https://x"}) is False
    assert es_generico({"nombre": "Barrita (Nutrisport)", "es_marca": True}) is False
    # Una url vacia o solo espacios no convierte a nadie en marca.
    assert es_generico({"nombre": "Arroz blanco", "url": "   "}) is True
