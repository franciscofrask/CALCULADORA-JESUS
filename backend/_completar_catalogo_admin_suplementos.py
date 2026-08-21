# -*- coding: utf-8 -*-
"""Completar el catálogo de admin de suplementos (doc 19-08, bloque 08).

    «Completar el catálogo de admin: tiene dieciséis fichas y en la web hay más.»

Las fichas de la web ya están en `db.supplements` (106, importadas de la guía). Este
script las vuelca a `supplement_catalog`, que es de donde el coach elige al montar un
protocolo, con `categoria='guia'` para que las dieciséis de siempre (base/intra/...)
sigan siendo las que arrancan la propuesta automática.

Idempotente: casa por id ('guia:<id de la ficha>') Y por título normalizado, y solo crea
lo que falte; no toca las fichas que ya existen ni las dieciséis originales. Casar solo
por id fue el fallo de la primera pasada (tarea 2.2, 21-08): las semillas tienen su id
propio, así que cada suplemento que ya estaba entre ellas se volcó otra vez como "guia" y
el selector lo ofrecía dos veces. Lo ya duplicado lo apaga _sanear_catalogo_suplementos.py.

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
    from _sanear_catalogo_suplementos import titulo_normalizado

    url, nombre = _cfg()
    db = AsyncIOMotorClient(url)[nombre]

    fichas = await db.supplements.find({"activo": {"$ne": False}}, {"_id": 0}).to_list(500)
    existentes, titulos = set(), set()
    async for c in db.supplement_catalog.find({}, {"_id": 0, "id": 1, "titulo": 1}):
        existentes.add(c["id"])
        titulos.add(titulo_normalizado(c.get("titulo")))

    creadas, ya = 0, 0
    for f in fichas:
        cid = f"guia:{f.get('id')}"
        titulo = f.get("nombre") or f.get("categoria") or cid
        # Por id Y por título: una semilla con el mismo nombre YA es esa ficha, aunque
        # tenga otro id. Volcarla otra vez es lo que duplicó el selector.
        if cid in existentes or titulo_normalizado(titulo) in titulos:
            ya += 1
            continue
        titulos.add(titulo_normalizado(titulo))
        partes = partir_ficha(f.get("descripcion"))
        await db.supplement_catalog.insert_one({
            "id": cid,
            "titulo": titulo,
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
