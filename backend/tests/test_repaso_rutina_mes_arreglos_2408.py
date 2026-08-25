# -*- coding: utf-8 -*-
"""Repaso 24-08 de la rutina del mes: los dos agujeros de DINERO que quedaron abiertos
al arreglar el fallo 14 (que lo que se compra se pueda entregar).

Los dos se reprodujeron contra el dev vivo, con un pago de verdad en el modo prueba de
Stripe, antes de tocar nada:

  A. SE ENTREGABA SIN PAGAR. `POST /billing/rutina-del-mes/checkout` le devuelve al
     cliente el `session_id` ANTES de que pague, y `POST /billing/checkout-session/sync`
     no miraba si la sesion estaba pagada. Bastaba con abrir el pago, cerrar Stripe y
     llamar al sync con ese id: la sesion volvia con `payment_status: unpaid` y aun asi se
     le entregaba el PDF y se le apuntaba `cobrado: true, importe_eur: 57`.

  B. UN PAGO, DOS VENTAS. El webhook de Stripe y la vuelta del navegador llegan los dos a
     la vez. El «¿ya esta apuntada?» leia la ficha y despues escribia, y entre lo uno y lo
     otro cabia la otra llamada: medido, DOS filas en `rutina_pdfs` con 32 ms de diferencia
     y DOS avisos «ha pagado la rutina del mes basica (57 EUR)» al equipo por un solo pago.
     El aviso de este tipo cuenta como DINERO en el panel, o sea una venta inventada en la
     caja del dia.

Sin backend y sin Mongo, como el resto de la familia: base de mentira y llamada directa.
La base de aqui entiende el `$ne` sobre un campo ANIDADO (`rutina_mes_pedida.session_id`),
que es justo lo que hace de candado, y devuelve `modified_count`, que es lo que se mira.
"""
import asyncio
import copy
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import core.rutina_del_mes as rm                                     # noqa: E402
import routes.billing as billing                                     # noqa: E402

from conftest import corre  # noqa: E402


# ── Una base de mentira con lo justo: rutas con punto, $ne y modified_count ──

def _mira(doc, camino):
    """El valor de `a.b.c` dentro del documento, o None."""
    actual = doc
    for tramo in camino.split("."):
        if not isinstance(actual, dict):
            return None
        actual = actual.get(tramo)
    return actual


def _casa(doc, filtro):
    for clave, valor in (filtro or {}).items():
        actual = _mira(doc, clave)
        if isinstance(valor, dict) and "$ne" in valor:
            if actual == valor["$ne"]:
                return False
        elif actual != valor:
            return False
    return True


class _Resultado:
    def __init__(self, n):
        self.modified_count = n
        self.matched_count = n


class _Coleccion:
    def __init__(self, *docs):
        self.docs = [copy.deepcopy(d) for d in docs]

    async def find_one(self, filtro=None, proyeccion=None, sort=None):
        for d in self.docs:
            if _casa(d, filtro):
                return copy.deepcopy(d)
        return None

    async def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

    async def update_one(self, filtro, cambio, **k):
        for d in self.docs:
            if not _casa(d, filtro):
                continue
            tocado = False
            for clave, valor in (cambio.get("$set") or {}).items():
                # Rutas con punto: `rutina_mes_pedida.rutina_puesta`.
                tramos = clave.split(".")
                destino = d
                for tramo in tramos[:-1]:
                    destino = destino.setdefault(tramo, {})
                destino[tramos[-1]] = valor
                tocado = True
            # `$addToSet` como el de verdad: si el valor ya estaba, NO cuenta como cambio.
            # Es justo lo que hace de candado contra el pago entregado dos veces.
            for clave, valor in (cambio.get("$addToSet") or {}).items():
                lista = d.setdefault(clave, [])
                if valor not in lista:
                    lista.append(valor)
                    tocado = True
            for fuera in (cambio.get("$unset") or {}):
                if fuera in d:
                    d.pop(fuera, None)
                    tocado = True
            return _Resultado(1 if tocado else 0)
        return _Resultado(0)

    async def update_many(self, filtro, cambio, **k):
        n = 0
        for d in list(self.docs):
            if _casa(d, filtro):
                d.update(cambio.get("$set") or {})
                n += 1
        return _Resultado(n)


class _Base:
    def __init__(self, **colecciones):
        for nombre, col in colecciones.items():
            setattr(self, nombre, col)

    def __getattr__(self, nombre):
        col = _Coleccion()
        setattr(self, nombre, col)
        return col


