"""
Los dos encargos de Francisco del 16-08 sobre el panel de planes.

1. EL PRECIO NO SE EDITA. Estaba en PLAN_EDITABLE_FIELDS, pero lo que se cobra no sale del
   catalogo: sale del Price de Stripe (`stripe_price_env`). O sea que se podia escribir un
   importe, cambiar el escaparate y seguir cobrando otra cosa sin que nada avisara. Aqui se
   fija que ni por la API se cuela, y que los overrides antiguos que ya traen `precio`
   dentro -- hay uno de `elm` en produccion -- se ignoran sin romper el resto de sus campos.

2. EL PLAN ANTIGUO REABIERTO PARA LOS SUYOS. Un interruptor por plan legacy
   (`renovable_por_los_suyos`), apagado por defecto. Encendido, el que YA tiene ese plan
   puede renovarlo con lo que incluye hoy y con su precio congelado. El que no lo tiene
   sigue sin poder contratarlo: ni en la tienda, ni por la API del checkout.

Lo que se vigila de verdad aqui es la puerta del checkout, que es donde se cobra: no basta
con encender el interruptor, hay que ser de los suyos.
"""
import asyncio

import pytest
from fastapi import HTTPException

import routes.billing as billing
import routes.plans as plans
from core.renovacion import montar_renovacion, salidas
from models.user import (
    PLAN_EDITABLE_FIELDS,
    merged_catalog,
    opciones_de_renovacion,
    puede_renovar_su_plan_legacy,
)


# --------------------------------------------------------------- dobles de prueba

class _Cursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield d
        return gen()

    async def to_list(self, n=None):
        return list(self._docs)


class _Coleccion:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.updates = []

    async def find_one(self, filtro=None, proj=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in (filtro or {}).items()):
                return dict(d)
        return None

    def find(self, filtro=None, proj=None):
        return _Cursor(self.docs)

    async def update_one(self, filtro, cambio, upsert=False):
        self.updates.append((filtro, cambio))
        return None

    async def delete_one(self, filtro):
        return None


class _Db:
    def __init__(self, perfiles=None, overrides=None, pagos=None):
        self.client_profiles = _Coleccion(perfiles or [])
        self.plan_overrides = _Coleccion(overrides or [])
        # La renovacion del legacy mira el ultimo cobro real cuando el perfil no trae
        # precio (cascada del 20-08).
        self.pagos_historicos = _ColeccionPagos(pagos or [])


class _ColeccionPagos(_Coleccion):
    async def find_one(self, filtro=None, proj=None, sort=None):
        # El filtro real lleva $gt/$exists; para el doble basta devolver el primero.
        return dict(self.docs[0]) if self.docs else None


def _catalogo_con_gold_reabierto():
    # ELM ya no vale de ejemplo: el doc del 19-08 lo sube a activos. El legacy con
    # gente y con Price en Stripe es gold.
    return merged_catalog({"gold": {"renovable_por_los_suyos": True}})


# --------------------------------------------------------------- 1 · el precio

class TestElPrecioNoSeEdita:
    def test_ni_precio_ni_precios_son_editables(self):
        assert "precio" not in PLAN_EDITABLE_FIELDS
        assert "precios" not in PLAN_EDITABLE_FIELDS

    def test_la_nota_del_precio_si_se_sigue_editando(self):
        """Es texto de escaparate: no lo lee ningun cobro."""
        assert "precio_nota" in PLAN_EDITABLE_FIELDS
        cat = merged_catalog({"elm": {"precio_nota": "97€/mes de siempre"}})
        assert cat["elm"]["precio_nota"] == "97€/mes de siempre"

    def test_un_override_viejo_con_precio_se_ignora_y_manda_el_codigo(self):
        """El de `elm` que hay guardado en produccion. Manda el codigo, que es lo que se cobra."""
        cat = merged_catalog({"elm": {"precio": 1.0, "precios": [], "name": "ELM de siempre"}})
        assert cat["elm"]["precio"] == 97.0
        assert cat["elm"]["precios"], "las opciones de precio siguen siendo las del catalogo"
        assert cat["elm"]["name"] == "ELM de siempre", "el resto del override sigue valiendo"

    def test_la_api_no_deja_editar_solo_el_precio(self):
        """Aunque alguien llame a mano a PUT /admin/plans/elm con {'precio': 1}."""
        db = _Db()
        original = plans.db
        plans.db = db
        try:
            with pytest.raises(HTTPException) as e:
                asyncio.run(plans.admin_update_plan("elm", {"precio": 1.0, "precios": []},
                                                    user={"id": "admin-1"}))
        finally:
            plans.db = original
        assert e.value.status_code == 400
        validos = {c.strip() for c in e.value.detail.split("Campos válidos:")[1].split(",")}
        assert "precio" not in validos and "precios" not in validos


