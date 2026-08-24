# -*- coding: utf-8 -*-
"""
MODO PRUEBAS: poner la cuenta en un estado TIENE que enseñar los avisos de ese estado.

Lo contó Francisco el 24-08 con sus palabras: «me pongo plan gold y marco por vencer
(renovación) y voy al panel cliente y no pasa nada; sí me cambia el plan, pero no veo
los avisos». Debajo había cuatro cosas, y las cuatro se vigilan aquí:

  1. «Por vencer» dejaba el fin del ciclo a DIEZ días y el aviso «Tu ciclo acaba en una
     semana» solo sale a SIETE o menos: el escenario caía fuera de la ventana del aviso
     que se pone para ver.
  2. Un escenario que no fija plan devolvía el plan al original de la foto, así que
     «gold» + «por vencer» deshacía el gold. El plan y el estado son dos ejes.
  3. Los avisos del cliente van topados a UNO AL DÍA: con cualquiera nacido hoy, el del
     estado nuevo no se creaba y no se veía hasta mañana.
  4. Ese tope contaba TAMBIÉN los avisos del equipo, que el cliente ni ve. En una cuenta
     que es cliente y staff a la vez -- la de Francisco --, un «Quiere la rutina del mes»
     le dejaba sin sus avisos el día entero. Ese es de producción, no del modo pruebas.

Contra la API viva, con la cuenta de laboratorio, y devolviéndola a su sitio al acabar.

Ejecutar:
    cd backend && REACT_APP_BACKEND_URL=http://127.0.0.1:8000 \
        venv/Scripts/python.exe -m pytest tests/test_modo_pruebas_avisos_2408.py -q
"""
import os
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import requests

from routes.settings import _campos_de_escenario

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"
REINTENTOS = 20   # el backend de dev va con --reload y rechaza conexiones al reiniciar

LABORATORIO = os.environ.get("TEST_ADMIN_EMAIL", "francisco@test.com")
CLAVE = os.environ.get("TEST_ADMIN_PASSWORD", "demo123")

# La ventana del aviso «Tu ciclo acaba en una semana» (regla 8a de core/avisos_cliente).
DIAS_DE_LA_VENTANA = 7


def pedir(metodo, ruta, **kw):
    fallo = None
    for _ in range(REINTENTOS):
        try:
            return requests.request(metodo, f"{API}{ruta}", timeout=120, **kw)
        except requests.RequestException as e:
            fallo = e
            time.sleep(2)
    raise AssertionError(f"El backend no responde en {ruta}: {fallo}")


@pytest.fixture(scope="module")
def cab():
    r = pedir("post", "/auth/login", json={"email": LABORATORIO, "password": CLAVE})
    if r.status_code != 200:
        pytest.skip(f"No se puede entrar como {LABORATORIO}")
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="module")
def yo(cab):
    r = pedir("get", "/auth/me", headers=cab)
    d = r.json() if r.status_code == 200 else {}
    if not d.get("es_pruebas"):
        pytest.skip(f"{LABORATORIO} no esta marcada es_pruebas: el panel no existe para ella")
    return d


@pytest.fixture(scope="module", autouse=True)
def devolver_la_cuenta(cab, yo):
    """Pase lo que pase, la cuenta de laboratorio vuelve a su estado real."""
    yield
    pedir("post", "/settings/mis-pruebas/restaurar", headers=cab)


def escenario(cab, nombre, plan=None):
    cuerpo = {"escenario": nombre}
    if plan:
        cuerpo["plan"] = plan
    r = pedir("post", "/settings/mis-pruebas/escenario", json=cuerpo, headers=cab)
    assert r.status_code == 200, f"{nombre} devolvio {r.status_code}: {r.text[:200]}"
    return r.json()


def ficha(cab):
    r = pedir("get", "/clients/profile", headers=cab)
    assert r.status_code == 200, f"no se lee la ficha: {r.status_code}"
    return r.json()


def avisos(cab):
    r = pedir("get", "/notifications", headers=cab)
    assert r.status_code == 200, f"no se leen los avisos: {r.status_code}"
    return r.json().get("notifications", [])


# ---------------------------------------------------------------------------
# 1 · el escenario cae DENTRO de la ventana del aviso que quiere enseñar
# ---------------------------------------------------------------------------

def test_por_vencer_cae_dentro_de_la_ventana_del_aviso():
    """Sin base ni HTTP: las fechas que fija el escenario, contra la regla del aviso."""
    campos = _campos_de_escenario("por_vencer", None)
    fin = datetime.fromisoformat(campos["current_period_end"]).date()
    quedan = (fin - date.today()).days
    assert 0 < quedan <= DIAS_DE_LA_VENTANA, (
        f"«por vencer» deja el fin a {quedan} dias y el aviso solo sale a "
        f"{DIAS_DE_LA_VENTANA} o menos: el escenario no enseñaria su propio aviso")
    assert campos["fin_de_ciclo"] == campos["current_period_end"], \
        "las dos fechas del fin de ciclo tienen que ir a la vez"


