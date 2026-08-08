# -*- coding: utf-8 -*-
"""Regla del 8 bis del plan: el prompt del agente lleva SOLO comportamiento.

Si aparece el nombre de un alimento del catálogo (o una palabra coloquial de comida) en
el prompt o en las descripciones de las herramientas, es un fallo: ahí es donde nació el
problema del sistema viejo (la tabla de 83 sinónimos DENTRO del prompt del router).
El test cruza el texto contra los nombres reales de db.foods, así no depende de que
nadie se acuerde de la regla.
"""
import asyncio
import os
import re
import sys
import unicodedata

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

MONGO_URL = os.environ.get("MONGO_URL")
pytestmark = pytest.mark.skipif(not MONGO_URL, reason="sin MONGO_URL: necesita el catálogo")

# Palabras que están en nombres de alimentos pero son lenguaje normal, no comida:
# "entera" (leche entera), "blanco" (pan blanco), "fresca"... El test veta PALABRAS DE
# COMIDA, no adjetivos sueltos. Sustantivos de alimento aquí NO pueden entrar.
_LENGUAJE_NORMAL = {
    "entera", "entero", "blanca", "blanco", "fresca", "fresco", "natural", "grande",
    "pequeña", "pequeño", "ligera", "ligero", "light", "mini", "extra", "clasico",
    "clasica", "original", "casera", "casero", "tierna", "tierno", "dulce", "salada",
    "salado", "cocida", "cocido", "cruda", "crudo", "seca", "seco", "verde", "negra",
    "negro", "roja", "rojo", "mixta", "mixto", "doble", "especial", "tradicional",
    "buena", "bueno", "rica", "rico", "sabor", "pack", "lata", "bote", "bolsa",
    "unidades", "gramos", "proteina", "proteinas", "hidratos", "grasa", "grasas",
    "calorias", "energia", "cero", "zero", "plus", "power", "gold", "real", "vital",
    # aparecen en nombres de productos pero son lenguaje, no comida
    "estilo", "libre", "macros", "macro", "unidad", "momento", "comida", "comidas",
    "minuto", "listo", "lista", "punto", "media", "medio", "corte", "trozos",
    "montar", "relleno", "toque", "total",
}


def _norm(s):
    t = (s or "").lower()
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


async def _vocabulario_comida():
    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    vocab = set()
    async for f in db.foods.find({}, {"_id": 0, "nombre": 1}):
        limpio = re.sub(r"[(),/%.\-]", " ", _norm(f.get("nombre", "")))
        for w in limpio.split():
            if len(w) >= 5 and w.isalpha() and w not in _LENGUAJE_NORMAL:
                vocab.add(w)
    return vocab


def _palabras_de(texto):
    return {w for w in re.findall(r"[a-zñ]+", _norm(texto)) if len(w) >= 5}


class TestPromptSinAlimentos:
    def test_prompt_del_agente(self):
        from agent_loop import _PROMPT
        vocab = asyncio.run(_vocabulario_comida())
        coladas = _palabras_de(_PROMPT) & vocab
        assert not coladas, (
            f"El prompt del agente nombra comida: {sorted(coladas)}. "
            "Los alimentos van en las herramientas y los datos, nunca en el prompt (8 bis).")

    def test_descripciones_de_herramientas(self):
        from agent_loop import _ESQUEMAS
        vocab = asyncio.run(_vocabulario_comida())
        texto = " ".join(e["description"] + " " +
                         " ".join(p.get("description", "") for p in
                                  e.get("parameters", {}).get("properties", {}).values())
                         for e in _ESQUEMAS)
        coladas = _palabras_de(texto) & vocab
        assert not coladas, f"Las descripciones de herramientas nombran comida: {sorted(coladas)}"
