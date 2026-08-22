# -*- coding: utf-8 -*-
"""
Sube TODAS las fotos de los clientes a Cloudflare R2 (bucket privado jg12-fotos, UE)
y las deja marcadas, SIN borrar nada del origen.

Las dos poblaciones, con el mismo convenio de claves que lee core/fotos.py:
  - client_photos (Mongo, el binario en `data`)      -> app/{user_id}/{photo_id}
    (si el doc no tiene user_id -- la trampa conocida -- se usa el client_id;
    la clave exacta queda guardada en `r2_key` del doc para que no haya que
    reconstruir nada nunca).
  - calma_raw.fotos_descargadas (ficheros en disco)  -> calma/{ruta original}
    (la misma ruta `file` del registro, p. ej. calma/ana_gmail.com/mensuales__....jpg).

La marca es `en_r2: true` (+ `r2_key` y `en_r2_at`) en el doc o en la entrada del
registro: es lo que core/fotos.py mira para servir desde R2. NO se borra ni el blob
de Mongo ni el fichero del disco: ese sera un paso posterior separado, cuando R2
lleve dias sirviendo sin sustos.

Idempotente y reanudable: lo ya marcado `en_r2` se salta, asi que se puede cortar
y relanzar sin miedo. Subir dos veces la misma clave a R2 tampoco duplica nada.

Pensado para correr EN EL VPS (alli viven el disco y el Mongo). Dependencias:
boto3 + pymongo + dotenv. La conexion sale del entorno o del .env de al lado:
MONGO_URL / DB_NAME, y R2_ENDPOINT / R2_BUCKET / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY.

Uso (desde backend/):
  python _migrar_fotos_a_r2.py                # dry-run (por defecto): cuenta y no toca nada
  python _migrar_fotos_a_r2.py --escribir     # sube a R2 y marca en_r2
  python _migrar_fotos_a_r2.py --verificar    # head_object de una muestra de lo marcado
  python _migrar_fotos_a_r2.py --limite 25 --escribir   # tope de fotos (pruebas)
"""
import argparse
import datetime
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))  # el entorno ya puesto manda sobre el .env

from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

# El mismo directorio del que sirve core/fotos.py. En el VPS: /opt/jg12/backend/_fotos_calma.
FOTOS_CALMA_DIR = os.path.join(HERE, "_fotos_calma")

MUESTRA_VERIFICAR = 20


def sin_secretos(url):
    """La URL de Mongo sin usuario ni contraseña, para poder imprimirla."""
    return re.sub(r"//[^@/]+@", "//***@", url)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def cliente_r2():
    """El cliente S3 contra R2, o None si faltan credenciales (dry-run sin ellas vale)."""
    access = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    endpoint = os.environ.get("R2_ENDPOINT", "").strip()
    if not (access and secret and endpoint):
        return None
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


BUCKET = os.environ.get("R2_BUCKET", "jg12-fotos").strip() or "jg12-fotos"

_CONTENT_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".gif": "image/gif",
}


def content_type_de(fichero):
    return _CONTENT_TYPES.get(os.path.splitext(fichero)[1].lower(), "image/jpeg")


def ruta_en_disco(fichero):
    """La ruta absoluta del fichero de Calma, o None si se sale del directorio
    (path traversal) o no existe. El mismo candado que core/fotos.py."""
    full = os.path.normpath(os.path.join(FOTOS_CALMA_DIR, fichero))
    if not full.startswith(FOTOS_CALMA_DIR + os.sep):
        return None
    if not os.path.isfile(full):
        return None
    return full


def clave_app(doc):
    dueno = doc.get("user_id") or doc.get("client_id") or "sin-dueno"
    return f"app/{dueno}/{doc.get('id')}"


# ---------------------------------------------------------------- fase 1: client_photos

