# -*- coding: utf-8 -*-
"""EL OBJETIVO LO PONE EL ENTRENADOR (fase 2 del doc de Jesus del 2-09; decisiones de
Francisco del 4-09: la respuesta del reporte no escribe la ficha, migracion literal,
maxima definicion = bajar del 14 % para todos).

Contra el backend vivo (:8000) y la base de dev. Lo que se prueba:

  (a) GET /clients/profile trae `objetivo_actual`, `foco` y `ciclo_actual` con semana y
      bloque, y no inventa un objetivo a quien no lo tiene
  (b) PUT /admin/clients/{id}/objetivo escribe objetivo_actual, goal = motor y el objetivo
      del ciclo abierto; un valor fuera de la lista da 400 con frase humana; sin ciclo
      abierto, `objetivo_ciclo` da 409; el cliente no puede ni por ahi ni por su PUT
  (c) el reporte del CLIENTE con otro proximo_objetivo NO cambia goal ni objetivo_actual y
      deja un aviso al equipo (solo con la ventana abierta hoy; si no, se salta y lo dice)
  (d) el reporte metido por el EQUIPO si los cambia
  (e) abrir_ciclo copia objetivo_actual al ciclo
  (f) desde_goal es literal; y el informe rotula con el nombre de la lista

Cada prueba se hace su cliente (marca TEST_OBJETIVOS en el correo) y todo se borra al
acabar, tambien los objetos que las fotos del mensual dejan en R2.
"""
import base64
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conftest import API, corre                                         # noqa: E402
from core.database import db                                            # noqa: E402
from core.ciclos import abrir_ciclo                                     # noqa: E402
from core.objetivos import desde_goal, motor_de                         # noqa: E402
from core.tiempo import a_madrid, hoy_madrid                            # noqa: E402

MARCA = "TEST_OBJETIVOS"
CLAVE = "demo123"
NOMBRE = "Objetivo De Prueba"
DIEZ_MEDIDAS = ["hombros", "mesoesternal", "brazo_d", "brazo_i", "muslo_d", "muslo_i",
                "cadera", "cintura", "gemelo_d", "gemelo_i"]
# Un PNG de 1x1: al endpoint de fotos solo le importan el content-type y el tamano.
PNG_MINIMO = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


async def _dentro(fn):
    return await fn()


def bd(fn):
    """Una llamada directa a Motor (`db.x.find_one(...)`) hecha DENTRO del bucle común.

    Motor programa el Future en el bucle de su cliente en el momento de llamar al método,
    y ata el cliente al bucle de esa primera llamada: hecha fuera de `corre`, se ataba a
    un bucle nuevo y el siguiente `corre` moría con «The future belongs to a different
    loop». Los tests del cuaderno no lo ven porque su primera llamada va dentro de una
    corutina de verdad (`abrir_ciclo`)."""
    return corre(_dentro(fn))


def _lunes_hace(semanas: int):
    """El lunes de hace `semanas` semanas, en el calendario de España (el del ciclo)."""
    hoy = (a_madrid(datetime.now(timezone.utc)) or datetime.now(timezone.utc)).date()
    return hoy - timedelta(days=hoy.weekday()) - timedelta(weeks=semanas)


def _ficha(cid: str) -> dict:
    return bd(lambda: db.client_profiles.find_one({"id": cid}, {"_id": 0}))


def _ciclo_abierto(cid: str):
    return bd(lambda: db.ciclos.find_one({"client_id": cid, "fin": None}, {"_id": 0}))


def _aviso(cid: str):
    return bd(lambda: db.notifications.find_one({"type": "objetivo_propuesto", "client_id": cid}, {"_id": 0}))


def _borrar_de_r2(docs) -> None:
    try:
        from core import fotos as fotos_core

        async def _todos():
            for d in docs:
                if d.get("en_r2"):
                    await fotos_core.borrar_objeto_r2(fotos_core._clave_r2_app(d))
        corre(_todos())
    except Exception as e:      # noqa: BLE001
        print(f"[{MARCA}] no se pudieron borrar los objetos de R2: {e}")


