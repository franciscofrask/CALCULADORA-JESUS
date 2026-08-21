# -*- coding: utf-8 -*-
"""La casilla por comida del Inicio nuevo (bloque 4, doc 21-08).

«Marcar la comida es lo que cuenta como comida»: PATCH /diets/{fecha}/comida-marcada
escribe `comidas.{k}.marcada` dentro del día para que Llevas y Falta salgan de la
cuenta del cliente en cualquier aparato. El peri no se marca (regla 3 del diseño).
"""
import requests

from conftest import API, CLIENT_EMAIL, CLIENT_PASSWORD

FECHA = "2030-02-11"  # una fecha lejana que no pisa datos de nadie


def _token():
    r = requests.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _limpiar(cab):
    requests.delete(f"{API}/diets/{FECHA}", headers=cab, timeout=30)


def test_marcar_y_desmarcar_persisten_en_el_dia():
    cab = _token()
    _limpiar(cab)
    try:
        r = requests.patch(f"{API}/diets/{FECHA}/comida-marcada",
                           json={"comida": "C2", "marcada": True}, headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        dia = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()
        assert (dia.get("comidas") or {}).get("C2", {}).get("marcada") is True

        r = requests.patch(f"{API}/diets/{FECHA}/comida-marcada",
                           json={"comida": "C2", "marcada": False}, headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        dia = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()
        assert (dia.get("comidas") or {}).get("C2", {}).get("marcada") is False
    finally:
        _limpiar(cab)


def test_el_peri_no_se_marca_y_la_basura_tampoco():
    cab = _token()
    for comida in ("Intra", "Post", "C0", "C10", "", None, "C1; drop"):
        r = requests.patch(f"{API}/diets/{FECHA}/comida-marcada",
                           json={"comida": comida, "marcada": True}, headers=cab, timeout=30)
        assert r.status_code == 400, f"{comida!r} tendría que rechazarse: {r.status_code}"


def test_sin_sesion_no_hay_marca():
    r = requests.patch(f"{API}/diets/{FECHA}/comida-marcada",
                       json={"comida": "C1", "marcada": True}, timeout=30)
    assert r.status_code in (401, 403)
