"""
El cobro de la rutina del mes: 57 EUR en la tarjeta que ya tiene puesta.

«Al marcar «Sí» autorizas el cargo en tu tarjeta» (doc 16-08, T8). Aquí se fija lo que no
puede fallar cuando hay dinero de por medio:

  - que no se cobre dos veces el mismo reporte,
  - que un cobro que no entra NO impida mandar el reporte,
  - y que sin tarjeta, sin Stripe o con una modalidad rara no se invente un cargo.

Se sustituye el módulo de Stripe por uno de mentira: lo de verdad se probó a mano contra
Stripe en modo test (cobro de 57,00 EUR, reintento con el mismo id devolviendo el mismo
cobro, y tarjeta rechazada).
"""
import asyncio

import pytest

from core import rutina_del_mes as rm


class StripeDeMentira:
    """Lo justo del SDK: la lista de tarjetas, el cliente y el cobro."""

    def __init__(self, *, con_tarjeta=True, revienta=None, estado="succeeded"):
        self.con_tarjeta = con_tarjeta
        self.revienta = revienta
        self.estado = estado
        self.cobros = []            # cada intento que llega a Stripe

        gestor = self

        class PaymentMethod:
            @staticmethod
            def list(**kwargs):
                return {"data": [{"id": "pm_1"}] if gestor.con_tarjeta else []}

        class Customer:
            @staticmethod
            def retrieve(cid, **kwargs):
                return {"id": cid, "invoice_settings": {"default_payment_method": None}}

        class PaymentIntent:
            @staticmethod
            def create(**kwargs):
                if gestor.revienta:
                    raise gestor.revienta
                gestor.cobros.append(kwargs)
                return {"id": f"pi_{len(gestor.cobros)}", "status": gestor.estado}

        self.PaymentMethod, self.Customer, self.PaymentIntent = PaymentMethod, Customer, PaymentIntent


@pytest.fixture
def stripe_de_mentira(monkeypatch):
    def _montar(**kwargs):
        falso = StripeDeMentira(**kwargs)
        monkeypatch.setattr("core.stripe_billing.get_stripe_module", lambda: falso)
        monkeypatch.setattr("core.stripe_billing.get_stripe_key_mode", lambda: "test")

        async def _llamar(fn, *a, **kw):
            return fn(*a, **kw)

        monkeypatch.setattr("core.stripe_billing.stripe_api_call", _llamar)
        return falso
    return _montar


PERFIL = {"id": "perfil-1", "stripe_customer_id": "cus_1"}


def test_cobra_los_57_euros(stripe_de_mentira):
    falso = stripe_de_mentira()
    r = asyncio.run(rm.cobrar(PERFIL, "basica", "rep-1"))
    assert r["cobrado"] is True
    assert r["importe_eur"] == 57.0
    assert falso.cobros[0]["amount"] == 5700
    assert falso.cobros[0]["currency"] == "eur"


def test_el_intento_lleva_lo_que_hace_falta_para_reconocerlo(stripe_de_mentira):
    """Fuera de sesión y confirmado: lo autorizó al marcar «Sí» en el reporte, no hay nadie
    delante de una pantalla de pago. Y con metadatos para saber de quién es cada cobro."""
    falso = stripe_de_mentira()
    asyncio.run(rm.cobrar(PERFIL, "avanzada", "rep-7"))
    intento = falso.cobros[0]
    assert intento["off_session"] is True and intento["confirm"] is True
    assert intento["metadata"]["tipo"] == "rutina_del_mes"
    assert intento["metadata"]["modalidad"] == "avanzada"
    assert intento["metadata"]["report_id"] == "rep-7"


def test_el_mismo_reporte_no_se_cobra_dos_veces(stripe_de_mentira):
    """La clave de idempotencia es del par cliente y reporte: reenviar el reporte no puede
    ser otro cargo de 57 EUR."""
    falso = stripe_de_mentira()
    asyncio.run(rm.cobrar(PERFIL, "basica", "rep-2"))
    asyncio.run(rm.cobrar(PERFIL, "basica", "rep-2"))
    claves = {c["idempotency_key"] for c in falso.cobros}
    assert claves == {"rutina_del_mes:perfil-1:rep-2"}


