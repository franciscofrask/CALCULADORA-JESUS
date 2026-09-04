# -*- coding: utf-8 -*-
"""
LA FOTO SABE DE QUE CICLO ES, Y EL REPORTE TAMBIEN (doc de Jesus del 2-09, fase 1; 4-09).

Jesus daba por hecho que «las fotos suben con el reporte, asi que la app ya sabe si es el
mes 1, 2 o 3 de ese ciclo». Medido en dev: una foto guardaba `taken_at` y `pose` y nada
mas, un reporte no guardaba ni ciclo ni semana ni bloque, y de 3.417 reportes ninguno
llevaba sus fotos cosidas. Desde el 4-09:

  (a) una foto subida nace con los cinco campos del ciclo (`ciclo_id`, `ciclo_numero`,
      `ciclo_inicio`, `semana_del_ciclo`, `bloque`) y con `report_id: None`; el ciclo es
      el del DIA DE LA FOTO, no el de la subida; y con el cuaderno de ciclos lleva su id;
  (b) un reporte nuevo nace con los mismos cinco, por las dos vias;
  (c) al mandar el reporte por la via del cliente, las fotos de la ventana quedan con su
      `report_id` y el reporte con sus `photos`;
  (d) una foto del alta (con `uso`) NO se cose;
  (e) la via del equipo cose igual, y una foto que ya es de un reporte no se repite.

Contra el backend vivo y la base de dev. Cada prueba se hace su propio cliente (marca
TEST_FOTOS_CICLO en el correo y en las notas) y todo se borra al acabar, tambien los
objetos que las fotos dejan en R2.

La via del cliente (c) solo acepta el reporte con la ventana abierta, y la ventana la
decide el calendario: para no depender del dia se prueban varios `cycle_start` hasta dar
con uno que la abra HOY (nivel2 lleva quincenal, miercoles y jueves, y mensual, de viernes
a lunes). Si ningun cycle_start la abre, esa prueba se salta y lo dice.
"""
import asyncio
import base64
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

# El .env se carga aqui arriba, como en test_casos_G_seguimiento: si se carga tarde,
# MONGO_URL no esta cuando se resuelven los fixtures y las pruebas se saltan en silencio.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_RAIZ, ".env"))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

MARCA = "TEST_FOTOS_CICLO"
CLAVE = "demo123"
CAMPOS_CICLO = ("ciclo_id", "ciclo_numero", "ciclo_inicio", "semana_del_ciclo", "bloque")

# Un PNG de 1x1: al endpoint de fotos solo le importan el content-type y el tamano.
PNG_MINIMO = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(PNG_MINIMO).decode()

# Las diez medidas de Jesus, que el mensual exige (caso 51).
DIEZ_MEDIDAS = ["hombros", "mesoesternal", "brazo_d", "brazo_i", "muslo_d", "muslo_i",
                "cadera", "cintura", "gemelo_d", "gemelo_i"]

# Por defecto el cliente de prueba va por la semana 3 de su ciclo (cycle_start dos lunes
# atras): bloque 1, y en nivel2 la semana del mensual.
SEMANAS_ATRAS_POR_DEFECTO = 2


# ==================== fontaneria ====================

def _pide(metodo: str, ruta: str, **kw):
    """Una llamada a la API, reintentando solo si la conexion se cae (el backend de dev se
    reinicia solo al guardar un .py). Un 4xx o un 5xx llega tal cual al test."""
    kw.setdefault("timeout", 90)
    ultimo = None
    for _ in range(8):
        try:
            return requests.request(metodo, f"{API}{ruta}", **kw)
        except requests.ConnectionError as e:
            ultimo = e
            time.sleep(5)
    raise ultimo


def _lunes_hace(semanas: int):
    """El lunes de hace `semanas` semanas, en el calendario de España (que es el del ciclo)."""
    from core.tiempo import a_madrid
    hoy = (a_madrid(datetime.now(timezone.utc)) or datetime.now(timezone.utc)).date()
    return hoy - timedelta(days=hoy.weekday()) - timedelta(weeks=semanas)


def _cycle_start_de(lunes) -> str:
    # A mediodia UTC: el mismo dia en Madrid en cualquier epoca del año.
    return f"{lunes.isoformat()}T12:00:00+00:00"