PERFIL = {"id": "c1", "user_id": "u1", "name": "Marta", "plan": "mantenimiento"}
SESION = "cs_test_deprueba"


@pytest.fixture
def montar(monkeypatch):
    """Base de mentira + la entrega y el aviso espiados.

    `avisar_al_equipo` y la entrega se sustituyen porque lo que se mide aqui es CUANTAS
    veces se llaman, no lo que hacen: entregar de verdad arrastra `routes.routines` entero.
    """
    hechos = {"entregas": [], "avisos": []}

    async def _entregar(client_id):
        hechos["entregas"].append(client_id)
        return "La rutina de agosto de 2026"

    async def _avisar(db, **kw):
        hechos["avisos"].append(kw)

    monkeypatch.setattr(rm, "_entregarsela", _entregar)
    import core.avisos_equipo as avisos
    monkeypatch.setattr(avisos, "avisar_al_equipo", _avisar)

    def _preparar(perfil_extra=None):
        perfil = {**PERFIL, **(perfil_extra or {})}
        base = _Base(client_profiles=_Coleccion(perfil))
        monkeypatch.setattr(rm, "db", base, raising=False)
        import core.database as database
        monkeypatch.setattr(database, "db", base)
        hechos["base"] = base
        return hechos

    return _preparar


def _ficha(hechos):
    return hechos["base"].client_profiles.docs[0].get("rutina_mes_pedida") or {}


# ── B · UN PAGO, UNA VENTA ──────────────────────────────────────────────────

class TestUnPagoUnaVenta:

    def test_el_pago_normal_entrega_y_avisa_una_vez(self, montar):
        hechos = montar()
        assert corre(rm.activar_tras_pago(dict(PERFIL), 57.0, "basica", session_id=SESION))
        assert hechos["entregas"] == ["c1"]
        assert len(hechos["avisos"]) == 1
        assert _ficha(hechos)["rutina_puesta"] == "La rutina de agosto de 2026"

    def test_la_segunda_vuelta_del_mismo_pago_no_entrega_otra_vez(self, montar):
        """El webhook y el `sync` llegan los dos con el mismo `session_id`."""
        hechos = montar()
        corre(rm.activar_tras_pago(dict(PERFIL), 57.0, "basica", session_id=SESION))
        # La segunda llega con la ficha YA leida antes de la primera: es el caso real, el
        # webhook se trae su copia del perfil de la base antes de que escriba nadie.
        assert corre(rm.activar_tras_pago(dict(PERFIL), 57.0, "basica",
                                          session_id=SESION)) is False
        assert hechos["entregas"] == ["c1"], "la entrega se ha repetido"
        assert len(hechos["avisos"]) == 1, "el equipo ve dos ventas de 57 EUR por un pago"

    def test_las_dos_a_la_vez_tampoco(self, montar):
        """EL FALLO MEDIDO: webhook y navegador a la vez, los dos con la ficha limpia.

        Antes del arreglo esto dejaba dos filas en `rutina_pdfs` y dos avisos de venta.
        """
        hechos = montar()

        async def _las_dos():
            return await asyncio.gather(
                rm.activar_tras_pago(dict(PERFIL), 57.0, "basica", session_id=SESION),
                rm.activar_tras_pago(dict(PERFIL), 57.0, "basica", session_id=SESION))

        resultado = corre(_las_dos())
        assert sorted(resultado) == [False, True], "las dos se han dado por buenas"
        assert hechos["entregas"] == ["c1"]
        assert len(hechos["avisos"]) == 1

    def test_otro_pago_distinto_si_entrega(self, montar):
        """Es «del mes»: el mes que viene vuelve a comprarla y tiene que recibirla."""
        hechos = montar()
        corre(rm.activar_tras_pago(dict(PERFIL), 57.0, "basica", session_id=SESION))
        perfil_ya_escrito = copy.deepcopy(hechos["base"].client_profiles.docs[0])
        assert corre(rm.activar_tras_pago(perfil_ya_escrito, 57.0, "basica",
                                          session_id="cs_test_otro"))
        assert hechos["entregas"] == ["c1", "c1"]
        assert len(hechos["avisos"]) == 2

    def test_la_cuenta_de_laboratorio_no_tiene_sesion_y_se_apunta_igual(self, montar):
        """Sin `session_id` no hay carrera que ganar: se apunta y se entrega."""
        hechos = montar()
        assert corre(rm.activar_tras_pago(dict(PERFIL), 0.0, "basica", session_id=None,
                                          cobrado=False, motivo="cuenta_de_pruebas"))
        assert hechos["entregas"] == ["c1"]
        ficha = _ficha(hechos)
        assert ficha["cobrado"] is False and ficha["motivo"] == "cuenta_de_pruebas"
        assert ficha["rutina_puesta"] == "La rutina de agosto de 2026"

    def test_el_aplazamiento_se_quita_al_comprar(self, montar):
        """El que dijo «preguntame en una semana» y luego compro seguia recibiendo el
        recordatorio. El `$unset` tiene que sobrevivir al candado nuevo."""
        hechos = montar(perfil_extra={"rutina_mes_aplazada_hasta": "2026-09-01"})
        corre(rm.activar_tras_pago(dict(PERFIL), 57.0, "basica", session_id=SESION))
        assert "rutina_mes_aplazada_hasta" not in hechos["base"].client_profiles.docs[0]


