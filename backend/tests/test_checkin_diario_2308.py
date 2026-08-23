"""
Bloque 14 del doc 23-08 («La app · todo lo que está mal»): el cierre del día.

  - P75: reenviar el cierre del MISMO día lo sustituye, no lo duplica (mismo id, mismo
    created_at, y lo que se dejó en blanco al editar se queda en blanco).
  - P76: el POST no tira ninguno de los siete datos del formulario y todos vuelven por
    el GET (el historial ya puede enseñarlos).
  - P80: /checkins/hoy dice si hay rutina (`tiene_rutina`), y la nota de entreno del que
    no la tiene cae al Diario, también para el equipo, sin arrastrar la nota privada.

Los de HTTP llevan reintentos: el backend de dev se reinicia solo (watchfiles) cuando
otro trabajo guarda un .py, y un ConnectionError en ese instante no es un fallo del test.
"""
import os
import time
import uuid

import pytest
import requests

from models.common import CheckInResponse
from routes.diary import _entrada_del_dia

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/") + "/api"


def _pedir(metodo, ruta, reintentos=4, **kwargs):
    """requests con paciencia: si el backend está reiniciándose, se espera y se repite."""
    kwargs.setdefault("timeout", 25)
    ultimo = None
    for _ in range(reintentos):
        try:
            return requests.request(metodo, f"{API}{ruta}", **kwargs)
        except requests.RequestException as e:
            ultimo = e
            time.sleep(3)
    raise ultimo


# ── Puros: la entrada del Diario con la nota de entreno (P80) ─────────────────

def test_la_entrada_del_dia_lleva_la_nota_de_entreno():
    e = _entrada_del_dia({
        "dia": "2026-08-20",
        "notas": {"texto": "Día flojo.", "compartida": False},
        "entreno_nota": "Media hora de bici",
        "created_at": "2026-08-20T21:00:00+00:00",
    })
    assert e["entreno_nota"] == "Media hora de bici"
    assert e["texto"] == "Día flojo."
    assert e["compartida"] is False


def test_al_equipo_no_le_llega_la_nota_privada_pero_si_el_entreno():
    """La fila entra a la lista del equipo por su nota de entreno; la personal, si no va
    compartida, no sale del servidor ni vacía de contenido."""
    e = _entrada_del_dia({
        "dia": "2026-08-20",
        "notas": {"texto": "Esto es mío.", "compartida": False},
        "entreno_nota": "Media hora de bici",
        "created_at": "2026-08-20T21:00:00+00:00",
    }, solo_compartidas=True)
    assert e["texto"] is None, "una nota privada no puede salir hacia el equipo"
    assert e["entreno_nota"] == "Media hora de bici"
    assert e["compartida"] is True, "lo que queda dentro es todo enseñable"


def test_la_respuesta_del_checkin_dice_su_dia():
    """`dia` se guardaba desde el bloque F pero no salía a la respuesta: sin él no se
    puede saber de qué día es una fila (el created_at va en UTC)."""
    c = CheckInResponse(id="x", client_id="y", type="daily",
                        created_at="2026-08-23T21:30:00+00:00", dia="2026-08-23")
    assert c.dia == "2026-08-23"
    assert c.updated_at is None


# ── Por HTTP, contra el backend vivo ─────────────────────────────────────────

def test_hoy_dice_si_tiene_rutina(api_disponible, cabeceras_cliente):
    r = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "tiene_rutina" in d, "la pantalla necesita saberlo para ofrecer la nota de entreno"
    assert isinstance(d["tiene_rutina"], bool)


def test_reenviar_el_mismo_dia_sustituye_y_no_duplica(api_disponible, cabeceras_cliente):
    """P75: el segundo envío del día corrige al primero. Mismo id, mismo created_at, una
    sola fila del día, y lo que el segundo no trae desaparece (sustituye entero)."""
    fecha = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()["fecha"]

    r1 = _pedir("POST", "/checkins", headers=cabeceras_cliente,
                json={"type": "daily", "fecha": fecha, "energy": 2, "descanso": 3})
    assert r1.status_code == 200, r1.text

    r2 = _pedir("POST", "/checkins", headers=cabeceras_cliente,
                json={"type": "daily", "fecha": fecha, "energy": 5, "hunger_anxiety": 1})
    assert r2.status_code == 200, r2.text

    assert r2.json()["id"] == r1.json()["id"], "corregir no es estrenar fila"
    assert r2.json()["created_at"] == r1.json()["created_at"], "el primer envío fecha la fila"

    hoy = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()
    assert hoy["hecho"] is True
    assert hoy["checkin"]["energy"] == 5, "vale lo último que dijo"
    assert hoy["checkin"].get("descanso") is None, "lo que el segundo envío no trae, se va"

    lista = _pedir("GET", "/checkins?type=daily&limit=100", headers=cabeceras_cliente).json()
    de_hoy = [c for c in lista if c.get("dia") == fecha]
    assert len(de_hoy) == 1, f"una fila por día, y hay {len(de_hoy)}"
    assert de_hoy[0].get("updated_at"), "la edición deja su huella"


