"""
Asignar tareas (doc del 19-08, apartado 05): el formulario de cuatro campos, la lista de
cada uno, marcar hecha y el registro en la ficha. Integración contra el servidor vivo.
"""
import uuid

import pytest
import requests

from conftest import API


@pytest.fixture()
def admin(cabeceras_admin):
    return cabeceras_admin


@pytest.fixture()
def yo(admin):
    equipo = requests.get(f"{API}/admin/tareas/equipo", headers=admin, timeout=30).json()
    assert equipo, "sin staff no hay a quién asignar"
    me = requests.get(f"{API}/auth/me", headers=admin, timeout=30).json()
    return me.get("id") or me.get("user", {}).get("id")


def test_asignar_una_suelta_y_marcarla_hecha(admin, yo):
    marca = f"prueba {uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/admin/tareas", headers=admin, timeout=30,
                      json={"a_quien": yo, "que": f"Tarea suelta de {marca}"})
    assert r.status_code == 200, r.text
    tarea = r.json()["tareas"][0]

    # Sale en «mis tareas de hoy» (sin fecha = para hoy, no para nunca).
    lista = requests.get(f"{API}/admin/tareas", headers=admin, timeout=60).json()
    assert any(t["id"] == tarea["id"] for t in lista["hoy"]), "no aparece en su lista"

    # Se marca hecha y desaparece de la lista, pero no del registro.
    rh = requests.put(f"{API}/admin/tareas/{tarea['id']}/hecha", headers=admin, timeout=30)
    assert rh.status_code == 200
    lista2 = requests.get(f"{API}/admin/tareas", headers=admin, timeout=60).json()
    assert not any(t["id"] == tarea["id"] for t in lista2["hoy"])
    assert any(t["id"] == tarea["id"] for t in lista2["hechas"])


def test_a_varios_de_golpe_queda_en_la_ficha_de_cada_uno(admin, yo):
    clientes = requests.get(f"{API}/admin/clients", headers=admin, timeout=60).json()
    dos = [c["id"] for c in clientes if c.get("id")][:2]
    assert len(dos) == 2, "hacen falta dos clientes con ficha"
    marca = f"contactar {uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/admin/tareas", headers=admin, timeout=30,
                      json={"a_quien": yo, "que": marca, "sobre_quienes": dos,
                            "para_cuando": "2030-01-07"})
    assert r.status_code == 200
    assert r.json()["creadas"] == 2, "una tarea POR CLIENTE, no una para los dos"

    # El registro en la ficha: qué se le pidió y a quién.
    for cid in dos:
        ficha = requests.get(f"{API}/admin/tareas/de-cliente/{cid}", headers=admin,
                             timeout=30).json()
        assert any(t["que"] == marca for t in ficha["pendientes"]), cid

    # Con fecha futura van en «próximas», no en «hoy».
    lista = requests.get(f"{API}/admin/tareas", headers=admin, timeout=60).json()
    assert any(t["que"] == marca for t in lista["proximas"])
    # limpiar: se marcan hechas para no ensuciar la lista de dev
    for t in [t for t in lista["proximas"] if t["que"] == marca]:
        requests.put(f"{API}/admin/tareas/{t['id']}/hecha", headers=admin, timeout=30)


def test_sin_quien_o_sin_que_no_hay_tarea(admin, yo):
    assert requests.post(f"{API}/admin/tareas", headers=admin, timeout=30,
                         json={"a_quien": yo, "que": "  "}).status_code == 400
    assert requests.post(f"{API}/admin/tareas", headers=admin, timeout=30,
                         json={"a_quien": "", "que": "algo"}).status_code == 400
    # A alguien que no es del equipo, tampoco: la tarea se perdería en el vacío.
    assert requests.post(f"{API}/admin/tareas", headers=admin, timeout=30,
                         json={"a_quien": "no-existe", "que": "algo"}).status_code == 400


def test_al_asignado_le_llega_el_aviso(admin, yo):
    marca = f"aviso {uuid.uuid4().hex[:6]}"
    requests.post(f"{API}/admin/tareas", headers=admin, timeout=30,
                  json={"a_quien": yo, "que": marca})
    avisos = requests.get(f"{API}/notifications/equipo", headers=admin, timeout=30).json()
    lista = avisos if isinstance(avisos, list) else avisos.get("notifications", [])
    assert any(marca in (a.get("message") or "") for a in lista), \
        "la tarea no dejó aviso en la campanita del equipo"
    # limpiar
    pend = requests.get(f"{API}/admin/tareas", headers=admin, timeout=60).json()
    for t in [t for t in pend["hoy"] if t["que"] == marca]:
        requests.put(f"{API}/admin/tareas/{t['id']}/hecha", headers=admin, timeout=30)
