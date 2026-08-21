# -*- coding: utf-8 -*-
"""La pantalla de rutina completa (tarea 7.1 del 21-08, apartados 12 y 19).

Tres piezas del lado del servidor, probadas contra el backend vivo:

1. LOS DOS DATOS DEL PDF: el reparto de grupos por día y las semanas que dura viajan
   con el PDF (db.rutina_pdfs), se leen en los dos info (admin y cliente) y se pueden
   corregir sin resubir el archivo (PATCH detalles).

2. LA SEMANA DE LA RUTINA (GET /routines/semana): con el reparto del entrenador y los
   días del cliente (training_weekdays, nombres de día) la semana dice qué grupo toca
   cada día, qué está hecho (workout_logs, T3) y qué se dejó; «Sí lo hice» marca un día
   pasado de esta semana y «Recuperarlo otro día» lo apunta en un día de descanso
   (decisión del apartado 12: no se mueve, se recupera).

3. EL GRUPO EN MI SEMANA (GET /diets/semana): el nombre del grupo llega cuando el
   reparto existe, sin rutina estructurada de por medio.

Todo lo que el módulo escribe en la base del demo se limpia al final.
"""
import io
import os
from datetime import date, datetime, timedelta, timezone

import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://127.0.0.1:8000").rstrip("/") + "/api"

# Los días que "elige" el demo en este escenario y el reparto que pone el entrenador.
DIAS_DEMO = ["lunes", "martes", "jueves", "viernes"]
REPARTO = ["Empuje", "Tirón", "Pierna", "Empuje"]
SEMANAS = 8
INDICES = {"lunes": 0, "martes": 1, "jueves": 3, "viernes": 4}

# Un PDF de verdad, mínimo: la subida valida el content-type, no el contenido.
PDF_MINIMO = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF\n"


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo123"}, timeout=10)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _mongo():
    import pymongo
    from dotenv import dotenv_values
    cfg = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
    return pymongo.MongoClient(cfg["MONGO_URL"])[cfg["DB_NAME"]]


@pytest.fixture(scope="module")
def esc():
    """El escenario entero: PDF con reparto subido al demo y sus días puestos.

    Se monta una vez y se desmonta entero al final: la base del demo queda como estaba.
    """
    try:
        admin = _login("francisco@test.com")
    except requests.ConnectionError:
        pytest.skip("backend apagado")
    cliente = _login("clientedemo@test.com")
    db = _mongo()

    me = requests.get(f"{BASE}/auth/me", headers=cliente, timeout=10).json()
    perfil = db.client_profiles.find_one({"user_id": me["id"]}, {"_id": 0, "id": 1,
                                                                 "training_days": 1,
                                                                 "training_weekdays": 1})
    cid = perfil["id"]

    ajustes = db.app_settings.find_one({"id": "app"}, {"_id": 0, "pantallas": 1}) or {}
    if not (ajustes.get("pantallas") or {}).get("t3_entreno"):
        pytest.skip("t3_entreno apagado en esta base: la mitad del escenario no aplica")

    # La foto de ANTES, para devolverlo todo a su sitio.
    antes = {
        "training_days": perfil.get("training_days"),
        "training_weekdays": perfil.get("training_weekdays"),
        "logs": {l["fecha"] for l in db.workout_logs.find({"client_id": cid}, {"fecha": 1})},
        "arranque": datetime.now(timezone.utc).isoformat(),
    }

    # Los días del cliente, como los guardaría el alta.
    db.client_profiles.update_one({"id": cid}, {"$set": {"training_weekdays": DIAS_DEMO,
                                                         "training_days": len(DIAS_DEMO)}})

    yield {"admin": admin, "cliente": cliente, "db": db, "cid": cid, "user_id": me["id"]}

    # ── La limpieza, entera ──────────────────────────────────────────────────
    db.rutina_pdfs.delete_many({"client_id": cid})
    db.workout_recuperaciones.delete_many({"client_id": cid})
    for l in db.workout_logs.find({"client_id": cid}, {"_id": 1, "fecha": 1}):
        if l["fecha"] not in antes["logs"]:
            db.workout_logs.delete_one({"_id": l["_id"]})
    restore = {}
    unset = {}
    for campo in ("training_days", "training_weekdays"):
        if antes[campo] is None:
            unset[campo] = ""
        else:
            restore[campo] = antes[campo]
    op = {}
    if restore:
        op["$set"] = restore
    if unset:
        op["$unset"] = unset
    if op:
        db.client_profiles.update_one({"id": cid}, op)
    # El aviso «Ya tienes tu rutina» que dispara la subida del PDF.
    db.notifications.delete_many({"user_id": me["id"], "familia": "rutina_nueva",
                                  "created_at": {"$gte": antes["arranque"]}})


