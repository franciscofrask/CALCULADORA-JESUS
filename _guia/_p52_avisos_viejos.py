# -*- coding: utf-8 -*-
"""Punto 52: los avisos YA GENERADOS que siguen con los textos viejos. SOLO MIRA."""
import asyncio, os, sys
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))

async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    print(f"base: {os.environ['DB_NAME']}\n")
    tot = await db.notifications.count_documents({})
    campos = Counter()
    titulos = Counter()
    sin_leer = Counter()
    async for n in db.notifications.find({}, {"_id": 0}):
        for k in n:
            campos[k] += 1
        t = (n.get("title") or "").strip()
        titulos[t] += 1
        if not n.get("read"):
            sin_leer[t] += 1
    print(f"avisos en la bandeja: {tot}")
    print(f"campos: {sorted(campos)}\n")
    print(f"{'sin leer':>9}  {'total':>6}  titulo")
    for t, c in titulos.most_common(60):
        print(f"{sin_leer.get(t, 0):>9}  {c:>6}  {t}")

asyncio.run(main())
