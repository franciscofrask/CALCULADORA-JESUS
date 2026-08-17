"""
Cobro del Nivel 3 despues de la llamada (doc del 03-08).

El Nivel 3 se vende hablando, pero se cobra por Stripe con tarjeta igual que los demas.
Lo que se fija aqui son las tres decisiones que no pueden cambiar sin querer:

  1. Es PAGO UNICO del ciclo (`mode="payment"`), no una suscripcion que renueve sola.
  2. Cobra el precio del CATALOGO (1.500 EUR), no una cifra escrita a mano en este
     fichero ni en el de leads. Y desde el 16-08 el catalogo es el del codigo tambien
     aqui: el importe ya no se edita en el panel.
  3. Al pagarlo NO se le activa el plan solo: se avisa al equipo para que le de el alta.
"""
import asyncio
import pytest

import routes.leads as leads
import routes.billing as billing
import core.stripe_billing as sb


# ---------------------------------------------------------------- dobles de prueba

class _Cursor:
    """Cursor asincrono de mongo con lo justo: `async for`."""
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield d
        return gen()


class _Coleccion:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.updates = []

    async def find_one(self, filtro, proj=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in filtro.items()):
                return dict(d)
        return None

    def find(self, filtro=None, proj=None):
        return _Cursor(self.docs)

    async def update_one(self, filtro, cambio):
        self.updates.append((filtro, cambio))
        return None


class _Db:
    def __init__(self, leads_docs, overrides=None):
        self.leads = _Coleccion(leads_docs)
        self.plan_overrides = _Coleccion(overrides or [])


LEAD = {"id": "lead-1", "name": "Marta", "email": "marta@ejemplo.com", "phone": "600112233",
        "status": "nuevo", "quiz_venta": {"quiere_llamada": True}}


@pytest.fixture
def stripe_espia(monkeypatch):
    """Sustituye Stripe por un espia que guarda con que se le llamo."""
    llamadas = {}

    async def _api_call(fn, *args, **kwargs):
        llamadas.update(kwargs)
        return {"id": "cs_test_123", "url": "https://checkout.stripe.com/c/pay/cs_test_123"}

    monkeypatch.setattr(sb, "get_stripe_module", lambda: type("S", (), {
        "checkout": type("C", (), {"Session": type("Se", (), {"create": staticmethod(lambda **k: None)})})})())
    monkeypatch.setattr(sb, "stripe_api_call", _api_call)
    monkeypatch.setattr(sb, "require_stripe_test_mode", lambda *a, **k: None)
    monkeypatch.setattr(sb, "build_frontend_url", lambda p, **k: f"https://app.test{p}")
    return llamadas


@pytest.fixture
def sin_auditoria(monkeypatch):
    async def _audit(*a, **k):
        return None
    monkeypatch.setattr(leads, "audit", _audit)


def _crear(db, plan="nivel3"):
    monkey_db = db
    original = leads.db
    leads.db = monkey_db
    try:
        return asyncio.run(leads.crear_enlace_pago("lead-1", {"plan": plan}, user={"id": "admin-1"}))
    finally:
        leads.db = original


# ---------------------------------------------------------------- el enlace de pago

class TestElEnlaceDePago:
    def test_es_pago_unico_y_no_suscripcion(self, stripe_espia, sin_auditoria):
        db = _Db([LEAD])
        _crear(db)
        assert stripe_espia["mode"] == "payment", "el ciclo es un pago unico, no una suscripcion"
        assert "subscription_data" not in stripe_espia

    def test_cobra_el_precio_del_catalogo(self, stripe_espia, sin_auditoria):
        db = _Db([LEAD])
        _crear(db)
        item = stripe_espia["line_items"][0]["price_data"]
        assert item["unit_amount"] == 150000, "1.500 EUR en centimos"
        assert item["currency"] == "eur"

    def test_un_precio_editado_en_el_panel_ya_no_cambia_lo_que_se_cobra(self, stripe_espia, sin_auditoria):
        """El importe dejo de ser editable (Francisco, 16-08).

        Antes este enlace era el unico sitio donde un `precio` escrito en el panel llegaba
        a cobrarse de verdad: por Stripe se cobra el Price de la variable de entorno, asi
        que en todo lo demas ese numero solo cambiaba el escaparate. Un mismo campo que
        unas veces cobra y otras no es peor que un campo que no se puede tocar.

        Quedan overrides antiguos guardados con `precio` dentro (uno de `elm` en
        produccion): se ignoran solos, porque merged_catalog solo copia lo editable.
        """
        db = _Db([LEAD], overrides=[{"code": "nivel3", "fields": {"precio": 1800.0}}])
        _crear(db)
        assert stripe_espia["line_items"][0]["price_data"]["unit_amount"] == 150000

    def test_lleva_el_lead_en_los_metadatos(self, stripe_espia, sin_auditoria):
        db = _Db([LEAD])
        _crear(db)
        assert stripe_espia["metadata"]["tipo"] == "cobro_lead"
        assert stripe_espia["metadata"]["lead_id"] == "lead-1"
        assert stripe_espia["client_reference_id"] == "lead-1"

    def test_devuelve_la_url_y_deja_el_lead_en_propuesta_enviada(self, stripe_espia, sin_auditoria):
        db = _Db([LEAD])
        res = _crear(db)
        assert res["url"].startswith("https://checkout.stripe.com/")
        assert res["importe_eur"] == 1500.0
        (_, cambio), = db.leads.updates
        assert cambio["$set"]["status"] == "propuesta_enviada"
        assert cambio["$set"]["quiz_venta.quiere_llamada"] is False
        assert cambio["$set"]["enlace_pago"]["estado"] == "enviado"

    def test_un_lead_que_no_existe_da_404(self, stripe_espia, sin_auditoria):
        from fastapi import HTTPException
        db = _Db([])
        with pytest.raises(HTTPException) as e:
            _crear(db)
        assert e.value.status_code == 404


# ---------------------------------------------------------------- el pago que llega

class TestCuandoPaga:
    def _procesar(self, db, monkeypatch, avisos):
        async def _avisar(_db, **kwargs):
            avisos.append(kwargs)
            return 1
        import core.avisos_equipo as ae
        monkeypatch.setattr(ae, "avisar_al_equipo", _avisar)
        original = billing.db
        billing.db = db
        try:
            asyncio.run(billing._registrar_cobro_de_lead(
                {"amount_total": 150000},
                {"tipo": "cobro_lead", "lead_id": "lead-1", "plan": "nivel3"}))
        finally:
            billing.db = original

    def test_marca_el_lead_convertido_y_avisa_al_equipo(self, monkeypatch):
        db = _Db([{**LEAD, "enlace_pago": {"estado": "enviado"}}])
        avisos = []
        self._procesar(db, monkeypatch, avisos)
        (_, cambio), = db.leads.updates
        assert cambio["$set"]["status"] == "convertido"
        assert cambio["$set"]["enlace_pago.estado"] == "pagado"
        assert cambio["$set"]["enlace_pago.importe_pagado_eur"] == 1500.0
        assert len(avisos) == 1
        assert avisos[0]["tipo"] == "lead_pagado"
        assert "600112233" in avisos[0]["mensaje"], "el telefono va en el aviso, para llamarle"

    def test_un_webhook_repetido_no_duplica_el_aviso(self, monkeypatch):
        db = _Db([{**LEAD, "enlace_pago": {"estado": "pagado"}}])
        avisos = []
        self._procesar(db, monkeypatch, avisos)
        assert avisos == [], "Stripe reintenta: el aviso solo puede salir una vez"
