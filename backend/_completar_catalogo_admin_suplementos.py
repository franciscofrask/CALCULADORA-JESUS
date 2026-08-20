# -*- coding: utf-8 -*-
"""Completar el catálogo de admin de suplementos (doc 19-08, bloque 08).

    «Completar el catálogo de admin: tiene dieciséis fichas y en la web hay más.»

Las fichas de la web ya están en `db.supplements` (106, importadas de la guía). Este
script las vuelca a `supplement_catalog`, que es de donde el coach elige al montar un
protocolo, con `categoria='guia'` para que las dieciséis de siempre (base/intra/...)
sigan siendo las que arrancan la propuesta automática.

Idempotente: casa por id ('guia:<id de la ficha>') y solo crea lo que falte; no toca las
fichas que ya existen ni las dieciséis originales.

Uso:
    ./venv/Scripts/python.exe _completar_catalogo_admin_suplementos.py            # dev (.env)
    MONGO_URL="mongodb://localhost:27018" DB_NAME=jg12_prod PYTHONIOENCODING=utf-8 \
      ./venv/Scripts/python.exe _completar_catalogo_admin_suplementos.py          # prod (tunel)
"""
import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient


def _cfg():
    if os.environ.get("MONGO_URL"):
        return os.environ["MONGO_URL"], os.environ.get("DB_NAME", "jg12_prod")
    from dotenv import dotenv_values
    cfg = dotenv_values(os.path.join(os.path.dirname(__file__), ".env"))
    return cfg["MONGO_URL"], cfg["DB_NAME"]


async def main():
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from core.guia_suplementacion import partir_ficha

    url, nombre = _cfg()
    db = AsyncIOMotorClient(url)[nombre]

    fichas = await db.supplements.find({"activo": {"$ne": False}}, {"_id": 0}).to_list(500)
    existentes = {c["id"] async for c in db.supplement_catalog.find({}, {"_id": 0, "id": 1})}

    creadas, ya = 0, 0
    for f in fichas:
        cid = f"guia:{f.get('id')}"
        if cid in existentes:
            ya += 1
            continue
        partes = partir_ficha(f.get("descripcion"))
        await db.supplement_catalog.insert_one({
            "id": cid,
            "titulo": f.get("nombre") or f.get("categoria") or cid,
            "imagen": f.get("imagen"),
            "enlaces": [e.get("url") if isinstance(e, dict) else e for e in (f.get("enlaces") or [])],
            "cuando": partes["cuando"] or "",
            "cuanto": partes["cuanto"] or "",
            "observaciones": " · ".join(x for x in (partes["que_es"], (f.get("notas") or "").strip() or None) if x) or None,
            "sexo": "ambos",
            "categoria": "guia",
            "objetivo": "ambos",
            "orden": 100,
            "activo": True,
        })
        creadas += 1

    total = await db.supplement_catalog.count_documents({})
    print(f"{nombre}: {creadas} fichas nuevas en el catalogo de admin, {ya} ya estaban; total ahora {total}")


asyncio.run(main())
