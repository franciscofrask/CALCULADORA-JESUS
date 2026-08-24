# -*- coding: utf-8 -*-
"""
Sincroniza a PRODUCCION las fotos de progreso de Calma que falten, sin duplicar ninguna.

Continuacion de _descargar_fotos_activos.py (el que bajo las 5.118 que ya hay en el
servidor). Reutiliza SU MISMO formato de nombres y SU MISMO esquema de metadatos,
porque el endpoint que las sirve (GET /admin/clients/{id}/calma-foto, routes/admin.py)
valida que el `file` pedido este en calma_raw.fotos_descargadas: si cambiamos el
nombre, las fotos dejan de verse.

Que hace, y por que:
- Ambito: SOLO los clientes con cuenta en la app (177 en prod tienen user_id), cruzados
  por email. Primero los que tienen la membresia viva (fin_membresia >= hoy), que son los
  que el entrenador mira. En el bucket hay 425 clientes: los 248 restantes no interesan.
- Antideduplicado: el conjunto de "lo que ya esta" se construye por `bucket_path` (la ruta
  de origen en Storage), NO por nombre de fichero. Dos blobs distintos pueden acabar en el
  mismo nombre local, y el mismo blob puede haberse guardado con nombre distinto; la ruta
  de Storage es la unica clave estable.
- Ademas se comprueba que el fichero EXISTE de verdad en el disco del servidor: hay
  entradas en fotos_descargadas cuyo fichero no esta (se re-bajan) y ficheros en disco sin
  entrada (se re-registran). El recuento de disco (5.118) no cuadra con el de clientes con
  registro (107 de 114 carpetas), asi que este cruce no es teorico.
- Idempotente: el registro se FUSIONA por bucket_path, nunca se reemplaza a ciegas, y los
  ficheros ya presentes no se vuelven a bajar. Ejecutarlo dos veces no cambia nada.

Las fotos NO viven en Mongo, viven en el disco del servidor
(/opt/jg12/backend/_fotos_calma, montado en el pod como /app/_fotos_calma). Por eso el
flujo es: Storage -> disco local de staging -> un unico tar por ssh -> Mongo.

Uso (desde backend/, con el tunel a prod abierto en 27018):
  venv/Scripts/python.exe _sync_fotos.py                 # dry-run (por defecto)
  venv/Scripts/python.exe _sync_fotos.py --escribir      # baja, sube y registra
  venv/Scripts/python.exe _sync_fotos.py --solo-vivas    # limita a membresia viva
  venv/Scripts/python.exe _sync_fotos.py --verificar     # solo el recuento final
"""
import argparse
import asyncio
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

from google.cloud import storage as gcs
from google.oauth2 import service_account
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()

HERE = os.path.dirname(os.path.abspath(__file__))
BUCKET = "jesusgallegopt.appspot.com"
JPEG_Q = 92                      # el mismo que uso _descargar_fotos_activos.py
PREFIJO = "archivosFormularios/"

from _destino_sync import destino, rotulo   # --dev escribe en desarrollo
MONGO_URI, BASE_DESTINO = destino()
MONGO_URI = os.environ.get("PROD_MONGO_URI", MONGO_URI)
MONGO_DB = os.environ.get("PROD_MONGO_DB", "jg12_prod")

SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519_jg12")
SSH_HOST = "root@s1.jesusgallegopt.com"
REMOTE_DIR = "/opt/jg12/backend/_fotos_calma"

# Staging local: aqui se deja lo que hay que subir antes de mandarlo de una sola vez.
STAGING = os.path.join(HERE, "_fotos_sync_staging")
# Cache local de _descargar_fotos_activos.py: 5.033 ficheros ya bajados y ya convertidos.
# Si el fichero esta aqui, nos ahorramos volver a bajarlo y volver a convertirlo.
CACHE_LOCAL = os.path.join(HERE, "_fotos_calma")
# El listado del bucket son 10.982 blobs; cachearlo hace que un segundo dry-run sea instantaneo.
CACHE_BLOBS = os.path.join(HERE, "_fotos_sync_blobs.json")