# --------------------------------------------------------------- 2 · el interruptor

class TestElInterruptorDelPlanAntiguo:
    def test_encendido_de_fabrica_en_todos_los_legacy(self):
        # Francisco, 20-08: «deben poder renovar su mismo plan». El apagado por defecto
        # del 16-08 queda sustituido; el interruptor sigue existiendo para APAGAR uno.
        for code, p in merged_catalog().items():
            if p.get("estado") == "legacy":
                assert p["renovable_por_los_suyos"] is True, code

    def test_apagado_por_override_al_legacy_no_se_le_deja_seguir(self):
        r = opciones_de_renovacion("gold", merged_catalog(
            {"gold": {"renovable_por_los_suyos": False}}))
        assert r["puede_seguir_igual"] is False
        assert r["mantiene_precio"] is False
        assert r["motivo"]

    def test_con_el_interruptor_el_suyo_puede_seguir_igual_y_con_su_precio(self):
        r = opciones_de_renovacion("gold", _catalogo_con_gold_reabierto())
        assert r["puede_seguir_igual"] is True
        assert r["mantiene_precio"] is True, "el precio se congela mientras no se de de baja"
        assert r["renovacion_legacy"] is True
        assert r["motivo"] is None

    def test_reabrirlo_no_lo_devuelve_a_la_tienda(self):
        """Es no echar de su plan al que ya esta, no volver a venderlo."""
        r = opciones_de_renovacion("gold", _catalogo_con_gold_reabierto())
        assert "gold" not in r["opciones"]

    def test_al_que_tiene_otro_plan_ese_legacy_le_sigue_sin_existir(self):
        cat = _catalogo_con_gold_reabierto()
        assert puede_renovar_su_plan_legacy("nivel2", cat) is False
        # reto60 desde el 20-08 tambien es renovable POR EL SUYO; lo que no cambia es que
        # el gold reabierto no aparece en la tienda de nadie.
        assert puede_renovar_su_plan_legacy("reto60", cat) is True
        assert "gold" not in opciones_de_renovacion("nivel2", cat)["opciones"]

    def test_encenderlo_en_un_plan_activo_no_significa_nada(self):
        cat = merged_catalog({"nivel2": {"renovable_por_los_suyos": True}})
        r = opciones_de_renovacion("nivel2", cat)
        assert r["renovacion_legacy"] is False
        assert r["puede_seguir_igual"] is True, "el nivel2 se vende igual, por su estado"

    def test_el_alias_del_perfil_tambien_cuenta(self):
        """Los perfiles migrados traen el plan escrito como venia ('CalMa')."""
        cat = merged_catalog({"calma12": {"renovable_por_los_suyos": True}})
        assert opciones_de_renovacion("CalMa", cat)["renovacion_legacy"] is True


