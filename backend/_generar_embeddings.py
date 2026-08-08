# -*- coding: utf-8 -*-
"""Genera los vectores del catálogo para la búsqueda semántica (db.food_embeddings).

Re-ejecutable y barato: salta los alimentos cuyo texto no cambió desde la última vez
(mismo texto + mismo modelo = mismo vector, no se vuelve a pedir). El catálogo entero
(~3.200 alimentos) cuesta menos de un céntimo con text-embedding-3-small.

Uso:
    ./venv/Scripts/python.exe _generar_embeddings.py            # genera/actualiza
    ./venv/Scripts/python.exe _generar_embeddings.py --forzar   # regenera todo
"""
import argparse
import asyncio
import os
import sys

import numpy as np
from bson import Binary

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient
from openai import AsyncOpenAI

from food_semantic import COLECCION, EMBED_MODEL, cargar_nombres_categorias, texto_de_alimento

LOTE = 256  # textos por llamada a la API


async def main(forzar: bool):
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mongo[os.environ.get("DB_NAME", "test_database")]
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    nombres_cat = await cargar_nombres_categorias(db)
    foods = await db.foods.find({}, {"_id": 0, "id": 1, "nombre": 1, "categorias": 1, "url": 1}).to_list(10000)
    existentes = {}
    if not forzar:
        async for d in db[COLECCION].find({}, {"_id": 0, "id": 1, "texto": 1, "model": 1}):
            existentes[int(d["id"])] = (d.get("texto"), d.get("model"))

    pendientes = []
    for f in foods:
        texto = texto_de_alimento(f, nombres_cat)
        if existentes.get(int(f["id"])) == (texto, EMBED_MODEL):
            continue
        pendientes.append((int(f["id"]), texto))

    print(f"Alimentos: {len(foods)} | ya al día: {len(foods) - len(pendientes)} | a generar: {len(pendientes)}")

    hechos = 0
    for i in range(0, len(pendientes), LOTE):
        lote = pendientes[i:i + LOTE]
        resp = await client.embeddings.create(model=EMBED_MODEL, input=[t for _, t in lote])
        for (aid, texto), dato in zip(lote, resp.data):
            v = np.array(dato.embedding, dtype=np.float32)
            await db[COLECCION].update_one(
                {"id": aid},
                {"$set": {"id": aid, "texto": texto, "model": EMBED_MODEL,
                          "dim": len(v), "vector": Binary(v.tobytes())}},
                upsert=True,
            )
        hechos += len(lote)
        print(f"  {hechos}/{len(pendientes)}")

    await db[COLECCION].create_index([("id", 1)], unique=True)

    # Huérfanos: alimentos borrados del catálogo cuyo vector sigue aquí.
    ids_foods = {int(f["id"]) for f in foods}
    borrados = 0
    async for d in db[COLECCION].find({}, {"_id": 0, "id": 1}):
        if int(d["id"]) not in ids_foods:
            await db[COLECCION].delete_one({"id": int(d["id"])})
            borrados += 1
    total = await db[COLECCION].count_documents({})
    print(f"HECHO: {total} vectores en db.{COLECCION}" + (f" ({borrados} huérfanos fuera)" if borrados else ""))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true", help="regenera todo aunque no haya cambios")
    args = ap.parse_args()
    asyncio.run(main(args.forzar))
