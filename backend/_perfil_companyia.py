# -*- coding: utf-8 -*-
"""Construye db.company_profiles: qué alimentos van juntos, sacado de db.diets.

    ./venv/Scripts/python.exe _perfil_companyia.py              # reconstruye
    ./venv/Scripts/python.exe _perfil_companyia.py --calibrar   # de dónde sale el corte

Re-ejecutable: borra y rehace. De solo lectura sobre db.diets y db.foods.

El modo --calibrar no toca nada: compara el peor par de comidas REALES con el de comidas
inventadas al azar con los mismos alimentos, y enseña dónde se separan. Es de donde sale
ELEVACION_MINIMA, para no elegir el número a ojo.
"""
import argparse
import asyncio
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient

from company_profile import (COLECCION, MIN_USOS_ALIMENTO, MIN_USOS_CATEGORIA,
                             PerfilCompanyia)
from moment_profile import cat2_de


async def _leer(db):
    """Recorre las dietas y cuenta: usos por alimento, coincidencias por par, y lo mismo
    por categoría fina. Devuelve también las comidas, para calibrar."""
    foods = {int(f["id"]): f async for f in
             db.foods.find({}, {"_id": 0, "id": 1, "nombre": 1, "categorias": 1})}

    usos, pares = Counter(), Counter()
    usos_cat, pares_cat = Counter(), Counter()
    tam = Counter()
    comidas_reales = []

    async for d in db.diets.find({}, {"_id": 0, "comidas": 1}):
        com = d.get("comidas")
        if not isinstance(com, dict):
            continue
        for _, c in com.items():
            if not isinstance(c, dict) or not c.get("alimentos"):
                continue
            # Un uso por alimento y comida: da igual 100 g que 300 g, cuenta que estaba.
            ids = sorted({int(a["alimento_id"]) for a in c["alimentos"]
                          if isinstance(a.get("alimento_id"), (int, float))
                          and int(a["alimento_id"]) in foods})
            if not ids:
                continue
            tam[len(ids)] += 1
            comidas_reales.append(ids)
            for i in ids:
                usos[i] += 1
            for k, a in enumerate(ids):
                for b in ids[k + 1:]:
                    pares[(a, b)] += 1
            cats = sorted({cat2_de(foods[i]) for i in ids})
            for k in cats:
                usos_cat[k] += 1
            for k, a in enumerate(cats):
                for b in cats[k + 1:]:
                    pares_cat[(a, b)] += 1

    return foods, usos, pares, usos_cat, pares_cat, tam, comidas_reales


def _documentos(usos, pares, usos_cat, pares_cat, tam, comidas):
    """Un documento por alimento con quién le acompaña, no uno por par: son 116.000 pares
    con datos y solo 1.161 alimentos."""
    con = {}
    for (a, b), n in pares.items():
        if usos[a] < MIN_USOS_ALIMENTO or usos[b] < MIN_USOS_ALIMENTO:
            continue
        con.setdefault(str(a), {})[str(b)] = n
        con.setdefault(str(b), {})[str(a)] = n

    docs = [{"tipo": "alimento", "clave": k, "n": usos[int(k)], "con": v}
            for k, v in con.items()]

    con_cat = {}
    for (a, b), n in pares_cat.items():
        if usos_cat[a] < MIN_USOS_CATEGORIA or usos_cat[b] < MIN_USOS_CATEGORIA:
            continue
        con_cat.setdefault(a, {})[b] = n
        con_cat.setdefault(b, {})[a] = n
    docs += [{"tipo": "categoria", "clave": k, "n": usos_cat[k], "con": v}
             for k, v in con_cat.items()]

    docs.append({"tipo": "_base", "clave": "_base", "comidas": comidas,
                 "tam": {str(k): v for k, v in tam.items()}})
    return docs


async def construir():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
    foods, usos, pares, usos_cat, pares_cat, tam, comidas = await _leer(db)
    docs = _documentos(usos, pares, usos_cat, pares_cat, tam, len(comidas))

    await db[COLECCION].delete_many({})
    for i in range(0, len(docs), 500):
        await db[COLECCION].insert_many(docs[i:i + 500])
    await db[COLECCION].create_index([("tipo", 1), ("clave", 1)])

    n_al = sum(1 for d in docs if d["tipo"] == "alimento")
    n_cat = sum(1 for d in docs if d["tipo"] == "categoria")
    print(f"{COLECCION}: {len(comidas)} comidas de {len(foods)} alimentos "
          f"-> {n_al} alimentos con compañía, {n_cat} categorías")


async def calibrar():
    """De dónde sale el corte: el peor par de comidas de verdad frente al de comidas
    inventadas al azar. Si el dato sirve, las dos repartos se separan."""
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
    perfil = await PerfilCompanyia.cargar(db)
    if not perfil.comidas:
        print("no hay perfil: construye primero")
        return
    foods = {int(f["id"]): f async for f in
             db.foods.find({}, {"_id": 0, "id": 1, "nombre": 1, "categorias": 1})}

    _, _, _, _, _, _, comidas = await _leer(db)
    rng = random.Random(12)                      # fijo: la calibración tiene que repetirse
    reales = [c for c in comidas if 2 <= len(c) <= 6]
    rng.shuffle(reales)
    muestra = reales[:4000]

    con_datos = [int(k) for k in perfil.alimentos]

    def peor(ids):
        p = perfil.peor_pareja([foods[i] for i in ids if i in foods])
        return p[0] if p else None

    peores_real = [x for x in (peor(c) for c in muestra) if x is not None]
    inventadas = [rng.sample(con_datos, len(c)) for c in muestra]
    peores_azar = [x for x in (peor(c) for c in inventadas) if x is not None]

    def reparto(v):
        v = sorted(v)
        return {p: v[int(len(v) * p / 100)] for p in (5, 10, 25, 50)}

    print(f"comidas de verdad: {len(peores_real)}   inventadas al azar: {len(peores_azar)}")
    print(f"  peor par, comidas REALES:      {reparto(peores_real)}")
    print(f"  peor par, comidas AL AZAR:     {reparto(peores_azar)}")
    print("\n  corte    deja fuera de las reales   deja fuera de las inventadas")
    for corte in (0.2, 0.3, 0.4, 0.45, 0.5, 0.6, 0.7):
        fr = 100 * sum(1 for x in peores_real if x < corte) / len(peores_real)
        fa = 100 * sum(1 for x in peores_azar if x < corte) / len(peores_azar)
        print(f"   {corte:4.2f}        {fr:5.1f} %                     {fa:5.1f} %")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrar", action="store_true")
    args = ap.parse_args()
    asyncio.run(calibrar() if args.calibrar else construir())
