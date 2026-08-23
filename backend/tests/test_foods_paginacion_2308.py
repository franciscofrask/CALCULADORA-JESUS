"""
Paginación del listado de alimentos (P39 del doc de Jesús del 23-08).

`/calculator/foods-listado` siempre devolvió el catálogo entero y se le pasaban
limit/offset por la cara: los ignoraba. Ahora admite los dos para pedir tandas, y
sin parámetros sigue devolviendo todo, que es como lo llama hoy la pantalla de
Alimentos. Aquí se comprueba el contrato por los dos lados.

Van contra el backend vivo (mismas credenciales que el resto de la suite, ver conftest).
"""
import os

import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"


def _listado(cabeceras, params=""):
    r = requests.get(f"{API}/calculator/foods-listado{params}", headers=cabeceras, timeout=120)
    assert r.status_code == 200, f"el listado no responde: {r.status_code} {r.text[:200]}"
    return r.json()


def test_sin_parametros_sigue_llegando_el_catalogo_entero(cabeceras_cliente):
    """El contrato de siempre no cambia: la pantalla llama sin parámetros y recibe todo."""
    todos = _listado(cabeceras_cliente)
    assert len(todos) > 300, (
        f"sin parámetros el listado se quedó en {len(todos)} alimentos; "
        "antes llegaba el catálogo entero")


def test_limit_devuelve_solo_la_tanda_pedida(cabeceras_cliente):
    tanda = _listado(cabeceras_cliente, "?limit=20")
    assert len(tanda) == 20, f"se pidieron 20 y llegaron {len(tanda)}"


def test_offset_avanza_sin_repetir_ni_saltarse_fichas(cabeceras_cliente):
    """Dos tandas seguidas tienen que ser el principio del catálogo entero: las mismas
    fichas y en el mismo orden, sin huecos ni repetidos entre tanda y tanda."""
    todos = _listado(cabeceras_cliente)
    primera = _listado(cabeceras_cliente, "?limit=15&offset=0")
    segunda = _listado(cabeceras_cliente, "?limit=15&offset=15")
    assert [f["id"] for f in primera + segunda] == [f["id"] for f in todos[:30]]


def test_offset_pasado_el_final_devuelve_lista_vacia(cabeceras_cliente):
    """Pedir más allá del final no revienta: lista vacía y a otra cosa."""
    fuera = _listado(cabeceras_cliente, "?limit=20&offset=999999")
    assert fuera == []


def test_parametros_negativos_se_rechazan(cabeceras_cliente):
    """Un limit u offset negativo es una llamada mal hecha: 422, no un troceo raro."""
    r = requests.get(f"{API}/calculator/foods-listado?limit=-1",
                     headers=cabeceras_cliente, timeout=60)
    assert r.status_code == 422
    r = requests.get(f"{API}/calculator/foods-listado?offset=-5",
                     headers=cabeceras_cliente, timeout=60)
    assert r.status_code == 422
