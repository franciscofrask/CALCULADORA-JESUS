# -*- coding: utf-8 -*-
"""Los candados de COMPRAR la rutina del mes (POST /billing/rutina-del-mes/checkout).

El endpoint que cobra 57 EUR se quedo sin un solo test: el de al lado
(test_rutina_del_mes_2408.py) prueba lo que pasa DESPUES de pagar, pero no quien puede
llegar a la pantalla de pago. Aqui estan los frenos que hay ANTES de Stripe:

  - hay que decir si la quiere basica o avanzada,
  - al que su plan ya se la incluye no se le vende,
  - al que ya le pusieron una rutina tampoco,
  - al que ya la pidio este mes (por cualquiera de las dos puertas) tampoco: el segundo
    cargo de 57 EUR es el fallo caro,
  - y una cuenta de pruebas NUNCA llega a Stripe.

Y EL MORDISCO: la rutina que se compro EL MISMO no puede cerrarle la compra del mes que
viene. Es «del mes», se vende todos los meses, y desde que el pago la entrega sola la
compra de agosto le dejaba una rutina activa que le cerraba la de septiembre para siempre.

Sin backend y sin Mongo, como el resto de la familia: base de mentira y llamada directa.
"""
import copy
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import core.plan_access as plan_access                              # noqa: E402
import core.rutina_del_mes as rm                                    # noqa: E402
import routes.billing as billing                                    # noqa: E402
import routes.routines as rutinas                                   # noqa: E402
from core.tiempo import hoy_madrid                                  # noqa: E402

from conftest import corre  # noqa: E402


# ── Una base de mentira que entiende $ne, $in y los rangos de fecha ──────────

def _casa(doc, filtro):
    for clave, valor in (filtro or {}).items():
        actual = doc.get(clave)
        if isinstance(valor, dict):
            if "$ne" in valor and actual == valor["$ne"]:
                return False
            if "$in" in valor and actual not in valor["$in"]:
                return False
            if "$gte" in valor and not (actual and actual >= valor["$gte"]):
                return False
            if "$lte" in valor and not (actual and actual <= valor["$lte"]):
                return False
        elif actual != valor:
            return False
    return True


class _Coleccion:
    def __init__(self, *docs):
        self.docs = [copy.deepcopy(d) for d in docs]

    async def find_one(self, filtro=None, proyeccion=None, sort=None):
        for d in self.docs:
            if _casa(d, filtro):
                return copy.deepcopy(d)
        return None

    async def update_one(self, filtro, cambio, **k):
        for d in self.docs:
            if _casa(d, filtro):
                d.update(cambio.get("$set") or {})
                for fuera in (cambio.get("$unset") or {}):
                    d.pop(fuera, None)
                break


class _Base:
    def __init__(self, **colecciones):
        for nombre, col in colecciones.items():
            setattr(self, nombre, col)

    def __getattr__(self, nombre):
        col = _Coleccion()
        setattr(self, nombre, col)
        return col


# Codigos que NO estan en el catalogo real a proposito: asi la prueba mide el criterio
# (`habilitaciones.rutina`) y no se cae el dia que a un plan de verdad le cambien la fila.
CATALOGO = {
    "plan_sin_rutina":     {"habilitaciones": {"rutina": "opcional"}},
    "plan_con_la_del_mes": {"habilitaciones": {"rutina": "del_mes"}},
    "plan_personalizado":  {"habilitaciones": {"rutina": "personalizada"}},
}
PERFIL = {"id": "c1", "user_id": "u1", "name": "Marta", "plan": "plan_sin_rutina"}
USUARIO = {"id": "u1", "email": "marta@ejemplo.com"}


