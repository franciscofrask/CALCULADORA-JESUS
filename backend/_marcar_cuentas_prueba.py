# -*- coding: utf-8 -*-
"""Marca las cuentas de prueba del equipo con `es_prueba: true` (en users y client_profiles).

Tarea 2.1 del plan del lunes (21-08-2026): las cuentas que el equipo creó para probar
tienen rol client, así que `_fuera_el_equipo` (que filtra por rol) no las tocaba y
contaban como clientes en todos los números del panel. Con el flag puesto, el propio
`_fuera_el_equipo` las deja fuera de todos los contadores de una vez.

La lista de emails es EXACTA y está verificada en producción el 21-08. Los admin/trainer
no van aquí: a esos ya los saca el filtro por rol.

Uso:  python _marcar_cuentas_prueba.py            (ensayo: enseña, no escribe)
      python _marcar_cuentas_prueba.py --escribir (aplica, con backup previo en JSON)

Por defecto conecta con el MONGO_URL/DB_NAME del .env del backend (la base de DEV).
CONTRA PRODUCCIÓN LO LANZA FRANCISCO A MANO: con el túnel SSH abierto al 27018,
    set MARCAR_MONGO_URL=mongodb://127.0.0.1:27018
    set MARCAR_MONGO_DB=jg12_prod
    python _marcar_cuentas_prueba.py --escribir
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
except ImportError:
    pass

from motor.motor_asyncio import AsyncIOMotorClient

URL = os.environ.get("MARCAR_MONGO_URL") or os.environ.get("MONGO_URL")
BASE = os.environ.get("MARCAR_MONGO_DB") or os.environ.get("DB_NAME")
ESCRIBIR = "--escribir" in sys.argv
HOY = datetime.now(timezone.utc)

# Verificados en produccion el 21-08-2026. Ni un email mas: si aparece otra cuenta de
# prueba, se añade aqui y se relanza (el script es idempotente).
CUENTAS_DE_PRUEBA = [
    "jose@test.com",
    "prueba@mail.com",
    "cliente2@jg12.com",
    "clientedemo@test.com",
    "user@jg12.com",
    "test@test.com",
    "francisco2@test.com",
    "francisco3@test.com",
    "rafelnadal@gmail.com",
    "francisc3@test.com",
    "franciscodemo@test.com",
    "pagodemo@test.com",
    "arhlnzqkszlhnvxbee@gonrr.net",
]


async def main():
    if not URL or not BASE:
        print("Sin MONGO_URL/DB_NAME no hay a donde conectar. Revisa el .env o las variables MARCAR_*.")
        return
    # La cadena de conexion ANTES DE NADA, para saber contra que base se va a escribir.
    print(f"conexion: {URL[:28]}...  base: {BASE}")
    print(f"{'ESCRIBIENDO' if ESCRIBIR else 'ENSAYO (no escribe)'}\n")

    db = AsyncIOMotorClient(URL, serverSelectionTimeoutMS=20000)[BASE]

    a_marcar, ya_marcados, no_existen = [], [], []
    for email in CUENTAS_DE_PRUEBA:
        user = await db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            no_existen.append(email)
            continue
        perfiles = await db.client_profiles.find({"user_id": user["id"]}, {"_id": 0}).to_list(10)
        falta_user = user.get("es_prueba") is not True
        perfiles_sin = [p for p in perfiles if p.get("es_prueba") is not True]
        if not falta_user and not perfiles_sin:
            ya_marcados.append(email)
            continue
        a_marcar.append({"email": email, "user": user, "perfiles": perfiles,
                         "marcar_user": falta_user, "marcar_perfiles": perfiles_sin})

    for c in a_marcar:
        piezas = (["users"] if c["marcar_user"] else []) + \
                 [f"client_profiles {p['id']}" for p in c["marcar_perfiles"]]
        sin_perfil = "" if c["perfiles"] else "  (sin perfil de cliente)"
        print(f"  {c['email']:36} -> {', '.join(piezas)}{sin_perfil}")
    if ya_marcados:
        print(f"\nya marcados (no se tocan): {', '.join(ya_marcados)}")
    if no_existen:
        print(f"\nNO EXISTEN en esta base (repasar la lista): {', '.join(no_existen)}")
    print(f"\ntotal a marcar: {len(a_marcar)}")

    if not ESCRIBIR or not a_marcar:
        if not ESCRIBIR:
            print("\nEnsayo. Ejecuta con --escribir para aplicar.")
        return

    # Backup de los documentos tal como estan ANTES de tocarlos.
    ruta = os.path.join(RAIZ, f"_backup_es_prueba_{HOY.strftime('%Y%m%d_%H%M%S')}.json")
    backup = [{"email": c["email"], "user": c["user"], "perfiles": c["perfiles"]} for c in a_marcar]
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=1, default=str)
    print(f"\nbackup: {ruta}")

    escritos = 0
    for c in a_marcar:
        if c["marcar_user"]:
            await db.users.update_one({"id": c["user"]["id"]}, {"$set": {"es_prueba": True}})
            escritos += 1
        for p in c["marcar_perfiles"]:
            await db.client_profiles.update_one({"id": p["id"]}, {"$set": {"es_prueba": True}})
            escritos += 1
    print(f"documentos escritos: {escritos}")


if __name__ == "__main__":
    asyncio.run(main())
