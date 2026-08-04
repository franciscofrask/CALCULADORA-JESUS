"""
Un pago unico de nivel arranca el LUNES, igual que las suscripciones.

Los tres niveles pasaron a pago unico (doc 03-08). Antes, el checkout de pago unico
contaba el ciclo desde el minuto del pago, con lo que quien pagaba un miercoles tenia un
ciclo desfasado respecto al de al lado. La parte 2 de la especificacion dice que todos
arrancan en lunes y que los dias sueltos hasta ese lunes son Semana 0 regalada.
"""
import asyncio
from datetime import datetime, timezone

import pytest

import core.stripe_billing as sb


PERFIL = {"id": "perf-1", "user_id": "user-1", "plan": "nivel2"}


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.fixture
def entorno(monkeypatch):
    """db falso + perfil encontrado siempre. Devuelve lo que se guardo."""
    guardado = {}

    class _Col:
        async def update_one(self, filtro, cambio):
            guardado.update(cambio["$set"])

        async def find_one(self, *a, **k):
            return dict(PERFIL, **guardado)

    class _Db:
        client_profiles = _Col()
        users = _Col()

    async def _find(**kwargs):
        return dict(PERFIL)

    monkeypatch.setattr(sb, "db", _Db())
    monkeypatch.setattr(sb, "find_client_profile", _find)
    return guardado


def _pagar(momento, plan="nivel2"):
    return {"payment_status": "paid", "created": int(momento.timestamp()),
            "client_reference_id": "perf-1", "customer": "cus_1",
            "metadata": {"plan": plan}}


class TestArranqueEnLunes:
    def test_quien_paga_un_miercoles_arranca_el_lunes_siguiente(self, entorno):
        # Miercoles 29 de julio de 2026 -> lunes 3 de agosto.
        asyncio.run(sb.sync_profile_from_one_time_session(_pagar(utc(2026, 7, 29, 15))))
        inicio = datetime.fromisoformat(entorno["current_period_start"])
        assert inicio.weekday() == 0, "el ciclo tiene que empezar un lunes"
        assert (inicio.year, inicio.month, inicio.day) == (2026, 8, 3)

    def test_el_ciclo_dura_las_12_semanas_desde_ese_lunes(self, entorno):
        asyncio.run(sb.sync_profile_from_one_time_session(_pagar(utc(2026, 7, 29, 15))))
        inicio = datetime.fromisoformat(entorno["current_period_start"])
        fin = datetime.fromisoformat(entorno["current_period_end"])
        assert (fin - inicio).days == 84, "12 semanas x 7 dias"
        assert (fin.year, fin.month, fin.day) == (2026, 10, 26)

    def test_los_dias_hasta_el_lunes_se_regalan(self, entorno):
        """Paga el miercoles y ya tiene acceso: el ciclo acaba mas tarde que si se
        hubieran contado las 12 semanas desde el pago."""
        pago = utc(2026, 7, 29, 15)
        asyncio.run(sb.sync_profile_from_one_time_session(_pagar(pago)))
        fin = datetime.fromisoformat(entorno["access_until"])
        assert (fin - pago).days > 84, "la Semana 0 es regalo, no se le come ciclo"
        assert datetime.fromisoformat(entorno["fecha_pago"]) == pago

    def test_no_deja_ningun_cobro_programado(self, entorno):
        asyncio.run(sb.sync_profile_from_one_time_session(_pagar(utc(2026, 7, 29, 15))))
        assert entorno["next_payment"] is None, "un pago unico no vuelve a cobrar"
        assert entorno["subscription_status"] is None
        assert entorno["cancel_at_period_end"] is False
        assert entorno["status"] == "activo"

    def test_un_pago_no_confirmado_no_activa_nada(self, entorno):
        sesion = _pagar(utc(2026, 7, 29, 15))
        sesion["payment_status"] = "unpaid"
        asyncio.run(sb.sync_profile_from_one_time_session(sesion))
        assert entorno == {}