def _bloque(semana: int) -> int:
    return (semana - 1) // 4 + 1


@pytest.fixture(scope="module")
def mongo(api_disponible):
    from pymongo import MongoClient

    from core.config import DB_NAME, MONGO_URL

    cliente = MongoClient(MONGO_URL)
    try:
        yield cliente[DB_NAME]
    finally:
        cliente.close()


def _borrar_de_r2(docs) -> None:
    """Los objetos que las fotos de prueba dejaron en el bucket. Sin R2 configurado no
    hay nada que borrar; si falla, el huerfano lo recogera una limpieza y aqui no se para."""
    try:
        from core import fotos as fotos_core

        async def _todos():
            for d in docs:
                if d.get("en_r2"):
                    await fotos_core.borrar_objeto_r2(fotos_core._clave_r2_app(d))

        asyncio.run(_todos())
    except Exception as e:      # noqa: BLE001
        print(f"[{MARCA}] no se pudieron borrar los objetos de R2: {e}")


@pytest.fixture(scope="module")
def persona(mongo):
    """Fabrica de clientes de prueba: registrados de verdad, con plan nivel2 activo y un
    ciclo que arranca un lunes conocido. Devuelve cabeceras, ids y lo que se espera de su
    ciclo hoy. Todo lo que crean se borra al acabar el modulo."""
    creados = []

    def _persona(semanas_atras: int = SEMANAS_ATRAS_POR_DEFECTO):
        correo = f"{MARCA.lower()}-{uuid.uuid4().hex[:10]}@test.com"
        r = _pide("POST", "/auth/register",
                  json={"email": correo, "password": CLAVE, "name": "Fotos Ciclo"})
        assert r.status_code == 200, f"no se ha podido registrar: {r.status_code} {r.text[:200]}"
        datos = r.json()
        uid = datos["user"]["id"]
        perfil = mongo.client_profiles.find_one({"user_id": uid})
        assert perfil, "el registro no dejo ficha de cliente"
        lunes = _lunes_hace(semanas_atras)
        # nivel2 lleva quincenal y mensual (12 semanas de ciclo): es el plan con mas dias
        # de ventana abierta. `activo` y `access_until` lejos, por el candado de plan.
        mongo.client_profiles.update_one(
            {"id": perfil["id"]},
            {"$set": {"plan": "nivel2", "status": "activo",
                      "access_until": "2099-01-01T00:00:00+00:00",
                      "cycle_start": _cycle_start_de(lunes)}})
        p = {"email": correo, "user_id": uid, "client_id": perfil["id"],
             "cabeceras": {"Authorization": f"Bearer {datos['access_token']}"},
             "ciclo_inicio": lunes.isoformat(), "semana": semanas_atras + 1}
        creados.append(p)
        return p

    yield _persona

    for p in creados:
        cid, uid = p["client_id"], p["user_id"]
        fotos = list(mongo.client_photos.find({"client_id": cid}, {"data": 0}))
        _borrar_de_r2(fotos)
        mongo.client_photos.delete_many({"client_id": cid})
        mongo.reports.delete_many({"client_id": cid})
        mongo.ciclos.delete_many({"client_id": cid})
        mongo.notifications.delete_many({"$or": [{"user_id": uid}, {"client_id": cid}]})
        mongo.tareas.delete_many({"client_id": cid})
        # OJO: en `users` la clave es `id`, no `user_id` (borrarlos por `user_id` los deja
        # vivos, que es lo que le pasa a la limpieza de test_reportes_de_calma).
        mongo.users.delete_many({"id": uid})
        for coleccion in ("client_profiles", "macro_history", "quiz_respuestas"):
            try:
                mongo[coleccion].delete_many({"user_id": uid})
            except Exception:      # noqa: BLE001
                pass
        mongo.leads.delete_many({"email": p["email"]})


def _sube_foto(p: dict, pose: str, taken_at: str = None) -> dict:
    params = {"pose": pose}
    if taken_at:
        params["taken_at"] = taken_at
    r = _pide("POST", "/reports/photos", headers=p["cabeceras"], params=params,
              files={"file": (f"{MARCA}.png", PNG_MINIMO, "image/png")})
    assert r.status_code == 200, f"no se pudo subir la foto de {pose}: {r.status_code} {r.text[:200]}"
    return r.json()


