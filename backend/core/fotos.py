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
`abrir_foto` sirve una foto validando siempre que es del que la pide. La semana
que viene el almacen migra a Cloudflare R2: cuando pase, cambia SOLO la tripa
de estas dos funciones; los endpoints y el frontend no se tocan.

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
import os
import re
from typing import Optional, Tuple

from fastapi import HTTPException

from core.database import db

# El mismo directorio que sirve el endpoint de admin (routes/admin.py). En el pod
# de produccion esta montado como /app/_fotos_calma.
_FOTOS_CALMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_fotos_calma")

CALMA_PREFIX = "calma/"

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


def _meta_calma(entrada: dict) -> Optional[dict]:
    """Una entrada de fotos_descargadas como foto del cliente, o None si no se
    puede servir (sin fichero en disco, o sin fecha con la que ordenarla)."""
    fichero = entrada.get("file")
    if not fichero or not _ruta_en_disco(fichero):
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
    o un registro huerfano) simplemente no salen.
    """
    client_id = await _client_id_de(user)

    cursor = db.client_photos.find(
        _filtro_del_dueno(user, client_id), {"_id": 0, "data": 0}).sort("taken_at", -1)
    docs = await cursor.to_list(length=200)

    fotos = [_meta_app(d) for d in docs]
    for entrada in await _registro_calma_de(user, client_id):
        meta = _meta_calma(entrada)
        if meta:
            fotos.append(meta)

    # Todo junto y por fecha: las ISO completas de la app y los YYYY-MM-DD de
    # Calma ordenan bien como texto (mismo prefijo).
    fotos.sort(key=lambda f: f.get("taken_at") or "", reverse=True)
    return fotos


async def abrir_foto(user: dict, ref: str) -> Tuple[bytes, str]:
    """El binario y el content-type de UNA foto del cliente, validando SIEMPRE
    que es suya. Levanta HTTPException 404 (no existe o no es suya y no hay por
    que contarle mas) o 403 (existe pero es de otro, en las de la app)."""
    client_id = await _client_id_de(user)

    if es_ref_calma(ref):
        fichero = ref[len(CALMA_PREFIX):]
        # La ref se valida contra la lista registrada de ESTE cliente (el mismo
        # criterio que el endpoint de admin): nada de rutas libres.
        registro = await _registro_calma_de(user, client_id)
        entrada = next((f for f in registro if f.get("file") == fichero), None)
        if not entrada:
            raise HTTPException(status_code=404, detail="Foto no encontrada")
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
    data = doc.get("data")
    if not data:
        raise HTTPException(status_code=404, detail="Foto sin datos")
    return bytes(data), doc.get("content_type") or "application/octet-stream"
