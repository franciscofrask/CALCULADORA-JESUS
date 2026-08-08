"""El margen del sugeridor es un TECHO: ampliarlo solo puede añadir menús.

Francisco, 08-08-2026: «si el margen es ±10 quiere decir que el menú puede ir de
margen 0, o sea que cuadras hasta un desfase de 10. Si en 5 me muestra menús, no
tiene sentido que no me muestre más si el margen es superior».

Tenía razón y estaba roto de dos formas:

  - La búsqueda se estrechaba con el margen (se preseleccionaba con `obj ± margen`),
    así que cambiarlo no ampliaba el conjunto: lo cambiaba entero. Medido antes del
    arreglo: al pasar de ±4 a ±5 aparecía un menú y DESAPARECÍA otro.
  - Se ordenaba por la SUMA de los tres desfases y el margen mide el PEOR de los
    tres. Un menú de (4,4,4) suma 12 y entra a ±5; otro de (6,0,0) suma 6 y solo
    entra a ±6, pero al ampliar se colaba por delante y echaba a alguien de la lista.

Este test fija las dos cosas. Es fácil de romper sin darse cuenta -- basta con volver
a meter el margen en la consulta o reordenar por el error total.
"""
import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000")
MARGENES = [1, 2, 3, 5, 8, 10, 15]


@pytest.fixture(scope="module")
def headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "clientedemo@test.com", "password": "demo123"},
                      timeout=60)
    assert r.status_code == 200, f"no se pudo entrar: {r.status_code} {r.text[:200]}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _pedir(headers, meal_key, margen, orden="cuadrado"):
    r = requests.post(f"{BASE_URL}/api/calculator/library-menus",
                      json={"mealKey": meal_key, "margen": margen,
                            "limit": 120, "orden": orden},
                      headers=headers, timeout=180)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    d = r.json()
    return d.get("total", 0), [m["biblioteca_id"] for m in d.get("menus", [])]


@pytest.mark.parametrize("meal_key", ["C1", "C2"])
def test_ampliar_el_margen_nunca_quita_menus(headers, meal_key):
    """Lo que sale a ±5 tiene que seguir saliendo a ±10. Es lo que significa un techo."""
    anterior_ids, anterior_margen = None, None
    for margen in MARGENES:
        total, ids = _pedir(headers, meal_key, margen)
        if anterior_ids is not None:
            perdidos = [x for x in anterior_ids if x not in ids]
            assert not perdidos, (
                f"{meal_key}: al pasar de ±{anterior_margen} a ±{margen} han "
                f"DESAPARECIDO {len(perdidos)} menús que ya salían")
        anterior_ids, anterior_margen = ids, margen


@pytest.mark.parametrize("meal_key", ["C1", "C2"])
def test_con_mas_margen_cuadran_mas_menus(headers, meal_key):
    """El total no puede bajar al ampliar: son los mismos más los nuevos."""
    anterior_total, anterior_margen = None, None
    for margen in MARGENES:
        total, _ = _pedir(headers, meal_key, margen)
        if anterior_total is not None:
            assert total >= anterior_total, (
                f"{meal_key}: con ±{margen} cuadran {total} menús y con ±{anterior_margen}, "
                f"que es más estrecho, cuadraban {anterior_total}")
        anterior_total, anterior_margen = total, margen


def test_el_primero_no_cambia_al_ampliar(headers):
    """El menú que mejor encaja lo hace igual de bien con el margen ancho: si cambia,
    es que el orden depende del margen y no debería."""
    _, estrecho = _pedir(headers, "C1", 5)
    _, ancho = _pedir(headers, "C1", 15)
    if estrecho:
        assert ancho and ancho[0] == estrecho[0], (
            "el primer menú cambia al ampliar el margen")
