# -*- coding: utf-8 -*-
"""Parte 1 del documento (puntos 36 al 74): que sigue siendo verdad HOY en produccion.

Solo mide, no toca nada. Se usa con el tunel abierto:
  MONGO_URL=mongodb://localhost:27018 DB_NAME=jg12_prod python _guia/_parte1_estado_2808.py
"""
import asyncio, os, sys
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))


def ok(b):
    return "ARREGLADO" if b else "SIGUE"


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    print(f"base: {os.environ['DB_NAME']}\n")

    # ── 36/37/65 · el listado de clientes ────────────────────────────────────
    total = await db.users.count_documents({"role": "client"})
    pruebas = await db.users.count_documents({"role": "client", "es_prueba": True})
    borrados = await db.users.count_documents({"role": "client", "deleted_at": {"$ne": None}})
    print(f"36 · clientes con rol client: {total}   (marcados de prueba: {pruebas}, borrados: {borrados})")

    raros = []
    async for u in db.users.find({"role": "client"}, {"name": 1, "email": 1}):
        n = (u.get("name") or "").strip()
        if not n or len(n) < 3 or n.lower() in ("user", "usuario", "cliente"):
            raros.append(f"{n!r} ({u.get('email')})")
    print(f"65 · nombres imposibles: {len(raros)}  {ok(not raros)}")
    for r in raros[:6]:
        print(f"      {r}")

    # ── 39/40 · planes legacy y renovable ────────────────────────────────────
    planes = {}
    async for p in db.plans.find({}, {"_id": 0}):
        planes[p.get("codigo") or p.get("id")] = p
    legacy = [c for c, p in planes.items() if p.get("legacy") or p.get("es_legacy")]
    renovables = [c for c in legacy if planes[c].get("renovable")]
    print(f"\n39 · planes legacy en el catalogo: {len(legacy)}")
    print(f"40 · de esos, marcados «renovable»: {len(renovables)}  {ok(not renovables)}")

    # ── 42/43 · el precio de la ficha contra el cobro ────────────────────────
    montalvo = await db.client_profiles.find_one(
        {"$or": [{"nombre": {"$regex": "montalvo", "$options": "i"}},
                 {"apellidos": {"$regex": "montalvo", "$options": "i"}}]},
        {"nombre": 1, "apellidos": 1, "price": 1, "plan": 1, "user_id": 1})
    if montalvo:
        print(f"\n42 · Montalvo: plan={montalvo.get('plan')} precio de ficha={montalvo.get('price')}")

    # ── 46 · las cifras del negocio ──────────────────────────────────────────
    con_acceso = 0
    async for c in db.client_profiles.find({}, {"status": 1, "access_until": 1}):
        if (c.get("status") or "") == "activo":
            con_acceso += 1
    print(f"46 · perfiles con status activo: {con_acceso}")

    # ── 51/67/68/69 · las rutinas ────────────────────────────────────────────
    rutinas = await db.routines.count_documents({})
    activas = await db.routines.count_documents({"activa": True}) if rutinas else 0
    con_rutina = len(await db.routines.distinct("client_id", {"activa": True})) if rutinas else 0
    print(f"\n67 · rutinas guardadas: {rutinas}   activas: {activas}   clientes con una activa: {con_rutina}  {ok(con_rutina > 0)}")
    con_pdf = await db.client_profiles.count_documents({"rutina_pdf": {"$nin": [None, ""]}})
    print(f"69 · perfiles con PDF de rutina: {con_pdf}")

    # ── 52 · los avisos con el texto viejo ───────────────────────────────────
    viejos = await db.notifications.count_documents(
        {"$or": [{"message": {"$regex": "puedo mirarlo", "$options": "i"}},
                 {"message": {"$regex": "Llevas 1[0-9][0-9] semanas", "$options": "i"}},
                 {"body": {"$regex": "puedo mirarlo", "$options": "i"}}]})
    print(f"\n52 · avisos vivos con el texto viejo: {viejos}  {ok(viejos == 0)}")

    # ── 60 · el historial mezcla dos cosas ───────────────────────────────────
    tipos = Counter()
    async for c in db.checkins.find({}, {"type": 1}):
        tipos[c.get("type")] += 1
    print(f"60 · tipos en checkins: {dict(tipos)}")

    # ── 66 · el cuestionario de unos ─────────────────────────────────────────
    unos = 0
    ejemplos = []
    async for c in db.client_profiles.find({}, {"edad": 1, "altura": 1, "peso_inicial": 1, "nombre": 1}):
        if (c.get("altura") or 0) in (1, "1") or (c.get("edad") or 0) in (1, 5, "1", "5"):
            unos += 1
            if len(ejemplos) < 5:
                ejemplos.append(f"{c.get('nombre')}: edad={c.get('edad')} altura={c.get('altura')} peso={c.get('peso_inicial')}")
    print(f"\n66 · fichas con datos imposibles (altura 1 o edad 1/5): {unos}  {ok(unos == 0)}")
    for e in ejemplos:
        print(f"      {e}")

    # ── 70 · el interruptor de los correos ───────────────────────────────────
    ajustes = await db.app_settings.find_one({"_id": "app"}) or await db.app_settings.find_one({}) or {}
    llaves = {k: v for k, v in ajustes.items() if "correo" in str(k).lower() or "aviso" in str(k).lower() or "email" in str(k).lower()}
    print(f"\n70 · interruptores de correo en app_settings: {llaves or '(ninguno)'}")

    # ── 68 · la biblioteca de rutinas ────────────────────────────────────────
    biblio = await db.routine_templates.count_documents({}) if "routine_templates" in await db.list_collection_names() else None
    print(f"68 · plantillas de rutina guardadas: {biblio if biblio is not None else '(no existe la coleccion)'}")

    cli.close()

asyncio.run(main())
