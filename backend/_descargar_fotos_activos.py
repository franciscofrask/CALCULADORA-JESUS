# -*- coding: utf-8 -*-
"""
Descarga las fotos de progreso de Calma de los clientes ACTIVOS (con user_id en
calma_raw) desde el bucket jesusgallegopt.appspot.com. DEV-ONLY.

- Lista la carpeta real de cada cliente (no se fia de la ruta de Firestore, cuya
  extension a veces no coincide: dice .heic y el archivo es .jpeg).
- JPG/JPEG/PNG: se guardan TAL CUAL (cero perdida, sin redimensionar).
- HEIC/HEIF: se convierten a JPG q=92 (el navegador no muestra HEIC). Sin redimensionar.
- Archivos -> disco (_fotos_calma/<email>/). Metadatos -> calma_raw.fotos_descargadas
  (solo texto; Mongo/Atlas no recibe bytes).
- Idempotente: si el archivo local ya existe, no lo vuelve a bajar.

Uso (desde backend/):
  venv/Scripts/python.exe _descargar_fotos_activos.py <email>   # 1 cliente (validar)
  venv/Scripts/python.exe _descargar_fotos_activos.py all
  venv/Scripts/python.exe _descargar_fotos_activos.py all --limit 5
"""
import asyncio, io, os, re, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")
from google.cloud import storage as gcs
from google.oauth2 import service_account
from PIL import Image, ImageOps
import pillow_heif
from core.database import db as mdb

pillow_heif.register_heif_opener()

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "_fotos_calma")
BUCKET = "jesusgallegopt.appspot.com"
JPEG_Q = 92

creds = service_account.Credentials.from_service_account_file(os.path.join(HERE, "serviceAccountKey.json"))
gclient = gcs.Client(credentials=creds, project=creds.project_id)
bucket = gclient.bucket(BUCKET)

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def safe(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)

FN_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[_-](.+)\.([A-Za-z0-9]+)$")

def parse_nombre(fname):
    m = FN_RE.match(fname)
    if m:
        return m.group(1), m.group(2), m.group(3).lower()
    return None, os.path.splitext(fname)[0], (fname.rsplit(".", 1)[-1].lower() if "." in fname else "")

async def procesar_cliente(email, stats):
    doc = await mdb.calma_raw.find_one({"email": email}, {"_id": 0, "id": 1, "client_id": 1, "user_id": 1})
    client_id = doc.get("client_id") if doc else None
    user_id = doc.get("user_id") if doc else None
    cdir = os.path.join(OUT_DIR, safe(email))
    fotos_meta = []

    for tipo in ("iniciales", "mensuales"):
        prefix = f"archivosFormularios/{tipo}/{email}/"
        for blob in gclient.list_blobs(bucket, prefix=prefix):
            if blob.name.endswith("/"):
                continue
            fname = blob.name.split("/")[-1]
            fecha, kind, ext = parse_nombre(fname)
            es_heic = ext in ("heic", "heif")
            base = f"{tipo}__{os.path.splitext(fname)[0]}"
            out_name = base + (".jpg" if es_heic else "." + ext)
            out_path = os.path.join(cdir, out_name)
            rel_path = os.path.join(safe(email), out_name).replace("\\", "/")

            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                stats["saltadas"] += 1
            else:
                try:
                    data = blob.download_as_bytes()
                except Exception as e:
                    stats["errores"] += 1
                    print(f"  ERROR download {blob.name}: {str(e)[:100]}")
                    continue
                os.makedirs(cdir, exist_ok=True)
                try:
                    if es_heic:
                        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
                        img.save(out_path, "JPEG", quality=JPEG_Q)
                        stats["convertidas"] += 1
                    else:
                        with open(out_path, "wb") as fh:
                            fh.write(data)
                        stats["descargadas"] += 1
                    stats["bytes"] += len(data)
                except Exception as e:
                    stats["errores"] += 1
                    print(f"  ERROR guardar {blob.name}: {str(e)[:100]}")
                    continue

            fotos_meta.append({
                "tipo": tipo, "kind": kind, "fecha": fecha,
                "file": rel_path,
                "content_type": "image/jpeg" if es_heic else (blob.content_type or ""),
                "size": os.path.getsize(out_path) if os.path.exists(out_path) else None,
                "convertida_de_heic": es_heic,
                "bucket_path": blob.name,
            })

    fotos_meta.sort(key=lambda x: (x.get("fecha") or "", x.get("kind") or ""))
    await mdb.calma_raw.update_one({"email": email}, {"$set": {
        "fotos_descargadas": fotos_meta,
        "fotos_descargadas_n": len(fotos_meta),
        "fotos_descargadas_at": now_iso(),
    }})
    return len(fotos_meta), client_id, user_id

async def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return
    os.makedirs(OUT_DIR, exist_ok=True)

    target = args[0]
    limit = None
    if "--limit" in args:
        try: limit = int(args[args.index("--limit") + 1])
        except Exception: limit = None

    if "@" in target:
        emails = [target.strip().lower()]
    elif target == "all":
        emails = []
        async for d in mdb.calma_raw.find({"user_id": {"$ne": None}}, {"_id": 0, "email": 1}):
            emails.append(d["email"])
        emails.sort()
        if limit:
            emails = emails[:limit]
    else:
        print("Uso: _descargar_fotos_activos.py <email> | all [--limit N]"); return

    print(f"clientes a procesar: {len(emails)}  (destino disco: {OUT_DIR})")
    stats = {"clientes": 0, "con_fotos": 0, "descargadas": 0, "convertidas": 0,
             "saltadas": 0, "errores": 0, "bytes": 0}
    for i, email in enumerate(emails, 1):
        try:
            n, cid, uid = await procesar_cliente(email, stats)
            stats["clientes"] += 1
            if n: stats["con_fotos"] += 1
            if i % 5 == 0 or i == len(emails):
                gb = stats["bytes"] / 1024 / 1024 / 1024
                print(f"[{i}/{len(emails)}] {email} | fotos={n} | acum: baj={stats['descargadas']} conv={stats['convertidas']} salt={stats['saltadas']} {gb:.2f}GB")
        except Exception as e:
            stats["errores"] += 1
            print(f"  ERROR cliente {email}: {type(e).__name__}: {e}")

    print("\n===== RESUMEN descarga fotos (activos, dev) =====")
    for k, v in stats.items():
        if k == "bytes":
            print(f"  {k}: {v/1024/1024/1024:.2f} GB")
        else:
            print(f"  {k}: {v}")

asyncio.run(main())