@pytest.fixture
def persona(api_disponible):
    """Un cliente registrado de verdad, con plan nivel2 activo (12 semanas) y `cycle_start`
    dos lunes atras (hoy: semana 3, bloque 1), con `goal` definicion y SIN objetivo_actual,
    que es como estan las fichas antes de la migracion. Sin entrenador: los avisos del
    equipo van a los administradores. Se borra entero al acabar."""
    correo = f"{MARCA.lower()}-{uuid.uuid4().hex[:10]}@test.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": correo, "password": CLAVE, "name": NOMBRE, "sex": "hombre"})
    if r.status_code == 429:
        pytest.skip("El limitador de registro está activo; pon AUTH_SIN_LIMITE=1 en dev.")
    assert r.status_code in (200, 201), f"no se pudo registrar: {r.status_code} {r.text[:200]}"
    datos = r.json()
    uid = datos["user"]["id"]
    perfil = bd(lambda: db.client_profiles.find_one({"user_id": uid}, {"_id": 0, "id": 1}))
    assert perfil, "el registro no dejó ficha de cliente"
    lunes = _lunes_hace(2)
    bd(lambda: db.client_profiles.update_one({"id": perfil["id"]}, {
        "$set": {"plan": "nivel2", "status": "activo", "access_until": "2099-01-01T00:00:00+00:00",
                 "cycle_start": f"{lunes.isoformat()}T12:00:00+00:00", "goal": "definicion",
                 "sex": "hombre"},
        "$unset": {"objetivo_actual": "", "foco": "", "fase_desde": ""}}))
    p = {"email": correo, "user_id": uid, "client_id": perfil["id"], "lunes": lunes.isoformat(),
         "cabeceras": {"Authorization": f"Bearer {datos['access_token']}"}}
    yield p

    cid = p["client_id"]
    _borrar_de_r2(bd(lambda: db.client_photos.find({"client_id": cid}, {"data": 0}).to_list(50)))
    for coleccion, filtro in (
        ("client_photos", {"client_id": cid}), ("reports", {"client_id": cid}),
        ("ciclos", {"client_id": cid}),
        ("notifications", {"$or": [{"user_id": uid}, {"client_id": cid}]}),
        ("tareas", {"client_id": cid}), ("audit_log", {"detail": {"$regex": NOMBRE}}),
        ("users", {"id": uid}), ("client_profiles", {"user_id": uid}),
        ("macro_history", {"user_id": uid}), ("quiz_respuestas", {"user_id": uid}),
        ("leads", {"email": correo}),
    ):
        try:
            bd(lambda: db[coleccion].delete_many(filtro))
        except Exception:      # noqa: BLE001
            pass


def _perfil_de_mentira(p: dict, **extra) -> dict:
    return {"id": p["client_id"], "user_id": p["user_id"], "plan": "nivel2", **extra}


def _abre_ciclo(p: dict, **extra) -> dict:
    """El ciclo abierto en el cuaderno con el mismo inicio que su cycle_start."""
    return corre(abrir_ciclo(_perfil_de_mentira(p, **extra), inicio=p["lunes"], origen="test"))


def _put_objetivo(p: dict, cabeceras: dict, **body):
    return requests.put(f"{API}/admin/clients/{p['client_id']}/objetivo", headers=cabeceras, json=body)


# ---------------------------------------------------------------- (a) el perfil

def test_a_el_perfil_trae_objetivo_foco_y_ciclo_actual(persona):
    p = persona
    # Sin migrar y sin cuaderno: los tres a null, y no se inventa nada al leer.
    r = requests.get(f"{API}/clients/profile", headers=p["cabeceras"])
    assert r.status_code == 200, r.text[:300]
    perfil = r.json()
    for campo in ("objetivo_actual", "foco", "ciclo_actual", "objetivo_puesto_por", "objetivo_puesto_en"):
        assert campo in perfil, f"falta `{campo}` en GET /clients/profile"
        assert perfil[campo] is None, f"`{campo}` tenía que ser null y es {perfil[campo]!r}"
    assert perfil["goal"] == "definicion"

    bd(lambda: db.client_profiles.update_one(
        {"id": p["client_id"]}, {"$set": {"objetivo_actual": "perder_grasa", "foco": "glúteo"}}))
    _abre_ciclo(p, objetivo_actual="perder_grasa")
    perfil = requests.get(f"{API}/clients/profile", headers=p["cabeceras"]).json()
    assert perfil["objetivo_actual"] == "perder_grasa"
    assert perfil["foco"] == "glúteo"
    assert perfil["ciclo_actual"] == {
        "numero": 1, "inicio": p["lunes"], "semanas": 12, "semana": 3, "bloque": 1,
        "objetivo": "perder_grasa"}, perfil["ciclo_actual"]


