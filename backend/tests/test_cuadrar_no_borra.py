"""Cuadrar reparte, no sirve en cola, y no quita ingredientes.

Francisco, 08-08-2026: montó una Comida 2 con seis ingredientes, pulsó «Cuadrar» y le
quedaron tres. «Vaciar no debería eliminar comidas, dime cuál es el criterio actual».

El criterio era una cola: se recorrían los alimentos EN EL ORDEN DE LA LISTA y cada uno
se llevaba todo lo que podía del presupuesto que quedaba. Los últimos se lo encontraban
a cero, recibían cantidad 0 y se borraban con el motivo «no_cabe». Se comprobó poniendo
el mismo alimento el primero y el cuarto: **el primero sobrevivía y el cuarto no, fuera
cual fuera el alimento**. No se iban por descuadrar: se iban por llegar tarde. Y el aviso
que veía el cliente («no cabían ni al mínimo») no era cierto: sí cabían.

Ahora se le reserva a cada uno su mínimo antes de repartir, así que los seis siguen ahí,
y lo que no se llega a cuadrar se dice en vez de resolverlo borrando.
"""
import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000")

# El caso tal cual lo montó Francisco
HUEVOS, CLARAS, AVENA = 321, 144, 1662
CACAO, LECHE_ALMENDRAS, PLATANO = 2940, 1708, 528
SEIS = [HUEVOS, CLARAS, AVENA, CACAO, LECHE_ALMENDRAS, PLATANO]

DIA = {"fecha": "2026-08-08", "tipo_dia": "entrenamiento", "num_comidas": 4,
       "momento_entreno": 1, "opcion_peri": "intra_post"}


@pytest.fixture(scope="module")
def headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "clientedemo@test.com", "password": "demo123"},
                      timeout=60)
    assert r.status_code == 200, f"no se pudo entrar: {r.status_code}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _cuadrar(headers, ids, meal="C2"):
    alimentos = [{"alimento_id": i, "cantidad_g": 100} for i in ids]
    r = requests.post(f"{BASE_URL}/api/calculator/refit-diet",
                      json={**DIA, "comidas": {meal: {"alimentos": alimentos}}},
                      headers=headers, timeout=180)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    d = r.json()
    return d["comidas"][meal]["alimentos"], d.get("excluidos", []), d.get("desfases", {}).get(meal)


def test_cuadrar_no_quita_ingredientes(headers):
    """Los seis que entran son los seis que salen."""
    alimentos, excluidos, _ = _cuadrar(headers, SEIS)
    assert len(alimentos) == len(SEIS), (
        f"entraron {len(SEIS)} ingredientes y salieron {len(alimentos)}: "
        f"{[a['nombre'] for a in alimentos]}")
    assert not excluidos, f"se han quitado: {[e.get('nombre') for e in excluidos]}"


def test_el_orden_no_decide_quien_sobrevive(headers):
    """Antes sobrevivían los tres primeros y morían los tres últimos, fuera cual fuera
    el alimento. Dar la vuelta a la lista tiene que dar los mismos seis."""
    normal, _, _ = _cuadrar(headers, SEIS)
    alreves, _, _ = _cuadrar(headers, list(reversed(SEIS)))
    assert {a["alimento_id"] for a in normal} == {a["alimento_id"] for a in alreves}, (
        "cambiar el orden cambia quién sobrevive")


def test_cada_ingrediente_se_lleva_algo(headers):
    """Que estén no basta: ninguno puede quedarse a cero."""
    alimentos, _, _ = _cuadrar(headers, SEIS)
    a_cero = [a["nombre"] for a in alimentos if float(a.get("cantidad_g") or 0) <= 0]
    assert not a_cero, f"se han quedado a cero: {a_cero}"


def test_cuando_no_cuadra_se_dice_y_no_se_borra(headers):
    """Tres alimentos grasos y ningún hidrato: no puede cuadrar. Lo que NO puede hacer
    es resolverlo quitando cosas, ni pasarse de largo para tapar el hueco."""
    alimentos, excluidos, desfase = _cuadrar(headers, [HUEVOS, CACAO, CLARAS])
    assert len(alimentos) == 3, "ha quitado alimentos para poder cuadrar"
    assert not excluidos
    assert desfase is not None, "no dice cuánto se ha quedado sin cuadrar"
    # Faltar hidratos es inevitable (no hay ninguno); pasarse de grasa, no.
    assert desfase["G"] <= 4, f"se pasa {desfase['G']}g de grasa para tapar el hueco"
    assert desfase["P"] <= 4, f"se pasa {desfase['P']}g de proteína para tapar el hueco"
