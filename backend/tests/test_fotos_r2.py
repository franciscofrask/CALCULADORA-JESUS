# -*- coding: utf-8 -*-
"""
La tripa R2 de core/fotos (22-08): mismo contrato, otro almacen.

Se prueba con la base falsa del patron de test_fotos_unificadas.py y un stub del
cliente S3 (monkeypatch sobre `fotos._cliente_r2`): sin servidor, sin boto3 y sin
tocar ningun bucket real.

Lo que fijan estos tests:
  - sin credenciales R2 todo va por el camino viejo (Mongo + disco), sin `url`,
  - con R2, `listar_fotos_de` añade la url firmada SOLO a las fotos con `en_r2`,
  - `abrir_foto` lee de R2 cuando hay marca y CAE al camino viejo si R2 falla:
    R2 caido no deja a nadie sin fotos mientras el origen viejo exista,
  - una foto de Calma que ya solo viva en R2 (sin fichero en disco) se sigue
    listando y sirviendo,
  - y la pertenencia se valida ANTES de mirar R2 (una ref ajena sigue en 403/404).
"""
import asyncio
import io

import pytest
from fastapi import HTTPException

from core import fotos


# ---------------------------------------------------------------- base falsa
# (el mismo lenguaje minimo de filtros que usa core/fotos: igualdad y $or)

def _casa(doc, filtro):
    for k, v in filtro.items():
        if k == "$or":
            if not any(_casa(doc, sub) for sub in v):
                return False
        elif doc.get(k) != v:
            return False
    return True


def _proyecta(doc, proyeccion):
    if not proyeccion:
        return dict(doc)
    fuera = {k for k, v in proyeccion.items() if v == 0}
    return {k: v for k, v in doc.items() if k not in fuera}


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, campo, sentido):
        self._docs = sorted(self._docs, key=lambda d: d.get(campo) or "",
                            reverse=(sentido == -1))
        return self

    async def to_list(self, length=None):
        return self._docs[:length] if length else self._docs


class _Coleccion:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, filtro, proyeccion=None):
        doc = next((d for d in self.docs if _casa(d, filtro)), None)
        return _proyecta(doc, proyeccion) if doc else None

    def find(self, filtro, proyeccion=None):
        return _Cursor([_proyecta(d, proyeccion) for d in self.docs if _casa(d, filtro)])


class _Base:
    def __init__(self):
        self.client_profiles = _Coleccion()
        self.client_photos = _Coleccion()
        self.calma_raw = _Coleccion()


# ---------------------------------------------------------------- stub de R2

class _StubR2:
    """Lo justo del cliente S3 que usa core/fotos: firmar urls y get_object."""

    def __init__(self):
        self.objetos = {}      # clave -> (bytes, content_type)
        self.fallar = False    # True = R2 caido: toda lectura revienta
        self.firmadas = []     # (clave, segundos) de cada url pedida
        self.leidas = []       # claves pedidas con get_object

    def generate_presigned_url(self, op, Params=None, ExpiresIn=None):
        assert op == "get_object"
        self.firmadas.append((Params["Key"], ExpiresIn))
        return f"https://r2.local/{Params['Bucket']}/{Params['Key']}?X-Amz-Expires={ExpiresIn}"

    def get_object(self, Bucket=None, Key=None):
        self.leidas.append(Key)
        if self.fallar:
            raise RuntimeError("R2 caido (stub)")
        if Key not in self.objetos:
            raise RuntimeError(f"NoSuchKey: {Key}")
        data, ct = self.objetos[Key]
        return {"Body": io.BytesIO(data), "ContentType": ct}


ANA = {"id": "u-ana"}