# ---------------------------------------------------------------- (b) el PUT del equipo

def test_b_el_put_del_objetivo_escribe_la_ficha_el_goal_y_el_ciclo(persona, cabeceras_admin):
    p = persona
    ciclo = _abre_ciclo(p)
    assert ciclo["objetivo"] is None, "la ficha no tenía objetivo: el ciclo nace sin él"

    r = _put_objetivo(p, cabeceras_admin, objetivo_actual="tonificacion", foco="  glúteo ",
                      objetivo_ciclo="perder_grasa")
    assert r.status_code == 200, r.text[:300]
    perfil = r.json()
    assert perfil["objetivo_actual"] == "tonificacion"
    assert perfil["goal"] == motor_de("tonificacion") == "definicion"
    assert perfil["foco"] == "glúteo"
    assert perfil["objetivo_puesto_por"] and perfil["objetivo_puesto_en"]
    assert perfil["ciclo_actual"]["objetivo"] == "perder_grasa"
    assert perfil["ciclo_actual"]["semana"] == 3 and perfil["ciclo_actual"]["bloque"] == 1

    ficha = _ficha(p["client_id"])
    assert ficha["objetivo_actual"] == "tonificacion" and ficha["goal"] == "definicion"
    assert ficha["foco"] == "glúteo"
    # El motor no cambió (definición sigue siendo definición): la fase no se refecha.
    assert ficha.get("fase_desde") is None
    assert _ciclo_abierto(p["client_id"])["objetivo"] == "perder_grasa"

    # Cambia de motor: goal pasa a volumen y la fase arranca hoy (la foto de «inicio de
    # fase» del informe). El objetivo del ciclo no se toca si no viene.
    r = _put_objetivo(p, cabeceras_admin, objetivo_actual="ganar_volumen")
    assert r.status_code == 200, r.text[:300]
    assert r.json()["goal"] == "volumen" and r.json()["objetivo_actual"] == "ganar_volumen"
    ficha = _ficha(p["client_id"])
    assert ficha["fase_desde"] == hoy_madrid().isoformat()
    assert ficha["foco"] == "glúteo", "cambiar el objetivo no borra el foco"
    assert _ciclo_abierto(p["client_id"])["objetivo"] == "perder_grasa"

    # El foco vacío lo quita; un valor viejo del cuestionario entra normalizado.
    r = _put_objetivo(p, cabeceras_admin, foco="")
    assert r.status_code == 200 and r.json()["foco"] is None
    r = _put_objetivo(p, cabeceras_admin, objetivo_actual="definicion")
    assert r.status_code == 200 and r.json()["objetivo_actual"] == "perder_grasa"
    assert r.json()["goal"] == "definicion"


def test_b_un_objetivo_fuera_de_la_lista_da_400_con_frase_humana(persona, cabeceras_admin):
    p = persona
    for body in ({"objetivo_actual": "ponerse cachas"}, {"objetivo_actual": ""},
                 {"objetivo_actual": None}, {"objetivo_ciclo": "definición máxima"}):
        r = _put_objetivo(p, cabeceras_admin, **body)
        assert r.status_code == 400, f"{body}: {r.status_code} {r.text[:200]}"
        detalle = r.json()["detail"]
        assert "no está en la lista" in detalle and "ganar volumen" in detalle, detalle
        for tecnico in ("Traceback", "Error", "None", "null"):
            assert tecnico not in detalle, detalle
    ficha = _ficha(p["client_id"])
    assert ficha.get("objetivo_actual") is None and ficha["goal"] == "definicion"

    r = _put_objetivo(p, cabeceras_admin, foco="x" * 81)
    assert r.status_code == 400 and "foco" in r.json()["detail"]
    r = _put_objetivo(p, cabeceras_admin)
    assert r.status_code == 400 and r.json()["detail"] == "No hay nada que cambiar"


