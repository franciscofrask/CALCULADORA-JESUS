# -*- coding: utf-8 -*-
"""
LOS PUNTOS DE CONTROL, EL COMPARADOR Y EL PICO DE FORMA (fase 3 del doc de Jesus del 2-09;
decisiones de Francisco del 4-09). Contra el backend vivo y la base de dev.

Lo que se comprueba, por la API de verdad (`GET /reports/puntos`, `GET
/admin/clients/{id}/puntos`, `PUT`/`DELETE /admin/reports/{id}/pico-de-forma`):

  (a) con un ciclo en el cuaderno y dos reportes mensuales, `puntos` trae los dos con nombre
      «Final bloque N · Ciclo M», del mas antiguo al de hoy, con `peso_maximo` y
      `peso_minimo` en el que toca; y el Punto 0 del alta delante, porque el primer reporte
      esta a mas de una semana del arranque;
  (b) un reporte quincenal NO es punto;
  (c) `grasa` es None sin medida a tres dias y lleva valor cuando la hay;
  (d) `macros` es la fila del historial vigente ese dia;
  (e) los reportes sin ciclo apuntado salen con `aproximado: true` y «Tramo»;
  (f) `atajos_fotos.inicio_de_este_ciclo` lleva nota cuando la foto esta a mas de 7 dias;
  (g) PUT pico-de-forma marca (y la etiqueta aparece en el punto), moverlo lo cambia de
      reporte, DELETE lo quita, y con el ciclo cerrado da 409;
  (h) el cliente no puede llamar al PUT (403).

Cada escenario se hace su propio cliente (marca TEST_PUNTOS_FASE3 en el correo y en el
nombre) y siembra directamente en Mongo lo que la API no deja fechar hacia atras (reportes,
fotos, filas de macros, ciclos), que es lo que hacen los tests vecinos del cuaderno. Todo se
borra al acabar.
"""
import base64
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from bson import Binary

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_RAIZ, ".env"))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

MARCA = "TEST_PUNTOS_FASE3"
CLAVE = "demo123"

PNG_MINIMO = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

DIEZ_MEDIDAS = ["hombros", "mesoesternal", "brazo_d", "brazo_i", "muslo_d", "muslo_i",
                "cadera", "cintura", "gemelo_d", "gemelo_i"]
CAMPOS_CICLO = ("ciclo_id", "ciclo_numero", "ciclo_inicio", "semana_del_ciclo", "bloque")

# El ciclo de prueba arranca hace 31 dias: cabe un reporte en la semana 2 (bloque 1) y otro
# en la semana 5 (bloque 2), los dos ya pasados.
DIAS_DESDE_EL_INICIO = 31


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


def _hoy():
    from core.tiempo import hoy_madrid
    return hoy_madrid()


def _dia(base, dias: int) -> str:
    return (base + timedelta(days=dias)).isoformat()


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(scope="module")
def mongo(api_disponible):
    from pymongo import MongoClient

    from core.config import DB_NAME, MONGO_URL

    cliente = MongoClient(MONGO_URL)
    try:
        yield cliente[DB_NAME]
    finally:
        cliente.close()