def migrar_app(db, r2, escribir, limite, stats):
    print("\n===== FASE 1: client_photos (blobs de Mongo) -> app/... =====")
    # Primero sin el binario: el plan se hace ligero y el blob se trae doc a doc.
    pendientes = list(db.client_photos.find(
        {"en_r2": {"$ne": True}},
        {"_id": 1, "id": 1, "user_id": 1, "client_id": 1, "content_type": 1, "size": 1},
    ))
    ya = db.client_photos.count_documents({"en_r2": True})
    print(f"  ya en R2 (marcadas): {ya}")
    print(f"  pendientes: {len(pendientes)}"
          f"  (~{sum(p.get('size') or 0 for p in pendientes) / 1024 / 1024:.1f} MB segun `size`)")

    if limite:
        pendientes = pendientes[:limite]
    if not escribir:
        return

    for i, p in enumerate(pendientes, 1):
        doc = db.client_photos.find_one({"_id": p["_id"]})
        data = doc.get("data")
        if not data:
            stats["app_sin_blob"] += 1
            print(f"  [sin blob] {doc.get('id')} no tiene `data`; se deja sin marcar")
            continue
        clave = clave_app(doc)
        try:
            r2.put_object(
                Bucket=BUCKET, Key=clave, Body=bytes(data),
                ContentType=doc.get("content_type") or "application/octet-stream",
            )
        except Exception as e:
            stats["errores"] += 1
            print(f"  ERROR subiendo {clave}: {str(e)[:200]}")
            continue
        db.client_photos.update_one(
            {"_id": p["_id"]},
            {"$set": {"en_r2": True, "r2_key": clave, "en_r2_at": now_iso()}},
        )
        stats["app_subidas"] += 1
        stats["bytes"] += len(data)
        if i % 50 == 0 or i == len(pendientes):
            print(f"  [{i}/{len(pendientes)}] subidas={stats['app_subidas']} "
                  f"{stats['bytes'] / 1024 / 1024:.0f} MB")


# ---------------------------------------------------------------- fase 2: calma (disco)

def migrar_calma(db, r2, escribir, limite, stats):
    print("\n===== FASE 2: calma_raw.fotos_descargadas (disco) -> calma/... =====")
    if not os.path.isdir(FOTOS_CALMA_DIR):
        print(f"  OJO: no existe {FOTOS_CALMA_DIR}; esta fase solo tiene sentido en el VPS.")
        return

    plan = []          # (_id del doc, email, entrada)
    ya = 0
    sin_fichero = 0
    for doc in db.calma_raw.find(
        {"fotos_descargadas.0": {"$exists": True}},
        {"_id": 1, "email": 1, "fotos_descargadas": 1},
    ):
        for entrada in doc.get("fotos_descargadas") or []:
            fichero = entrada.get("file")
            if not fichero:
                continue
            if entrada.get("en_r2"):
                ya += 1
                continue
            if not ruta_en_disco(fichero):
                sin_fichero += 1
                continue
            plan.append((doc["_id"], doc.get("email"), entrada))

    print(f"  ya en R2 (marcadas): {ya}")
    print(f"  registros sin fichero en disco (se saltan): {sin_fichero}")
    print(f"  pendientes: {len(plan)}"
          f"  (~{sum(e.get('size') or 0 for _, _, e in plan) / 1024 / 1024:.1f} MB segun `size`)")

    if limite:
        plan = plan[:limite]
    if not escribir:
        return

    for i, (doc_id, email, entrada) in enumerate(plan, 1):
        fichero = entrada["file"]
        clave = "calma/" + fichero
        full = ruta_en_disco(fichero)
        if not full:                     # por si el disco cambia a mitad
            stats["calma_sin_fichero"] += 1
            continue
        try:
            with open(full, "rb") as fh:
                data = fh.read()
            r2.put_object(
                Bucket=BUCKET, Key=clave, Body=data,
                ContentType=entrada.get("content_type") or content_type_de(fichero),
            )
        except Exception as e:
            stats["errores"] += 1
            print(f"  ERROR subiendo {clave}: {str(e)[:200]}")
            continue
        # Se marca SOLO esa entrada del array (elemMatch + posicional): reanudable
        # foto a foto, y si hubiera un `file` repetido se van marcando de una en una.
        db.calma_raw.update_one(
            {"_id": doc_id,
             "fotos_descargadas": {"$elemMatch": {"file": fichero, "en_r2": {"$ne": True}}}},
            {"$set": {"fotos_descargadas.$.en_r2": True,
                      "fotos_descargadas.$.r2_key": clave,
                      "fotos_descargadas.$.en_r2_at": now_iso()}},
        )
        stats["calma_subidas"] += 1
        stats["bytes"] += len(data)
        if i % 100 == 0 or i == len(plan):
            print(f"  [{i}/{len(plan)}] subidas={stats['calma_subidas']} "
                  f"{stats['bytes'] / 1024 / 1024:.0f} MB")


