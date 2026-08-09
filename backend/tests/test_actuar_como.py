# -*- coding: utf-8 -*-
"""
Punto 4.11: el entrenador entra en la calculadora de su cliente.

Esto es SUPLANTACION, asi que lo que hay que probar no es que funcione -- eso se ve a la
primera -- sino que no funcione cuando no debe. Los cuatro cerrojos de `core/actuar_como`:

  1. solo el equipo,
  2. solo hacia clientes (nada de actuar como otro admin),
  3. solo sobre los suyos (la misma regla que la ficha),
  4. y queda anotado.

Se prueba contra la API de verdad porque la cabecera la resuelve `get_current_user`, que es
una dependencia de FastAPI: probarla en aislado seria probar otra cosa.
"""
import pytest
import requests

from conftest import API

CABECERA = "X-Actuar-Como"


def _cabeceras(token, actuar_como=None):
    h = {"Authorization": f"Bearer {token}"}
    if actuar_como:
        h[CABECERA] = actuar_como
    return h


# Los tokens salen de los fixtures de conftest, que ya saltan la prueba con un motivo claro
# si no hay backend o no se puede entrar.
@pytest.fixture(scope="module")
def admin(token_admin):
    return token_admin


@pytest.fixture(scope="module")
def cliente(token_cliente):
    return token_cliente


@pytest.fixture(scope="module")
def id_de_un_cliente(admin):
    r = requests.get(f"{API}/admin/clients?limit=5", headers=_cabeceras(admin), timeout=30)
    r.raise_for_status()
    datos = r.json()
    lista = datos if isinstance(datos, list) else (datos.get("clients") or datos.get("items") or [])
    for c in lista:
        if c.get("user_id"):
            return c["user_id"]
    pytest.skip("no hay clientes con user_id para probar")


class TestLosCerrojos:
    def test_un_cliente_no_puede_actuar_como_otro(self, cliente, id_de_un_cliente):
        """El cerrojo que importa: sin esto, cualquiera se inventa la cabecera."""
        r = requests.get(f"{API}/clients/profile",
                         headers=_cabeceras(cliente, id_de_un_cliente), timeout=30)
        assert r.status_code == 403, f"un cliente ha podido actuar como otro ({r.status_code})"

    def test_sin_la_cabecera_todo_sigue_igual(self, cliente):
        r = requests.get(f"{API}/clients/profile", headers=_cabeceras(cliente), timeout=30)
        assert r.status_code == 200

    def test_actuar_como_uno_mismo_no_es_actuar(self, admin):
        me = requests.get(f"{API}/auth/me", headers=_cabeceras(admin), timeout=30).json()
        r = requests.get(f"{API}/auth/me", headers=_cabeceras(admin, me["id"]), timeout=30)
        assert r.status_code == 200
        assert r.json()["id"] == me["id"]

    def test_no_se_puede_actuar_como_otro_del_equipo(self, admin):
        """Actuar como otro admin seria una escalada de privilegios con nombre bonito."""
        me = requests.get(f"{API}/auth/me", headers=_cabeceras(admin), timeout=30).json()
        equipo = requests.get(f"{API}/admin/trainers", headers=_cabeceras(admin), timeout=30)
        if equipo.status_code != 200:
            pytest.skip("no se pudo listar el equipo")
        otros = [t for t in (equipo.json() or []) if t.get("id") and t["id"] != me["id"]]
        if not otros:
            pytest.skip("no hay otro miembro del equipo con el que probar")
        r = requests.get(f"{API}/clients/profile",
                         headers=_cabeceras(admin, otros[0]["id"]), timeout=30)
        assert r.status_code == 403, "se ha podido actuar como otro miembro del equipo"

    def test_un_usuario_que_no_existe(self, admin):
        r = requests.get(f"{API}/clients/profile",
                         headers=_cabeceras(admin, "no-existo-12345"), timeout=30)
        assert r.status_code == 404


class TestQueDeVerdadFunciona:
    def test_el_admin_ve_el_perfil_del_cliente(self, admin, id_de_un_cliente):
        mio = requests.get(f"{API}/auth/me", headers=_cabeceras(admin), timeout=30).json()
        r = requests.get(f"{API}/auth/me",
                         headers=_cabeceras(admin, id_de_un_cliente), timeout=30)
        assert r.status_code == 200
        assert r.json()["id"] == id_de_un_cliente, "deberia devolver al CLIENTE, no a mi"
        assert r.json()["id"] != mio["id"]

    def test_y_ve_SUS_dietas(self, admin, id_de_un_cliente):
        """Que es el punto: la calculadora entera funciona sin duplicar la API."""
        r = requests.get(f"{API}/diets/recent?limit=3",
                         headers=_cabeceras(admin, id_de_un_cliente), timeout=30)
        assert r.status_code == 200
        assert "diets" in r.json()


class TestQuedaAnotado:
    def test_lo_que_se_guarda_lleva_quien_lo_guardo(self, admin, id_de_un_cliente):
        """«Si el entrenador le monta una dieta el martes y el cliente la cambia el
        miercoles, los dos tienen que poder verlo»."""
        fecha = "2020-01-05"   # una fecha vieja y vacia: no pisa nada de nadie
        r = requests.post(f"{API}/diets", json={"fecha": fecha, "comidas": {}},
                          headers=_cabeceras(admin, id_de_un_cliente), timeout=30)
        assert r.status_code == 200, r.text
        d = requests.get(f"{API}/diets/{fecha}",
                         headers=_cabeceras(admin, id_de_un_cliente), timeout=30).json()
        assert d.get("editado_como") == "entrenador"
        assert d.get("editado_por"), "tiene que decir QUIEN, no solo que fue el equipo"
        # Y se limpia lo que ha dejado el test.
        requests.delete(f"{API}/diets/{fecha}",
                        headers=_cabeceras(admin, id_de_un_cliente), timeout=30)
