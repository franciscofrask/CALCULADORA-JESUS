"""BLOQUE 6 del doc del cuestionario (18-08): lo que faltaba decidir, ya decidido.

Dos cosas que la app prometía por escrito y no cumplía:

  1. LOS DOS CORREOS. La primera pantalla del alta pide un email y le dice «te escribiremos
     a este, salvo que nos digas lo contrario». Ese email no lo guardaba nadie: se pedía y
     se tiraba. Y no se puede sobrescribir el de acceso, que es con el que entra y con el
     que cruzan los cobros de Stripe, así que se guardan los dos.

  2. EL % DE GRASA CADA 12 SEMANAS. Lo promete el pie de la pantalla donde se lo pedimos la
     primera vez, y no había ningún sitio donde se volviera a preguntar. El dato se quedaba
     con la edad que tuviera, y con él se calculan los macros.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

from conftest import API

CLAVE = "Prueba1234"


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
def alta(mongo):
    creados = []

    def _alta():
        correo = f"bloque6-{uuid.uuid4().hex[:10]}@test.com"
        r = requests.post(f"{API}/auth/register",
                          json={"email": correo, "password": CLAVE, "name": "Bloque Seis"},
                          timeout=30)
        assert r.status_code == 200, f"no se ha podido registrar: {r.status_code}"
        d = r.json()
        persona = {"email": correo, "user_id": d["user"]["id"],
                   "cabeceras": {"Authorization": f"Bearer {d['access_token']}"}}
        mongo.client_profiles.update_one({"user_id": persona["user_id"]},
                                         {"$set": {"plan": "calculadora_jp", "status": "activo"}})
        creados.append(persona)
        return persona

    yield _alta

    for p in creados:
        for coleccion in ("users", "client_profiles", "macro_history", "quiz_respuestas",
                          "diets", "weight_series", "body_fat_series"):
            try:
                mongo[coleccion].delete_many({"user_id": p["user_id"]})
            except Exception:      # noqa: BLE001
                pass
        mongo.leads.delete_many({"email": p["email"]})


def hacer_el_alta(persona, email):
    return requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"], timeout=60,
                         json={"name": "Bloque Seis", "email": email, "goal": "definicion",
                               "sex": "hombre", "weight": 84.0, "body_fat": 20.0, "height": 178.0})


class TestLosDosCorreos:

    def test_el_correo_del_alta_se_guarda_y_no_pisa_el_de_acceso(self, alta, mongo):
        persona = alta()
        otro = f"contacto-{uuid.uuid4().hex[:8]}@gmail.com"
        r = hacer_el_alta(persona, otro)
        assert r.status_code == 200, r.text[:200]

        u = mongo.users.find_one({"id": persona["user_id"]}, {"_id": 0, "email": 1})
        assert u["email"] == persona["email"], (
            "le han cambiado el correo de acceso: con ese entra y con ese cruzan sus cobros")

        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert p.get("email_contacto") == otro, (
            f"el correo que escribe en el alta no se guarda ({p.get('email_contacto')}), y la "
            "propia pantalla le promete que le escribiremos ahí")
        assert p.get("email_preferido") == "contacto"

    def test_si_pone_el_mismo_no_hay_dos_correos(self, alta, mongo):
        persona = alta()
        hacer_el_alta(persona, persona["email"])
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert not p.get("email_contacto"), "no hay dos correos, no hay nada que apuntar"

    def test_puede_cambiar_a_cual_se_le_escribe(self, alta, mongo):
        persona = alta()
        hacer_el_alta(persona, f"otro-{uuid.uuid4().hex[:8]}@gmail.com")
        r = requests.put(f"{API}/clients/profile", headers=persona["cabeceras"],
                         json={"email_preferido": "acceso"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert p.get("email_preferido") == "acceso"

    def test_el_enlace_de_la_contrasena_va_al_de_acceso(self, alta, mongo):
        """Su correo de contacto puede ser otro, pero la llave de la cuenta va donde entra.
        Si fuera al de contacto, quien lo escribió mal en el alta se queda fuera y sin
        forma de volver."""
        persona = alta()
        contacto = f"contacto-{uuid.uuid4().hex[:8]}@gmail.com"
        hacer_el_alta(persona, contacto)

        r = requests.post(f"{API}/auth/forgot-password", json={"email": persona["email"]},
                          timeout=30)
        assert r.status_code == 200
        ultimo = mongo.correos_pendientes.find_one({"tipo": "recuperar_password"},
                                                   sort=[("creado_en", -1)])
        assert ultimo and ultimo["para"] == persona["email"], (
            f"el enlace de la contraseña se ha ido a {ultimo and ultimo.get('para')}")


class TestElPorcentajeDeGrasaCada12Semanas:

    def test_el_bloque_sale_solo_cuando_toca(self):
        from core.datos_reporte import bloques_del_mensual

        sin_pedir = bloques_del_mensual("completo")
        pidiendo = bloques_del_mensual("completo", pedir_grasa=True)
        assert "grasa" not in sin_pedir, "no se le pregunta todos los meses, solo cada 12 semanas"
        assert pidiendo.index("grasa") == 1, "va detrás del peso, que es cuando mira sus números"
        assert len(pidiendo) == len(sin_pedir) + 1

    def test_a_las_doce_semanas_hay_que_volver_a_pedirlo(self):
        from core.series_cliente import grasa_vigente

        hace_mucho = (datetime.now(timezone.utc) - timedelta(weeks=13)).strftime("%Y-%m-%d")
        hace_poco = (datetime.now(timezone.utc) - timedelta(weeks=4)).strftime("%Y-%m-%d")
        viejo = grasa_vigente({"porcentajes_grasos": [{"fecha": hace_mucho, "valor": 20.0}]})
        reciente = grasa_vigente({"porcentajes_grasos": [{"fecha": hace_poco, "valor": 20.0}]})
        assert viejo["hay_que_pedirlo"] is True
        assert reciente["hay_que_pedirlo"] is False

    def test_el_reporte_acepta_el_porcentaje_y_lo_valida(self):
        """Con rango, como el peso: un % graso imposible entra en el cálculo de macros."""
        from pydantic import ValidationError

        from models.common import ReportCreate

        assert ReportCreate(weight=84.0, body_fat=18.5).body_fat == 18.5
        assert ReportCreate(weight=84.0).body_fat is None
        for imposible in (0, 95):
            with pytest.raises(ValidationError):
                ReportCreate(weight=84.0, body_fat=imposible)