class TestLoQueVeElClienteAlRenovar:
    def _perfil(self, plan="gold"):
        return {"plan": plan, "week": 11, "precio_alta": 87.0}

    def _pantalla(self, catalogo, plan="gold"):
        return montar_renovacion(
            perfil=self._perfil(plan), catalogo=catalogo,
            opciones_catalogo=opciones_de_renovacion(plan, catalogo),
            resumen={},
        )

    def test_le_sale_seguir_igual_y_pasa_por_la_pasarela(self):
        cat = _catalogo_con_gold_reabierto()
        pantalla = self._pantalla(cat)
        seguir = [s for s in pantalla["salidas"] if s["tipo"] == "renovar"]
        assert len(seguir) == 1
        assert seguir[0]["plan"] == "gold"
        assert seguir[0]["por_checkout"] is True, "su suscripcion no renueva sola: hay que cobrarla"
        assert seguir[0]["precio"] == 87.0, "el precio congelado que trae su perfil"

    def test_no_se_le_dice_que_se_renueva_solo(self):
        assert self._pantalla(_catalogo_con_gold_reabierto())["renueva_solo"] is False

    def test_al_del_plan_vivo_sin_suscripcion_se_le_dice_que_renueva_el(self):
        # Nada renueva solo desde el 20-08: el del catalogo sin suscripcion de Stripe
        # renueva a mano, y la pantalla ya no puede prometerle lo contrario.
        cat = merged_catalog()
        pantalla = self._pantalla(cat, plan="nivel2")
        seguir = [s for s in pantalla["salidas"] if s["tipo"] == "renovar"]
        assert seguir and seguir[0].get("por_checkout") is False
        assert pantalla["renueva_solo"] is False

    def test_con_el_interruptor_apagado_no_hay_seguir_igual(self):
        pantalla = self._pantalla(merged_catalog({"gold": {"renovable_por_los_suyos": False}}))
        assert not [s for s in pantalla["salidas"] if s["tipo"] == "renovar"]

    def test_al_que_todavia_le_cobra_stripe_no_se_le_manda_a_pagar_otra_vez(self):
        """Si su suscripcion sigue viva, «seguir igual» es no hacer nada, como siempre."""
        pantalla = montar_renovacion(
            perfil={**self._perfil(), "subscription_status": "active"},
            catalogo=_catalogo_con_gold_reabierto(),
            opciones_catalogo=opciones_de_renovacion("gold", _catalogo_con_gold_reabierto()),
            resumen={})
        seguir = [s for s in pantalla["salidas"] if s["tipo"] == "renovar"]
        assert seguir and seguir[0]["por_checkout"] is False
        assert pantalla["renueva_solo"] is True

    def test_la_salida_a_la_membresia_sigue_estando(self):
        """Reabrirle su plan no le quita la puerta de salir."""
        fuera = salidas(plan_actual="gold", catalogo=_catalogo_con_gold_reabierto(),
                        opciones_catalogo=opciones_de_renovacion("gold", _catalogo_con_gold_reabierto()),
                        precio_alta=None)
        assert fuera[-1]["tipo"] == "salida"


# --------------------------------------------------------------- 3 · guardar el interruptor

class TestGuardarElInterruptor:
    def _guardar(self, code, campos, guardados=None):
        db = _Db(overrides=guardados or [])
        original = plans.db
        plans.db = db
        async def _audit(*a, **k):
            return None
        audit_original = plans.audit
        plans.audit = _audit
        try:
            return asyncio.run(plans.admin_update_plan(code, campos, user={"id": "admin-1"})), db
        finally:
            plans.db = original
            plans.audit = audit_original

    def test_se_puede_encender_en_un_legacy_con_precio_en_stripe(self, monkeypatch):
        monkeypatch.setenv("STRIPE_PRICE_GOLD", "price_de_prueba")
        resultado, db = self._guardar("gold", {"renovable_por_los_suyos": True})
        assert resultado["renovable_por_los_suyos"] is True
        (_, cambio), = db.plan_overrides.updates
        assert cambio["$set"]["fields"]["renovable_por_los_suyos"] is True

    def test_no_se_puede_encender_en_un_plan_que_se_vende(self, monkeypatch):
        monkeypatch.setenv("STRIPE_PRICE_NIVEL2", "price_de_prueba")
        with pytest.raises(HTTPException) as e:
            self._guardar("nivel2", {"renovable_por_los_suyos": True})
        assert e.value.status_code == 400
        assert "ya no se venden" in e.value.detail

    def test_ya_no_hace_falta_price_en_stripe_para_encenderlo(self, monkeypatch):
        """La renovacion del legacy cobra el precio congelado EN LINEA (20-08), asi que
        el 503 que motivaba esta validacion ya no puede pasar: se puede encender aunque
        el plan no tenga Price."""
        monkeypatch.delenv("STRIPE_PRICE_CALMA12", raising=False)
        resultado, _ = self._guardar("calma12", {"renovable_por_los_suyos": True})
        assert resultado["renovable_por_los_suyos"] is True

    def test_apagarlo_no_pide_nada(self):
        resultado, _ = self._guardar("calma12", {"renovable_por_los_suyos": False})
        assert resultado["renovable_por_los_suyos"] is False


# --------------------------------------------------------------- 4 · la puerta del cobro