# ---------------------------------------------------------------------------
# 2 · plan y estado son dos ejes: se combinan
# ---------------------------------------------------------------------------

def test_el_estado_no_se_lleva_por_delante_el_plan_elegido(cab, yo):
    """«Aplicar plan: gold» y luego «por vencer» tiene que dejar gold Y por vencer."""
    escenario(cab, "cambiar_plan", "gold")
    assert ficha(cab).get("plan") == "gold", "«Aplicar plan» no dejo el plan puesto"
    escenario(cab, "por_vencer")
    p = ficha(cab)
    assert p.get("plan") == "gold", \
        "poner «por vencer» devolvio el plan al original: gold y por vencer no se combinan"
    assert p.get("current_period_end"), "«por vencer» no dejo fecha de fin de ciclo"


def test_desde_sin_plan_el_siguiente_estado_recupera_el_plan(cab, yo):
    """El fallo del 22-08 al reves: tras «sin plan», el estado siguiente no puede
    quedarse sin plan (si no, todos salian como «sin plan»)."""
    escenario(cab, "cambiar_plan", "nivel2")
    escenario(cab, "sin_plan")
    assert not (ficha(cab).get("plan") or ""), "«sin plan» no vacio el plan"
    escenario(cab, "caducado")
    assert ficha(cab).get("plan"), \
        "tras «sin plan», el estado siguiente se quedo sin plan y todo sale como «sin plan»"


# ---------------------------------------------------------------------------
# 3 · el estado nuevo enseña sus avisos AHORA, no mañana
# ---------------------------------------------------------------------------

def test_por_vencer_enseña_el_aviso_de_la_renovacion(cab, yo):
    """Lo que pidio Francisco: ponerse «por vencer» y ver el aviso, sin esperar a mañana.

    Se deja un aviso cualquiera nacido hoy para que el tope de uno al dia este disparado:
    asi se comprueba de verdad que poner el escenario limpia y vuelve a evaluar.
    """
    escenario(cab, "cambiar_plan", "gold")
    assert avisos(cab) is not None
    escenario(cab, "por_vencer")
    titulos = [a.get("title") for a in avisos(cab)]
    claves = [str(a.get("clave") or "") for a in avisos(cab)]
    assert any(c.startswith("fin_ciclo") for c in claves), (
        f"«por vencer» no enseña el aviso del fin de ciclo; solo salen: {titulos}")
    ciclo = next(a for a in avisos(cab) if str(a.get("clave") or "").startswith("fin_ciclo"))
    assert ciclo.get("link") == "/renovacion", \
        "el aviso del fin de ciclo tiene que llevar a la renovacion"


# ---------------------------------------------------------------------------
# 4 · un aviso del equipo no gasta el cupo diario del cliente (esto es de produccion)
# ---------------------------------------------------------------------------

def test_un_aviso_del_equipo_no_deja_al_cliente_sin_los_suyos(cab, yo):
    """En una cuenta que es cliente y staff, el buzon del equipo no puede callar el suyo.

    Se siembra por la API de tareas del equipo lo que de verdad pasaba -- una peticion de
    rutina del mes -- y despues se pide un estado que genera aviso de cliente.
    """
    # Sembrar con pymongo, NO con el Motor del backend: el cliente de Motor se ata al
    # bucle en el que nace y llamarlo desde dos `asyncio.run` distintos da «Event loop is
    # closed» (la trampa de siempre en esta casa).
    from pymongo import MongoClient
    from core.database import DB_NAME, MONGO_URL

    uid = yo["id"]
    marca = "Quiere la rutina del mes (prueba " + str(uuid.uuid4())[:8] + ")"
    base = MongoClient(MONGO_URL)[DB_NAME]
    base.notifications.insert_one({
        "id": str(uuid.uuid4()), "user_id": uid, "type": "rutina_del_mes",
        "title": marca, "equipo": True, "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()})
    try:
        escenario(cab, "cambiar_plan", "gold")
        escenario(cab, "por_vencer")
        claves = [str(a.get("clave") or "") for a in avisos(cab)]
        assert any(c.startswith("fin_ciclo") for c in claves), (
            "un aviso del EQUIPO nacido hoy dejo al cliente sin su aviso: el tope de uno "
            "al dia no puede contar avisos que el cliente ni ve")
        assert base.notifications.count_documents({"user_id": uid, "title": marca}) == 1, \
            "el aviso del equipo no puede irse con la limpieza del modo pruebas"
    finally:
        base.notifications.delete_many({"user_id": uid, "title": marca})
