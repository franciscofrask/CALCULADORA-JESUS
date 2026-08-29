# -*- coding: utf-8 -*-
"""
Punto 4.11: el entrenador entra en la calculadora de su cliente.

Esto es SUPLANTACION, asi que lo que hay que probar no es que funcione -- eso se ve a la
primera -- sino que no funcione cuando no debe. Los cuatro cerrojos de `core/actuar_como`:

  1. solo el equipo,
  2. hacia clientes, y de admin tambien hacia un entrenador (29-08; nada de actuar como un
     admin, y un entrenador no entra en nadie del equipo),
  3. solo sobre los suyos (la misma regla que la ficha),
  4. y queda anotado.

Se prueba contra la API de verdad porque la cabecera la resuelve `get_current_user`, que es
una dependencia de FastAPI: probarla en aislado seria probar otra cosa.
"""
import os

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


# El coach de las cuentas de QA (22-08). No esta en conftest porque hasta hoy ninguna prueba
# necesitaba entrar COMO entrenador: el unico caso que lo pide es el cerrojo 2, que desde el
# 29-08 responde distinto segun quien pregunte.
@pytest.fixture(scope="module")
def entrenador(api_disponible):
    from conftest import login
    t = login(os.getenv("TEST_TRAINER_EMAIL", "coach.prueba@test.com"),
              os.getenv("TEST_TRAINER_PASSWORD", "QaPrueba2026!"))
    if not t:
        pytest.skip("No se pudo entrar como entrenador. Ajusta TEST_TRAINER_EMAIL/PASSWORD.")
    return t


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

    @pytest.mark.parametrize("rol", ["trainer", "admin"])
    def test_un_admin_entra_en_cualquiera_del_equipo(self, admin, rol):
        """Francisco, 29-08: el equipo usa la app como cliente y reporta fallos de SUS
        pantallas, y no habia forma de verlas sin pedirles la clave.

        Los DOS roles, y el segundo no es un extra: quien lo pidio -- Gonzalo Rubio, que
        entrena -- tiene la cuenta con rol admin, como 7 de los 15 del equipo. Abrirlo solo
        para `trainer` no habria servido justo para su caso.

        Un admin no gana ningun permiso con esto (ya los tiene todos) y ademas ya podia entrar
        por la puerta mala: resetearle la contraseña desde Usuarios.

        Hace falta que el objetivo tenga ficha de cliente: sin ella no hay calculadora que
        abrir y el cerrojo 3 responde 404, que es lo correcto.
        """
        me = requests.get(f"{API}/auth/me", headers=_cabeceras(admin), timeout=30).json()
        equipo = requests.get(f"{API}/admin/users?staff=true", headers=_cabeceras(admin), timeout=30)
        if equipo.status_code != 200:
            pytest.skip("no se pudo listar el equipo")
        objetivos = [u for u in (equipo.json() or [])
                     if u.get("role") == rol and u.get("profile_id") and u["id"] != me["id"]]
        if not objetivos:
            pytest.skip(f"no hay ningun {rol} con ficha de cliente con el que probar")
        r = requests.get(f"{API}/clients/profile",
                         headers=_cabeceras(admin, objetivos[0]["id"]), timeout=30)
        assert r.status_code == 200, f"un admin no ha podido entrar en un {rol} ({r.status_code})"

    def test_un_entrenador_no_entra_en_nadie_del_equipo(self, entrenador, admin):
        """Lo que NO se abrio el 29-08: de entrenador a entrenador sigue cerrado.

        El objetivo se busca con el token de ADMIN a proposito: la lista de Usuarios es solo de
        admin, y si se pidiera con el del entrenador esto seria un skip permanente disfrazado
        de prueba en verde.
        """
        me = requests.get(f"{API}/auth/me", headers=_cabeceras(entrenador), timeout=30).json()
        equipo = requests.get(f"{API}/admin/users?staff=true", headers=_cabeceras(admin), timeout=30)
        if equipo.status_code != 200:
            pytest.skip("no se pudo listar el equipo")
        otros = [u for u in (equipo.json() or []) if u.get("id") and u["id"] != me["id"]]
        if not otros:
            pytest.skip("no hay otro miembro del equipo con el que probar")
        r = requests.get(f"{API}/clients/profile",
                         headers=_cabeceras(entrenador, otros[0]["id"]), timeout=30)
        assert r.status_code == 403, "un entrenador ha entrado en la cuenta de otro del equipo"

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