def _reporte_por_el_equipo(p: dict, cabeceras_admin: dict, **extra) -> dict:
    cuerpo = {"weight": 80.0, "notes": MARCA}
    cuerpo.update(extra)
    r = _pide("POST", f"/admin/clients/{p['client_id']}/reporte", headers=cabeceras_admin, json=cuerpo)
    assert r.status_code == 200, f"el equipo no pudo meter el reporte: {r.status_code} {r.text[:300]}"
    return r.json()


def _abrir_la_ventana(p: dict, mongo) -> dict:
    """Busca un cycle_start que deje la ventana del cliente ABIERTA hoy, probando de una en
    una las doce semanas del ciclo. Devuelve la ventana (con `tipos`) y deja `p` con la
    semana y el inicio que quedaron; None si hoy no hay forma de abrirla."""
    for semanas_atras in range(12):
        lunes = _lunes_hace(semanas_atras)
        mongo.client_profiles.update_one(
            {"id": p["client_id"]}, {"$set": {"cycle_start": _cycle_start_de(lunes)}})
        r = _pide("GET", "/reports/due", headers=p["cabeceras"])
        assert r.status_code == 200, f"GET /reports/due responde {r.status_code}"
        ventana = r.json().get("window") or {}
        if ventana.get("due") and ventana.get("is_open") and not ventana.get("submitted"):
            p["ciclo_inicio"], p["semana"] = lunes.isoformat(), semanas_atras + 1
            return ventana
    return None


def _comprueba_ciclo(doc: dict, p: dict, *, ciclo_id=None, ciclo_numero=1, donde: str):
    for campo in CAMPOS_CICLO:
        assert campo in doc, f"{donde}: falta `{campo}`"
    assert doc["ciclo_id"] == ciclo_id, f"{donde}: ciclo_id {doc['ciclo_id']!r}, esperaba {ciclo_id!r}"
    assert doc["ciclo_numero"] == ciclo_numero, f"{donde}: ciclo_numero {doc['ciclo_numero']!r}"
    assert doc["ciclo_inicio"] == p["ciclo_inicio"], (
        f"{donde}: ciclo_inicio {doc['ciclo_inicio']!r}, esperaba {p['ciclo_inicio']!r}")
    assert doc["semana_del_ciclo"] == p["semana"], (
        f"{donde}: semana_del_ciclo {doc['semana_del_ciclo']!r}, esperaba {p['semana']}")
    assert doc["bloque"] == _bloque(p["semana"]), f"{donde}: bloque {doc['bloque']!r}"


# ==================== (a) la foto ====================

class TestLaFotoSabeDeQueCicloEs:

    def test_a_una_foto_subida_nace_con_su_ciclo_y_sin_reporte(self, persona, mongo):
        """Los cinco campos, congelados al subirla, en la respuesta, en la base y en el
        listado del cliente; y `report_id` a None porque todavia no es de ningun reporte."""
        p = persona()
        meta = _sube_foto(p, "frente")
        _comprueba_ciclo(meta, p, donde="la respuesta de POST /reports/photos")
        assert "report_id" in meta and meta["report_id"] is None, "una foto recien subida no es de ningun reporte"

        doc = mongo.client_photos.find_one({"id": meta["id"]})
        assert doc, "la foto no esta en client_photos"
        _comprueba_ciclo(doc, p, donde="el documento de client_photos")
        assert doc.get("report_id") is None

        # Y viaja en el listado (core/fotos.listar_fotos_de), que es de donde lee Evolucion.
        r = _pide("GET", "/reports/photos", headers=p["cabeceras"])
        assert r.status_code == 200
        mia = next((f for f in r.json()["photos"] if f["id"] == meta["id"]), None)
        assert mia, "la foto no sale en GET /reports/photos"
        _comprueba_ciclo(mia, p, donde="GET /reports/photos")
        assert "report_id" in mia and mia["report_id"] is None

    def test_a_el_ciclo_es_el_del_dia_de_la_foto_no_el_de_la_subida(self, persona):
        """El equipo sube por WhatsApp fotos de dias atras (punto 45): la foto de un lunes
        de la semana 1 es de la semana 1 aunque se suba en la 3."""
        p = persona()
        meta = _sube_foto(p, "espalda", taken_at=f"{p['ciclo_inicio']}T10:00:00+00:00")
        assert meta["semana_del_ciclo"] == 1, f"la foto es del primer dia del ciclo: semana 1, no {meta['semana_del_ciclo']}"
        assert meta["bloque"] == 1
        assert meta["ciclo_inicio"] == p["ciclo_inicio"]

    def test_a_con_el_cuaderno_de_ciclos_la_foto_lleva_el_id_de_su_ciclo(self, persona, mongo):
        """Con el ciclo apuntado en el cuaderno (core/ciclos) la foto lleva su `ciclo_id` y
        su numero de verdad, no el calculado."""
        p = persona()
        ciclo = {
            "id": f"{MARCA}_{uuid.uuid4().hex[:8]}", "client_id": p["client_id"],
            "user_id": p["user_id"], "numero": 2, "inicio": p["ciclo_inicio"], "fin": None,
            "fin_previsto": None, "semanas": 12, "plan": "nivel2", "motivo": "renovacion",
            "origen": MARCA, "objetivo": None, "pico_de_forma": None,
            "created_at": datetime.now(timezone.utc).isoformat(), "cerrado_at": None,
        }
        mongo.ciclos.insert_one(dict(ciclo))
        try:
            meta = _sube_foto(p, "perfil")
            _comprueba_ciclo(meta, p, ciclo_id=ciclo["id"], ciclo_numero=2,
                             donde="la foto con el cuaderno")
        finally:
            mongo.ciclos.delete_many({"client_id": p["client_id"]})