MARGEN_DISCO_GB = 5.0            # no dejamos el disco del servidor al limite


def ssh(cmd, timeout=180):
    """Un comando por ssh en el servidor de produccion."""
    p = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=20",
         SSH_HOST, cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    if p.returncode != 0:
        raise RuntimeError(f"ssh fallo ({p.returncode}): {p.stderr.strip()[:300]}")
    return p.stdout


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def safe(s):
    """Mismo saneado de email a carpeta que _descargar_fotos_activos.py. No tocar."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)


FN_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[_-](.+)\.([A-Za-z0-9]+)$")


def parse_nombre(fname):
    """'2025-08-18_Espalda.jpeg' -> ('2025-08-18', 'Espalda', 'jpeg'). Igual que el original."""
    m = FN_RE.match(fname)
    if m:
        return m.group(1), m.group(2), m.group(3).lower()
    return None, os.path.splitext(fname)[0], (fname.rsplit(".", 1)[-1].lower() if "." in fname else "")


def destino(email, tipo, blob_name):
    """Ruta relativa de destino, calcada de _descargar_fotos_activos.py.

    Ojo: la carpeta se calcula con el email TAL COMO ESTA EN calma_raw (no el del bucket),
    porque asi se generaron las 5.118 que ya hay y asi lo busca el endpoint.
    """
    fname = blob_name.split("/")[-1]
    fecha, kind, ext = parse_nombre(fname)
    es_heic = ext in ("heic", "heif")
    base = f"{tipo}__{os.path.splitext(fname)[0]}"
    out_name = base + (".jpg" if es_heic else "." + ext)
    return f"{safe(email)}/{out_name}", fecha, kind, ext, es_heic


# ---------------------------------------------------------------- inventarios

def listar_bucket(usar_cache=True):
    """Todos los blobs de archivosFormularios/ de una vez.

    Un solo listado paginado en lugar de 177 x 2 llamadas: mismo resultado, mucho mas rapido.
    """
    if usar_cache and os.path.exists(CACHE_BLOBS):
        with open(CACHE_BLOBS, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        print(f"  bucket: {len(data)} blobs (cache {CACHE_BLOBS})")
        return data

    creds = service_account.Credentials.from_service_account_file(
        os.path.join(HERE, "serviceAccountKey.json"))
    client = gcs.Client(credentials=creds, project=creds.project_id)
    out = []
    for blob in client.list_blobs(BUCKET, prefix=PREFIJO):
        if blob.name.endswith("/"):
            continue
        out.append({"name": blob.name, "size": blob.size or 0,
                    "content_type": blob.content_type or ""})
    with open(CACHE_BLOBS, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print(f"  bucket: {len(out)} blobs listados")
    return out


def indexar_bucket(blobs):
    """{email_minusculas: [(tipo, blob), ...]}.

    Se indexa en minusculas porque las carpetas del bucket las creo el usuario al subir el
    formulario y la caja del email no tiene por que coincidir con la de calma_raw: si
    cruzamos en exacto se nos cae gente sin enterarnos.
    """
    idx = {}
    for b in blobs:
        partes = b["name"].split("/")
        # archivosFormularios/<tipo>/<email>/<fichero>
        if len(partes) < 4:
            continue
        tipo, email = partes[1], partes[2]
        if tipo not in ("iniciales", "mensuales"):
            continue
        idx.setdefault(email.strip().lower(), []).append((tipo, b))
    return idx


def listar_disco_servidor():
    """{ruta_relativa: size} de lo que hay AHORA en el disco del servidor."""
    salida = ssh(f'cd {REMOTE_DIR} && find . -type f -printf "%P\\t%s\\n"', timeout=300)
    disco = {}
    for linea in salida.splitlines():
        if not linea.strip():
            continue
        ruta, _, size = linea.rpartition("\t")
        disco[ruta.replace("\\", "/")] = int(size or 0)
    return disco


def libre_gb_servidor():
    salida = ssh("df -PBK /opt | tail -1")
    campos = salida.split()
    return int(campos[3].rstrip("K")) / 1024 / 1024


# ---------------------------------------------------------------- analisis

async def cargar_clientes(db, solo_vivas):
    """Los clientes con cuenta en la app, con la membresia viva delante.

    user_id != None es la marca de "tiene cuenta": son 177 de los 1.324 de calma_raw.
    """
    hoy = datetime.date.today().isoformat()
    clientes = []
    async for d in db.calma_raw.find(
        {"user_id": {"$ne": None}},
        {"_id": 0, "email": 1, "nombre": 1, "user_id": 1, "client_id": 1,
         "fin_membresia": 1, "fotos_descargadas": 1, "foto_paths": 1},
    ):
        email = (d.get("email") or "").strip()
        if not email:
            continue
        fin = (d.get("fin_membresia") or "")[:10]
        d["_viva"] = bool(fin and fin >= hoy)
        d["email"] = email
        clientes.append(d)
    if solo_vivas:
        clientes = [c for c in clientes if c["_viva"]]
    # Las vivas primero: si algo peta a mitad, lo que se ha bajado es lo que mas se mira.
    clientes.sort(key=lambda c: (not c["_viva"], c["email"].lower()))
    return clientes


def analizar(clientes, idx_bucket, disco):
    """Cruza los tres inventarios y devuelve el plan + los descuadres.

    ya_ok = registrado por bucket_path Y con el fichero presente en el disco del servidor.
    Cualquier otra cosa se considera pendiente: es la unica forma de que un registro
    huerfano (sin fichero) se arregle solo.
    """
    plan = []                       # blobs que hay que bajar y subir
    solo_registro = []              # entrada en fotos_descargadas sin fichero en disco
    solo_disco = []                 # fichero en disco sin entrada que lo referencie
    dup_registro = []               # bucket_path repetido dentro del mismo cliente
    ya = 0
    sin_carpeta_bucket = []

    for c in clientes:
        email = c["email"]
        fotos = c.get("fotos_descargadas") or []

        vistos = set()
        por_bucket = {}
        for f in fotos:
            bp = f.get("bucket_path")
            if not bp:
                continue
            if bp in vistos:
                dup_registro.append((email, bp))
                continue
            vistos.add(bp)
            por_bucket[bp] = f

        # Registro que apunta a un fichero que no esta: se vuelve a bajar.
        for bp, f in por_bucket.items():
            if f.get("file") not in disco:
                solo_registro.append((email, bp, f.get("file")))

        # Fichero en disco de este cliente que ningun registro referencia.
        carpeta = safe(email) + "/"
        referenciados = {f.get("file") for f in fotos}
        for ruta in disco:
            if ruta.startswith(carpeta) and ruta not in referenciados:
                solo_disco.append((email, ruta))

        entradas = idx_bucket.get(email.lower(), [])
        if not entradas:
            # Distinguimos dos cosas muy distintas: el que nunca subio fotos, y el que
            # segun Firestore (foto_paths) SI las subio pero en Storage no estan. El
            # segundo es un agujero real que no arregla ninguna descarga.
            sin_carpeta_bucket.append((email, len(c.get("foto_paths") or [])))
            continue

        for tipo, blob in entradas:
            bp = blob["name"]
            f = por_bucket.get(bp)
            if f and f.get("file") in disco:
                ya += 1
                continue
            rel, fecha, kind, ext, es_heic = destino(email, tipo, bp)
            plan.append({
                "email": email, "tipo": tipo, "kind": kind, "fecha": fecha,
                "file": rel, "bucket_path": bp, "es_heic": es_heic,
                "content_type": "image/jpeg" if es_heic else blob["content_type"],
                "bytes_origen": blob["size"], "viva": c["_viva"],
            })

    return {"plan": plan, "ya": ya, "solo_registro": solo_registro,
            "solo_disco": solo_disco, "dup_registro": dup_registro,
            "sin_carpeta_bucket": sin_carpeta_bucket}


def informe(res, clientes):
    plan = res["plan"]
    mb = sum(p["bytes_origen"] for p in plan) / 1024 / 1024
    emails = {p["email"] for p in plan}
    vivas = {p["email"] for p in plan if p["viva"]}

    print("\n===== DRY-RUN: lo que falta en produccion =====")
    print(f"  clientes en ambito (cuenta en la app): {len(clientes)}"
          f"   (membresia viva: {sum(1 for c in clientes if c['_viva'])})")
    print(f"  fotos ya presentes (registro + fichero): {res['ya']}")
    print(f"  fotos QUE FALTAN: {len(plan)}  de {len(emails)} clientes"
          f"  ({len(vivas)} con membresia viva)")
    print(f"  espacio a ocupar: {mb:.1f} MB  ({mb/1024:.2f} GB)")

    por_tipo = {}
    por_pose = {}
    for p in plan:
        por_tipo[p["tipo"]] = por_tipo.get(p["tipo"], 0) + 1
        por_pose[p["kind"] or "(sin pose)"] = por_pose.get(p["kind"] or "(sin pose)", 0) + 1
    print("\n  por tipo:")
    for k, v in sorted(por_tipo.items(), key=lambda x: -x[1]):
        print(f"    {k:12s} {v}")
    print("  por pose:")
    for k, v in sorted(por_pose.items(), key=lambda x: -x[1])[:15]:
        print(f"    {k:24s} {v}")

    print("\n  descuadres entre disco y registro:")
    print(f"    registros SIN fichero en disco: {len(res['solo_registro'])}")
    print(f"    ficheros en disco SIN registro: {len(res['solo_disco'])}")
    print(f"    bucket_path duplicados en el registro: {len(res['dup_registro'])}")
    for e, bp, f in res["solo_registro"][:5]:
        print(f"      [sin fichero] {e} -> {f}")
    for e, r in res["solo_disco"][:5]:
        print(f"      [sin registro] {e} -> {r}")

    sin = res["sin_carpeta_bucket"]
    prometidas = [(e, n) for e, n in sin if n]
    print(f"\n  clientes sin nada en el bucket: {len(sin)}"
          f"  (de ellos {len(prometidas)} con foto_paths en Firestore)")
    if prometidas:
        print("    OJO: Firestore dice que subieron fotos, pero en Storage no existen.")
        print("    No se pueden bajar; es un agujero de origen, no del sincronizador:")
        for e, n in prometidas:
            print(f"      {e}  ({n} rutas en foto_paths)")
    return mb


# ---------------------------------------------------------------- ejecucion

def preparar_staging(plan, stats):
    """Deja en STAGING los ficheros que faltan, listos para un unico tar.

    Si el fichero ya esta en el cache local de _descargar_fotos_activos.py se copia de ahi:
    ya esta bajado y ya esta convertido, y evita 20 GB de trafico repetido.
    """
    creds = service_account.Credentials.from_service_account_file(
        os.path.join(HERE, "serviceAccountKey.json"))
    client = gcs.Client(credentials=creds, project=creds.project_id)
    bucket = client.bucket(BUCKET)

    hechos = []
    for i, p in enumerate(plan, 1):
        destino_local = os.path.join(STAGING, p["file"].replace("/", os.sep))
        os.makedirs(os.path.dirname(destino_local), exist_ok=True)

        if os.path.exists(destino_local) and os.path.getsize(destino_local) > 0:
            stats["reintento_ok"] += 1        # ya estaba de una ejecucion anterior
        else:
            cache = os.path.join(CACHE_LOCAL, p["file"].replace("/", os.sep))
            if os.path.exists(cache) and os.path.getsize(cache) > 0:
                shutil.copy2(cache, destino_local)
                stats["del_cache"] += 1
            else:
                try:
                    data = bucket.blob(p["bucket_path"]).download_as_bytes()
                except Exception as e:
                    stats["errores"] += 1
                    print(f"  ERROR bajando {p['bucket_path']}: {str(e)[:120]}")
                    continue
                try:
                    if p["es_heic"]:
                        # El navegador no muestra HEIC: se convierte a JPG sin redimensionar.
                        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
                        img.save(destino_local, "JPEG", quality=JPEG_Q)
                        stats["convertidas"] += 1
                    else:
                        with open(destino_local, "wb") as fh:
                            fh.write(data)
                        stats["descargadas"] += 1
                except Exception as e:
                    stats["errores"] += 1
                    print(f"  ERROR guardando {p['bucket_path']}: {str(e)[:120]}")
                    continue

        p["size"] = os.path.getsize(destino_local)
        stats["bytes"] += p["size"]
        hechos.append(p)
        if i % 100 == 0 or i == len(plan):
            print(f"  staging [{i}/{len(plan)}]  baj={stats['descargadas']} "
                  f"conv={stats['convertidas']} cache={stats['del_cache']} "
                  f"{stats['bytes']/1024/1024:.0f}MB")
    return hechos


def subir(hechos):
    """Un solo tar por ssh en vez de N scp: una conexion, minutos en lugar de horas.

    La tuberia se monta en Python y no en el shell: la ruta de staging es de Windows
    (C:\\...\\) y meterla entre comillas en una linea de bash la rompe.
    """
    if not hechos:
        return
    print(f"\n  subiendo {len(hechos)} ficheros al servidor...")
    empaqueta = subprocess.Popen(
        ["tar", "-cf", "-", "-C", STAGING.replace("\\", "/"), "."],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    extrae = subprocess.Popen(
        ["ssh", "-i", SSH_KEY.replace("\\", "/"), "-o", "StrictHostKeyChecking=no",
         SSH_HOST, f"mkdir -p {REMOTE_DIR} && tar -xf - -C {REMOTE_DIR}"],
        stdin=empaqueta.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    empaqueta.stdout.close()
    _, err_ssh = extrae.communicate(timeout=7200)
    empaqueta.wait(timeout=60)
    if extrae.returncode != 0 or empaqueta.returncode != 0:
        raise RuntimeError(f"subida fallo (tar={empaqueta.returncode} ssh={extrae.returncode}): "
                           f"{err_ssh.decode('utf-8', 'replace')[:400]}")
    print("  subida terminada")


async def registrar(db, hechos, stats):
    """Fusiona en calma_raw.fotos_descargadas SIN duplicar.

    Se lee lo que hay, se indexa por bucket_path y se sobrescribe esa clave. Asi una segunda
    pasada no añade nada, y de paso se limpian los bucket_path repetidos que hubiera.
    """
    por_email = {}
    for h in hechos:
        por_email.setdefault(h["email"], []).append(h)

    for email, nuevas in por_email.items():
        doc = await db.calma_raw.find_one({"email": email}, {"_id": 0, "fotos_descargadas": 1})
        actuales = (doc or {}).get("fotos_descargadas") or []
        idx = {}
        for f in actuales:
            bp = f.get("bucket_path")
            if bp:
                idx[bp] = f                       # el ultimo gana: deduplica de paso
        for h in nuevas:
            idx[h["bucket_path"]] = {
                "tipo": h["tipo"], "kind": h["kind"], "fecha": h["fecha"],
                "file": h["file"], "content_type": h["content_type"],
                "size": h["size"], "convertida_de_heic": h["es_heic"],
                "bucket_path": h["bucket_path"],
            }
        fotos = sorted(idx.values(), key=lambda x: (x.get("fecha") or "", x.get("kind") or ""))
        await db.calma_raw.update_one({"email": email}, {"$set": {
            "fotos_descargadas": fotos,
            "fotos_descargadas_n": len(fotos),
            "fotos_descargadas_at": now_iso(),
        }})
        stats["clientes_registrados"] += 1


async def verificar(db, clientes):
    """Recuento final: disco, registro y bucket_path repetidos."""
    disco = listar_disco_servidor()
    emails = {c["email"] for c in clientes}
    n_reg = 0
    dups = 0
    faltan_fichero = 0
    con_fotos = 0
    async for d in db.calma_raw.find({"user_id": {"$ne": None}},
                                     {"_id": 0, "email": 1, "fotos_descargadas": 1}):
        if d["email"] not in emails:
            continue
        fotos = d.get("fotos_descargadas") or []
        if fotos:
            con_fotos += 1
        n_reg += len(fotos)
        vistos = set()
        for f in fotos:
            bp = f.get("bucket_path")
            if bp in vistos:
                dups += 1
            vistos.add(bp)
            if f.get("file") not in disco:
                faltan_fichero += 1

    print("\n===== VERIFICACION =====")
    print(f"  ficheros en el disco del servidor: {len(disco)}")
    print(f"  tamano total en disco: {sum(disco.values())/1024/1024/1024:.2f} GB")
    print(f"  entradas en fotos_descargadas (clientes en ambito): {n_reg}"
          f"  de {con_fotos} clientes")
    print(f"  bucket_path REPETIDOS: {dups}")
    print(f"  entradas cuyo fichero NO esta en disco: {faltan_fichero}")


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--escribir", action="store_true",
                    help="baja, sube y registra de verdad (sin esto, dry-run)")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--solo-vivas", action="store_true",
                    help="limita a los clientes con la membresia viva")
    ap.add_argument("--verificar", action="store_true", help="solo el recuento final")
    ap.add_argument("--refrescar-bucket", action="store_true",
                    help="vuelve a listar el bucket en vez de usar la cache")
    ap.add_argument("--limite", type=int, default=0, help="tope de fotos (pruebas)")
    args = ap.parse_args()

    cli = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    db = cli[MONGO_DB]

    print("inventariando...")
    clientes = await cargar_clientes(db, args.solo_vivas)
    print(f"  clientes con cuenta en la app: {len(clientes)}")

    if args.verificar:
        await verificar(db, clientes)
        return

    blobs = listar_bucket(usar_cache=not args.refrescar_bucket)
    idx_bucket = indexar_bucket(blobs)
    disco = listar_disco_servidor()
    print(f"  disco del servidor: {len(disco)} ficheros, "
          f"{sum(disco.values())/1024/1024/1024:.2f} GB")

    res = analizar(clientes, idx_bucket, disco)
    if args.limite:
        res["plan"] = res["plan"][:args.limite]
    mb = informe(res, clientes)

    if not res["plan"]:
        print("\nNo falta nada. Produccion esta al dia.")
        return

    # Regla 4: medir antes de bajar. Si no cabe con margen, se para.
    libre = libre_gb_servidor()
    print(f"\n  disco libre en el servidor: {libre:.1f} GB")
    if libre - (mb / 1024) < MARGEN_DISCO_GB:
        print(f"  PARO: harian falta {mb/1024:.2f} GB y solo quedarian "
              f"{libre - mb/1024:.1f} GB libres (margen minimo {MARGEN_DISCO_GB} GB).")
        return

    if not args.escribir:
        print("\n(dry-run: no se ha tocado nada. Añade --escribir para bajarlas.)")
        return

    os.makedirs(STAGING, exist_ok=True)
    stats = {"descargadas": 0, "convertidas": 0, "del_cache": 0, "reintento_ok": 0,
             "errores": 0, "bytes": 0, "clientes_registrados": 0}
    print(f"\n===== BAJANDO {len(res['plan'])} fotos =====")
    hechos = preparar_staging(res["plan"], stats)
    subir(hechos)
    await registrar(db, hechos, stats)

    print("\n===== RESUMEN =====")
    for k, v in stats.items():
        print(f"  {k}: {v/1024/1024:.1f} MB" if k == "bytes" else f"  {k}: {v}")
    print(f"  fotos subidas: {len(hechos)} de {len({h['email'] for h in hechos})} clientes")

    # El staging solo sirve por si la subida falla a medias. Si todo fue bien se borra:
    # son copias de fotos que ya estan en el servidor y aqui solo ocupan.
    if not stats["errores"]:
        shutil.rmtree(STAGING, ignore_errors=True)

    await verificar(db, clientes)


asyncio.run(main())