# ── A · NO SE ENTREGA LO QUE NO SE HA PAGADO ────────────────────────────────

class _Sesion(dict):
    """Una sesion de Stripe de mentira, con lo que mira el codigo."""

    def __init__(self, payment_status, session_id=SESION):
        super().__init__(id=session_id, mode="payment", payment_status=payment_status,
                         amount_total=5700, customer="cus_1",
                         client_reference_id="c1",
                         metadata={"tipo": "rutina_del_mes", "modalidad": "basica",
                                   "user_id": "u1", "profile_id": "c1"})


@pytest.fixture
def stripe_de_mentira(monkeypatch):
    """El `sync` sin Stripe ni base: solo se mira a quien llama y con que."""
    entregas = []

    async def _activar(profile, importe_eur=None, modalidad="basica", session_id=None,
                       cobrado=True, motivo=None):
        entregas.append({"id": profile.get("id"), "importe_eur": importe_eur,
                         "session_id": session_id})
        return True

    # Un modulo de Stripe con lo justo: el codigo pide `stripe.checkout.Session.retrieve`
    # para pasarselo a `stripe_api_call`, que aqui tambien es de mentira.
    modulo = SimpleNamespace(checkout=SimpleNamespace(Session=SimpleNamespace(retrieve=None)))
    monkeypatch.setattr(rm, "activar_tras_pago", _activar)
    monkeypatch.setattr(billing, "get_stripe_module", lambda: modulo)
    monkeypatch.setattr(billing, "require_stripe_test_mode", lambda *a, **k: None)
    monkeypatch.setattr(billing, "db", _Base(client_profiles=_Coleccion(dict(PERFIL))))

    def _con(sesion):
        async def _api(_funcion, *a, **k):
            return sesion
        monkeypatch.setattr(billing, "stripe_api_call", _api)
        return entregas

    return _con


class TestNoSeEntregaSinPagar:

    def test_la_sesion_sin_pagar_no_entrega_nada(self, stripe_de_mentira):
        """EL AGUJERO: el `session_id` se lo damos al cliente antes de que pague."""
        entregas = stripe_de_mentira(_Sesion("unpaid"))
        salida = corre(billing.sync_checkout_session({"session_id": SESION},
                                                     user={"id": "u1"}))
        assert entregas == [], "se le ha entregado la rutina sin haber pagado"
        assert salida["payment_status"] == "unpaid"

    def test_la_sesion_pagada_si_entrega(self, stripe_de_mentira):
        entregas = stripe_de_mentira(_Sesion("paid"))
        corre(billing.sync_checkout_session({"session_id": SESION}, user={"id": "u1"}))
        assert len(entregas) == 1
        assert entregas[0]["importe_eur"] == 57.0
        assert entregas[0]["session_id"] == SESION

    def test_el_webhook_tambien_exige_que_este_pagada(self, stripe_de_mentira):
        """Hoy con tarjeta siempre llega pagada; el dia que se abra un pago diferido,
        `checkout.session.completed` llega SIN cobrar y el bueno es otro evento."""
        for estado, cuantas in (("unpaid", 0), ("paid", 1)):
            entregas = stripe_de_mentira(_Sesion(estado))
            corre(billing._process_stripe_event(
                {"type": "checkout.session.completed",
                 "data": {"object": _Sesion(estado)}}))
            assert len(entregas) == cuantas, f"con payment_status={estado}"