def test_reportes_distintos_son_cobros_distintos(stripe_de_mentira):
    falso = stripe_de_mentira()
    asyncio.run(rm.cobrar(PERFIL, "basica", "rep-3"))
    asyncio.run(rm.cobrar(PERFIL, "basica", "rep-4"))
    assert len({c["idempotency_key"] for c in falso.cobros}) == 2


def test_sin_tarjeta_guardada_no_se_cobra(stripe_de_mentira):
    falso = stripe_de_mentira(con_tarjeta=False)
    r = asyncio.run(rm.cobrar(PERFIL, "basica", "rep-5"))
    assert r == {"cobrado": False, "importe_eur": 57.0, "modalidad": "basica",
                 "motivo": rm.SIN_TARJETA}
    assert falso.cobros == []


def test_sin_cliente_de_stripe_no_se_cobra(stripe_de_mentira):
    stripe_de_mentira()
    r = asyncio.run(rm.cobrar({"id": "perfil-2"}, "basica", "rep-6"))
    assert r["motivo"] == rm.SIN_TARJETA


def test_una_tarjeta_rechazada_no_revienta_el_envio(stripe_de_mentira):
    """Lo importante: devuelve, no levanta. Si levantara, el cliente no podría mandar su
    reporte por un cobro que falló."""
    stripe_de_mentira(revienta=RuntimeError("Your card was declined"))
    r = asyncio.run(rm.cobrar(PERFIL, "basica", "rep-8"))
    assert r["cobrado"] is False and r["motivo"] == rm.RECHAZADA


def test_si_el_banco_pide_confirmacion_se_dice_con_su_nombre(stripe_de_mentira):
    error = RuntimeError("authentication_required")
    error.code = "authentication_required"
    stripe_de_mentira(revienta=error)
    r = asyncio.run(rm.cobrar(PERFIL, "basica", "rep-9"))
    assert r["motivo"] == rm.REQUIERE_AUTENTICACION


def test_una_modalidad_que_no_existe_no_cobra(stripe_de_mentira):
    falso = stripe_de_mentira()
    r = asyncio.run(rm.cobrar(PERFIL, "vip", "rep-10"))
    assert r["cobrado"] is False and falso.cobros == []


def test_sin_stripe_configurado_no_cobra_y_lo_dice(monkeypatch):
    monkeypatch.setattr("core.stripe_billing.get_stripe_key_mode", lambda: "missing")
    r = asyncio.run(rm.cobrar(PERFIL, "basica", "rep-11"))
    assert r["motivo"] == rm.SIN_STRIPE


def test_en_live_bloqueado_no_cobra(monkeypatch):
    """El mismo cerrojo que el resto de los pagos: si el entorno no tiene el modo live
    abierto, no se cobra de verdad por accidente."""
    monkeypatch.setattr("core.stripe_billing.get_stripe_key_mode", lambda: "live")
    monkeypatch.setattr("core.stripe_billing.STRIPE_ALLOW_LIVE_MODE", False)
    r = asyncio.run(rm.cobrar(PERFIL, "basica", "rep-12"))
    assert r["motivo"] == rm.SIN_STRIPE


def test_el_precio_es_el_del_documento():
    assert rm.PRECIO_EUR == 57.0
    assert rm.importe_centimos() == 5700


def test_el_precio_que_se_enseña_es_el_que_se_cobra():
    """La rutina del mes cuesta 57 € SE COMPRE COMO SE COMPRE (decisión de Jesús del
    24-08). Tenía dos precios desde el 19-08 -- 57 dentro de un plan y 67 suelta -- y el
    Inicio del cliente de Mantenimiento leía el suelto: veía 67 donde la pantalla de
    Rutina y el cobro del reporte decían 57. Las dos filas siguen (son las dos formas de
    llevársela y la app busca la suya por la etiqueta); el número ya no cambia."""
    from models.user import PLAN_CATALOG

    catalogo = PLAN_CATALOG["rutina_mes"]
    assert catalogo["precio"] == rm.PRECIO_EUR
    dentro = next(p for p in catalogo["precios"] if "plan" in p["label"].lower())
    assert dentro["importe"] == rm.PRECIO_EUR
    assert f"{rm.PRECIO_EUR:.0f}€" in catalogo["precio_nota"]
    # La suelta es la puerta del que no tiene plan que la incluya, y vale lo mismo.
    suelta = next(p for p in catalogo["precios"] if p["label"].lower() == "suelta")
    assert suelta["importe"] == rm.PRECIO_EUR == 57.0
