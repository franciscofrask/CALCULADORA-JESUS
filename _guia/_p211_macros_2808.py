# -*- coding: utf-8 -*-
"""Punto 211: los días a repetir salían todos a «0 P · 0 H · 0 G».

La causa: la lista sumaba el campo `macros_efectivos` de cada alimento guardado, y ese
campo muchas veces no está (los días que vinieron de Calma no lo tienen ni uno).

Esto lo reproduce a propósito: le quita `macros_efectivos` a un día montado de la cuenta
de prueba, pide la lista y comprueba que los macros siguen saliendo. Deja el día como estaba.
"""
import asyncio, os, sys, copy, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import date

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))
API = os.environ.get("API", "http://127.0.0.1:8000/api")
EMAIL, CLAVE = "clientedemo@test.com", "demo123"
HOY = date.today().isoformat()


def entrar():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": CLAVE}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def lista(cab):
    r = requests.get(f"{API}/diets/recent",
                     params={"limit": 14, "para": HOY, "hoy_cliente": HOY},
                     headers=cab, timeout=90)
    r.raise_for_status()
    return r.json().get("diets") or []


async def main():
    cab = entrar()
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    u = await db.users.find_one({"email": EMAIL}, {"id": 1})
    uid = u["id"]

    dias = lista(cab)
    print(f"la lista trae {len(dias)} dias\n")
    ceros = [d["fecha"] for d in dias
             if sum((d.get("macros") or {}).get(m, 0) for m in "PHG") <= 0]
    print("dias que salen a 0 P · 0 H · 0 G:", ceros or "ninguno  BIEN")
    for d in dias[:5]:
        m = d.get("macros") or {}
        print(f"   {d['fecha']}  {m.get('P')} P · {m.get('H')} H · {m.get('G')} G")

    # ── Ahora el caso de Jesus: un dia montado SIN `macros_efectivos` ──────────
    victima = next((d["fecha"] for d in dias
                    if sum((d.get("macros") or {}).get(m, 0) for m in "PHG") > 0), None)
    if not victima:
        print("\nno hay ningun dia montado con macros: no se puede probar")
        cli.close(); return

    doc = await db.diets.find_one({"user_id": uid, "fecha": victima}, {"_id": 0})
    original = copy.deepcopy(doc.get("comidas") or {})
    antes = next(d for d in dias if d["fecha"] == victima)["macros"]

    pelado = copy.deepcopy(original)
    quitados = 0
    for c in pelado.values():
        for a in (c or {}).get("alimentos") or []:
            if a.pop("macros_efectivos", None) is not None:
                quitados += 1
    await db.diets.update_one({"user_id": uid, "fecha": victima}, {"$set": {"comidas": pelado}})
    print(f"\n=== al dia {victima} se le quitan {quitados} `macros_efectivos` (como los de Calma) ===")

    despues = next((d for d in lista(cab) if d["fecha"] == victima), None)
    m = (despues or {}).get("macros")
    print(f"   antes:   {antes}")
    print(f"   despues: {m}")
    igual = m == antes
    print(f"   los macros aguantan sin el campo guardado   {'BIEN' if igual else 'MAL'}")

    await db.diets.update_one({"user_id": uid, "fecha": victima}, {"$set": {"comidas": original}})
    vuelto = next((d for d in lista(cab) if d["fecha"] == victima), None)
    print(f"\ndia repuesto -> {(vuelto or {}).get('macros')}")
    cli.close()

asyncio.run(main())
