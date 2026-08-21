# -*- coding: utf-8 -*-
"""Extras del día (apartado 5 y «Extras» del doc del 21-08).

Lo que el cliente se come fuera de su dieta se apunta en `extras`, una lista hermana de
`comidas` en el documento del día: POST /diets/{fecha}/extras lo añade con los macros de
etiqueta ya calculados, DELETE /diets/{fecha}/extras/{id} lo quita. Cuentan en «Llevas»
(los suma la pantalla) y NO tocan la dieta: `servido_comidas` no debe moverse por un extra.
"""
import requests

from conftest import API, CLIENT_EMAIL, CLIENT_PASSWORD

FECHA = "2030-02-12"  # una fecha lejana que no pisa datos de nadie


def _token():
    r = requests.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _limpiar(cab):
    requests.delete(f"{API}/diets/{FECHA}", headers=cab, timeout=30)


def _un_alimento(cab):
    """Un alimento real del catálogo con macros que contar."""
    r = requests.get(f"{API}/calculator/foods", params={"limit": 50}, headers=cab, timeout=30)
    assert r.status_code == 200, r.text
    for f in r.json():
        if (f.get("proteinas") or f.get("hidratos") or f.get("grasas")):
            return f
    raise AssertionError("No hay alimentos con macros en el catálogo local")


def test_anadir_extra_calcula_macros_y_persiste_y_borrar_borra():
    cab = _token()
    _limpiar(cab)
    try:
        food = _un_alimento(cab)
        r = requests.post(f"{API}/diets/{FECHA}/extras",
                          json={"alimento_id": food["id"], "cantidad_g": 100},
                          headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        extra = r.json()["extra"]
        assert extra["id"] and extra["alimento_id"] == food["id"]
        assert extra["nombre"] == food["nombre"]
        assert extra["cantidad_g"] == 100
        macros = extra["macros"]
        # Macros de etiqueta calculados al añadir: alguno tiene que contar.
        assert (macros["P"] + macros["H"] + macros["G"]) > 0

        # Persiste: /diets/{fecha} devuelve el día (upsertado) con su extra.
        dia = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()
        guardados = dia.get("extras") or []
        assert [e["id"] for e in guardados] == [extra["id"]]
        assert guardados[0]["macros"] == macros

        # Y borrar borra: la lista queda vacía y repetir el borrado es un 404.
        r = requests.delete(f"{API}/diets/{FECHA}/extras/{extra['id']}", headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        dia = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()
        assert not (dia.get("extras") or [])
        r = requests.delete(f"{API}/diets/{FECHA}/extras/{extra['id']}", headers=cab, timeout=30)
        assert r.status_code == 404, r.text
    finally:
        _limpiar(cab)


def test_el_servido_de_comidas_no_cuenta_los_extras():
    """Los extras cuentan en Llevas (los suma la pantalla), NO en la dieta: `servido_comidas`
    sale de las comidas y un extra no debe moverlo ni un gramo."""
    cab = _token()
    _limpiar(cab)
    try:
        food = _un_alimento(cab)
        # Un día con UNA comida montada de verdad...
        r = requests.post(f"{API}/diets", headers=cab, timeout=30, json={
            "fecha": FECHA, "tipo_dia": "entrenamiento", "num_comidas": 4,
            "comidas": {"C1": {"alimentos": [
                {"alimento_id": food["id"], "nombre": food["nombre"], "cantidad_g": 100},
            ]}},
        })
        assert r.status_code == 200, r.text
        antes = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()["servido_comidas"]

        # ...y un extra encima: el servido de las comidas tiene que quedarse igual.
        r = requests.post(f"{API}/diets/{FECHA}/extras",
                          json={"alimento_id": food["id"], "cantidad_g": 250},
                          headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        dia = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()
        assert dia["servido_comidas"] == antes
        assert len(dia.get("extras") or []) == 1
    finally:
        _limpiar(cab)


def test_alimento_inexistente_y_cantidades_basura():
    cab = _token()
    r = requests.post(f"{API}/diets/{FECHA}/extras",
                      json={"alimento_id": -999999, "cantidad_g": 100}, headers=cab, timeout=30)
    assert r.status_code == 404, r.text

    food = _un_alimento(cab)
    for cantidad in (0, -50, "nada", None, 999999):
        r = requests.post(f"{API}/diets/{FECHA}/extras",
                          json={"alimento_id": food["id"], "cantidad_g": cantidad},
                          headers=cab, timeout=30)
        assert r.status_code == 400, f"cantidad {cantidad!r} tendría que rechazarse: {r.status_code}"

    r = requests.post(f"{API}/diets/una-fecha-mala/extras",
                      json={"alimento_id": food["id"], "cantidad_g": 100}, headers=cab, timeout=30)
    assert r.status_code == 400, r.text


def test_sin_sesion_no_hay_extras():
    r = requests.post(f"{API}/diets/{FECHA}/extras",
                      json={"alimento_id": 1, "cantidad_g": 100}, timeout=30)
    assert r.status_code in (401, 403)
    r = requests.delete(f"{API}/diets/{FECHA}/extras/loquesea", timeout=30)
    assert r.status_code in (401, 403)
