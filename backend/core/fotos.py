# -*- coding: utf-8 -*-
"""
Las fotos del cliente, TODAS, en un solo sitio (tarea 1.1 del plan del lunes).

Hoy conviven dos almacenes: las fotos subidas desde la app (Mongo, coleccion
`client_photos`, con el binario en `data`) y las importadas de Calma (disco del
servidor, `_fotos_calma/`, con el registro en `calma_raw.fotos_descargadas`).
El panel de admin ya las funde; la pantalla del cliente solo veia las de la app,
y 436 clientes importados se encontraban un "todavia no has subido fotos" con
sus fotos a un metro.

Este modulo es la UNICA puerta: `listar_fotos_de` devuelve la lista fundida y
`abrir_foto` sirve una foto validando siempre que es del que la pide. Los
endpoints y el frontend no se tocan.

R2 (desde el 22-08): el almacen definitivo es Cloudflare R2 (bucket privado
`jg12-fotos`, jurisdiccion UE). CONVENIO DE CLAVES en el bucket:
  - nativas de la app:  app/{user_id}/{photo_id}   (si el doc no tiene user_id,
    la trampa de abajo, se usa el client_id; la migracion deja la clave exacta
    en `r2_key` y aqui se lee esa antes de reconstruir nada).
  - importadas de Calma: calma/{ruta original}, la misma ruta `file` que ya
    viaja en calma_raw.fotos_descargadas (p. ej. calma/ana_gmail.com/mensuales__....jpg).
La marca de "este objeto ya esta en R2" es el campo `en_r2` (en el doc de
client_photos o en la entrada de fotos_descargadas); la pone _migrar_fotos_a_r2.py.

Estados posibles, los dos validos:
  - SIN credenciales R2 en el .env: todo funciona como siempre (Mongo + disco).
  - CON credenciales: las fotos con `en_r2` se listan ademas con una `url`
    firmada de 10 minutos y `abrir_foto` lee de R2; si R2 falla, se cae al
    origen viejo (Mongo/disco) y el detalle va a consola. R2 caido no puede
    dejar a un cliente sin fotos mientras el origen viejo exista.

La ref de una foto:
  - de la app:   su `id` de `client_photos` (un uuid).
  - de Calma:    "calma/<fichero>", el mismo `file` registrado en
                 `calma_raw.fotos_descargadas` (carpeta/nombre, con una barra).

Trampa conocida que este modulo tapa: el cliente filtraba `client_photos` por
`user_id` y el admin por `client_id`; un documento con `client_id` pero sin
`user_id` era invisible para su dueño. Aqui se busca por los dos.

En dev el directorio `_fotos_calma` puede no existir o estar a medias: la lista
sale sin las fotos que no esten en disco, sin excepcion.
"""
import asyncio
import os
import re
from typing import Optional, Tuple

from fastapi import HTTPException

from core.database import db

# El mismo directorio que sirve el endpoint de admin (routes/admin.py). En el pod
# de produccion esta montado como /app/_fotos_calma.
_FOTOS_CALMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_fotos_calma")

CALMA_PREFIX = "calma/"

# Segundos de vida de la url firmada que acompaña a cada foto en la lista.
_URL_FIRMADA_SEGUNDOS = 600

# El cliente S3 contra R2 se construye UNA vez y solo si hay credenciales.
# boto3 se importa dentro para que dev y tests funcionen sin tenerlo instalado.
_r2_estado = {"cliente": None, "intentado": False}


def _cliente_r2():
    """El cliente S3 contra R2, o None si no hay credenciales (o boto3 falla).

    Con R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY vacios en el .env este modulo
    se comporta exactamente como antes de R2: Mongo + disco."""
    if _r2_estado["intentado"]:
        return _r2_estado["cliente"]
    _r2_estado["intentado"] = True
    access = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    endpoint = os.environ.get("R2_ENDPOINT", "").strip()
    if not (access and secret and endpoint):
        return None
    try:
        import boto3
        from botocore.config import Config
        _r2_estado["cliente"] = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
    except Exception as e:
        # Sin drama: se sigue sirviendo desde Mongo/disco. El detalle, a consola.
        print(f"[fotos] R2 configurado pero el cliente no arranca: {e}")
        _r2_estado["cliente"] = None
    return _r2_estado["cliente"]


def _bucket_r2() -> str:
    return os.environ.get("R2_BUCKET", "jg12-fotos").strip() or "jg12-fotos"


def _clave_r2_app(doc: dict) -> str:
    """La clave en el bucket de una foto nativa. La migracion deja la exacta en
    `r2_key`; si no esta, se reconstruye por convenio (user_id, o client_id si
    el doc es de los de la trampa sin user_id)."""
    if doc.get("r2_key"):
        return doc["r2_key"]
    dueno = doc.get("user_id") or doc.get("client_id") or "sin-dueno"
    return f"app/{dueno}/{doc.get('id')}"


def _clave_r2_calma(fichero: str) -> str:
    return CALMA_PREFIX + fichero


