# -*- coding: utf-8 -*-
"""Punto 208: las 66 favoritas con nombre de otras clientas.

Mide en la base: cuantas favoritas hay, de quien son, cuantas vienen de Calma, cuantas
llevan nombre de persona y a cuanta gente le sale el contador inflado.
"""
import asyncio, os, sys, re, unicodedata
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))


def plano(t):
    t = unicodedata.normalize("NFKD", str(t or ""))
    return "".join(c for c in t if not unicodedata.combining(c)).lower().strip()


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]

    total = await db.diet_favorites.count_documents({})
    print(f"favoritas guardadas en total: {total}")

    # De quien son y de donde vienen
    campos = Counter()
    por_usuario = Counter()
    ambitos = Counter()
    origen = Counter()
    nombres_por_usuario = {}
    async for f in db.diet_favorites.find({}, {"_id": 0}):
        for k in f:
            campos[k] += 1
        u = f.get("user_id")
        por_usuario[u] += 1
        ambitos[f.get("ambito") or "(sin ambito = dia)"] += 1
        marca = "calma" if any(k in f for k in ("calma_id", "calma_migrated", "origen_calma")) else "-"
        origen[marca] += 1
        nombres_por_usuario.setdefault(u, []).append(f.get("nombre") or f.get("name") or "?")

    print(f"campos que trae el documento: {sorted(campos)}")
    print(f"por ambito: {dict(ambitos)}")
    print(f"marca de origen: {dict(origen)}")
    print(f"\ncuentas con favoritas: {len(por_usuario)}")
    print("las que mas tienen:")
    for uid, n in por_usuario.most_common(8):
        u = await db.users.find_one({"id": uid}, {"email": 1, "name": 1})
        print(f"   {n:>4}  {(u or {}).get('email')}  ({(u or {}).get('name')})")

    # Los nombres de la cuenta de Jesus
    jesus = await db.users.find_one({"email": "hola@jesusgallegopt.com"}, {"id": 1})
    if jesus:
        nn = nombres_por_usuario.get(jesus["id"], [])
        print(f"\nla cuenta de Jesus tiene {len(nn)} favoritas. Los nombres:")
        for x in nn:
            print(f"   · {x}")

    # ¿Cuantos nombres parecen de PERSONA? Se cruza con los nombres reales de la base.
    personas = set()
    async for u in db.users.find({}, {"name": 1}):
        for parte in re.split(r"[\s,]+", plano(u.get("name"))):
            if len(parte) >= 4:
                personas.add(parte)
    async for c in db.client_profiles.find({}, {"nombre": 1, "apellidos": 1}):
        for campo in ("nombre", "apellidos"):
            for parte in re.split(r"[\s,]+", plano(c.get(campo))):
                if len(parte) >= 4:
                    personas.add(parte)

    con_nombre = {}
    for uid, nombres in nombres_por_usuario.items():
        marcadas = [n for n in nombres
                    if any(p in personas for p in re.split(r"[\s,\-0-9]+", plano(n)) if len(p) >= 4)]
        if marcadas:
            con_nombre[uid] = marcadas
    print(f"\ncuentas con alguna favorita cuyo nombre coincide con el de una persona de la base: {len(con_nombre)}")
    for uid, marcadas in sorted(con_nombre.items(), key=lambda x: -len(x[1]))[:6]:
        u = await db.users.find_one({"id": uid}, {"email": 1})
        print(f"   {len(marcadas):>4} de {len(nombres_por_usuario[uid]):<4} {(u or {}).get('email')}")
        print(f"        {', '.join(marcadas[:10])}")

    cli.close()

asyncio.run(main())