# ==================== (b), (d) y (e): el reporte por la via del equipo ====================

class TestElReportePorLaViaDelEquipo:

    def test_b_y_e_nace_con_su_ciclo_y_cose_las_fotos_sueltas(self, persona, mongo, cabeceras_admin):
        """(b) el reporte nace con los cinco campos; (e) sin `photos` en el body se lleva
        las fotos sueltas del cliente, en orden, y a ellas les queda el `report_id`. Y un
        segundo reporte no repite las que ya son del primero."""
        p = persona()
        primera = _sube_foto(p, "frente")
        segunda = _sube_foto(p, "espalda")

        respuesta = _reporte_por_el_equipo(p, cabeceras_admin)
        reporte = mongo.reports.find_one({"id": respuesta["id"]})
        assert reporte, "el reporte no esta en la base"
        _comprueba_ciclo(reporte, p, donde="el reporte del equipo")
        assert reporte.get("photos") == [primera["id"], segunda["id"]], (
            f"el reporte tenia que llevarse las dos fotos sueltas, en orden: {reporte.get('photos')}")
        assert respuesta.get("photos") == [primera["id"], segunda["id"]], "la respuesta no trae las fotos"
        for foto in (primera, segunda):
            doc = mongo.client_photos.find_one({"id": foto["id"]})
            assert doc.get("report_id") == reporte["id"], f"la foto {foto['pose']} no sabe de que reporte es"

        # Una tercera foto y otro reporte: solo se lleva la nueva.
        tercera = _sube_foto(p, "perfil")
        segundo = mongo.reports.find_one({"id": _reporte_por_el_equipo(p, cabeceras_admin)["id"]})
        assert segundo.get("photos") == [tercera["id"]], (
            f"el segundo reporte se llevo fotos que ya eran del primero: {segundo.get('photos')}")
        assert mongo.client_photos.find_one({"id": primera["id"]})["report_id"] == reporte["id"]
        assert mongo.client_photos.find_one({"id": tercera["id"]})["report_id"] == segundo["id"]

    def test_e_si_el_body_trae_fotos_se_respetan_y_tambien_se_atan(self, persona, mongo, cabeceras_admin):
        p = persona()
        una = _sube_foto(p, "frente")
        otra = _sube_foto(p, "espalda")
        respuesta = _reporte_por_el_equipo(p, cabeceras_admin, photos=[otra["id"]])
        assert respuesta.get("photos") == [otra["id"]]
        assert mongo.client_photos.find_one({"id": otra["id"]})["report_id"] == respuesta["id"]
        assert mongo.client_photos.find_one({"id": una["id"]})["report_id"] is None, (
            "la foto que el body no traia se quedo atada sin que nadie lo pidiera")

    def test_e_la_foto_que_se_subio_sin_ciclo_coge_el_del_reporte(self, persona, mongo, cabeceras_admin):
        """Si al subirla no se pudo situar (los cinco a None), al coserla se le ponen los
        del reporte: son de la misma ventana."""
        p = persona()
        foto = _sube_foto(p, "frente")
        mongo.client_photos.update_one({"id": foto["id"]}, {"$set": {c: None for c in CAMPOS_CICLO}})
        respuesta = _reporte_por_el_equipo(p, cabeceras_admin)
        doc = mongo.client_photos.find_one({"id": foto["id"]})
        assert doc["report_id"] == respuesta["id"]
        _comprueba_ciclo(doc, p, donde="la foto que estaba sin ciclo")

    def test_d_una_foto_del_alta_no_se_cose(self, persona, mongo, cabeceras_admin):
        """La del carrusel de grasa del cuestionario (routes/users, con `uso`) nace con su
        ciclo pero NUNCA acaba en un reporte: no es una foto de progreso."""
        p = persona()
        r = _pide("POST", "/clients/questionnaire", headers=p["cabeceras"],
                  json={"name": "Fotos Ciclo", "email": p["email"], "phone": "600222333",
                        "goal": "volumen", "sex": "hombre", "weight": 80.0, "body_fat": 20.0,
                        "height": 178.0, "foto_grasa": PNG_DATA_URL})
        assert r.status_code == 200, f"el cuestionario no entro: {r.status_code} {r.text[:300]}"
        perfil = mongo.client_profiles.find_one({"id": p["client_id"]})
        alta_id = perfil.get("foto_grasa_id")
        assert alta_id, "la foto del alta no dejo id en la ficha"
        alta = mongo.client_photos.find_one({"id": alta_id})
        assert alta.get("uso") == "alta_grasa"
        assert alta.get("report_id") is None
        _comprueba_ciclo(alta, p, donde="la foto del alta")

        progreso = _sube_foto(p, "frente")
        respuesta = _reporte_por_el_equipo(p, cabeceras_admin)
        assert respuesta.get("photos") == [progreso["id"]], (
            f"el reporte se llevo la foto del alta: {respuesta.get('photos')}")
        assert mongo.client_photos.find_one({"id": alta_id}).get("report_id") is None, (
            "la foto del alta quedo atada a un reporte")


