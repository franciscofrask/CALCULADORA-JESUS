"""
«Macros por revisar» sin duplicados (2.5 del plan del lunes, doc 21-08).

Cada recalculo del cliente dejaba un insert en db.macro_revisiones, asi que el panel
enseñaba «Macros por revisar: 7» con 7 filas del mismo cliente, 4 identicas: la lista
contaba recalculos, no clientes por revisar. Lo que se fija aqui:

  - dos recalculos seguidos dejan UNA sola pendiente, y con la comparacion mas reciente
    (las anteriores quedan como «reemplazada», no se borran: son historial),
  - la campanita del entrenador suena la primera vez y no con cada recalculo,
  - y lo que no requiere revision sigue sin registrar nada.

Con una base de mentira (el patron de test_trazas_chat): ninguna prueba escribe en la
base de verdad.
"""
import asyncio

import pytest

from core import quiz_store


@pytest.fixture(autouse=True)
def _la_db_del_modulo_se_restaura():
    """Estas pruebas cambian `quiz_store.db` por la de mentira; al salir se devuelve la
    de verdad para no contaminar al resto de la bateria."""
    original = quiz_store.db
    yield
    quiz_store.db = original


class ColeccionDeMentira:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def update_many(self, filtro, cambio):
        n = 0
        for d in self.docs:
            if all(d.get(k) == v for k, v in filtro.items()):
                d.update(cambio.get("$set", {}))
                n += 1
        return type("R", (), {"modified_count": n})()


class BaseDeMentira:
    def __init__(self):
        self.macro_revisiones = ColeccionDeMentira()


PERFIL = {"id": "cli-1", "trainer_id": None}
USUARIO = {"id": "usr-1", "name": "Cliente de prueba"}


def _resultado(diferencia):
    return {"revision": {"requiere_revision": True, "hc_reportados": 300,
                         "hc_recomendados": 250, "diferencia": diferencia}}


def _registrar(base, perfil=PERFIL, resultado=None):
    quiz_store.db = base
    return asyncio.run(quiz_store.registrar_revision(perfil, USUARIO, resultado))


def _pendientes(base):
    return [d for d in base.macro_revisiones.docs if d["status"] == "pendiente"]


def test_dos_recalculos_seguidos_dejan_una_pendiente():
    base = BaseDeMentira()
    assert _registrar(base, resultado=_resultado(50)) is True
    assert _registrar(base, resultado=_resultado(80)) is True

    pendientes = _pendientes(base)
    assert len(pendientes) == 1, base.macro_revisiones.docs
    # La que queda es la ULTIMA: es la comparacion que el coach tiene que mirar.
    assert pendientes[0]["comparacion"]["diferencia"] == 80


def test_la_reemplazada_queda_como_historial_y_con_fecha():
    base = BaseDeMentira()
    _registrar(base, resultado=_resultado(50))
    _registrar(base, resultado=_resultado(80))

    reemplazadas = [d for d in base.macro_revisiones.docs if d["status"] == "reemplazada"]
    assert len(reemplazadas) == 1
    assert reemplazadas[0]["comparacion"]["diferencia"] == 50
    assert reemplazadas[0].get("resolved_at")


def test_siete_recalculos_siguen_dejando_una():
    base = BaseDeMentira()
    for i in range(7):
        _registrar(base, resultado=_resultado(10 + i))
    assert len(_pendientes(base)) == 1
    assert len(base.macro_revisiones.docs) == 7      # el historial no se pierde


def test_clientes_distintos_no_se_pisan():
    base = BaseDeMentira()
    _registrar(base, perfil={"id": "cli-1", "trainer_id": None}, resultado=_resultado(50))
    _registrar(base, perfil={"id": "cli-2", "trainer_id": None}, resultado=_resultado(60))
    assert len(_pendientes(base)) == 2


def test_sin_client_id_deduplica_por_usuario():
    """Perfiles a medio migrar sin `id`: el fallback es el user_id, no dejar de deduplicar."""
    base = BaseDeMentira()
    _registrar(base, perfil={"id": None, "trainer_id": None}, resultado=_resultado(50))
    _registrar(base, perfil={"id": None, "trainer_id": None}, resultado=_resultado(80))
    assert len(_pendientes(base)) == 1


def test_lo_que_cuadra_no_registra_nada():
    base = BaseDeMentira()
    assert _registrar(base, resultado={"revision": {"requiere_revision": False}}) is False
    assert base.macro_revisiones.docs == []


def test_la_campanita_suena_solo_la_primera_vez(monkeypatch):
    """El aviso al coach salio con la primera pendiente; repetirlo con cada recalculo
    mientras esa pendiente siga abierta es ruido, no informacion."""
    import routes.notifications as rn

    avisos = []

    async def notify_de_mentira(user_id, tipo, mensaje, link=None):
        avisos.append((user_id, tipo))

    monkeypatch.setattr(rn, "notify", notify_de_mentira)

    base = BaseDeMentira()
    perfil = {"id": "cli-1", "trainer_id": "coach-1"}
    _registrar(base, perfil=perfil, resultado=_resultado(50))
    _registrar(base, perfil=perfil, resultado=_resultado(80))

    assert len(_pendientes(base)) == 1
    assert avisos == [("coach-1", "macros_revision")]