def test_b_sin_ciclo_abierto_el_objetivo_del_ciclo_da_409_y_no_escribe_nada(persona, cabeceras_admin):
    p = persona
    r = _put_objetivo(p, cabeceras_admin, objetivo_actual="recomposicion", objetivo_ciclo="recomposicion")
    assert r.status_code == 409, r.text[:200]
    assert r.json()["detail"] == "Este cliente no tiene un ciclo abierto todavía"
    ficha = _ficha(p["client_id"])
    assert ficha.get("objetivo_actual") is None, "con el 409 no se escribe ni el objetivo actual"
    assert ficha["goal"] == "definicion"


def test_b_el_cliente_no_puede_ponerse_el_objetivo(persona):
    p = persona
    r = _put_objetivo(p, p["cabeceras"], objetivo_actual="ganar_volumen")
    assert r.status_code == 403, r.text[:200]
    # Ni por su propio PUT del perfil: esos dos campos se descartan.
    r = requests.put(f"{API}/clients/profile", headers=p["cabeceras"],
                     json={"objetivo_actual": "ganar_volumen", "foco": "brazos"})
    assert r.status_code == 200, r.text[:200]
    ficha = _ficha(p["client_id"])
    assert ficha.get("objetivo_actual") is None and ficha.get("foco") is None
    assert ficha["goal"] == "definicion"


# ---------------------------------------------------------------- (c) el reporte del cliente

def _abrir_la_ventana(p: dict):
    """Un cycle_start que deje la ventana del cliente ABIERTA hoy, probando las doce
    semanas del ciclo (misma táctica que test_fotos_y_reportes_con_ciclo). None si hoy
    no hay forma."""
    for semanas_atras in range(12):
        lunes = _lunes_hace(semanas_atras)
        bd(lambda: db.client_profiles.update_one(
            {"id": p["client_id"]}, {"$set": {"cycle_start": f"{lunes.isoformat()}T12:00:00+00:00"}}))
        r = requests.get(f"{API}/reports/due", headers=p["cabeceras"])
        assert r.status_code == 200, f"GET /reports/due responde {r.status_code}"
        ventana = r.json().get("window") or {}
        if ventana.get("due") and ventana.get("is_open") and not ventana.get("submitted"):
            return ventana
    return None


def _sube_foto(p: dict, pose: str) -> dict:
    r = requests.post(f"{API}/reports/photos", headers=p["cabeceras"], params={"pose": pose},
                      files={"file": (f"{MARCA}.png", PNG_MINIMO, "image/png")}, timeout=90)
    assert r.status_code == 200, f"no se pudo subir la foto de {pose}: {r.status_code} {r.text[:200]}"
    return r.json()


