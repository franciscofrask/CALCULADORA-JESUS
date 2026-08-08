# -*- coding: utf-8 -*-
"""Banco de recuperación de la búsqueda semántica (F0 del plan del chatbot-agente).

Mide si la búsqueda semántica encuentra lo que la tabla de sinónimos escrita a mano
(query_mappings, en chatbot.search_foods) resolvía por decreto. Los 83 pares de esa tabla
sirven de casos de prueba gratis: "tostadas" debería encontrar el pan tostado SIN la tabla.

La tabla se lee del propio código fuente de chatbot.py (con ast): así el banco sigue en
sincronía hasta el día en que la tabla muera, sin copiarla a otro sitio.

Criterio por caso:
  - verdad-terreno: el top-1 de search_foods(término_canónico) — lo que el sistema actual
    da cuando la tabla YA tradujo. (search_foods con _remap habría vuelto a traducir el
    coloquial; por eso se busca el canónico.)
  - ACIERTO si ese alimento aparece en el top-5 semántico del término COLOQUIAL.
  - ACEPTABLE si comparte categoría fina (2 niveles) con alguno del top-3 semántico
    (p.ej. la tabla manda "huevos" a "huevos enteros L" y la semántica da otro huevo).

Uso:
    ./venv/Scripts/python.exe _eval_busqueda_semantica.py            # banco completo
    ./venv/Scripts/python.exe _eval_busqueda_semantica.py --estilo   # además, consultas de estilo (cualitativo)
"""
import argparse
import ast
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient

from chatbot import NutritionChatbot
from food_semantic import BusquedaSemantica, CorrectorErratas


def leer_query_mappings() -> dict:
    """Los 83 pares coloquial->catálogo de la tabla vieja, como casos de prueba.

    La tabla se borró de chatbot.py en F3 (06-08); estos pares quedaron CONGELADOS en un
    json ese mismo día y siguen siendo el banco: lo que la tabla resolvía por decreto,
    la semántica debe resolverlo por significado. Si una rama vieja aún tuviera la tabla
    en chatbot.py, se lee de ahí, que siempre está más viva."""
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chatbot.py")
    try:
        arbol = ast.parse(open(ruta, encoding="utf-8").read())
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Assign):
                for t in nodo.targets:
                    if isinstance(t, ast.Name) and t.id == "query_mappings":
                        return ast.literal_eval(nodo.value)
    except Exception:
        pass
    import json
    congelado = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                             "_internos_proceso", "query_mappings_congelado_0608.json")
    return json.load(open(congelado, encoding="utf-8"))


def cat2(food: dict) -> str:
    """Categoría fina (2 niveles) del alimento: '2.2.1 | YA' -> '2.2'."""
    for tok in str(food.get("categorias") or "").split("|"):
        tok = tok.strip()
        if tok and tok[0].isdigit():
            return ".".join(tok.split(".")[:2])
    return "?"


CONSULTAS_ESTILO = [
    "comida liquida",
    "algo liquido con mucha proteina",
    "batido",
    "algo para llevar al trabajo",
    "algo que se coma con cuchara",
    "algo rapido sin cocinar",
    "algo dulce para desayunar",
    "cena ligera",
    "algo generico sin marca",
    "fruta para despues de entrenar",
]


async def main(estilo: bool):
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mongo[os.environ.get("DB_NAME", "test_database")]
    bs = await BusquedaSemantica.cargar(db)
    corrector = await CorrectorErratas.cargar(db)
    bot = NutritionChatbot("eval_semantica", db)
    foods = {int(f["id"]): f async for f in db.foods.find({}, {"_id": 0})}

    mappings = leer_query_mappings()
    aciertos, aceptables, fallos = [], [], []
    for coloquial, canonico in mappings.items():
        # Verdad-terreno por el camino viejo (la tabla ya tradujo -> se busca el canónico)
        gt = await bot.search_foods(canonico, limit=1, _remap=False)
        if not gt:
            gt = await bot.search_foods(canonico, limit=1)
        if not gt:
            fallos.append((coloquial, canonico, "sin verdad-terreno"))
            continue
        gt_id, gt_cat = int(gt[0]["id"]), cat2(gt[0])

        sem = await bs.buscar(corrector.corregir(coloquial), limite=5)
        sem_ids = [h["id"] for h in sem]
        if gt_id in sem_ids:
            aciertos.append((coloquial, canonico))
        elif any(cat2(foods.get(h, {})) == gt_cat for h in sem_ids[:3]):
            aceptables.append((coloquial, canonico,
                               foods.get(sem_ids[0], {}).get("nombre", "?")))
        else:
            fallos.append((coloquial, canonico,
                           " / ".join(foods.get(h, {}).get("nombre", "?")[:38] for h in sem_ids[:3])))

    n = len(mappings)
    print(f"BANCO DE RECUPERACION ({n} pares de query_mappings)")
    print(f"  ACIERTO   (top-1 viejo en top-5 semantico): {len(aciertos):3}  ({100*len(aciertos)//n}%)")
    print(f"  ACEPTABLE (misma categoria fina en top-3):  {len(aceptables):3}  ({100*len(aceptables)//n}%)")
    print(f"  FALLO:                                      {len(fallos):3}  ({100*len(fallos)//n}%)")
    if aceptables:
        print("\n[ACEPTABLE] coloquial -> tabla vieja | top-1 semantico:")
        for c, k, top in aceptables:
            print(f"  {c:28} -> {k:32} | {top}")
    if fallos:
        print("\n[FALLO] coloquial -> tabla vieja | top-3 semantico:")
        for c, k, top in fallos:
            print(f"  {c:28} -> {k:32} | {top}")

    if estilo:
        print("\n" + "=" * 70)
        print("CONSULTAS DE ESTILO (cualitativo, revisar a ojo):")
        for q in CONSULTAS_ESTILO:
            sem = await bs.buscar(q, limite=5)
            print(f"\n  \"{q}\"")
            for h in sem:
                f = foods.get(h["id"], {})
                marca = "  [marca]" if f.get("url") else ""
                print(f"    {h['score']:.3f}  {f.get('nombre', '?')[:58]}{marca}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--estilo", action="store_true")
    asyncio.run(main(ap.parse_args().estilo))
