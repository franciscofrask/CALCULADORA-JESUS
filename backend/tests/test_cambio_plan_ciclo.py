"""Cambiar el plan de un cliente NO le resetea el ciclo (punto 70 del doc del 23-08).

El panel reiniciaba `cycle_start` en TODO cambio de plan: el que migraba en la semana
10 de 12 amanecía en la semana 1, y deshacer el cambio -- que es otro cambio de plan --
tampoco lo devolvía. La semana se calcula desde `cycle_start` (core/cycle.py), así que
la regla entera se reduce a una invariante: el ancla del ciclo solo se mueve cuando se
le da plan a alguien que NO tenía.

De paso, cada cambio comprueba que la sesión del cliente sigue viva (punto 71: se
observó un cierre de sesión al pasar a ELM que no se pudo reproducir; esto lo vigila).
"""
import uuid

import pytest
import requests

from conftest import API


@pytest.fixture(scope="module")
def cuenta_fresca(api_disponible, cabeceras_admin):
    """Una cuenta recién registrada, sin plan, con su token de cliente."""
    email = f"ciclo.{uuid.uuid4().hex[:10]}@test.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "demo123", "name": "Ciclo De Prueba", "sex": "hombre"})
    if r.status_code == 429:
        pytest.skip("El limitador de registro está activo; pon AUTH_SIN_LIMITE=1 en dev.")
    assert r.status_code in (200, 201), r.text
    tok = requests.post(f"{API}/auth/login", json={"email": email, "password": "demo123"}).json()["access_token"]
    hc = {"Authorization": f"Bearer {tok}"}
    uid = requests.get(f"{API}/auth/me", headers=hc).json()["id"]
    return {"uid": uid, "hc": hc}


def _poner_plan(cabeceras_admin, uid, plan):
    r = requests.put(f"{API}/admin/users/{uid}", headers=cabeceras_admin, json={"plan": plan})
    assert r.status_code == 200, r.text


def _perfil(hc):
    r = requests.get(f"{API}/clients/profile", headers=hc)
    assert r.status_code == 200, r.text
    return r.json()


def test_el_ciclo_arranca_al_dar_el_primer_plan(cuenta_fresca, cabeceras_admin):
    _poner_plan(cabeceras_admin, cuenta_fresca["uid"], "nivel2")
    p = _perfil(cuenta_fresca["hc"])
    assert p.get("plan") == "nivel2"
    assert p.get("cycle_start"), "al dar plan a quien no tenía, el ciclo tiene que arrancar"


def test_cambiar_de_plan_conserva_el_ancla_del_ciclo(cuenta_fresca, cabeceras_admin):
    uid, hc = cuenta_fresca["uid"], cuenta_fresca["hc"]
    ancla = _perfil(hc)["cycle_start"]
    # El recorrido del doc: varios planes seguidos, con ELM en medio, y el deshacer.
    for plan in ("nivel1", "gold", "elm", "mantenimiento", "nivel2"):
        _poner_plan(cabeceras_admin, uid, plan)
        p = _perfil(hc)
        assert p["cycle_start"] == ancla, f"el cambio a {plan} movió el ancla del ciclo"
        # Punto 71: la sesión del cliente sigue viva tras cada cambio (ELM incluido).
        assert requests.get(f"{API}/auth/me", headers=hc).status_code == 200, \
            f"el cambio a {plan} tumbó la sesión del cliente"


def test_quitar_el_plan_no_toca_el_ancla(cuenta_fresca, cabeceras_admin):
    uid, hc = cuenta_fresca["uid"], cuenta_fresca["hc"]
    ancla = _perfil(hc)["cycle_start"]
    _poner_plan(cabeceras_admin, uid, None)
    p = _perfil(hc)
    assert p.get("plan") is None
    assert p["cycle_start"] == ancla, "quitar el plan no debe mover el ancla"


def test_volver_a_dar_plan_tras_sin_plan_si_reinicia(cuenta_fresca, cabeceras_admin):
    uid, hc = cuenta_fresca["uid"], cuenta_fresca["hc"]
    ancla_vieja = _perfil(hc)["cycle_start"]
    _poner_plan(cabeceras_admin, uid, "nivel1")
    p = _perfil(hc)
    assert p["cycle_start"] != ancla_vieja, \
        "al volver de 'sin plan' el ciclo tiene que arrancar de cero (la regla vieja que sí vale)"