# ---------------------------------------------------------------- verificacion

def verificar(db, r2):
    """head_object de una muestra de lo marcado en_r2: lo que Mongo dice que esta
    en el bucket tiene que estar de verdad."""
    print("\n===== VERIFICACION (muestra) =====")
    claves = []
    for doc in db.client_photos.find({"en_r2": True}, {"r2_key": 1, "user_id": 1,
                                                       "client_id": 1, "id": 1}):
        claves.append(doc.get("r2_key") or clave_app(doc))
    n_app = len(claves)
    n_calma = 0
    for doc in db.calma_raw.find({"fotos_descargadas.en_r2": True}, {"fotos_descargadas": 1}):
        for e in doc.get("fotos_descargadas") or []:
            if e.get("en_r2"):
                claves.append(e.get("r2_key") or ("calma/" + (e.get("file") or "")))
                n_calma += 1
    print(f"  marcadas en_r2: {n_app} de la app + {n_calma} de calma = {len(claves)}")
    if not claves:
        return
    muestra = random.sample(claves, min(MUESTRA_VERIFICAR, len(claves)))
    mal = 0
    for clave in muestra:
        try:
            r2.head_object(Bucket=BUCKET, Key=clave)
        except Exception as e:
            mal += 1
            print(f"  FALTA en el bucket: {clave} ({str(e)[:120]})")
    print(f"  muestra comprobada: {len(muestra) - mal}/{len(muestra)} en el bucket")
    if mal:
        print("  OJO: hay marcas en_r2 sin objeto detras. Revisar antes de seguir.")


def main():
    ap = argparse.ArgumentParser(description="Migra las fotos a R2 sin borrar el origen.")
    ap.add_argument("--escribir", action="store_true",
                    help="sube a R2 y marca en_r2 de verdad (sin esto, dry-run)")
    ap.add_argument("--verificar", action="store_true",
                    help="solo comprobar una muestra de lo ya marcado")
    ap.add_argument("--limite", type=int, default=0, help="tope de fotos (pruebas)")
    args = ap.parse_args()

    print(f"Mongo:  {sin_secretos(MONGO_URL)}  db={DB_NAME}")
    print(f"R2:     bucket={BUCKET}  endpoint={os.environ.get('R2_ENDPOINT', '(sin poner)')}")
    print(f"Disco:  {FOTOS_CALMA_DIR}")
    print(f"Modo:   {'ESCRIBIR' if args.escribir else 'verificar' if args.verificar else 'dry-run'}")

    r2 = cliente_r2()
    if (args.escribir or args.verificar) and not r2:
        print("\nFaltan las credenciales de R2 en el entorno (R2_ACCESS_KEY_ID / "
              "R2_SECRET_ACCESS_KEY). Sin ellas solo se puede hacer el dry-run.")
        sys.exit(1)

    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    db = cli[DB_NAME]
    db.command("ping")

    if args.verificar:
        verificar(db, r2)
        return

    stats = {"app_subidas": 0, "app_sin_blob": 0, "calma_subidas": 0,
             "calma_sin_fichero": 0, "errores": 0, "bytes": 0}
    migrar_app(db, r2, args.escribir, args.limite, stats)
    migrar_calma(db, r2, args.escribir, args.limite, stats)

    if not args.escribir:
        print("\n(dry-run: no se ha subido ni marcado nada. Añade --escribir para migrar.)")
        return

    print("\n===== RESUMEN =====")
    for k, v in stats.items():
        print(f"  {k}: {v / 1024 / 1024:.1f} MB" if k == "bytes" else f"  {k}: {v}")
    if stats["errores"]:
        print("  Hubo errores: relanzar cuando pase la tormenta; lo subido queda marcado.")
    verificar(db, r2)


if __name__ == "__main__":
    main()
