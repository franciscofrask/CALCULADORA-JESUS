# -*- coding: utf-8 -*-
"""
Tarea 1.1: el cliente ve TODAS sus fotos, incluidas las importadas de Calma.

Se prueba `core/fotos` -- la unica puerta a las fotos del cliente -- contra una base
falsa y un directorio temporal que hace de `_fotos_calma`, como en
test_historial_una_por_dia.py: sin Mongo y sin backend, corren en un segundo.

Lo que fijan estos tests:
  - la fusion de las dos fuentes (client_photos + calma_raw.fotos_descargadas),
  - la trampa del doc con client_id pero sin user_id (invisible para su dueño hasta ahora),
  - que una ref ajena o inventada NO se sirve (403/404), tampoco por path traversal,
  - y que sin el directorio de Calma en disco (dev) la lista sale sin las de disco,
    sin excepcion.
"""
import asyncio

import pytest
from fastapi import HTTPException

from core import fotos


# ---------------------------------------------------------------- base falsa

def _casa(doc, filtro):
    """Lo justo del lenguaje de filtros de Mongo que usa core/fotos: igualdad y $or."""
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


ANA = {"id": "u-ana"}
LUIS = {"id": "u-luis"}

FICHERO_ANA = "ana_gmail.com/mensuales__2025-05-01_Frontal.jpg"
FICHERO_LUIS = "luis_gmail.com/iniciales__2025-04-01_Espalda.jpg"


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    """Base falsa + un _fotos_calma temporal con la foto de Ana y la de Luis en disco."""
    base = _Base()
    base.client_profiles.docs = [
        {"id": "c-ana", "user_id": "u-ana"},
        {"id": "c-luis", "user_id": "u-luis"},
    ]
    base.client_photos.docs = [
        # La de Ana subida desde la app, con todo en orden.
        {"id": "p1", "user_id": "u-ana", "client_id": "c-ana", "pose": "frente",
         "taken_at": "2026-08-01T10:00:00+00:00", "content_type": "image/jpeg",
         "data": b"FOTO-P1", "filename": "p1.jpg", "size": 7},
        # LA TRAMPA: client_id de Ana pero sin user_id (subida por el equipo, doc a medias).
        {"id": "p2", "user_id": None, "client_id": "c-ana",
         "taken_at": "2026-07-01T10:00:00+00:00", "content_type": "image/png",
         "data": b"FOTO-P2", "filename": "p2.png", "size": 7},
        # La de otro cliente.
        {"id": "p3", "user_id": "u-luis", "client_id": "c-luis",
         "taken_at": "2026-06-01T10:00:00+00:00", "data": b"FOTO-P3"},
    ]
    base.calma_raw.docs = [
        {"email": "ana@gmail.com", "user_id": "u-ana", "client_id": "c-ana",
         "fotos_descargadas": [
             {"file": FICHERO_ANA, "fecha": "2025-05-01", "kind": "Frontal",
              "content_type": "image/jpeg", "size": 9},
             # Registro huerfano: el fichero no esta en disco.
             {"file": "ana_gmail.com/huerfana.jpg", "fecha": "2025-06-01", "kind": "Espalda"},
             # Registro malicioso: aunque estuviera registrado, fuera del directorio no se sirve.
             {"file": "../fuera.jpg", "fecha": "2025-07-01", "kind": "Frontal"},
         ]},
        {"email": "luis@gmail.com", "user_id": "u-luis", "client_id": "c-luis",
         "fotos_descargadas": [
             {"file": FICHERO_LUIS, "fecha": "2025-04-01", "kind": "Espalda"},
         ]},
    ]

    disco = tmp_path / "_fotos_calma"
    (disco / "ana_gmail.com").mkdir(parents=True)
    (disco / "ana_gmail.com" / "mensuales__2025-05-01_Frontal.jpg").write_bytes(b"CALMA-ANA")
    (disco / "luis_gmail.com").mkdir(parents=True)
    (disco / "luis_gmail.com" / "iniciales__2025-04-01_Espalda.jpg").write_bytes(b"CALMA-LUIS")
    # El fichero del path traversal EXISTE (un nivel por encima): solo el candado lo para.
    (tmp_path / "fuera.jpg").write_bytes(b"NO-SE-SIRVE")

    monkeypatch.setattr(fotos, "db", base)
    monkeypatch.setattr(fotos, "_FOTOS_CALMA_DIR", str(disco))
    return base


