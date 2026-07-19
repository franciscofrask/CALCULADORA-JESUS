# -*- coding: utf-8 -*-
"""Importa las fotos de progreso de Calma pendientes (photo_urls_calma en checkins).

Migracion 04-07: las fotos quedaron como URLs gs:// en los check-ins porque el
Storage daba 403. La clave de servicio es del proyecto jesusgallegopt: SU bucket
ya abre (672 fotos); el del proyecto viejo jesus-gallego sigue 403 (741 fotos,
haran falta credenciales de ese proyecto).

- Descarga cada foto accesible y la inserta en client_photos con el formato de
  la app (routes/checkins.py) + campos origen='calma' y gs_url (idempotencia:
  si ya existe ese gs_url, se salta).
- Guarda copia en disco (OUT_DIR) + index.json para replicar la carga en PROD.
- taken_at: fecha del nombre de archivo (2024-05-15_Frente.jpg) o la del check-in.

Uso: ./venv/Scripts/python.exe _importar_fotos_calma.py [--dry-run]
"""
import asyncio
import json
import mimetypes
import os
import re
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

import firebase_admin
from firebase_admin import credentials, storage
from bson.binary import Binary

from core.database import db

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_fotos_calma")
BUCKET_OK = "jesusgallegopt.appspot.com"

cred = credentials.Certificate(os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json"))
firebase_admin.initialize_app(cred)


def fecha_de_nombre(nombre, fallback):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", nombre)
    if m:
        return m.group(1) + "T12:00:00+00:00"
    return fallback


async def main():
    dry = "--dry-run" in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)
    bucket = storage.bucket(BUCKET_OK)

    # SOLO DISCO: el cluster gratuito de Atlas (512 MB) no puede con ~700 MB de
    # fotos (2026-07-19: llego a bloquear escrituras). El destino es PROD (Mongo
    # del VPS); aqui se descarga a OUT_DIR y la insercion se hace alli.
    index_path = os.path.join(OUT_DIR, "index.json")
    index = []
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as fh:
            index = json.load(fh)
    hechas = {e["gs_url"] for e in index}

    # user_id por client_id para las fotos (los checkins ya lo llevan, pero por si falta)
    uid_por_cid = {}
    async for p in db.client_profiles.find({}, {"_id": 0, "id": 1, "user_id": 1}):
        if p.get("id"):
            uid_por_cid[p["id"]] = p.get("user_id")

    stats = {"descargadas": 0, "ya_importadas": 0, "bloqueadas_otro_bucket": 0,
             "errores": 0, "bytes": 0}

    async for c in db.checkins.find(
        {"photo_urls_calma.0": {"$exists": True}},
        {"_id": 0, "id": 1, "client_id": 1, "user_id": 1, "created_at": 1, "photo_urls_calma": 1},
    ):
        fallback = c.get("created_at") or datetime.now(timezone.utc).isoformat()
        for url in c["photo_urls_calma"]:
            b = url.split("/")[2]
            if b != BUCKET_OK:
                stats["bloqueadas_otro_bucket"] += 1
                continue
            if url in hechas:
                stats["ya_importadas"] += 1
                continue
            path = url.split(BUCKET_OK + "/", 1)[1]
            nombre = os.path.basename(path)
            try:
                blob = bucket.blob(path)
                data = blob.download_as_bytes()
            except Exception as e:
                stats["errores"] += 1
                print("ERROR", url, str(e)[:120])
                continue
            content_type = mimetypes.guess_type(nombre)[0] or "image/jpeg"
            doc = {
                "id": str(uuid.uuid4()),
                "client_id": c.get("client_id"),
                "user_id": c.get("user_id") or uid_por_cid.get(c.get("client_id")),
                "filename": nombre,
                "content_type": content_type,
                "size": len(data),
                "taken_at": fecha_de_nombre(nombre, fallback),
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "origen": "calma",
                "gs_url": url,
                "checkin_id": c.get("id"),
            }
            # copia a disco + index (para replicar en PROD)
            fname = doc["id"] + "_" + re.sub(r"[^A-Za-z0-9._-]", "_", nombre)
            with open(os.path.join(OUT_DIR, fname), "wb") as fh:
                fh.write(data)
            index.append({**doc, "file": fname})
            hechas.add(url)
            stats["descargadas"] += 1
            stats["bytes"] += len(data)
            if stats["descargadas"] % 50 == 0:
                print(f"... {stats['descargadas']} fotos ({stats['bytes']//1024//1024} MB)")

    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False)
    print("RESUMEN:", stats)
    print("Copias en:", OUT_DIR)


asyncio.run(main())