@pytest.fixture(scope="module")
def persona(mongo):
    """Fabrica de clientes de prueba registrados de verdad, con plan nivel2 (ciclo de 12
    semanas) y su `cycle_start` hace 31 dias. Todo lo que crean se borra al acabar."""
    creados = []

    def _persona():
        correo = f"{MARCA.lower()}-{uuid.uuid4().hex[:10]}@test.com"
        r = _pide("POST", "/auth/register", json={"email": correo, "password": CLAVE, "name": MARCA})
        assert r.status_code == 200, f"no se ha podido registrar: {r.status_code} {r.text[:200]}"
        datos = r.json()
        uid = datos["user"]["id"]
        perfil = mongo.client_profiles.find_one({"user_id": uid})
        assert perfil, "el registro no dejo ficha de cliente"
        inicio = _hoy() - timedelta(days=DIAS_DESDE_EL_INICIO)
        mongo.client_profiles.update_one(
            {"id": perfil["id"]},
            {"$set": {"plan": "nivel2", "status": "activo",
                      "access_until": "2099-01-01T00:00:00+00:00",
                      "cycle_start": f"{inicio.isoformat()}T12:00:00+00:00"}})
        p = {"email": correo, "user_id": uid, "client_id": perfil["id"], "inicio": inicio,
             "cabeceras": {"Authorization": f"Bearer {datos['access_token']}"}}
        creados.append(p)
        return p

    yield _persona

    for p in creados:
        cid, uid = p["client_id"], p["user_id"]
        mongo.client_photos.delete_many({"client_id": cid})
        mongo.reports.delete_many({"client_id": cid})
        mongo.ciclos.delete_many({"client_id": cid})
        mongo.notifications.delete_many({"$or": [{"user_id": uid}, {"client_id": cid}]})
        mongo.tareas.delete_many({"client_id": cid})
        mongo.users.delete_many({"id": uid})
        for coleccion in ("client_profiles", "macro_history", "quiz_respuestas"):
            try:
                mongo[coleccion].delete_many({"user_id": uid})
            except Exception:      # noqa: BLE001
                pass
        mongo.macro_history.delete_many({"client_id": cid})
        mongo.leads.delete_many({"email": p["email"]})
    # Lo que el pico de forma dejo en la auditoria del panel lleva el nombre del cliente.
    mongo.audit_log.delete_many({"detail": {"$regex": MARCA}})


# ==================== siembra ====================

def _ciclo(p, mongo, *, numero=1, motivo="alta", semanas=12, fin=None) -> dict:
    inicio = p["inicio"].isoformat()
    ciclo = {
        "id": f"{MARCA}_{uuid.uuid4().hex[:8]}", "client_id": p["client_id"], "user_id": p["user_id"],
        "numero": numero, "inicio": inicio, "fin": fin, "fin_previsto": _dia(p["inicio"], semanas * 7 - 1),
        "semanas": semanas, "plan": "nivel2", "motivo": motivo, "origen": MARCA,
        "objetivo": "perder_grasa", "pico_de_forma": None, "created_at": _ahora(), "cerrado_at": None,
    }
    mongo.ciclos.insert_one(dict(ciclo))
    return ciclo


