"""Punto 21 del doc del 19-08: los cinco de «TONIFICAR» pasan a definicion.

    «Definición. Los cinco. En mi método tonificar es perder grasa manteniendo el
     músculo, no hay una tercera cosa que pueda ser.»

Son los clientes que en el cuestionario de Calma pusieron TONIFICAR como objetivo: la app
solo entiende definicion y volumen, asi que se quedaron con la ficha sin objetivo, y sin
objetivo no hay macros. En calma_raw hay 24 con esa palabra, pero solo cinco tienen cuenta
en la app Y la ficha sin objetivo; el resto o no se ha dado de alta o ya lo tiene puesto.

Se ejecuta contra produccion por el tunel (27018):

    MONGO_URL="mongodb://localhost:27018" DB_NAME=jg12_prod \
      ./venv/Scripts/python.exe _fix_tonificar_definicion.py

Idempotente: solo escribe si `goal` sigue vacio, y deja backup de las cinco fichas.
"""
import asyncio
import json
import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

# Los cinco, por el email de su cuenta (verificados contra prod el 19-08: TONIFICAR en su
# formulario de Calma, cuenta viva en la app y `goal` vacio en la ficha).
LOS_CINCO = [
    "cbautistasanchez@gmail.com",           # Carmen Bautista Sanchez · elm
    "dbarrios26@outlook.com",               # Deisy Diana Barrios Barreto · gold
    "nyd1508@gmail.com",                    # Nuria Garrido · gold
    "rociopucela@hotmail.com",              # Rocio Fernandez Fernandez · bronze
    "susana.santandreu.jimenez@gmail.com",  # Susana Santandreu Jimenez · elm
]


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    backup, cambiados = [], 0
    for email in LOS_CINCO:
        u = await db.users.find_one({"email": email}, {"_id": 0, "id": 1, "name": 1})
        if not u:
            print(f"OJO sin usuario: {email}")
            continue
        p = await db.client_profiles.find_one({"user_id": u["id"]}, {"_id": 0})
        if not p:
            print(f"OJO sin ficha: {email}")
            continue
        backup.append(p)
        if p.get("goal"):
            print(f"ya tiene objetivo ({p['goal']}), no se toca: {email}")
            continue
        await db.client_profiles.update_one(
            {"user_id": u["id"], "$or": [{"goal": None}, {"goal": ""},
                                         {"goal": {"$exists": False}}]},
            {"$set": {"goal": "definicion"}},
        )
        cambiados += 1
        print(f"definicion -> {u.get('name')} ({email})")

    sello = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ruta = f"_backup_tonificar_{sello}.json"
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n{cambiados} cambiados · backup en {ruta}")


if __name__ == "__main__":
    asyncio.run(main())