# ==================== (c) el reporte por la via del cliente ====================

class TestElReportePorLaViaDelCliente:

    def test_c_al_mandarlo_las_fotos_de_la_ventana_quedan_con_su_reporte(self, persona, mongo):
        """Por la ruta de verdad, POST /reports, con la ventana abierta: el reporte nace
        con su ciclo y sus `photos`, y cada foto con su `report_id`."""
        p = persona()
        ventana = _abrir_la_ventana(p, mongo)
        if not ventana:
            pytest.skip("Hoy no hay cycle_start que abra la ventana del cliente de prueba "
                        "(el mensual abre de viernes 10:00 a lunes 18:00 y el quincenal de "
                        "miercoles 10:00 a jueves 20:00, hora de España); la costura por la "
                        "via del cliente se prueba esos dias.")
        tipo = (ventana.get("tipos") or [None])[0]

        subidas = [_sube_foto(p, pose)["id"] for pose in ("frente", "espalda", "perfil")]
        cuerpo = {"weight": 80.0, "notes": MARCA, "tipo": tipo,
                  "measurements": {m: 90.0 for m in DIEZ_MEDIDAS}}
        r = _pide("POST", "/reports", headers=p["cabeceras"], json=cuerpo)
        assert r.status_code == 200, f"el cliente no pudo mandar el reporte ({tipo}): {r.status_code} {r.text[:300]}"
        respuesta = r.json()
        assert respuesta.get("photos") == subidas, f"la respuesta no trae las tres fotos en orden: {respuesta.get('photos')}"

        reporte = mongo.reports.find_one({"id": respuesta["id"]})
        assert reporte, "el reporte no esta en la base"
        _comprueba_ciclo(reporte, p, donde="el reporte del cliente")
        assert reporte.get("photos") == subidas
        for fid in subidas:
            doc = mongo.client_photos.find_one({"id": fid})
            assert doc.get("report_id") == reporte["id"], f"la foto {fid} no sabe de que reporte es"
            _comprueba_ciclo(doc, p, donde="una foto cosida")
