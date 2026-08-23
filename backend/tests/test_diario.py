"""
El Diario (T5 del doc 16-08).

Dos cosas se prueban aquí, y son las dos que pueden hacer daño:

  1. Cómo se compone una entrada (el peso destacado, la fecha de los cierres viejos). Son
     funciones puras y se prueban sin base ni servidor.
  2. Que al equipo NO le llegue una nota privada. Esa es la promesa que se le hace al
     cliente al escribirla, y el filtro está en el servidor: si alguien lo mueve al front
     algún día, este test lo tiene que cantar.
"""
import os

import pytest
import requests

from routes.diary import _entrada_de_entreno, _entrada_del_dia, _numero, _peso_destacado

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/") + "/api"


# ── Cómo se monta una entrada ────────────────────────────────────────────────

def test_numero_sin_decimales_de_adorno():
    assert _numero(80.0) == "80"
    assert _numero(82.5) == "82,5"       # con coma, que es como se escribe aquí
    assert _numero(None) == ""


def test_peso_destacado_es_el_mas_pesado():
    pesos = [
        {"ejercicio": "Curl", "reps": 10, "peso_kg": 22.5},
        {"ejercicio": "Press banca", "reps": 8, "peso_kg": 80},
    ]
    assert _peso_destacado(pesos) == "Press banca 80 kg"


def test_sin_pesos_no_se_inventa_ninguno():
    assert _peso_destacado([]) is None
    assert _peso_destacado(None) is None
    # Una fila a medias (sin peso apuntado) tampoco cuenta.
    assert _peso_destacado([{"ejercicio": "Sentadilla", "reps": 10}]) is None


def test_entrada_de_entreno_lleva_estrellas_y_marca():
    e = _entrada_de_entreno({
        "fecha": "2026-08-20", "nota": "La última serie a duras penas.", "estrellas": 4,
        "compartida": True, "pesos": [{"ejercicio": "Press banca", "peso_kg": 80}],
        "created_at": "2026-08-20T09:00:00+00:00",
    })
    assert e["tipo"] == "entreno"
    assert e["estrellas"] == 4
    assert e["compartida"] is True
    assert e["peso_destacado"] == "Press banca 80 kg"


def test_la_fecha_del_cierre_es_el_dia_del_cliente():
    """El cierre de las 23:30 de Madrid es del día 20, aunque en UTC ya sea el 21."""
    e = _entrada_del_dia({
        "dia": "2026-08-20", "created_at": "2026-08-20T21:30:00+00:00",
        "notas": {"texto": "Sin ganas, pero entrené.", "compartida": False},
    })
    assert e["fecha"] == "2026-08-20"
    assert e["compartida"] is False
    assert e["estrellas"] is None


def test_los_cierres_viejos_no_se_quedan_sin_fecha():
    """Los cierres de antes de T4 no traen `dia`: se saca del created_at y así se ordenan."""
    e = _entrada_del_dia({"created_at": "2026-07-02T18:00:00+00:00",
                          "notas": {"texto": "Algo", "compartida": True}})
    assert e["fecha"] == "2026-07-02"


# ── Lo que ve cada uno (necesita backend vivo) ───────────────────────────────

def _saltar_si_apagado(r):
    if r.status_code == 403 and "todavía no está disponible" in r.text:
        pytest.skip("El interruptor t5_diario está apagado en este entorno.")


def test_el_cliente_ve_su_diario(cabeceras_cliente):
    r = requests.get(f"{API}/diary", headers=cabeceras_cliente, timeout=15)
    _saltar_si_apagado(r)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert "entradas" in datos and "hay_mas" in datos
    fechas = [e["fecha"] for e in datos["entradas"]]
    assert fechas == sorted(fechas, reverse=True), "el diario va de lo más nuevo a lo más viejo"
    for e in datos["entradas"]:
        assert e["tipo"] in ("entreno", "dia")
        # Desde el P80 (doc 23-08) una entrada puede venir solo con la nota de entreno
        # del cierre (quien no tiene rutina la apunta ahi): texto o nota, pero algo trae.
        assert e["texto"] or e.get("entreno_nota")


def test_el_equipo_solo_ve_las_compartidas(cabeceras_admin, cabeceras_cliente):
    # OJO CON LOS DOS IDS: el diario va por el id del PERFIL (como `checkins` y
    # `workout_logs`), no por el del usuario. Se resuelve como en el panel: del usuario
    # que ha entrado a su perfil.
    yo = requests.get(f"{API}/auth/me", headers=cabeceras_cliente, timeout=15)
    assert yo.status_code == 200, yo.text
    user_id = yo.json().get("id")
    lista = requests.get(f"{API}/admin/clients?limit=500", headers=cabeceras_admin, timeout=30)
    assert lista.status_code == 200, lista.text
    datos = lista.json()
    clientes = datos if isinstance(datos, list) else datos.get("clients", [])
    demo = next((c for c in clientes if c.get("user_id") == user_id), None)
    client_id = (demo or {}).get("id")
    if not client_id:
        pytest.skip("No se encontró el perfil del cliente de pruebas en el panel.")

    r = requests.get(f"{API}/admin/clients/{client_id}/diary", headers=cabeceras_admin, timeout=15)
    _saltar_si_apagado(r)
    assert r.status_code == 200, r.text
    for e in r.json()["entradas"]:
        assert e["compartida"] is True, "una nota privada no puede salir del servidor"


def test_un_cliente_no_abre_el_diario_de_nadie(cabeceras_cliente):
    r = requests.get(f"{API}/admin/clients/cualquiera/diary", headers=cabeceras_cliente, timeout=15)
    assert r.status_code in (401, 403)