FICHERO_ANA = "ana_gmail.com/mensuales__2025-05-01_Frontal.jpg"
FICHERO_SOLO_R2 = "ana_gmail.com/mensuales__2025-03-01_Frontal.jpg"   # ya no esta en disco
FICHERO_SIN_R2 = "ana_gmail.com/iniciales__2025-02-01_Espalda.jpg"    # en disco, sin migrar


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    base = _Base()
    base.client_profiles.docs = [
        {"id": "c-ana", "user_id": "u-ana"},
        {"id": "c-luis", "user_id": "u-luis"},
    ]
    base.client_photos.docs = [
        # Migrada a R2 (la clave se reconstruye por convenio: app/u-ana/p1).
        {"id": "p1", "user_id": "u-ana", "client_id": "c-ana", "en_r2": True,
         "taken_at": "2026-08-01T10:00:00+00:00", "content_type": "image/jpeg",
         "data": b"FOTO-P1", "filename": "p1.jpg", "size": 7},
        # Sin migrar: ni url ni R2, camino viejo.
        {"id": "p2", "user_id": "u-ana", "client_id": "c-ana",
         "taken_at": "2026-07-01T10:00:00+00:00", "content_type": "image/png",
         "data": b"FOTO-P2", "filename": "p2.png", "size": 7},
        # La trampa (sin user_id) migrada: la migracion dejo la clave exacta en r2_key.
        {"id": "p4", "user_id": None, "client_id": "c-ana", "en_r2": True,
         "r2_key": "app/c-ana/p4",
         "taken_at": "2026-06-15T10:00:00+00:00", "content_type": "image/webp",
         "data": b"FOTO-P4", "filename": "p4.webp", "size": 7},
        # La de otro cliente, tambien en R2: la pertenencia va antes que el almacen.
        {"id": "p3", "user_id": "u-luis", "client_id": "c-luis", "en_r2": True,
         "taken_at": "2026-06-01T10:00:00+00:00", "data": b"FOTO-P3"},
    ]
    base.calma_raw.docs = [
        {"email": "ana@gmail.com", "user_id": "u-ana", "client_id": "c-ana",
         "fotos_descargadas": [
             {"file": FICHERO_ANA, "fecha": "2025-05-01", "kind": "Frontal",
              "content_type": "image/jpeg", "size": 9, "en_r2": True,
              "r2_key": "calma/" + FICHERO_ANA},
             # Ya solo en R2: el fichero no esta en el disco.
             {"file": FICHERO_SOLO_R2, "fecha": "2025-03-01", "kind": "Frontal",
              "content_type": "image/jpeg", "en_r2": True,
              "r2_key": "calma/" + FICHERO_SOLO_R2},
             # En disco y sin migrar.
             {"file": FICHERO_SIN_R2, "fecha": "2025-02-01", "kind": "Espalda"},
         ]},
    ]

    disco = tmp_path / "_fotos_calma"
    (disco / "ana_gmail.com").mkdir(parents=True)
    (disco / "ana_gmail.com" / "mensuales__2025-05-01_Frontal.jpg").write_bytes(b"CALMA-ANA")
    (disco / "ana_gmail.com" / "iniciales__2025-02-01_Espalda.jpg").write_bytes(b"CALMA-VIEJA")

    monkeypatch.setattr(fotos, "db", base)
    monkeypatch.setattr(fotos, "_FOTOS_CALMA_DIR", str(disco))
    return base


@pytest.fixture
def stub(monkeypatch):
    """R2 'configurado': el modulo ve este stub en lugar del cliente boto3."""
    r2 = _StubR2()
    r2.objetos = {
        "app/u-ana/p1": (b"R2-P1", "image/jpeg"),
        "app/c-ana/p4": (b"R2-P4", "image/webp"),
        "calma/" + FICHERO_ANA: (b"R2-CALMA", "image/jpeg"),
        "calma/" + FICHERO_SOLO_R2: (b"R2-SOLO", "image/jpeg"),
    }
    monkeypatch.setattr(fotos, "_cliente_r2", lambda: r2)
    return r2


def _error(user, ref):
    with pytest.raises(HTTPException) as e:
        asyncio.run(fotos.abrir_foto(user, ref))
    return e.value.status_code


# ---------------------------------------------------------------- sin credenciales

def test_sin_credenciales_no_hay_cliente(entorno, monkeypatch):
    """La puerta de verdad: con las claves vacias del .env, _cliente_r2 da None."""
    monkeypatch.setattr(fotos, "_r2_estado", {"cliente": None, "intentado": False})
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "")
    assert fotos._cliente_r2() is None


