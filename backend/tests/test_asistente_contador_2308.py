"""El asistente cuenta CUATRO comidas: el perientreno va aparte (P30, doc del 23-08).

Jesús lo vio en la app: «Ya tienes 5 de 5 comidas montadas de ese día» y en la cabecera
«Día: 5 de 5 comidas», con un día de 4 comidas y peri. La regla del método es que son
CUATRO comidas y el peri no se marca, no se cuadra y no entra en el contador.

Se prueba por donde lo lee el cliente: POST /api/chatbot/configure, que es lo que el
front pinta al abrir el chat. `total_comidas_principales` (el contador de cara al
usuario) tiene que decir 4 con el peri puesto, y el mensaje de apertura de un día ya
hecho tiene que decir «4 de 4», nunca «5 de 5». El total interno con peri
(`total_comidas`) se queda como está: hay cuentas internas que lo necesitan.
"""
import os
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"


def _alimento(cabeceras, texto):
    r = requests.get(f"{API}/calculator/foods", params={"search": texto, "limit": 1},
                     headers=cabeceras, timeout=30)
    assert r.status_code == 200, r.text
    fichas = r.json()
    assert fichas, f"no hay ningún alimento que se llame '{texto}'"
    return fichas[0]


def _item_de_dieta(ficha, cantidad_g):
    return {"alimento_id": ficha["id"], "nombre": ficha["nombre"], "cantidad_g": cantidad_g,
            "categorias": ficha.get("categorias"), "racion": ficha.get("racion"),
            "unidades": ficha.get("unidades", False)}


def _arrancar(cabeceras, fecha, **config):
    """/start + /configure, que es como abre el asistente el front."""
    r = requests.post(f"{API}/chatbot/start", headers=cabeceras, timeout=60)
    assert r.status_code == 200, r.text
    arranque = r.json()
    cfg = {"tipo_dia": "entrenamiento", "num_comidas": 4, "momento_entreno": 1,
           "opcion_peri": "solo_post", "fecha": fecha}
    cfg.update(config)
    r2 = requests.post(f"{API}/chatbot/configure",
                       params={"session_id": arranque["session_id"]},
                       headers=cabeceras, json=cfg, timeout=120)
    assert r2.status_code == 200, r2.text
    return arranque, r2.json()


@pytest.fixture
def fecha_libre(cabeceras_cliente):
    """Un día futuro del cliente demo, vacío al empezar y borrado al terminar.

    A 47 días para no pisar el +40 que usan los tests del caso 38."""
    fecha = (date.today() + timedelta(days=47)).isoformat()
    requests.delete(f"{API}/diets/{fecha}", headers=cabeceras_cliente, timeout=30)
    yield fecha
    requests.delete(f"{API}/diets/{fecha}", headers=cabeceras_cliente, timeout=30)


@pytest.fixture
def dia_entero_con_peri(cabeceras_cliente, fecha_libre):
    """El día de la queja: las 4 comidas hechas Y el post-entreno también."""
    pollo = _alimento(cabeceras_cliente, "Pechuga de pollo")
    arroz = _alimento(cabeceras_cliente, "Arroz blanco")
    cuerpo = {
        "fecha": fecha_libre,
        "tipo_dia": "entrenamiento",
        "num_comidas": 4,
        "momento_entreno": 1,
        "opcion_peri": "solo_post",
        "comidas": {
            "C1": {"alimentos": [_item_de_dieta(pollo, 150), _item_de_dieta(arroz, 100)]},
            "C2": {"alimentos": [_item_de_dieta(pollo, 120), _item_de_dieta(arroz, 80)]},
            "C3": {"alimentos": [_item_de_dieta(pollo, 130), _item_de_dieta(arroz, 90)]},
            "C4": {"alimentos": [_item_de_dieta(pollo, 140), _item_de_dieta(arroz, 70)]},
            "Post": {"alimentos": [_item_de_dieta(arroz, 60)]},
        },
    }
    r = requests.post(f"{API}/diets", headers=cabeceras_cliente, json=cuerpo, timeout=30)
    assert r.status_code == 200, r.text
    return fecha_libre


@pytest.mark.usefixtures("api_disponible")
class TestContadorSinPeri:
    """El contador de cara al usuario dice 4 con 4 comidas + peri."""

    def test_cuatro_comidas_y_post_cuentan_cuatro(self, cabeceras_cliente, fecha_libre):
        _, cfg = _arrancar(cabeceras_cliente, fecha_libre, opcion_peri="solo_post")
        ov = cfg["day_overview"]
        assert ov["total_comidas_principales"] == 4, ov
        assert ov["total_peri"] == 1, ov
        # El total interno con el peri dentro sigue existiendo para quien lo necesite.
        assert ov["total_comidas"] == 5, ov

    def test_con_intra_y_post_siguen_siendo_cuatro(self, cabeceras_cliente, fecha_libre):
        _, cfg = _arrancar(cabeceras_cliente, fecha_libre, opcion_peri="intra_post")
        ov = cfg["day_overview"]
        assert ov["total_comidas_principales"] == 4, ov
        assert ov["total_peri"] == 2, ov
        assert ov["total_comidas"] == 6, ov

    def test_descanso_sin_peri_cuenta_igual(self, cabeceras_cliente, fecha_libre):
        _, cfg = _arrancar(cabeceras_cliente, fecha_libre,
                           tipo_dia="descanso", opcion_peri="sin_peri")
        ov = cfg["day_overview"]
        assert ov["total_comidas_principales"] == 4, ov
        assert ov["total_peri"] == 0, ov


@pytest.mark.usefixtures("api_disponible")
class TestMensajeDeAperturaConDiaHecho:
    """El caso literal de Jesús: día entero con peri, el mensaje dice 4 de 4."""

    def test_dice_4_de_4_y_el_peri_aparte(self, cabeceras_cliente, dia_entero_con_peri):
        _, cfg = _arrancar(cabeceras_cliente, dia_entero_con_peri, opcion_peri="solo_post")
        mensaje = cfg["mensaje"]
        assert "4 de 4 comidas" in mensaje, f"no dice 4 de 4: {mensaje!r}"
        assert "5 de 5" not in mensaje, f"cuenta el peri como comida: {mensaje!r}"
        # El peri se nombra aparte, no dentro del contador.
        assert "peri-entreno también" in mensaje, mensaje
        ov = cfg["day_overview"]
        assert ov["completas_principales"] == 4, ov
        assert ov["completas_peri"] == 1, ov
