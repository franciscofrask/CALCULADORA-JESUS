"""Copia el historial de dietas de un cliente real a la cuenta de pruebas.

Para que el orden de fuentes del asistente (historial con umbral -> biblioteca ->
recetario -> compositor, decision de Francisco del 15-08) se pueda probar con un
historial DE VERDAD: la cuenta de pruebas solo tenia basura de sesiones de QA.

Reglas de la casa:
- Dry-run por defecto; escribir exige --escribir.
- Imprime la CADENA DE CONEXION, no el nombre de la base (dev y prod se llaman igual).
- Para una base que no sea la del .env hace falta ademas --uri explicita y
  --si-otra-base (la llave larga, como el importador de suplementos).
- Idempotente: las copias llevan `_copia_qa: <user_id origen>` y se borran y rehacen
  en cada pasada. Las dietas propias del destino NO se tocan: su fecha se salta.
- Las fechas copiadas se recolocan consecutivas ACABANDO el 2026-08-09, para no pisar
  los dias 10-08 en adelante, que son los que usa el ciclo de QA en vivo.

Uso:
  venv/Scripts/python.exe _copiar_dietas_qa.py                      # dry-run en dev
  venv/Scripts/python.exe _copiar_dietas_qa.py --escribir           # escribe en dev
  venv/Scripts/python.exe _copiar_dietas_qa.py --escribir \
      --uri mongodb://localhost:27018 --si-otra-base                # escribe en prod (tunel)
"""
import argparse
import asyncio
import json
import os
from datetime import date, timedelta
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

ORIGEN_EMAIL = "andrescano84@hotmail.com"
DESTINO_EMAIL = "francisco@test.com"
DIAS = 120
ULTIMA_FECHA = date(2026, 8, 9)


async def correr(args):
    from dotenv import dotenv_values
    env = dotenv_values(Path(__file__).parent / ".env")
    uri = args.uri or env.get("MONGO_URL") or "mongodb://localhost:27017"
    if args.uri and args.uri != env.get("MONGO_URL") and not args.si_otra_base:
        raise SystemExit("URI distinta de la del .env: hace falta --si-otra-base")
    print(f"Conexion: {uri[:38]}...  escribir={args.escribir}")
    db = AsyncIOMotorClient(uri)[env.get("DB_NAME") or "jg12_restored"]

    origen = await db.users.find_one({"email": args.origen}, {"_id": 0, "id": 1})
    destino = await db.users.find_one({"email": args.destino}, {"_id": 0, "id": 1})
    if not origen:
        raise SystemExit(f"no existe el usuario origen {args.origen}")
    if not destino:
        raise SystemExit(f"no existe el usuario destino {args.destino}")
    oid, did = origen["id"], destino["id"]
    print(f"origen  {args.origen} -> {oid}")
    print(f"destino {args.destino} -> {did}")

    # Copia de seguridad de las dietas actuales del destino (antes de tocar nada).
    actuales = await db.diets.find({"user_id": did}).to_list(5000)
    respaldo = Path(__file__).parent / f"_backup_dietas_{did[:8]}.json"
    respaldo.write_text(json.dumps(actuales, default=str, ensure_ascii=False))
    print(f"respaldo: {len(actuales)} dietas del destino en {respaldo.name}")

    # Fechas propias del destino que no son copias nuestras: intocables.
    propias = {d.get("fecha") for d in actuales if not d.get("_copia_qa")}
    viejas = [d for d in actuales if d.get("_copia_qa")]
    print(f"copias previas a borrar: {len(viejas)}; fechas propias intocables: {len(propias)}")

    # Las N dietas mas recientes del origen con alguna comida bien formada.
    fuente = []
    async for d in db.diets.find({"user_id": oid}, {"_id": 0}).sort("fecha", -1).limit(args.dias * 2):
        util = any(2 <= len({a.get("alimento_id") for a in (c or {}).get("alimentos", [])
                             if a.get("alimento_id") is not None}) <= 7
                   for c in (d.get("comidas") or {}).values())
        if util:
            fuente.append(d)
        if len(fuente) >= args.dias:
            break
    fuente.sort(key=lambda d: d.get("fecha") or "")
    print(f"dietas utiles del origen: {len(fuente)}")

    # Recolocadas consecutivas acabando en ULTIMA_FECHA.
    nuevas = []
    for i, d in enumerate(fuente):
        fecha = (ULTIMA_FECHA - timedelta(days=len(fuente) - 1 - i)).isoformat()
        if fecha in propias:
            continue
        doc = dict(d)
        doc["user_id"] = did
        doc["fecha"] = fecha
        doc["_copia_qa"] = oid
        nuevas.append(doc)
    print(f"a insertar: {len(nuevas)} dietas ({nuevas[0]['fecha']} .. {nuevas[-1]['fecha']})"
          if nuevas else "nada que insertar")

    if not args.escribir:
        print("DRY-RUN: no se ha escrito nada. Repite con --escribir.")
        return
    if viejas:
        r = await db.diets.delete_many({"user_id": did, "_copia_qa": {"$exists": True}})
        print(f"borradas {r.deleted_count} copias previas")
    if nuevas:
        await db.diets.insert_many(nuevas)
        print(f"insertadas {len(nuevas)}")
    total = await db.diets.count_documents({"user_id": did})
    print(f"el destino queda con {total} dietas")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--uri", default=None)
    p.add_argument("--origen", default=ORIGEN_EMAIL)
    p.add_argument("--destino", default=DESTINO_EMAIL)
    p.add_argument("--dias", type=int, default=DIAS)
    p.add_argument("--escribir", action="store_true")
    p.add_argument("--si-otra-base", dest="si_otra_base", action="store_true")
    args = p.parse_args()
    asyncio.run(correr(args))