@pytest.fixture
def checkout_de_mentira(monkeypatch):
    """Todo Stripe sustituido por espias: lo que se mira es la puerta, no la pasarela."""
    llamadas = {}

    async def _api_call(fn, **kwargs):
        llamadas.update(kwargs)
        return {"id": "cs_test_999", "url": "https://checkout.stripe.com/c/pay/cs_test_999"}

    async def _perfil(user, code, **k):
        return {"id": "perfil-1", "plan": code}

    async def _customer(user, profile):
        return "cus_test_1"

    monkeypatch.setattr(billing, "get_stripe_module", lambda: type("S", (), {
        "checkout": type("C", (), {"Session": type("Se", (), {"create": staticmethod(lambda **k: None)})}),
        "Coupon": type("Cu", (), {"create": staticmethod(lambda **k: None)})})())
    monkeypatch.setattr(billing, "require_stripe_test_mode", lambda *a, **k: None)
    monkeypatch.setattr(billing, "stripe_api_call", _api_call)
    monkeypatch.setattr(billing, "build_frontend_url", lambda p, **k: f"https://app.test{p or '/'}")
    monkeypatch.setattr(billing, "ensure_checkout_profile", _perfil)
    monkeypatch.setattr(billing, "get_or_create_stripe_customer", _customer)
    monkeypatch.setattr(billing, "get_stripe_price_id_for_plan", lambda code: f"price_{code}")
    return llamadas


def _pedir_checkout(db, plan, user_id="u-1"):
    from models.common import CheckoutSessionRequest
    original_billing, original_plans = billing.db, plans.db
    billing.db, plans.db = db, db
    try:
        return asyncio.run(billing.create_checkout_session(
            CheckoutSessionRequest(plan=plan), user={"id": user_id}))
    finally:
        billing.db, plans.db = original_billing, original_plans


class TestLaPuertaDelCobro:
    OVERRIDE_ENCENDIDO = [{"code": "gold", "fields": {"renovable_por_los_suyos": True}}]

    def test_el_que_ya_lo_tiene_llega_a_stripe_con_su_precio_congelado(self, checkout_de_mentira):
        # Desde el 20-08 el legacy se cobra con price_data (su precio, en linea) y como
        # pago unico: los planes retirados no tienen Price en Stripe.
        db = _Db(perfiles=[{"user_id": "u-1", "id": "perfil-1", "plan": "gold", "price": 87.0}],
                 overrides=self.OVERRIDE_ENCENDIDO)
        res = _pedir_checkout(db, "gold")
        assert res.checkout_url.startswith("https://checkout.stripe.com/")
        linea = checkout_de_mentira["line_items"][0]
        assert linea["price_data"]["unit_amount"] == 8700
        assert checkout_de_mentira["mode"] == "payment"

    def test_el_que_no_lo_tiene_se_queda_fuera(self, checkout_de_mentira):
        db = _Db(perfiles=[{"user_id": "u-1", "id": "perfil-1", "plan": "nivel1"}],
                 overrides=self.OVERRIDE_ENCENDIDO)
        with pytest.raises(HTTPException) as e:
            _pedir_checkout(db, "gold")
        assert e.value.status_code == 400
        assert "nuevas contrataciones" in e.value.detail

    def test_el_que_no_tiene_perfil_tampoco(self, checkout_de_mentira):
        db = _Db(perfiles=[], overrides=self.OVERRIDE_ENCENDIDO)
        with pytest.raises(HTTPException) as e:
            _pedir_checkout(db, "gold")
        assert e.value.status_code == 400

    def test_con_el_interruptor_apagado_ni_el_suyo(self, checkout_de_mentira):
        # Encendido de fabrica (20-08): apagarlo ahora es un override en False.
        db = _Db(perfiles=[{"user_id": "u-1", "id": "perfil-1", "plan": "gold"}],
                 overrides=[{"code": "gold", "fields": {"renovable_por_los_suyos": False}}])
        with pytest.raises(HTTPException) as e:
            _pedir_checkout(db, "gold")
        assert e.value.status_code == 400

    def test_apagar_un_plan_no_apaga_el_de_al_lado(self, checkout_de_mentira):
        """Apagado el de gold, un cliente de reto60 sigue pudiendo renovar el suyo."""
        db = _Db(perfiles=[{"user_id": "u-1", "id": "perfil-1", "plan": "reto60", "price": 60.0}],
                 overrides=[{"code": "gold", "fields": {"renovable_por_los_suyos": False}}])
        res = _pedir_checkout(db, "reto60")
        assert res.checkout_url.startswith("https://checkout.stripe.com/")

    def test_los_planes_que_se_venden_siguen_entrando_sin_perfil(self, checkout_de_mentira):
        db = _Db(perfiles=[], overrides=[])
        res = _pedir_checkout(db, "nivel1")
        assert res.checkout_url.startswith("https://checkout.stripe.com/")
