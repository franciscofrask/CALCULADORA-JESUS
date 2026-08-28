# -*- coding: utf-8 -*-
"""Punto 210: por que «Repetir un dia» ofrece dias de 2027.

Mira, en la base de dev, cuantos dias guardados tienen fecha por delante de hoy y
como serian los 5 primeros que devuelve /diets/recent (sort fecha desc, limit 14).
"""
import asyncio, os, sys
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))
HOY = "2026-08-28"


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]

    total = await db.diets.count_documents({})
    futuros = await db.diets.count_documents({"fecha": {"$gt": HOY}})
    print(f"dias guardados: {total}   con fecha posterior a {HOY}: {futuros}")

    anios = Counter()
    async for d in db.diets.find({"fecha": {"$gt": HOY}}, {"fecha": 1, "user_id": 1}):
        anios[(d.get("fecha") or "????")[:4]] += 1
    print("  por anio:", dict(sorted(anios.items())))

    # Los usuarios con mas dias futuros
    porusu = Counter()
    async for d in db.diets.find({"fecha": {"$gt": HOY}}, {"user_id": 1}):
        porusu[d.get("user_id")] += 1
    for uid, n in porusu.most_common(5):
        u = await db.users.find_one({"id": uid}, {"email": 1, "name": 1})
        print(f"  {n:>4} dias futuros  {uid}  {(u or {}).get('email')}")

    # Para el que mas tiene: los 5 primeros de /diets/recent tal cual (sort fecha desc)
    if porusu:
        uid = porusu.most_common(1)[0][0]
        print(f"\nLo que devolveria /diets/recent para {uid}:")
        cur = db.diets.find({"user_id": uid}, {"fecha": 1, "tipo_dia": 1, "comidas": 1}).sort("fecha", -1).limit(5)
        async for d in cur:
            comidas = d.get("comidas") or {}
            conali = {k: v for k, v in comidas.items() if (v or {}).get("alimentos")}
            P = H = G = 0.0
            for v in conali.values():
                for a in v.get("alimentos") or []:
                    me = a.get("macros_efectivos") or {}
                    P += float(me.get("P") or 0); H += float(me.get("H") or 0); G += float(me.get("G") or 0)
            claves = list(conali)[:2]
            muestra = ""
            if claves:
                a0 = (conali[claves[0]].get("alimentos") or [{}])[0]
                muestra = f"  1er alimento: {a0.get('nombre')!r} macros_efectivos={a0.get('macros_efectivos')} cantidad={a0.get('cantidad')}"
            print(f"  {d['fecha']}  {d.get('tipo_dia')}  {len(conali)} comidas  {P:.0f}P {H:.0f}H {G:.0f}G")
            if muestra:
                print(muestra)

    cli.close()

asyncio.run(main())