def _reporte(p, mongo, dias: int, peso: float, *, tipo="mensual", ciclo=None, medidas=True) -> str:
    """Un reporte fechado `dias` despues del inicio del ciclo (negativo: antes). Con `ciclo`
    se congelan los cinco campos como hace el envio de verdad; sin el, van a None (un
    reporte de antes del cuaderno)."""
    fecha = _dia(p["inicio"], dias)
    doc = {
        "id": str(uuid.uuid4()), "client_id": p["client_id"], "tipo": tipo, "weight": peso,
        "measurements": {m: 90.0 + dias / 10 for m in DIEZ_MEDIDAS} if medidas else None,
        "photos": None, "notes": MARCA, "trainer_feedback": None,
        "created_at": f"{fecha}T10:00:00+00:00",
    }
    if ciclo:
        semana = max(0, dias) // 7 + 1
        doc.update({"ciclo_id": ciclo["id"], "ciclo_numero": ciclo["numero"], "ciclo_inicio": ciclo["inicio"],
                    "semana_del_ciclo": semana, "bloque": (semana - 1) // 4 + 1})
    else:
        doc.update({c: None for c in CAMPOS_CICLO})
    mongo.reports.insert_one(doc)
    return doc["id"]


def _foto(p, mongo, dias: int, pose: str, report_id=None) -> str:
    fecha = _dia(p["inicio"], dias)
    doc = {
        "id": str(uuid.uuid4()), "client_id": p["client_id"], "user_id": p["user_id"],
        "filename": f"{MARCA}_{pose}_{fecha}.png", "content_type": "image/png", "size": len(PNG_MINIMO),
        "taken_at": f"{fecha}T09:00:00+00:00", "uploaded_at": _ahora(), "pose": pose, "inicial": False,
        "data": Binary(PNG_MINIMO), "report_id": report_id,
    }
    doc.update({c: None for c in CAMPOS_CICLO})
    mongo.client_photos.insert_one(doc)
    return doc["id"]


def _macros(p, mongo, dias: int, proteina: float) -> str:
    fecha = _dia(p["inicio"], dias)
    doc = {
        "id": str(uuid.uuid4()), "client_id": p["client_id"], "user_id": p["user_id"],
        "effective_date": fecha, "created_at": f"{fecha}T08:00:00+00:00", "note": MARCA,
        "training": {"protein": proteina, "carbs": 250.0, "fat": 60.0},
        "rest": {"protein": proteina, "carbs": 150.0, "fat": 70.0},
        "peri": None,
    }
    mongo.macro_history.insert_one(doc)
    return doc["id"]


def _puntos(p) -> dict:
    r = _pide("GET", "/reports/puntos", headers=p["cabeceras"])
    assert r.status_code == 200, f"GET /reports/puntos responde {r.status_code}: {r.text[:300]}"
    return r.json()


def _punto(respuesta: dict, punto_id: str) -> dict:
    punto = next((x for x in respuesta["puntos"] if x["id"] == punto_id), None)
    assert punto, f"el punto {punto_id} no esta en la lista: {[x['nombre'] for x in respuesta['puntos']]}"
    return punto


# ==================== escenario A: un ciclo del cuaderno con dos mensuales ====================

@pytest.fixture(scope="module")
def escenario(persona, mongo):
    """Un cliente con su ciclo del alta en el cuaderno (hace 31 dias), dos reportes
    mensuales (dia 10 y dia 28), un quincenal (dia 20), una medida de grasa a un dia del
    segundo reporte, dos ajustes de macros (uno de antes del ciclo, otro del dia 27) y
    fotos: la sesion del dia 10 cosida al primer reporte, un frente del dia 28 cosido al
    segundo, y una espalda suelta del dia 29 (el ultimo dia sin foto de frente)."""
    p = persona()
    ciclo = _ciclo(p, mongo, motivo="alta")
    r1 = _reporte(p, mongo, 10, 80.0, ciclo=ciclo)
    r2 = _reporte(p, mongo, 28, 78.5, ciclo=ciclo)
    quincenal = _reporte(p, mongo, 20, 79.0, tipo="quincenal", ciclo=ciclo, medidas=False)
    mongo.client_profiles.update_one(
        {"id": p["client_id"]},
        {"$set": {"porcentajes_grasos": [{"fecha": _dia(p["inicio"], 27), "valor": 18.0, "origen": MARCA}],
                  "medidas_inicio": {"cintura": 90.0, "fecha": p["inicio"].isoformat()},
                  "medidas_sueltas": [{"fecha": _dia(p["inicio"], 15), "measurements": {"cintura": 89.0},
                                       "created_at": _ahora()}]}})
    macros_antes = _macros(p, mongo, -20, 150.0)
    macros_despues = _macros(p, mongo, 27, 180.0)
    fotos = {
        "frente_10": _foto(p, mongo, 10, "frente", report_id=r1),
        "perfil_10": _foto(p, mongo, 10, "perfil", report_id=r1),
        "espalda_10": _foto(p, mongo, 10, "espalda", report_id=r1),
        "frente_28": _foto(p, mongo, 28, "frente", report_id=r2),
        "espalda_29": _foto(p, mongo, 29, "espalda"),
    }
    return {"p": p, "ciclo": ciclo, "r1": r1, "r2": r2, "quincenal": quincenal, "fotos": fotos,
            "macros_antes": _dia(p["inicio"], -20), "macros_despues": _dia(p["inicio"], 27)}


class TestLosPuntos:

    def test_a_dos_mensuales_con_nombre_de_bloque_y_ciclo_del_mas_antiguo_al_de_hoy(self, escenario):
        r = _puntos(escenario["p"])
        reportes = [x for x in r["puntos"] if x["tipo"] == "reporte"]
        assert [x["id"] for x in reportes] == [escenario["r1"], escenario["r2"]], (
            f"tenian que ser los dos mensuales, del mas antiguo al de hoy: {[x['nombre'] for x in reportes]}")
        assert reportes[0]["nombre"] == "Final bloque 1 · Ciclo 1"
        assert reportes[0]["nombre_secundario"] == "y el inicio del bloque 2"
        assert reportes[1]["nombre"] == "Final bloque 2 · Ciclo 1"
        assert reportes[1]["nombre_secundario"] == "y el inicio del bloque 3"
        for x in reportes:
            assert x["ciclo_id"] == escenario["ciclo"]["id"] and x["aproximado"] is False
            assert x["objetivo"] == "perder_grasa" and x["objetivo_nombre"] == "Perder grasa"
            assert x["medidas"] and len(x["medidas"]) == 10
        assert reportes[0]["semana"] == 2 and reportes[0]["bloque"] == 1
        assert reportes[1]["semana"] == 5 and reportes[1]["bloque"] == 2
        # El orden de toda la lista es el del tiempo: el Punto 0 del alta va delante.
        fechas = [x["fecha"] for x in r["puntos"]]
        assert fechas == sorted(fechas)

    def test_a_peso_maximo_y_minimo_en_el_que_toca_y_solo_una_vez(self, escenario):
        r = _puntos(escenario["p"])
        assert _punto(r, escenario["r1"])["etiquetas"] == ["peso_maximo"]
        assert _punto(r, escenario["r2"])["etiquetas"] == ["peso_minimo"]
        assert sum("peso_maximo" in x["etiquetas"] for x in r["puntos"]) == 1
        assert sum("peso_minimo" in x["etiquetas"] for x in r["puntos"]) == 1
        assert r["atajos_puntos"]["peso_maximo"] == escenario["r1"]
        assert r["atajos_puntos"]["peso_minimo"] == escenario["r2"]
        assert r["atajos_puntos"]["hoy"] == escenario["r2"]
        assert r["atajos_puntos"]["pico_de_forma"] is None

    def test_a_el_punto_0_del_alta_va_delante_cuando_el_primer_reporte_esta_lejos(self, escenario):
        """El alta esta a 10 dias del primer reporte, mas de una semana: el ciclo arranca
        con un Punto 0 con las medidas de inicio y el nombre del doc."""
        r = _puntos(escenario["p"])
        cero = r["puntos"][0]
        assert cero["tipo"] == "punto0" and cero["id"] == f"punto0:{escenario['ciclo']['id']}"
        assert cero["nombre"] == "Punto 0 · Ciclo 1" and cero["nombre_secundario"] == "el alta"
        assert cero["fecha"] == escenario["p"]["inicio"].isoformat()
        assert cero["medidas"] == {"cintura": 90.0}
        assert cero["report_id"] is None
        assert r["atajos_puntos"]["inicio_de_este_ciclo"] == {"id": cero["id"], "nota": None}
        # El ciclo del cuaderno sale en `ciclos`, abierto y sin aproximar.
        ciclo = next(c for c in r["ciclos"] if c["id"] == escenario["ciclo"]["id"])
        assert ciclo["abierto"] is True and ciclo["aproximado"] is False
        assert ciclo["etiqueta"].startswith("Ciclo 1 · desde ")
        assert ciclo["objetivo_nombre"] == "Perder grasa"

    def test_b_un_quincenal_no_es_punto(self, escenario):
        r = _puntos(escenario["p"])
        assert all(x["id"] != escenario["quincenal"] for x in r["puntos"]), "el quincenal no es un punto"
        assert all(x["report_id"] != escenario["quincenal"] for x in r["puntos"])

    def test_c_grasa_none_sin_medida_a_tres_dias_y_con_valor_cuando_la_hay(self, escenario):
        r = _puntos(escenario["p"])
        assert _punto(r, escenario["r1"])["grasa"] is None, "no hay medida de grasa cerca del primer reporte"
        assert _punto(r, escenario["r2"])["grasa"] == 18.0, "la medida del dia 27 esta a un dia del segundo"

    def test_d_los_macros_son_la_fila_vigente_ese_dia(self, escenario):
        r = _puntos(escenario["p"])
        m1 = _punto(r, escenario["r1"])["macros"]
        m2 = _punto(r, escenario["r2"])["macros"]
        assert m1 and m1["fecha"] == escenario["macros_antes"], f"el primer reporte llevaba el ajuste de antes del ciclo: {m1}"
        assert m1["entreno"] == {"proteina": 150, "hidratos": 250, "grasa": 60}
        assert m1["descanso"] == {"proteina": 150, "hidratos": 150, "grasa": 70}
        assert m1["peri"] is None
        assert m2 and m2["fecha"] == escenario["macros_despues"], f"el segundo reporte llevaba el ajuste del dia 27: {m2}"
        assert m2["entreno"]["proteina"] == 180

    def test_las_fotos_de_un_punto_son_las_cosidas_a_su_reporte(self, escenario):
        r = _puntos(escenario["p"])
        f = escenario["fotos"]
        assert [x["id"] for x in _punto(r, escenario["r1"])["fotos"]] == [f["frente_10"], f["perfil_10"], f["espalda_10"]]
        assert [x["id"] for x in _punto(r, escenario["r2"])["fotos"]] == [f["frente_28"]]
        for foto in _punto(r, escenario["r1"])["fotos"]:
            for clave in ("id", "pose", "taken_at", "fecha", "url"):
                assert clave in foto, f"la foto del punto no trae `{clave}`"

    def test_f_el_atajo_al_inicio_del_ciclo_lleva_nota_si_la_foto_esta_a_mas_de_7_dias(self, escenario):
        r = _puntos(escenario["p"])
        f = escenario["fotos"]
        atajo = r["atajos_fotos"]["inicio_de_este_ciclo"]
        assert atajo and atajo["id"] == f["frente_10"], f"la mas cercana al inicio es el frente del dia 10: {atajo}"
        assert atajo["nota"] and atajo["nota"].startswith("la más próxima al inicio del ciclo: "), atajo
        # Los otros tres: la primera foto (de frente, sin nota), el fin del ciclo anterior
        # (no hay: apagado) y hoy, que es la espalda del dia 29 y lo dice.
        assert r["atajos_fotos"]["mi_primera_foto"] == f["frente_10"]
        assert r["atajos_fotos"]["mi_primera_foto_nota"] is None
        assert r["atajos_fotos"]["fin_del_ciclo_anterior"] is None
        assert r["atajos_fotos"]["hoy"] == f["espalda_29"]
        assert r["atajos_fotos"]["hoy_nota"] == "no tienes foto de frente de esa fecha"
        # Y el selector: las cinco, del ciclo del cuaderno, sin marca (ninguna a una semana
        # del inicio y el fin aun no ha llegado).
        assert len(r["fotos"]) == 5
        for foto in r["fotos"]:
            assert foto["grupo"]["id"] == escenario["ciclo"]["id"] and foto["grupo"]["aproximado"] is False
            assert foto["marca"] is None
        assert [x["fecha"] for x in r["fotos"]] == sorted(x["fecha"] for x in r["fotos"])

    def test_las_tomas_de_medidas_vienen_de_las_tres_puertas(self, escenario):
        r = _puntos(escenario["p"])
        tomas = r["tomas_medidas"]
        por_origen = {t["origen"]: t for t in tomas}
        assert set(t["origen"] for t in tomas) == {"inicio", "suelta", "reporte"}
        assert [t["id"] for t in tomas][0] == "inicio" and tomas[0]["marca"] == "inicio"
        assert por_origen["suelta"]["id"] == f"suelta:{_dia(escenario['p']['inicio'], 15)}"
        assert por_origen["suelta"]["measurements"] == {"cintura": 89.0}
        assert [t["id"] for t in tomas if t["origen"] == "reporte"] == [escenario["r1"], escenario["r2"]], (
            "el quincenal sin medidas no es una toma")
        assert r["atajos_medidas"]["mi_primera_foto"] == "inicio"
        assert r["atajos_medidas"]["inicio_de_este_ciclo"] == {"id": "inicio", "nota": None}
        assert r["atajos_medidas"]["hoy"] == escenario["r2"]

    def test_el_equipo_ve_lo_mismo_por_su_ruta(self, escenario, cabeceras_admin):
        r = _pide("GET", f"/admin/clients/{escenario['p']['client_id']}/puntos", headers=cabeceras_admin)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        mio = _puntos(escenario["p"])
        assert [x["id"] for x in r.json()["puntos"]] == [x["id"] for x in mio["puntos"]]
        assert r.json()["atajos_puntos"] == mio["atajos_puntos"]


# ==================== escenario B: reportes de antes del cuaderno ====================

class TestLosReportesSinCicloApuntado:

    def test_e_salen_aproximados_y_con_tramo(self, persona, mongo):
        """Dos mensuales de antes del cuaderno (60 y 30 dias antes del ciclo apuntado), sin
        ciclo: se situan en tramos contados desde lo primero que hay (el primer reporte, que
        es anterior al alta de la ficha), en bloques de cuatro semanas, y se dice."""
        p = persona()
        ciclo = _ciclo(p, mongo, numero=2, motivo="renovacion")
        viejo1 = _reporte(p, mongo, -60, 82.0)
        viejo2 = _reporte(p, mongo, -30, 81.0)
        nuevo = _reporte(p, mongo, 10, 80.0, ciclo=ciclo)
        r = _puntos(p)
        assert [x["id"] for x in r["puntos"]] == [viejo1, viejo2, nuevo]
        a, b, c = r["puntos"]
        assert a["aproximado"] is True and a["ciclo_id"] is None
        assert a["nombre"] == "Final bloque 1 · Tramo 1" and a["semana"] == 1
        assert b["aproximado"] is True and b["ciclo_id"] is None
        assert b["nombre"] == "Final bloque 2 · Tramo 1" and b["semana"] == 5
        assert b["objetivo"] is None, "un tramo aproximado no tiene objetivo: nadie lo puso"
        assert c["aproximado"] is False and c["nombre"] == "Final bloque 1 · Ciclo 2"
        # En `ciclos`, el tramo delante del ciclo del cuaderno, recortado el dia antes.
        assert [g["id"] for g in r["ciclos"]] == ["tramo:1", ciclo["id"]]
        tramo = r["ciclos"][0]
        assert tramo["aproximado"] is True and tramo["numero"] == 1
        assert tramo["inicio"] == _dia(p["inicio"], -60)
        assert tramo["fin"] == _dia(p["inicio"], -1)
        assert tramo["etiqueta"].startswith("Tramo 1 · ")
        # Sin Punto 0: es una renovacion, no un alta ni una vuelta.
        assert all(x["tipo"] == "reporte" for x in r["puntos"])


# ==================== el pico de forma ====================

class TestElPicoDeForma:

    def test_g_marcar_mover_quitar_y_el_ciclo_cerrado(self, escenario, mongo, cabeceras_admin):
        r1, r2, ciclo = escenario["r1"], escenario["r2"], escenario["ciclo"]
        try:
            r = _pide("PUT", f"/admin/reports/{r2}/pico-de-forma", headers=cabeceras_admin)
            assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
            assert r.json()["pico_de_forma"] == r2 and r.json()["pico_de_forma_puesto_por"]
            assert mongo.ciclos.find_one({"id": ciclo["id"]})["pico_de_forma"] == r2

            puntos = _puntos(escenario["p"])
            assert "pico_de_forma" in _punto(puntos, r2)["etiquetas"]
            assert "pico_de_forma" not in _punto(puntos, r1)["etiquetas"]
            assert puntos["atajos_puntos"]["pico_de_forma"] == r2
            # «El pico no es el peso minimo»: son dos etiquetas y aqui caen en el mismo
            # reporte por casualidad, cada una por lo suyo.
            assert _punto(puntos, r2)["etiquetas"] == ["pico_de_forma", "peso_minimo"]

            # Uno por ciclo: marcar el otro lo mueve.
            r = _pide("PUT", f"/admin/reports/{r1}/pico-de-forma", headers=cabeceras_admin)
            assert r.status_code == 200 and r.json()["pico_de_forma"] == r1
            puntos = _puntos(escenario["p"])
            assert "pico_de_forma" in _punto(puntos, r1)["etiquetas"]
            assert "pico_de_forma" not in _punto(puntos, r2)["etiquetas"]

            # Quitarlo del que no lo tiene no hace nada; del que lo tiene, lo quita.
            r = _pide("DELETE", f"/admin/reports/{r2}/pico-de-forma", headers=cabeceras_admin)
            assert r.status_code == 200 and r.json()["pico_de_forma"] == r1
            r = _pide("DELETE", f"/admin/reports/{r1}/pico-de-forma", headers=cabeceras_admin)
            assert r.status_code == 200 and r.json()["pico_de_forma"] is None
            puntos = _puntos(escenario["p"])
            assert all("pico_de_forma" not in x["etiquetas"] for x in puntos["puntos"])
            assert puntos["atajos_puntos"]["pico_de_forma"] is None

            # Con el ciclo cerrado, ni marcar ni quitar.
            mongo.ciclos.update_one({"id": ciclo["id"]}, {"$set": {"fin": _dia(escenario["p"]["inicio"], 30)}})
            r = _pide("PUT", f"/admin/reports/{r2}/pico-de-forma", headers=cabeceras_admin)
            assert r.status_code == 409, f"{r.status_code} {r.text[:300]}"
            assert r.json()["detail"] == "Ese ciclo ya está cerrado: el pico de forma se marca mientras el ciclo está abierto"
            r = _pide("DELETE", f"/admin/reports/{r2}/pico-de-forma", headers=cabeceras_admin)
            assert r.status_code == 409
        finally:
            mongo.ciclos.update_one({"id": ciclo["id"]}, {"$set": {"fin": None, "pico_de_forma": None}})

    def test_g_un_quincenal_o_un_reporte_sin_ciclo_no_pueden_ser_pico(self, escenario, persona, mongo, cabeceras_admin):
        r = _pide("PUT", f"/admin/reports/{escenario['quincenal']}/pico-de-forma", headers=cabeceras_admin)
        assert r.status_code == 409 and "mensual" in r.json()["detail"], f"{r.status_code} {r.text[:300]}"
        p = persona()
        sin_ciclo = _reporte(p, mongo, -40, 80.0)
        r = _pide("PUT", f"/admin/reports/{sin_ciclo}/pico-de-forma", headers=cabeceras_admin)
        assert r.status_code == 409, f"{r.status_code} {r.text[:300]}"
        assert r.json()["detail"] == "Este reporte no tiene ciclo apuntado"
        r = _pide("PUT", f"/admin/reports/{uuid.uuid4()}/pico-de-forma", headers=cabeceras_admin)
        assert r.status_code == 404

    def test_h_el_cliente_no_puede_marcar_el_pico(self, escenario, mongo):
        r = _pide("PUT", f"/admin/reports/{escenario['r2']}/pico-de-forma", headers=escenario["p"]["cabeceras"])
        assert r.status_code == 403, f"{r.status_code} {r.text[:300]}"
        assert mongo.ciclos.find_one({"id": escenario["ciclo"]["id"]})["pico_de_forma"] is None
        r = _pide("DELETE", f"/admin/reports/{escenario['r2']}/pico-de-forma", headers=escenario["p"]["cabeceras"])
        assert r.status_code == 403