def _url_firmada(r2, clave: str) -> Optional[str]:
    """Una url GET firmada de 10 minutos, o None si no se pudo firmar (la lista
    sale igual y el front sigue pidiendo por /reports/foto/{ref})."""
    try:
        return r2.generate_presigned_url(
            "get_object",
            Params={"Bucket": _bucket_r2(), "Key": clave},
            ExpiresIn=_URL_FIRMADA_SEGUNDOS,
        )
    except Exception as e:
        print(f"[fotos] no se pudo firmar la url de {clave}: {e}")
        return None


async def _leer_de_r2(r2, clave: str) -> Tuple[bytes, Optional[str]]:
    """El objeto entero desde R2 (en un hilo: boto3 es sincrono). Deja que la
    excepcion suba: el que llama decide el fallback."""
    resp = await asyncio.to_thread(r2.get_object, Bucket=_bucket_r2(), Key=clave)
    data = await asyncio.to_thread(resp["Body"].read)
    return data, resp.get("ContentType")

# El mismo mapeo de pose que usa el panel (ClientDetailPage._poseDeKind), pero a las
# claves que entiende la pantalla del cliente ('frente' | 'perfil' | 'espalda').
_POSES = (
    ("frente", re.compile(r"frent|frontal|delante|front")),
    ("espalda", re.compile(r"espald|atras|atrás|trasera|back|dorsal")),
    ("perfil", re.compile(r"lateral|perfil|lado|side")),
)

_FECHA_EN_NOMBRE = re.compile(r"(\d{4}-\d{2}-\d{2})")

_CONTENT_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".gif": "image/gif",
}


def es_ref_calma(ref: str) -> bool:
    return isinstance(ref, str) and ref.startswith(CALMA_PREFIX)


def _pose_de_kind(kind: Optional[str]) -> Optional[str]:
    k = (kind or "").lower()
    for pose, patron in _POSES:
        if patron.search(k):
            return pose
    return None


def _content_type_de(fichero: str) -> str:
    return _CONTENT_TYPES.get(os.path.splitext(fichero)[1].lower(), "image/jpeg")


def _ruta_en_disco(fichero: str) -> Optional[str]:
    """La ruta absoluta del fichero de Calma, o None si se sale del directorio
    (path traversal) o no existe. Mismo candado que el endpoint de admin."""
    full = os.path.normpath(os.path.join(_FOTOS_CALMA_DIR, fichero))
    if not full.startswith(_FOTOS_CALMA_DIR + os.sep):
        return None
    if not os.path.isfile(full):
        return None
    return full


async def _client_id_de(user: dict) -> Optional[str]:
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    return profile["id"] if profile else None


def _filtro_del_dueno(user: dict, client_id: Optional[str]) -> dict:
    """Por user_id O por client_id: es lo que tapa la trampa del documento con
    `client_id` pero sin `user_id` (invisible para su dueño hasta ahora)."""
    condiciones = [{"user_id": user["id"]}]
    if client_id:
        condiciones.append({"client_id": client_id})
    return {"$or": condiciones}


async def _registro_calma_de(user: dict, client_id: Optional[str]) -> list:
    """Las fotos registradas en calma_raw para ESTE cliente (mismo criterio de
    cruce que el endpoint de admin: por client_id o por user_id)."""
    raw = await db.calma_raw.find_one(
        _filtro_del_dueno(user, client_id), {"_id": 0, "fotos_descargadas": 1})
    return (raw or {}).get("fotos_descargadas") or []


def _meta_app(doc: dict) -> dict:
    """Los mismos campos que siempre devolvio /reports/photos, mas fuente y ref."""
    return {
        "id":           doc.get("id"),
        "ref":          doc.get("id"),
        "fuente":       "app",
        "client_id":    doc.get("client_id"),
        "user_id":      doc.get("user_id"),
        "filename":     doc.get("filename"),
        "content_type": doc.get("content_type"),
        "size":         doc.get("size"),
        "taken_at":     doc.get("taken_at"),
        "uploaded_at":  doc.get("uploaded_at"),
        "pose":         doc.get("pose"),
        "inicial":      bool(doc.get("inicial")),
    }


def _meta_calma(entrada: dict, con_r2: bool = False) -> Optional[dict]:
    """Una entrada de fotos_descargadas como foto del cliente, o None si no se
    puede servir (sin fichero en disco ni objeto en R2, o sin fecha con la que
    ordenarla). Con R2 configurado, una entrada `en_r2` se sirve aunque el
    fichero ya no este en el disco."""
    fichero = entrada.get("file")
    if not fichero:
        return None
    servible = bool(_ruta_en_disco(fichero)) or (con_r2 and entrada.get("en_r2"))
    if not servible:
        return None
    fecha = entrada.get("fecha")
    if not fecha:
        m = _FECHA_EN_NOMBRE.search(os.path.basename(fichero))
        fecha = m.group(1) if m else None
    if not fecha:
        # Sin fecha no hay donde colocarla en la linea temporal del cliente.
        return None
    ref = CALMA_PREFIX + fichero
    return {
        # La ref viaja tambien como `id`: las pantallas que ya piden el binario
        # por /reports/photos/{id} cargan estas sin cambiar ni una linea.
        "id":           ref,
        "ref":          ref,
        "fuente":       "calma",
        "client_id":    None,
        "user_id":      None,
        "filename":     os.path.basename(fichero),
        "content_type": entrada.get("content_type") or _content_type_de(fichero),
        "size":         entrada.get("size"),
        "taken_at":     fecha,
        "uploaded_at":  None,
        "pose":         _pose_de_kind(entrada.get("kind")),
        "inicial":      False,
    }


