# -*- coding: utf-8 -*-
"""Puntos 67 y 69: quien tiene rutina de verdad y que cuenta el panel. SOLO MIRA."""
import asyncio, os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))

async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    print(f"base: {os.environ['DB_NAME']}\n")

    print("== como es un PDF de rutina ==")
    p = await db.rutina_pdfs.find_one({}, {"_id": 0, "contenido": 0, "data": 0, "pdf": 0, "bytes": 0})
    print("   campos:", sorted((p or {}).keys()))
    print("   ejemplo:", json.dumps({k: (str(v)[:60]) for k, v in (p or {}).items()}, ensure_ascii=False)[:400])

    pdfs = {}
    async for x in db.rutina_pdfs.find({}, {"_id": 0, "client_id": 1, "user_id": 1, "created_at": 1, "activo": 1, "modo": 1}):
        k = x.get("client_id") or x.get("user_id")
        if k:
            pdfs.setdefault(k, []).append(x)
    print(f"\n   PDFs: {await db.rutina_pdfs.count_documents({})} en {len(pdfs)} clientes")

    activas = set()
    async for r in db.routines.find({"status": "active"}, {"_id": 0, "client_id": 1}):
        activas.add(r.get("client_id"))
    print(f"   rutinas estructuradas activas: {len(activas)} clientes")

    from models.user import merged_catalog
    from core.plan_access import plan_grants_feature
    con_plan, con_estructurada, con_pdf, sin_nada = 0, 0, 0, 0
    ejemplos_pdf = []
    async for c in db.client_profiles.find({"status": {"$in": ["activo", "pago_pendiente"]}},
                                           {"_id": 0, "id": 1, "user_id": 1, "plan": 1}):
        if not plan_grants_feature(c.get("plan"), "rutina"):
            continue
        con_plan += 1
        tiene_e = c["id"] in activas
        tiene_p = (c["id"] in pdfs) or (c.get("user_id") in pdfs)
        if tiene_e: con_estructurada += 1
        if tiene_p:
            con_pdf += 1
            if not tiene_e and len(ejemplos_pdf) < 5:
                ejemplos_pdf.append(c["id"])
        if not tiene_e and not tiene_p: sin_nada += 1

    print(f"\n== de los clientes activos cuyo PLAN incluye rutina ==")
    print(f"   son:                          {con_plan}")
    print(f"   con rutina estructurada:      {con_estructurada}")
    print(f"   con PDF (y el panel no lo cuenta): {con_pdf}")
    print(f"   sin ninguna de las dos:       {sin_nada}")
    print(f"\n   el panel diria «sin rutina» de {con_plan - con_estructurada}, de los cuales {con_pdf} SI tienen su PDF")
asyncio.run(main())