@pytest.fixture
def montar(monkeypatch):
    """Monta la base, el catalogo y un `activar_tras_pago` que solo apunta lo que le llega.
    Devuelve el ayudante; las entregas quedan en `montar.entregas`."""
    entregas = []

    async def _activar(profile, importe_eur=None, modalidad="basica", session_id=None,
                       cobrado=True, motivo=None):
        entregas.append({"id": profile.get("id"), "importe_eur": importe_eur,
                         "modalidad": modalidad, "cobrado": cobrado, "motivo": motivo})
        return True

    monkeypatch.setattr(rm, "activar_tras_pago", _activar)

    async def _catalogo():
        return CATALOGO

    monkeypatch.setattr(plan_access, "catalogo_vivo", _catalogo)

    def _preparar(*, plan="plan_sin_rutina", rutinas_puestas=(), perfil_extra=None,
                  es_pruebas=False):
        perfil = {**PERFIL, "plan": plan, **(perfil_extra or {})}
        base = _Base(client_profiles=_Coleccion(perfil),
                     routines=_Coleccion(*rutinas_puestas),
                     reports=_Coleccion())
        monkeypatch.setattr(billing, "db", base)
        monkeypatch.setattr(rutinas, "db", base)
        return {**USUARIO, "es_pruebas": es_pruebas}

    _preparar.entregas = entregas
    return _preparar


def _comprar(user, modalidad="basica"):
    return corre(billing.comprar_la_rutina_del_mes({"modalidad": modalidad}, user=user))


class TestQuienNoPuedeComprarla:

    def test_la_ruta_existe(self):
        assert "/billing/rutina-del-mes/checkout" in {r.path for r in billing.router.routes}

    def test_hay_que_decir_como_la_quiere(self, montar):
        user = montar()
        with pytest.raises(HTTPException) as e:
            _comprar(user, modalidad="")
        assert e.value.status_code == 400 and "básica o avanzada" in e.value.detail

    @pytest.mark.parametrize("plan", ["plan_con_la_del_mes", "plan_personalizado"])
    def test_al_que_su_plan_ya_se_la_incluye_no_se_le_vende(self, montar, plan):
        user = montar(plan=plan)
        with pytest.raises(HTTPException) as e:
            _comprar(user)
        assert e.value.status_code == 400 and "ya incluye" in e.value.detail

    def test_al_que_ya_le_pusieron_una_rutina_tampoco(self, montar):
        """La que le puso el equipo desde la biblioteca: no compra otra por error."""
        user = montar(rutinas_puestas=[{"client_id": "c1", "status": "active",
                                        "origen": "biblioteca"}])
        with pytest.raises(HTTPException) as e:
            _comprar(user)
        assert e.value.status_code == 400 and "Ya tienes una rutina activa" in e.value.detail

    def test_una_rutina_vieja_e_inactiva_no_frena_nada(self, montar):
        user = montar(rutinas_puestas=[{"client_id": "c1", "status": "inactive",
                                        "origen": "biblioteca"}], es_pruebas=True)
        assert _comprar(user)["sin_pago"] is True

    def test_la_que_se_compro_el_no_le_cierra_el_mes_que_viene(self, montar):
        """EL MORDISCO: con la entrega automatica, comprarla una vez la cerraba para
        siempre. Es «del mes» y se vende todos los meses."""
        user = montar(rutinas_puestas=[{"client_id": "c1", "status": "active",
                                        "origen": "rutina_del_mes"}], es_pruebas=True)
        assert _comprar(user)["sin_pago"] is True

    def test_al_que_ya_la_pidio_este_mes_no_se_le_cobra_otra_vez(self, montar):
        user = montar(perfil_extra={"rutina_mes_pedida": {"fecha": hoy_madrid().isoformat(),
                                                          "modalidad": "basica"}})
        with pytest.raises(HTTPException) as e:
            _comprar(user)
        assert e.value.status_code == 409 and "Ya nos pediste" in e.value.detail

    def test_pasado_el_mes_puede_volver_a_pedirla(self, montar):
        """Sin plazo, el que la pago y nunca la recibio se quedaba sin forma de reclamarla."""
        user = montar(perfil_extra={"rutina_mes_pedida": {"fecha": "2020-01-01",
                                                          "modalidad": "basica"}},
                      es_pruebas=True)
        assert _comprar(user)["sin_pago"] is True


