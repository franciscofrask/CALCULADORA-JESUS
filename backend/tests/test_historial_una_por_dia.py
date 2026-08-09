# -*- coding: utf-8 -*-
"""
Punto 62: una fila por (cliente, fecha de vigencia) en el historial de macros.

Lo que reporto Jesus: cinco filas para el 30/06/2026 del mismo cliente, cuatro de ellas
identicas. Salen de guardar varias veces el mismo dia -- calcular, mirar, tocar un numero
y volver a guardar -- porque los seis caminos que escriben hacian `insert_one`.

Estos tests fijan la regla sin tocar Mongo: el modulo se prueba contra una coleccion
falsa, asi que corren en un segundo y no dependen de que haya base de datos.
"""
import asyncio

import pytest

from core import historial_macros


class _Coleccion:
    """Lo justo de una coleccion de Mongo para este modulo: find_one, insert, replace."""

    def __init__(self):
        self.docs = []
        self._n = 0

    def _casa(self, doc, filtro):
        return all(doc.get(k) == v for k, v in filtro.items() if k != "_id") and \
            (filtro.get("_id") is None or doc.get("_id") == filtro["_id"])

    async def find_one(self, filtro, *a, **k):
        return next((d for d in self.docs if self._casa(d, filtro)), None)

    async def insert_one(self, doc):
        self._n += 1
        doc.setdefault("_id", self._n)
        self.docs.append(doc)

    async def replace_one(self, filtro, doc):
        for i, d in enumerate(self.docs):
            if self._casa(d, filtro):
                doc["_id"] = d["_id"]
                self.docs[i] = doc
                return


class _Base:
    def __init__(self):
        self.macro_history = _Coleccion()
        self.auditoria = _Coleccion()

    def __getitem__(self, nombre):
        return self.auditoria


@pytest.fixture
def base(monkeypatch):
    b = _Base()
    monkeypatch.setattr(historial_macros, "db", b)
    return b


def _log(id_, cid, fecha, training, rest, previo=None):
    return {"id": id_, "client_id": cid, "effective_date": fecha,
            "created_at": f"{fecha}T10:0{id_}:00",
            "training": training, "rest": rest,
            "previous_training": previo, "previous_rest": previo}


def test_dos_guardados_el_mismo_dia_dejan_una_fila(base):
    """El caso de Jesus: guardar cuatro veces el 30/06 deja UNA fila, la ultima."""
    for i, p in enumerate([200, 210, 220, 230], start=1):
        asyncio.run(historial_macros.guardar(
            _log(i, "cli", "2026-06-30", {"protein": p, "carbs": 330, "fat": 70},
                 {"protein": p, "carbs": 260, "fat": 80},
                 previo={"protein": 200 if i == 1 else p - 10, "carbs": 300, "fat": 60})))

    assert len(base.macro_history.docs) == 1, "el mismo dia no puede dejar cuatro filas"
    queda = base.macro_history.docs[0]
    assert queda["training"]["protein"] == 230, "manda el ultimo guardado, que es la correccion"
    # Y el rastro no se ha perdido.
    assert len(base.auditoria.docs) == 3
    assert {d["id"] for d in base.auditoria.docs} == {1, 2, 3}


def test_el_de_donde_venia_es_el_real(base):
    """Los estados intermedios no existieron: la fila que queda dice de donde se salio."""
    asyncio.run(historial_macros.guardar(
        _log(1, "cli", "2026-06-30", {"protein": 210, "carbs": 300, "fat": 60},
             {"protein": 210, "carbs": 300, "fat": 60},
             previo={"protein": 200, "carbs": 300, "fat": 60})))
    asyncio.run(historial_macros.guardar(
        _log(2, "cli", "2026-06-30", {"protein": 230, "carbs": 300, "fat": 60},
             {"protein": 230, "carbs": 300, "fat": 60},
             previo={"protein": 210, "carbs": 300, "fat": 60})))

    queda = base.macro_history.docs[0]
    assert queda["previous_training"]["protein"] == 200, \
        "tiene que decir 'de 200 a 230', no 'de 210 a 230': el 210 no lo vio nadie"
    # Y `cambios` se recalcula contra ese 200, no contra el intermedio.
    assert queda["cambios"]["entreno"]["proteina"] is True
    assert queda["cambios"]["entreno"]["hidratos"] is False


def test_dias_distintos_son_filas_distintas(base):
    for i, fecha in enumerate(["2026-06-30", "2026-07-15", "2026-07-30"], start=1):
        asyncio.run(historial_macros.guardar(
            _log(i, "cli", fecha, {"protein": 200}, {"protein": 180})))
    assert len(base.macro_history.docs) == 3, "un ajuste por quincena son tres filas, no una"


def test_clientes_distintos_el_mismo_dia_no_se_pisan(base):
    asyncio.run(historial_macros.guardar(_log(1, "ana", "2026-06-30", {"protein": 150}, {})))
    asyncio.run(historial_macros.guardar(_log(2, "luis", "2026-06-30", {"protein": 220}, {})))
    assert len(base.macro_history.docs) == 2
    assert not base.auditoria.docs


def test_sin_effective_date_vale_el_dia_de_created_at(base):
    """Las filas viejas no traen effective_date; la fecha sale de cuando se creo."""
    for i in (1, 2):
        asyncio.run(historial_macros.guardar(
            {"id": i, "client_id": "cli", "created_at": "2026-06-30T19:4%d:00" % i,
             "training": {"protein": 200 + i}}))
    assert len(base.macro_history.docs) == 1
    assert base.macro_history.docs[0]["effective_date"] == "2026-06-30"


def test_sin_cliente_no_se_deduplica(base):
    """Sin clave no se puede agrupar, y perder un ajuste seria peor que dejar un duplicado."""
    for i in (1, 2):
        asyncio.run(historial_macros.guardar(
            {"id": i, "effective_date": "2026-06-30", "training": {"protein": 200}}))
    assert len(base.macro_history.docs) == 2