def test_c_el_reporte_del_cliente_no_cambia_su_objetivo_y_avisa_al_equipo(persona):
    p = persona
    cid = p["client_id"]
    bd(lambda: db.client_profiles.update_one({"id": cid}, {"$set": {"objetivo_actual": "perder_grasa"}}))
    ventana = _abrir_la_ventana(p)
    if not ventana:
        pytest.skip("Hoy no hay cycle_start que abra la ventana del cliente de prueba (el mensual "
                    "abre de viernes 10:00 a lunes 18:00 y el quincenal de miércoles 10:00 a jueves "
                    "20:00, hora de España); la vía del cliente se prueba esos días.")
    tipo = (ventana.get("tipos") or [None])[0]
    # Con el valor VIEJO del formulario, que es lo que manda la app que lleva en el móvil.
    cuerpo = {"weight": 80.0, "notes": MARCA, "tipo": tipo, "proximo_objetivo": "volumen"}
    if tipo == "mensual":
        for pose in ("frente", "espalda", "perfil"):
            _sube_foto(p, pose)
        cuerpo["measurements"] = {m: 90.0 for m in DIEZ_MEDIDAS}
    r = requests.post(f"{API}/reports", headers=p["cabeceras"], json=cuerpo, timeout=120)
    assert r.status_code == 200, f"el cliente no pudo mandar el reporte ({tipo}): {r.status_code} {r.text[:300]}"
    assert r.json()["proximo_objetivo"] == "ganar_volumen", "el reporte guarda la clave nueva"
    reporte = bd(lambda: db.reports.find_one({"id": r.json()["id"]}, {"_id": 0}))
    assert reporte["proximo_objetivo"] == "ganar_volumen"

    # La ficha, intacta: ni goal, ni objetivo_actual, ni fase_desde.
    ficha = _ficha(cid)
    assert ficha["objetivo_actual"] == "perder_grasa"
    assert ficha["goal"] == "definicion"
    assert ficha.get("fase_desde") is None
    assert ficha.get("objetivo_puesto_por") is None

    # Y el aviso al equipo, con lo que el botón de «aplicar» necesita.
    aviso = _aviso(cid)
    assert aviso, "no quedó aviso al equipo"
    assert aviso["message"] == (f"{NOMBRE} dice que su objetivo ahora es ganar volumen. "
                                "Lo aplicas al contestar su reporte.")
    assert aviso["equipo"] is True and aviso["read"] is False
    assert aviso["objetivo_propuesto"] == "ganar_volumen"
    assert aviso["objetivo_actual"] == "perder_grasa"
    assert aviso["report_id"] == reporte["id"]
    # Sin entrenador, a los administradores (uno por admin).
    admin = bd(lambda: db.users.find_one({"id": aviso["user_id"]}, {"_id": 0, "role": 1}))
    assert admin and admin["role"] == "admin"


# ---------------------------------------------------------------- (d) el reporte del equipo