def test_sin_r2_todo_va_por_el_camino_viejo(entorno, monkeypatch):
    monkeypatch.setattr(fotos, "_cliente_r2", lambda: None)
    lista = asyncio.run(fotos.listar_fotos_de(ANA))
    # Ninguna lleva url, y la que solo vive en R2 no sale (sin R2 no es servible).
    assert all("url" not in f for f in lista)
    ids = [f["id"] for f in lista]
    assert "calma/" + FICHERO_SOLO_R2 not in ids
    assert ids == ["p1", "p2", "p4", "calma/" + FICHERO_ANA, "calma/" + FICHERO_SIN_R2]
    # Y abrir sirve desde Mongo y disco, en_r2 o no.
    assert asyncio.run(fotos.abrir_foto(ANA, "p1")) == (b"FOTO-P1", "image/jpeg")
    assert asyncio.run(fotos.abrir_foto(ANA, "calma/" + FICHERO_ANA)) == (b"CALMA-ANA", "image/jpeg")


# ---------------------------------------------------------------- listar con R2

def test_listar_firma_url_solo_a_las_en_r2(entorno, stub):
    lista = asyncio.run(fotos.listar_fotos_de(ANA))
    por_id = {f["id"]: f for f in lista}
    assert "app/u-ana/p1" in por_id["p1"]["url"]                 # clave por convenio
    assert "app/c-ana/p4" in por_id["p4"]["url"]                 # clave de r2_key (la trampa)
    assert "calma/" + FICHERO_ANA in por_id["calma/" + FICHERO_ANA]["url"]
    assert "url" not in por_id["p2"]                             # sin migrar: sin url
    assert "url" not in por_id["calma/" + FICHERO_SIN_R2]
    # Todas las urls son de 10 minutos.
    assert stub.firmadas and all(seg == 600 for _, seg in stub.firmadas)


def test_la_calma_que_solo_vive_en_r2_sale_en_la_lista(entorno, stub):
    lista = asyncio.run(fotos.listar_fotos_de(ANA))
    solo_r2 = next(f for f in lista if f["id"] == "calma/" + FICHERO_SOLO_R2)
    assert "calma/" + FICHERO_SOLO_R2 in solo_r2["url"]
    assert solo_r2["taken_at"] == "2025-03-01"


def test_si_firmar_falla_la_lista_sale_sin_url(entorno, stub, monkeypatch):
    monkeypatch.setattr(stub, "generate_presigned_url",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stub")))
    lista = asyncio.run(fotos.listar_fotos_de(ANA))
    assert all("url" not in f for f in lista)
    assert [f["id"] for f in lista][:3] == ["p1", "p2", "p4"]


# ---------------------------------------------------------------- abrir con R2

def test_abrir_app_lee_de_r2(entorno, stub):
    assert asyncio.run(fotos.abrir_foto(ANA, "p1")) == (b"R2-P1", "image/jpeg")


def test_abrir_app_usa_la_r2_key_guardada(entorno, stub):
    assert asyncio.run(fotos.abrir_foto(ANA, "p4")) == (b"R2-P4", "image/webp")


def test_abrir_app_sin_marca_no_toca_r2(entorno, stub):
    assert asyncio.run(fotos.abrir_foto(ANA, "p2")) == (b"FOTO-P2", "image/png")
    assert stub.leidas == []            # y nadie pidio nada al bucket por el camino


def test_abrir_app_cae_a_mongo_si_r2_falla(entorno, stub):
    stub.fallar = True
    assert asyncio.run(fotos.abrir_foto(ANA, "p1")) == (b"FOTO-P1", "image/jpeg")


def test_abrir_calma_lee_de_r2(entorno, stub):
    assert asyncio.run(fotos.abrir_foto(ANA, "calma/" + FICHERO_ANA)) == (b"R2-CALMA", "image/jpeg")


def test_abrir_calma_cae_al_disco_si_r2_falla(entorno, stub):
    stub.fallar = True
    assert asyncio.run(fotos.abrir_foto(ANA, "calma/" + FICHERO_ANA)) == (b"CALMA-ANA", "image/jpeg")


def test_abrir_calma_solo_r2_sirve_y_sin_r2_ni_disco_da_404(entorno, stub):
    assert asyncio.run(fotos.abrir_foto(ANA, "calma/" + FICHERO_SOLO_R2)) == (b"R2-SOLO", "image/jpeg")
    # Si R2 se cae y el fichero ya no esta en disco, 404 limpio, sin reventar.
    stub.fallar = True
    assert _error(ANA, "calma/" + FICHERO_SOLO_R2) == 404


def test_la_pertenencia_va_antes_que_r2(entorno, stub):
    """p3 esta en R2, pero es de Luis: 403 sin pasar por el bucket."""
    assert _error(ANA, "p3") == 403
    assert _error(ANA, "no-existe") == 404