class TestLaCuentaDePruebasNoLlegaAStripe:
    """Una cuenta de laboratorio NUNCA cobra de verdad, aunque Stripe este en vivo. Es la
    misma regla que frena el cobro del reporte mensual (`rutina_del_mes.cobrar`)."""

    def test_no_se_cobra_y_se_le_entrega_igual(self, montar, monkeypatch):
        user = montar(es_pruebas=True)

        def _no_deberia(*a, **k):
            raise AssertionError("una cuenta de pruebas no puede tocar Stripe")

        monkeypatch.setattr(billing, "get_stripe_module", _no_deberia)

        salida = _comprar(user, "avanzada")
        assert salida["sin_pago"] is True and salida["importe_eur"] == 57.0
        assert "no se ha cobrado nada" in salida["mensaje"]
        entrega = montar.entregas[-1]
        assert entrega["cobrado"] is False and entrega["motivo"] == "cuenta_de_pruebas"
        assert entrega["importe_eur"] == 0.0 and entrega["modalidad"] == "avanzada"

    def test_tambien_vale_marcada_en_la_ficha(self, montar):
        user = montar(perfil_extra={"es_pruebas": True})
        assert _comprar(user)["sin_pago"] is True

    def test_sin_ninguna_marcada_no_le_decimos_que_ya_la_tiene(self, montar):
        """Sin plantilla marcada como la del mes no hay nada que entregar, y darlo por
        puesto es lo que hace que una prueba se de por buena sin serlo."""
        user = montar(es_pruebas=True)
        salida = _comprar(user)
        assert salida["rutina_puesta"] is None
        assert "no se te ha puesto ninguna" in salida["mensaje"]

    def test_con_una_marcada_si_se_lo_decimos(self, montar, monkeypatch):
        user = montar(es_pruebas=True)

        async def _activar_y_entregar(profile, *a, **k):
            await billing.db.client_profiles.update_one(
                {"id": profile["id"]},
                {"$set": {"rutina_mes_pedida": {"rutina_puesta": "Agosto hombre"}}})
            return True

        monkeypatch.setattr(rm, "activar_tras_pago", _activar_y_entregar)
        salida = _comprar(user)
        assert salida["rutina_puesta"] == "Agosto hombre"
        assert "ya tienes la rutina puesta" in salida["mensaje"]


class TestElAvisoAlEquipoNoInventaVentas:
    """El aviso de la rutina del mes cuenta como DINERO en el panel del equipo
    (`avisos_equipo.TIPOS_EQUIPO`), asi que no puede decir «ha pagado 57 €» cuando no se ha
    cobrado nada: le mete a Jesus una venta que no existe en la caja del dia."""

    def _montar(self, monkeypatch):
        avisos = []

        async def _avisar(db, **kw):
            avisos.append(kw)

        async def _entregar(client_id, origen="compra"):
            return "Rutina de agosto"

        monkeypatch.setattr("core.database.db", _Base(client_profiles=_Coleccion(dict(PERFIL))))
        monkeypatch.setattr("core.avisos_equipo.avisar_al_equipo", _avisar)
        monkeypatch.setattr(rutinas, "entregar_la_rutina_del_mes", _entregar)
        return avisos

    def test_cobrado_dice_el_importe_que_entro(self, monkeypatch):
        avisos = self._montar(monkeypatch)
        corre(rm.activar_tras_pago(dict(PERFIL), 57.0, "basica", session_id="cs_1"))
        assert avisos[0]["titulo"] == "Ha comprado la rutina del mes"
        assert "ha pagado la rutina del mes básica (57 €)" in avisos[0]["mensaje"]

    def test_sin_cobrar_lo_dice_y_no_se_inventa_los_57(self, monkeypatch):
        avisos = self._montar(monkeypatch)
        corre(rm.activar_tras_pago(dict(PERFIL), 0.0, "basica", session_id=None,
                                   cobrado=False, motivo="cuenta_de_pruebas"))
        assert avisos[0]["titulo"] == "Rutina del mes sin cobrar"
        assert "SIN COBRAR" in avisos[0]["mensaje"] and "57 €" not in avisos[0]["mensaje"]
        assert avisos[0]["extra"]["importe_eur"] == 0.0