def test_d_el_reporte_metido_por_el_equipo_si_cambia_el_objetivo(persona, cabeceras_admin):
    p = persona
    cid = p["client_id"]
    bd(lambda: db.client_profiles.update_one({"id": cid}, {"$set": {"objetivo_actual": "perder_grasa"}}))
    r = requests.post(f"{API}/admin/clients/{cid}/reporte", headers=cabeceras_admin,
                      json={"weight": 80.0, "notes": MARCA, "proximo_objetivo": "ganar_volumen"}, timeout=120)
    assert r.status_code == 200, r.text[:300]
    assert r.json()["proximo_objetivo"] == "ganar_volumen"
    ficha = _ficha(cid)
    assert ficha["objetivo_actual"] == "ganar_volumen"
    assert ficha["goal"] == "volumen"
    assert ficha["objetivo_puesto_por"] and ficha["objetivo_puesto_en"]
    assert ficha["fase_desde"] == hoy_madrid().isoformat()
    # Lo puso el equipo: no hay nada que avisarle.
    assert _aviso(cid) is None

    # Un valor viejo entra normalizado; y el mismo objetivo otra vez no reescribe quién.
    r = requests.post(f"{API}/admin/clients/{cid}/reporte", headers=cabeceras_admin,
                      json={"weight": 80.0, "notes": MARCA, "proximo_objetivo": "definicion"}, timeout=120)
    assert r.status_code == 200, r.text[:300]
    ficha = _ficha(cid)
    assert ficha["objetivo_actual"] == "perder_grasa" and ficha["goal"] == "definicion"
    puesto_en = ficha["objetivo_puesto_en"]
    r = requests.post(f"{API}/admin/clients/{cid}/reporte", headers=cabeceras_admin,
                      json={"weight": 80.0, "notes": MARCA, "proximo_objetivo": "perder_grasa"}, timeout=120)
    assert r.status_code == 200
    assert _ficha(cid)["objetivo_puesto_en"] == puesto_en

    # Sin objetivo en el reporte, la ficha no se toca; con uno que no existe, tampoco.
    for valor in (None, "ponerse cachas"):
        r = requests.post(f"{API}/admin/clients/{cid}/reporte", headers=cabeceras_admin,
                          json={"weight": 80.0, "notes": MARCA, "proximo_objetivo": valor}, timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert _ficha(cid)["objetivo_actual"] == "perder_grasa"


# ---------------------------------------------------------------- (e) el cuaderno

def test_e_abrir_ciclo_copia_el_objetivo_actual_de_la_ficha():
    sufijo = uuid.uuid4().hex[:12]
    perfil = {"id": f"objetivos-test-{sufijo}", "user_id": f"objetivos-test-user-{sufijo}",
              "plan": "nivel1", "objetivo_actual": "recomposicion"}
    try:
        ciclo = corre(abrir_ciclo(perfil, inicio="2026-01-05", origen="test"))
        assert ciclo["objetivo"] == "recomposicion"
        # El siguiente nace con lo que la ficha tenga ENTONCES; sin objetivo, sin él.
        siguiente = corre(abrir_ciclo({**perfil, "objetivo_actual": None}, inicio="2026-03-30", origen="test"))
        assert siguiente["objetivo"] is None
        assert bd(lambda: db.ciclos.find_one({"id": ciclo["id"]}, {"_id": 0}))["objetivo"] == "recomposicion"
    finally:
        bd(lambda: db.ciclos.delete_many({"client_id": perfil["id"]}))


# ---------------------------------------------------------------- (f) la migración y el informe

def test_f_desde_goal_es_literal():
    assert desde_goal("volumen") == "ganar_volumen"
    # Definición pasa a perder grasa, NUNCA a máxima definición (Francisco, 4-09).
    assert desde_goal("definicion") == "perder_grasa"
    assert desde_goal(" Definicion ") == "perder_grasa"
    assert desde_goal("mantenimiento") == "mantenimiento"
    assert desde_goal("recomposicion") == "recomposicion"
    # Una clave nueva se queda como está; lo que no se reconoce, a nada.
    assert desde_goal("maxima_definicion") == "maxima_definicion"
    assert desde_goal(None) is None and desde_goal("") is None and desde_goal("otra cosa") is None


def test_f_el_informe_rotula_con_el_nombre_de_la_lista_si_hay_objetivo_actual():
    from core.informe_del_mes import donde_estas, objetivo_del_perfil
    from core.informe_mensual import objetivo_de_ritmo, ritmo_objetivo

    # Sin objetivo_actual, lo de siempre: goal y su rótulo.
    assert objetivo_del_perfil({"goal": "definicion"}) == ("definicion", "Bajar grasa")
    assert objetivo_del_perfil({"goal": "recomposicion"}) == ("recomposicion", None)
    assert objetivo_del_perfil({}) == (None, None)
    # Con él: la clave del motor (para los colores) y el nombre de la lista.
    assert objetivo_del_perfil({"goal": "definicion", "objetivo_actual": "tonificacion"}) == ("definicion", "Tonificación")
    assert objetivo_del_perfil({"goal": "volumen", "objetivo_actual": "maxima_definicion"}) == ("definicion", "Máxima definición")
    assert objetivo_del_perfil({"goal": "volumen", "objetivo_actual": "recomposicion"}) == ("mantenimiento", "Recomposición")
    assert donde_estas("definicion", 3, 12, etiqueta="Tonificación")["objetivo_label"] == "Tonificación"
    assert donde_estas("definicion", 3, 12)["objetivo_label"] == "Bajar grasa"
    # El ritmo: mantenimiento y recomposición van a «mantener»; sin objetivo_actual, goal.
    assert objetivo_de_ritmo({"goal": "definicion", "objetivo_actual": "mantenimiento"}) == "recomposicion"
    assert ritmo_objetivo(objetivo_de_ritmo({"objetivo_actual": "mantenimiento"}), 20.0)["sentido"] == "mantener"
    assert objetivo_de_ritmo({"goal": "volumen"}) == "volumen"
    assert objetivo_de_ritmo({"goal": "definicion", "objetivo_actual": "ganar_volumen"}) == "volumen"