def _subir_pdf(esc, reparto=", ".join(REPARTO), semanas=str(SEMANAS)):
    files = {"file": ("rutina_prueba.pdf", io.BytesIO(PDF_MINIMO), "application/pdf")}
    data = {}
    if reparto is not None:
        data["reparto"] = reparto
    if semanas is not None:
        data["semanas"] = semanas
    r = requests.post(f"{BASE}/admin/routines/pdf/{esc['cid']}", headers=esc["admin"],
                      files=files, data=data, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _semana(esc):
    r = requests.get(f"{BASE}/routines/semana", headers=esc["cliente"], timeout=10)
    assert r.status_code == 200, r.text
    return r.json()


class TestLosDosDatosDelPdf:
    def test_sin_pdf_la_semana_dice_que_no_hay(self, esc):
        # Días puestos pero ningún PDF ni rutina: no hay semana que pintar.
        s = _semana(esc)
        assert s["hay"] is False
        assert s["tiene_pdf"] is False

    def test_el_reparto_y_las_semanas_viajan_con_el_pdf(self, esc):
        subida = _subir_pdf(esc)
        assert subida["reparto"] == REPARTO
        assert subida["semanas"] == SEMANAS

        # El info del admin y el del cliente los devuelven igual.
        r = requests.get(f"{BASE}/admin/routines/pdf/{esc['cid']}/info",
                         headers=esc["admin"], timeout=10)
        assert r.status_code == 200
        assert r.json()["reparto"] == REPARTO
        assert r.json()["semanas"] == SEMANAS

        r = requests.get(f"{BASE}/routines/pdf/info", headers=esc["cliente"], timeout=10)
        assert r.status_code == 200
        assert r.json()["reparto"] == REPARTO
        assert r.json()["semanas"] == SEMANAS

    def test_los_detalles_se_corrigen_sin_resubir(self, esc):
        r = requests.patch(f"{BASE}/admin/routines/pdf/{esc['cid']}/detalles",
                           headers=esc["admin"], timeout=10,
                           json={"reparto": "Torso, Pierna", "semanas": 6})
        assert r.status_code == 200
        info = requests.get(f"{BASE}/routines/pdf/info", headers=esc["cliente"], timeout=10).json()
        assert info["reparto"] == ["Torso", "Pierna"]
        assert info["semanas"] == 6
        # Y de vuelta al escenario del módulo.
        requests.patch(f"{BASE}/admin/routines/pdf/{esc['cid']}/detalles",
                       headers=esc["admin"], timeout=10,
                       json={"reparto": ", ".join(REPARTO), "semanas": SEMANAS})

    def test_unas_semanas_imposibles_no_se_guardan(self, esc):
        r = requests.patch(f"{BASE}/admin/routines/pdf/{esc['cid']}/detalles",
                           headers=esc["admin"], timeout=10, json={"semanas": "cero"})
        assert r.status_code == 200
        assert r.json()["semanas"] is None
        requests.patch(f"{BASE}/admin/routines/pdf/{esc['cid']}/detalles",
                       headers=esc["admin"], timeout=10, json={"semanas": SEMANAS})


class TestLaSemanaDeLaRutina:
    def test_la_cabecera_y_la_tira(self, esc):
        s = _semana(esc)
        assert s["hay"] is True
        assert s["tiene_pdf"] is True
        assert s["numero"] == 1                      # su primer PDF
        assert s["semanas"] == SEMANAS
        assert s["semana_actual"] == 1               # subido esta misma semana
        assert s["dias_de_entreno"] == len(DIAS_DEMO)
        assert len(s["dias"]) == 7

        # El reparto, POR ORDEN sobre sus días: lunes Empuje, martes Tirón, jueves
        # Pierna, viernes Empuje; el resto, descanso.
        por_dia = {d["dia"]: d for d in s["dias"]}
        assert por_dia["lunes"]["grupo"] == "Empuje"
        assert por_dia["martes"]["grupo"] == "Tirón"
        assert por_dia["jueves"]["grupo"] == "Pierna"
        assert por_dia["viernes"]["grupo"] == "Empuje"
        for dia in ("miércoles", "sábado", "domingo"):
            assert por_dia[dia]["entrena"] is False
            assert por_dia[dia]["grupo"] is None

        # «Hoy» es el día de hoy de la tira, no otro. En HORA DE ESPAÑA, que es la
        # del servidor: date.today() aquí es la de la máquina y de madrugada (o desde
        # otro huso) se equivoca de día. Es la trampa documentada de la casa.
        assert s["hoy"]["hoy"] is True
        hoy_servidor = next(d["fecha"] for d in s["dias"] if d["hoy"])
        assert s["hoy"]["fecha"] == hoy_servidor

    def test_el_descanso_es_un_estado(self, esc):
        # Un día de descanso viene sin grupo y sin «hecho» que rellenar: la pantalla
        # no tiene nada que pedir.
        s = _semana(esc)
        descanso = next(d for d in s["dias"] if not d["entrena"])
        assert descanso["grupo"] is None
        assert descanso["hecho"] is None

    def test_el_que_se_dejo_es_el_mas_reciente_sin_registro(self, esc):
        s = _semana(esc)
        hoy = date.fromisoformat(s["hoy"]["fecha"])
        logs = {l["fecha"] for l in esc["db"].workout_logs.find(
            {"client_id": esc["cid"]}, {"fecha": 1})}
        lunes = hoy - timedelta(days=hoy.weekday())
        esperado = None
        for i in sorted(INDICES.values(), reverse=True):
            f = (lunes + timedelta(days=i)).isoformat()
            if f < hoy.isoformat() and f not in logs:
                esperado = f
                break
        if esperado is None:
            assert s["pendiente"] is None
        else:
            assert s["pendiente"] is not None, "tocaba preguntar por el entreno perdido"
            assert s["pendiente"]["fecha"] == esperado

    def test_si_lo_hice_marca_ese_dia(self, esc):
        s = _semana(esc)
        if not s["pendiente"]:
            pytest.skip("esta semana no tiene ningún entreno sin registrar todavía")
        pendiente = s["pendiente"]
        r = requests.post(f"{BASE}/routines/semana/hecho", headers=esc["cliente"],
                          json={"fecha": pendiente["fecha"], "grupo": pendiente["grupo"]},
                          timeout=10)
        assert r.status_code == 200, r.text
        # El registro está en workout_logs, la fuente única de lo hecho (T3).
        log = esc["db"].workout_logs.find_one({"client_id": esc["cid"],
                                               "fecha": pendiente["fecha"]}, {"_id": 0})
        assert log and log["hecho"] is True
        assert log["dia_rutina"] == pendiente["grupo"]
        # Y la semana ya no pregunta por ese día.
        s2 = _semana(esc)
        marcado = next(d for d in s2["dias"] if d["fecha"] == pendiente["fecha"])
        assert marcado["hecho"] is True
        assert not (s2["pendiente"] and s2["pendiente"]["fecha"] == pendiente["fecha"])

    def test_un_dia_futuro_no_se_puede_marcar(self, esc):
        s = _semana(esc)
        futuro = next((d for d in s["dias"] if d["fecha"] > s["hoy"]["fecha"]), None)
        if not futuro:
            pytest.skip("domingo: no queda semana por delante")
        r = requests.post(f"{BASE}/routines/semana/hecho", headers=esc["cliente"],
                          json={"fecha": futuro["fecha"]}, timeout=10)
        assert r.status_code == 400

    def test_una_fecha_de_otra_semana_no_vale(self, esc):
        fuera = (date.today() - timedelta(days=9)).isoformat()
        r = requests.post(f"{BASE}/routines/semana/hecho", headers=esc["cliente"],
                          json={"fecha": fuera}, timeout=10)
        assert r.status_code == 400

    def test_recuperar_apunta_el_grupo_en_un_descanso(self, esc):
        s = _semana(esc)
        hoy = s["hoy"]["fecha"]
        perdido = next((d for d in s["dias"]
                        if d["entrena"] and d["fecha"] < hoy
                        and not d["registrado"] and not d["recuperado_en"]), None)
        descanso = next((d for d in s["dias"]
                         if not d["entrena"] and d["fecha"] >= hoy), None)
        if not perdido or not descanso:
            pytest.skip("esta semana no deja hueco para recuperar (ni perdido ni descanso)")
        r = requests.post(f"{BASE}/routines/semana/recuperar", headers=esc["cliente"],
                          json={"fecha_original": perdido["fecha"], "fecha": descanso["fecha"]},
                          timeout=10)
        assert r.status_code == 200, r.text
        s2 = _semana(esc)
        dia_rec = next(d for d in s2["dias"] if d["fecha"] == descanso["fecha"])
        assert dia_rec["recuperacion"] is True
        assert dia_rec["grupo"] == perdido["grupo"]
        original = next(d for d in s2["dias"] if d["fecha"] == perdido["fecha"])
        assert original["recuperado_en"] == descanso["fecha"]
        # Y ya no se le vuelve a preguntar por ese día.
        assert not (s2["pendiente"] and s2["pendiente"]["fecha"] == perdido["fecha"])

    def test_no_se_recupera_encima_de_otro_entreno(self, esc):
        s = _semana(esc)
        hoy = s["hoy"]["fecha"]
        perdido = next((d for d in s["dias"] if d["entrena"] and d["fecha"] < hoy), None)
        entreno_futuro = next((d for d in s["dias"]
                               if d["entrena"] and d["fecha"] >= hoy
                               and not d["recuperacion"]), None)
        if not perdido or not entreno_futuro:
            pytest.skip("no hay con qué montar el caso esta semana")
        r = requests.post(f"{BASE}/routines/semana/recuperar", headers=esc["cliente"],
                          json={"fecha_original": perdido["fecha"],
                                "fecha": entreno_futuro["fecha"]}, timeout=10)
        assert r.status_code == 400

    def test_un_entreno_que_no_se_ha_perdido_no_se_recupera(self, esc):
        s = _semana(esc)
        futuro = next((d for d in s["dias"]
                       if d["entrena"] and d["fecha"] >= s["hoy"]["fecha"]), None)
        descanso = next((d for d in s["dias"]
                         if not d["entrena"] and d["fecha"] >= s["hoy"]["fecha"]), None)
        if not futuro or not descanso:
            pytest.skip("no hay con qué montar el caso esta semana")
        r = requests.post(f"{BASE}/routines/semana/recuperar", headers=esc["cliente"],
                          json={"fecha_original": futuro["fecha"], "fecha": descanso["fecha"]},
                          timeout=10)
        assert r.status_code == 400


class TestElGrupoEnMiSemana:
    def test_diets_semana_dice_el_grupo_del_reparto(self, esc):
        # Sin rutina estructurada: el nombre sale del reparto del PDF + sus días.
        r = requests.get(f"{BASE}/diets/semana", headers=esc["cliente"], timeout=30)
        assert r.status_code == 200, r.text
        dias = r.json()["dias"]
        por_indice = {i: d for i, d in enumerate(dias)}
        # Lunes no tiene dieta guardada: el tipo y el grupo salen del reparto.
        assert por_indice[0]["tipo_dia"] == "entrenamiento"
        assert por_indice[0]["entreno"]["nombre"] == "Empuje"
        # Martes tiene dieta de entrenamiento: el grupo llega igual.
        assert por_indice[1]["entreno"]["nombre"] == "Tirón"
        # Miércoles no es día de entreno según sus días: si su dieta no dice otra
        # cosa... la suya SÍ dice entrenamiento, así que se respeta la dieta y el
        # nombre queda vacío (el reparto no tiene grupo para ese día).
        assert por_indice[2]["entreno"]["nombre"] is None

    def test_sin_reparto_no_se_inventa_nada(self, esc):
        # Se le quita el reparto al PDF: Mi semana vuelve a no decir grupo.
        requests.patch(f"{BASE}/admin/routines/pdf/{esc['cid']}/detalles",
                       headers=esc["admin"], timeout=10, json={"reparto": ""})
        r = requests.get(f"{BASE}/diets/semana", headers=esc["cliente"], timeout=30)
        assert r.status_code == 200
        assert all((d["entreno"]["nombre"] or None) is None for d in r.json()["dias"])
        # Y la pantalla de rutina se queda con «Entreno» a secas, sin grupos inventados.
        # La recuperación apuntada conserva el suyo: se escribió cuando el reparto
        # existía y ese entreno concreto sigue siendo el que era.
        s = _semana(esc)
        assert s["hay"] is True
        assert all(d["grupo"] in (None, "Entreno") for d in s["dias"] if not d["recuperacion"])
        requests.patch(f"{BASE}/admin/routines/pdf/{esc['cid']}/detalles",
                       headers=esc["admin"], timeout=10,
                       json={"reparto": ", ".join(REPARTO)})
