# -*- coding: utf-8 -*-
"""Punto 210/211: que son esos dias de 2027 y por que suman 0 macros."""
import asyncio, os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))
UID = "577f920f-5b3c-45bc-a911-120ccc22756e"
HOY = "2026-08-28"


def resumen(d):
    comidas = d.get("comidas") or {}
    conali = {k: v for k, v in comidas.items() if (v or {}).get("alimentos")}
    P = H = G = 0.0
    sin_me = 0
    n_ali = 0
    for v in conali.values():
        for a in v.get("alimentos") or []:
            n_ali += 1
            me = a.get("macros_efectivos")
            if not me:
                sin_me += 1
            else:
                P += float(me.get("P") or 0); H += float(me.get("H") or 0); G += float(me.get("G") or 0)
    return len(conali), n_ali, sin_me, P, H, G


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]

    d = await db.diets.find_one({"user_id": UID, "fecha": "2027-05-17"}, {"_id": 0})
    print("== un dia de 2027, entero (recortado) ==")
    plano = {k: v for k, v in d.items() if k != "comidas"}
    print(json.dumps(plano, ensure_ascii=False, default=str)[:1200])
    for k, v in (d.get("comidas") or {}).items():
        if (v or {}).get("alimentos"):
            print(" ", k, json.dumps(v, ensure_ascii=False, default=str)[:700])

    print("\n== los 12 ultimos dias DEL PASADO de Jesus ==")
    cur = db.diets.find({"user_id": UID, "fecha": {"$lte": HOY}},
                        {"fecha": 1, "tipo_dia": 1, "comidas": 1}).sort("fecha", -1).limit(12)
    async for x in cur:
        nc, na, sm, P, H, G = resumen(x)
        print(f"  {x['fecha']}  {x.get('tipo_dia'):<14} {nc} comidas  {na} alimentos  "
              f"{sm} sin macros_efectivos  ->  {P:.0f}P {H:.0f}H {G:.0f}G")

    print("\n== cuantos dias futuros tienen alimentos SIN macros_efectivos ==")
    tot = con = 0
    async for x in db.diets.find({"user_id": UID, "fecha": {"$gt": HOY}}, {"fecha": 1, "comidas": 1}):
        nc, na, sm, P, H, G = resumen(x)
        tot += 1
        if sm:
            con += 1
    print(f"  {con} de {tot}")

    cli.close()

asyncio.run(main())
