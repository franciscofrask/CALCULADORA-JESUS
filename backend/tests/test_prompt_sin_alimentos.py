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
    # "De Nuestra Tierra" es una marca (alcachofas, anchoas, pimientos del piquillo), asi
    # que "nuestra" entraba en el vocabulario de comida y el test saltaba porque el prompt
    # del agente dice "nuestra". Es un pronombre, no un alimento.
    "nuestra", "nuestro", "nuestras", "nuestros", "tierra",
    # "origen" es una clave de datos del borrador (origen='recetario'), no un alimento.
    # Entraba en el vocabulario por productos con "denominacion de origen" en el nombre.
    "origen",
    # "alimento" es la palabra con la que la app habla de esto: está en el prompt y en
    # media docena de descripciones de herramientas, y tiene que estar. Entró en el
    # vocabulario por dos nombres del catálogo -- "Hamburguesa Angus (Confialiments)", una
    # marca, y un "Alimento de prueba caso 37" que se coló de un test interrumpido -- y
    # tumbó los dos tests a la vez. Un producto que lleve la palabra genérica en el nombre
    # no puede prohibir la palabra genérica.
    "alimento", "alimentos",
    # "categoria" es como la app organiza el catalogo y el prompt habla de ellas con
    # todo el derecho; entro al vocabulario por productos con la palabra en el nombre
    # ("huevos frescos categoria A"). Igual que "alimento": la palabra generica de la
    # casa no puede quedar vetada por un producto que la lleve.
    "categoria", "categorias",
    # "receta" es palabra de la casa, como "alimento": el recetario de Jesús, el parámetro
    # `receta` de componer_menu y la regla «si llama a una receta por su nombre». Entró al
    # vocabulario por productos tipo "Tomate frito receta artesana (Hacendado)": un producto
    # que lleva la palabra genérica en el nombre no puede vetarla.
    "receta",
    # Familias de la CALIBRACIÓN PROGRESIVA: "cereales y panes" y "frutos secos" son
    # concepto del método (tramos por gramos acumulados), no un alimento suelto, y el
    # agente tiene que poder nombrarlas para explicar la regla. Colisionan con productos
    # como "Cereales Crunchy Choc (Hacendado)" o "Frutos secos cocktail tostado sin sal".
    "cereales", "frutos", "secos",
    # "cortes" en el prompt son los cortes (tramos) de la calibración progresiva; colisiona
    # con "Pan de barra 5 cortes (Europastry)", donde es un formato, no un alimento.
    "cortes",
    # "cucharadita" es una medida: entra por las coletillas del catálogo ("Aceite de coco
    # una cucharadita de café") y el prompt la cita justo para enseñar que la coletilla
    # NO es el alimento («...una cucharadita de café» no es un café).
    "cucharadita",
    # "enteros" (el singular "entero" ya estaba): en el prompt es "cuentan enteros" (al
    # 100 % del tramo); colisiona con "Huevos enteros L" y los "Pimientos del piquillo
    # enteros". Adjetivo, no comida.
    "enteros",
    # "ingles" es el idioma («aunque el cliente escriba en inglés»); entra al vocabulario
    # por la marca "El Corte Inglés". Una marca no puede vetar el nombre de un idioma.
    "ingles",
    # "memoria" viene de "Brain Latte Memoria (Baña Food)"; en el prompt es «no la
    # reconstruyas de memoria». Lenguaje corriente, no comida.
    "memoria",
    # "menos" es un adverbio («menos [alimento]», «jamás menos»); entra por nombres tipo
    # "Fiambre de pechuga de pavo de baja calidad (menos del 85 %)".
    "menos",
    # "pasas" en el prompt es el verbo pasarse («te pasas 9 g», la regla de cómo decir el
    # desvío); colisiona con "Uvas pasas". Si algún día el prompt hablara de las uvas
    # pasas de verdad, esto lo taparía: se asume, el verbo es irrenunciable.
    "pasas",
    # "sabores" son las coletillas de los nombres del catálogo («medidas, sabores»),
    # de "Sabores de langosta (La Sirena)". Lenguaje, no un alimento.
    "sabores",
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