async def listar_fotos_de(user: dict) -> list:
    """Todas las fotos del cliente (app + Calma), mas recientes primero, solo metadatos.

    Cada foto lleva `fuente` ("app" | "calma") y `ref` con la que pedirla a
    `abrir_foto`. Las de Calma que no esten en el disco (dev sin `_fotos_calma`,
    o un registro huerfano) simplemente no salen, salvo que ya esten en R2.

    Con R2 configurado, las fotos con objeto en el bucket (`en_r2`) llevan
    ademas `url`: una url firmada de 10 minutos para que el navegador tire
    directo de R2. Sin R2 (o sin objeto) no hay `url` y el front sigue pidiendo
    el binario por /reports/foto/{ref}, como siempre.
    """
    client_id = await _client_id_de(user)
    r2 = _cliente_r2()

    cursor = db.client_photos.find(
        _filtro_del_dueno(user, client_id), {"_id": 0, "data": 0}).sort("taken_at", -1)
    docs = await cursor.to_list(length=200)

    fotos = []
    for d in docs:
        meta = _meta_app(d)
        if r2 and d.get("en_r2"):
            url = _url_firmada(r2, _clave_r2_app(d))
            if url:
                meta["url"] = url
        fotos.append(meta)
    for entrada in await _registro_calma_de(user, client_id):
        meta = _meta_calma(entrada, con_r2=bool(r2))
        if not meta:
            continue
        if r2 and entrada.get("en_r2"):
            url = _url_firmada(r2, _clave_r2_calma(entrada["file"]))
            if url:
                meta["url"] = url
        fotos.append(meta)

    # Todo junto y por fecha: las ISO completas de la app y los YYYY-MM-DD de
    # Calma ordenan bien como texto (mismo prefijo).
    fotos.sort(key=lambda f: f.get("taken_at") or "", reverse=True)
    return fotos


async def abrir_foto(user: dict, ref: str) -> Tuple[bytes, str]:
    """El binario y el content-type de UNA foto del cliente, validando SIEMPRE
    que es suya. Levanta HTTPException 404 (no existe o no es suya y no hay por
    que contarle mas) o 403 (existe pero es de otro, en las de la app).

    Con R2 configurado y la foto marcada `en_r2`, el binario sale de R2; si R2
    falla se cae al origen viejo (Mongo/disco) con el detalle a consola."""
    client_id = await _client_id_de(user)
    r2 = _cliente_r2()

    if es_ref_calma(ref):
        fichero = ref[len(CALMA_PREFIX):]
        # La ref se valida contra la lista registrada de ESTE cliente (el mismo
        # criterio que el endpoint de admin): nada de rutas libres.
        registro = await _registro_calma_de(user, client_id)
        entrada = next((f for f in registro if f.get("file") == fichero), None)
        if not entrada:
            raise HTTPException(status_code=404, detail="Foto no encontrada")
        if r2 and entrada.get("en_r2"):
            clave = _clave_r2_calma(fichero)
            try:
                data, ct = await _leer_de_r2(r2, clave)
                return data, entrada.get("content_type") or ct or _content_type_de(fichero)
            except Exception as e:
                print(f"[fotos] R2 fallo leyendo {clave}, se cae al disco: {e}")
        full = _ruta_en_disco(fichero)
        if not full:
            raise HTTPException(status_code=404, detail="Foto no encontrada")
        with open(full, "rb") as fh:
            data = fh.read()
        return data, entrada.get("content_type") or _content_type_de(fichero)

    doc = await db.client_photos.find_one({"id": ref}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    es_suya = doc.get("user_id") == user["id"] or (
        client_id is not None and doc.get("client_id") == client_id)
    if not es_suya:
        raise HTTPException(status_code=403, detail="Esa foto no es tuya.")
    if r2 and doc.get("en_r2"):
        clave = _clave_r2_app(doc)
        try:
            data, ct = await _leer_de_r2(r2, clave)
            return data, doc.get("content_type") or ct or "application/octet-stream"
        except Exception as e:
            print(f"[fotos] R2 fallo leyendo {clave}, se cae a Mongo: {e}")
    data = doc.get("data")
    if not data:
        raise HTTPException(status_code=404, detail="Foto sin datos")
    return bytes(data), doc.get("content_type") or "application/octet-stream"