# ---------------------------------------------------------------- listar_fotos_de

def test_fusiona_app_y_calma_por_fecha(entorno):
    lista = asyncio.run(fotos.listar_fotos_de(ANA))
    assert [f["id"] for f in lista] == ["p1", "p2", "calma/" + FICHERO_ANA]
    assert [f["fuente"] for f in lista] == ["app", "app", "calma"]
    # Y ni la huerfana (sin fichero) ni la maliciosa (fuera del directorio) salen.


def test_la_trampa_del_user_id_nulo_queda_tapada(entorno):
    """p2 tiene client_id de Ana pero user_id nulo: antes era invisible para ella."""
    lista = asyncio.run(fotos.listar_fotos_de(ANA))
    assert "p2" in {f["id"] for f in lista}


def test_la_de_calma_lleva_lo_necesario_para_pintarla(entorno):
    calma = [f for f in asyncio.run(fotos.listar_fotos_de(ANA)) if f["fuente"] == "calma"][0]
    assert calma["ref"] == "calma/" + FICHERO_ANA
    assert calma["taken_at"] == "2025-05-01"      # la fecha del registro (la del nombre)
    assert calma["pose"] == "frente"              # kind 'Frontal' -> la clave del cliente
    assert calma["content_type"] == "image/jpeg"
    assert calma["inicial"] is False


def test_no_mezcla_fotos_de_otro_cliente(entorno):
    ids = {f["id"] for f in asyncio.run(fotos.listar_fotos_de(ANA))}
    assert "p3" not in ids
    assert "calma/" + FICHERO_LUIS not in ids


def test_sin_disco_la_lista_sale_sin_las_de_calma(entorno, monkeypatch):
    """En dev _fotos_calma puede no existir: lista sin las de disco, sin excepcion."""
    monkeypatch.setattr(fotos, "_FOTOS_CALMA_DIR", "Z:\\no-existe\\_fotos_calma")
    lista = asyncio.run(fotos.listar_fotos_de(ANA))
    assert [f["id"] for f in lista] == ["p1", "p2"]


# ---------------------------------------------------------------- abrir_foto

def _error(user, ref):
    with pytest.raises(HTTPException) as e:
        asyncio.run(fotos.abrir_foto(user, ref))
    return e.value.status_code


def test_abre_la_suya_de_la_app(entorno):
    data, ct = asyncio.run(fotos.abrir_foto(ANA, "p1"))
    assert (data, ct) == (b"FOTO-P1", "image/jpeg")


def test_abre_la_de_la_trampa_por_client_id(entorno):
    data, ct = asyncio.run(fotos.abrir_foto(ANA, "p2"))
    assert (data, ct) == (b"FOTO-P2", "image/png")


def test_abre_la_suya_de_calma(entorno):
    data, ct = asyncio.run(fotos.abrir_foto(ANA, "calma/" + FICHERO_ANA))
    assert (data, ct) == (b"CALMA-ANA", "image/jpeg")


def test_la_app_ajena_da_403(entorno):
    assert _error(ANA, "p3") == 403


def test_la_calma_ajena_da_404(entorno):
    """La ref de Luis no esta en el registro de Ana: mismo criterio que el admin."""
    assert _error(ANA, "calma/" + FICHERO_LUIS) == 404


def test_la_inventada_da_404(entorno):
    assert _error(ANA, "no-existe") == 404
    assert _error(ANA, "calma/ana_gmail.com/no-existe.jpg") == 404


def test_el_registro_huerfano_da_404(entorno):
    assert _error(ANA, "calma/ana_gmail.com/huerfana.jpg") == 404


def test_path_traversal_no_se_sirve(entorno):
    """El fichero existe y hasta esta 'registrado', pero se sale del directorio: 404."""
    assert _error(ANA, "calma/../fuera.jpg") == 404


def test_sin_disco_la_de_calma_da_404_sin_reventar(entorno, monkeypatch):
    monkeypatch.setattr(fotos, "_FOTOS_CALMA_DIR", "Z:\\no-existe\\_fotos_calma")
    assert _error(ANA, "calma/" + FICHERO_ANA) == 404