def test_el_post_no_tira_ninguno_de_los_siete_datos(api_disponible, cabeceras_cliente):
    """P76: descanso, energía, hambre, desgaste, suplementos, entreno y notas entran y
    vuelven. El peso no se manda aquí para no ensuciar la serie de la cuenta demo; su
    circuito (anotar_peso) ya tiene los suyos."""
    marca = f"prueba-2308-{uuid.uuid4().hex[:6]}"
    fecha = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()["fecha"]
    cuerpo = {
        "type": "daily", "fecha": fecha,
        "descanso": 4, "energy": 3, "hunger_anxiety": 2, "movimiento": "mas",
        "suplementos": {"respuesta": "no_todos", "detalle": "La creatina, se me acabó."},
        "entreno_respuesta": "no_entrene",
        "entreno_nota": f"Paseo largo por la tarde ({marca})",
        "exceso_nota": "Cena de cumpleaños.",
        "cena_hecha": True, "comida_pendiente": "C4",
        "notas": {"texto": f"Buen día en general ({marca})", "compartida": True},
    }
    r = _pedir("POST", "/checkins", headers=cabeceras_cliente, json=cuerpo)
    assert r.status_code == 200, r.text

    guardado = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()["checkin"]
    assert guardado["descanso"] == 4
    assert guardado["energy"] == 3
    assert guardado["hunger_anxiety"] == 2
    assert guardado["movimiento"] == "mas"
    assert guardado["suplementos"] == {"respuesta": "no_todos", "detalle": "La creatina, se me acabó."}
    assert guardado["entreno_respuesta"] == "no_entrene"
    assert marca in guardado["entreno_nota"]
    assert guardado["exceso_nota"] == "Cena de cumpleaños."
    assert guardado["cena_hecha"] is True and guardado["comida_pendiente"] == "C4"
    assert marca in guardado["notas"]["texto"] and guardado["notas"]["compartida"] is True

    # Y por el listado del historial (CheckInResponse) sale igual de entero.
    lista = _pedir("GET", "/checkins?type=daily&limit=5", headers=cabeceras_cliente).json()
    fila = next(c for c in lista if c.get("dia") == fecha)
    for campo in ("descanso", "movimiento", "suplementos", "entreno_nota", "exceso_nota", "notas"):
        assert fila.get(campo) is not None, f"el historial se queda sin {campo}"


@pytest.fixture()
def diario_encendido(api_disponible, cabeceras_admin):
    r = _pedir("PUT", "/admin/settings", headers=cabeceras_admin,
               json={"pantallas": {"t5_diario": True}})
    assert r.status_code == 200, r.text


def test_la_nota_de_entreno_cae_al_diario(api_disponible, cabeceras_cliente, cabeceras_admin, diario_encendido):
    """P80 de punta a punta: el cierre con nota de entreno y nota personal PRIVADA. El
    cliente ve las dos en su diario; el equipo, solo la de entreno."""
    marca = f"diario-2308-{uuid.uuid4().hex[:6]}"
    fecha = _pedir("GET", "/checkins/hoy", headers=cabeceras_cliente).json()["fecha"]
    r = _pedir("POST", "/checkins", headers=cabeceras_cliente, json={
        "type": "daily", "fecha": fecha, "energy": 4,
        "entreno_nota": f"Media hora de andar rápido ({marca})",
        "notas": {"texto": f"Solo para mí ({marca})", "compartida": False},
    })
    assert r.status_code == 200, r.text

    mio = _pedir("GET", "/diary", headers=cabeceras_cliente).json()["entradas"]
    entrada = next(e for e in mio if e["tipo"] == "dia" and e["fecha"] == fecha)
    assert marca in (entrada.get("entreno_nota") or "")
    assert marca in (entrada.get("texto") or ""), "el dueño ve su nota privada"

    # El client_id del perfil (no el del usuario: en esta base conviven dos ids).
    user_id = _pedir("GET", "/auth/me", headers=cabeceras_cliente).json().get("id")
    lista = _pedir("GET", "/admin/clients?limit=500", headers=cabeceras_admin).json()
    clientes = lista if isinstance(lista, list) else lista.get("clients", [])
    client_id = next((c.get("id") for c in clientes if c.get("user_id") == user_id), None)
    if not client_id:
        pytest.skip("No se encontró el perfil del cliente de pruebas en el panel.")

    equipo = _pedir("GET", f"/admin/clients/{client_id}/diary", headers=cabeceras_admin).json()["entradas"]
    del_dia = next((e for e in equipo if e["tipo"] == "dia" and e["fecha"] == fecha), None)
    assert del_dia is not None, "la nota de entreno tiene que llegarle al equipo"
    assert marca in (del_dia.get("entreno_nota") or "")
    assert not del_dia.get("texto"), "la nota privada no sale hacia el equipo"
