# -*- coding: utf-8 -*-
"""Construye el perfil de momento por alimento desde db.diets -> db.moment_profiles.

Re-ejecutable: borra y reescribe la colección entera (es un derivado puro de db.diets,
no hay nada que conservar). Ver la cabecera de moment_profile.py para el porqué del
diseño (mapeo posición->momento por día, bloques únicos fuera).

Uso:
    ./venv/Scripts/python.exe _perfil_momento.py            # construye
    ./venv/Scripts/python.exe _perfil_momento.py --muestra  # además, enseña ejemplos
"""
import argparse
import asyncio
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient

from meal_moment import momento_de_comida, PERI
from moment_profile import COLECCION, MOMENTOS_PERFIL, cat2_de


async def main(muestra: bool):
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mongo[os.environ.get("DB_NAME", "test_database")]

    conteo_alimento = defaultdict(Counter)   # alimento_id -> Counter(momento)
    base = Counter()
    dias_usados = dias_saltados = 0

    async for d in db.diets.find({}, {"_id": 0, "comidas": 1, "num_comidas": 1}):
        com = d.get("comidas")
        if not isinstance(com, dict):
            continue
        try:
            n = int(d.get("num_comidas") or 0)
        except (TypeError, ValueError):
            n = 0
        # Bloque único: el día entero en una comida; no dice nada de momentos.
        if n <= 1:
            dias_saltados += 1
            continue
        dias_usados += 1
        for key, comida in com.items():
            if not isinstance(comida, dict) or not comida.get("alimentos"):
                continue
            momento = momento_de_comida(key, n)
            if momento != PERI and momento not in MOMENTOS_PERFIL:
                continue
            # Un uso por alimento y comida (da igual 100 g que 300 g: cuenta que estaba).
            # El PERI cuenta en el TOTAL del alimento pero no en el reparto base: así un
            # producto que solo se usa en peri (aminoácidos, dextrosa) queda con
            # coherencia ~0 en desayuno/comida/cena y la poda lo aparta sola de las
            # comidas normales. Aprendido de los datos, no de una lista de categorías.
            vistos = set()
            for a in comida["alimentos"]:
                aid = a.get("alimento_id")
                if aid is None or aid in vistos:
                    continue
                vistos.add(aid)
                conteo_alimento[int(aid)][momento] += 1
                if momento != PERI:
                    base[momento] += 1

    # Herencia por categoría fina (los alimentos sin evidencia propia heredan de aquí)
    foods = {int(f["id"]): f async for f in db.foods.find({}, {"_id": 0, "id": 1, "categorias": 1, "nombre": 1})}
    conteo_cat = defaultdict(Counter)
    for aid, cnt in conteo_alimento.items():
        f = foods.get(aid)
        if f:
            conteo_cat[cat2_de(f)].update(cnt)

    ahora = datetime.now(timezone.utc).isoformat()
    docs = [{"tipo": "_base", "clave": "_base", "conteos": dict(base),
             "total": sum(base.values()), "updated_at": ahora}]
    for aid, cnt in conteo_alimento.items():
        docs.append({"tipo": "alimento", "clave": str(aid), "conteos": dict(cnt),
                     "total": sum(cnt.values()), "updated_at": ahora})
    for cat, cnt in conteo_cat.items():
        docs.append({"tipo": "categoria", "clave": cat, "conteos": dict(cnt),
                     "total": sum(cnt.values()), "updated_at": ahora})

    await db[COLECCION].delete_many({})
    await db[COLECCION].insert_many(docs)
    await db[COLECCION].create_index([("tipo", 1), ("clave", 1)], unique=True)

    print(f"Días usados: {dias_usados} | bloque único fuera: {dias_saltados}")
    print(f"Usos contados: {sum(base.values())} | reparto general: "
          + " ".join(f"{m}={100*base[m]//max(sum(base.values()),1)}%" for m in MOMENTOS_PERFIL))
    print(f"HECHO: {len(docs)} perfiles en db.{COLECCION} "
          f"({len(conteo_alimento)} alimentos, {len(conteo_cat)} categorías)")

    if muestra:
        from moment_profile import PerfilMomento
        perfil = await PerfilMomento.cargar(db)
        print("\nMUESTRA (coherencia: >1 típico del momento, <1 atípico, 1.0 sin datos):")
        nombres = ["Copos de avena", "Huevos enteros L", "Arroz blanco", "Merluza congelada",
                   "Callos a la madrileña lata (Litoral)", "Yogur griego"]
        for nom in nombres:
            f = next((x for x in foods.values() if x.get("nombre", "").lower().startswith(nom.lower())), None)
            if not f:
                continue
            fila = "  ".join(f"{m[:4]}={perfil.coherencia(f, m):.2f}" for m in MOMENTOS_PERFIL)
            print(f"  {f['nombre'][:42]:44} {fila}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--muestra", action="store_true")
    asyncio.run(main(ap.parse_args().muestra))
