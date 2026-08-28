# -*- coding: utf-8 -*-
"""Punto 65: eliminar la cuenta de prueba «user» (user@user.com) de produccion.

Es una cuenta creada el 17-05, que NUNCA ha entrado, ya marcada `es_prueba`, con una dieta
de ese mismo dia, un cobro de 149 EUR sin Stripe ni origen (un apunte de prueba) y cuatro
alertas de «Reporte vencido» que siguen saliendo en el panel.

MIRA Y NO TOCA SIN `--escribir`. Antes de borrar deja copia de TODO lo suyo en un JSON, asi
que la cuenta se puede reponer entera.

Uso:
  MONGO_URL=mongodb://localhost:27018 DB_NAME=jg12_prod python _guia/_p65_borrar_user.py
  ... --escribir      para borrar de verdad
"""
import asyncio, os, sys, json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))

CORREO = "user@user.com"
ESCRIBIR = "--escribir" in sys.argv


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    print(f"base: {os.environ['DB_NAME']}   modo: {'BORRAR' if ESCRIBIR else 'solo mirar'}\n")

    u = await db.users.find_one({"email": CORREO})
    if not u:
        print(f"no existe {CORREO}: no hay nada que borrar")
        cli.close(); return
    uid = u["id"]
    perfil = await db.client_profiles.find_one({"user_id": uid})
    cid = (perfil or {}).get("id")
    print(f"cuenta: {CORREO}  id={uid}")
    print(f"ficha:  {cid}")
    print(f"nunca entro: {u.get('last_login') is None}   marcada de prueba: {u.get('es_prueba')}\n")

    # BARRIDO DE TODAS LAS COLECCIONES, no solo las que uno se imagina: una cuenta puede
    # tener rastro en sitios que no estan en la lista mental de nadie.
    claves = [("user_id", uid), ("client_id", cid), ("cliente_id", cid),
              ("usuario_id", uid), ("owner_id", uid), ("id", uid)]
    encontrado = {}
    for nombre in sorted(await db.list_collection_names()):
        if nombre.startswith("system."):
            continue
        docs = []
        for campo, valor in claves:
            if valor is None:
                continue
            async for d in db[nombre].find({campo: valor}):
                d.pop("_id", None)
                if d not in docs:
                    docs.append(d)
        if docs:
            encontrado[nombre] = docs
            print(f"   {nombre:<24} {len(docs)}")

    # Y la ficha y el usuario, por si el barrido no los pilla por `id`.
    encontrado.setdefault("users", [])
    if not any(d.get("id") == uid for d in encontrado["users"]):
        encontrado["users"].append({k: v for k, v in u.items() if k != "_id"})
    if perfil:
        encontrado.setdefault("client_profiles", [])
        if not any(d.get("id") == cid for d in encontrado["client_profiles"]):
            encontrado["client_profiles"].append({k: v for k, v in perfil.items() if k != "_id"})

    total = sum(len(v) for v in encontrado.values())
    print(f"\ntotal a borrar: {total} documentos en {len(encontrado)} colecciones")

    if not ESCRIBIR:
        print("\n(solo se ha mirado; para borrar de verdad, --escribir)")
        cli.close(); return

    # LA COPIA, ANTES DE TOCAR NADA. Con esto la cuenta se repone entera.
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend",
                        f"_backup_user_borrado_{sello}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"cuenta": CORREO, "user_id": uid, "client_id": cid,
                   "base": os.environ["DB_NAME"], "cuando": sello,
                   "documentos": encontrado}, f, ensure_ascii=False, indent=2, default=str)
    print(f"copia guardada en {os.path.abspath(ruta)}")

    borrados = {}
    for nombre, docs in encontrado.items():
        ids = [d.get("id") for d in docs if d.get("id")]
        n = 0
        if ids:
            r = await db[nombre].delete_many({"id": {"$in": ids}})
            n = r.deleted_count
        # Lo que no tenga `id` propio se borra por la clave con la que se encontro.
        for campo, valor in claves:
            if valor is None or campo == "id":
                continue
            r = await db[nombre].delete_many({campo: valor})
            n += r.deleted_count
        borrados[nombre] = n
        print(f"   borrados {n:>3} de {nombre}")

    print("\n== comprobacion ==")
    print(f"   la cuenta existe todavia: {bool(await db.users.find_one({'email': CORREO}))}")
    print(f"   su ficha existe todavia:  {bool(await db.client_profiles.find_one({'user_id': uid}))}")
    tot = await db.users.count_documents({"role": "client"})
    pru = await db.users.count_documents({"role": "client", "es_prueba": True})
    print(f"   clientes: {tot}   de prueba: {pru}")
    cli.close()

asyncio.run(main())
