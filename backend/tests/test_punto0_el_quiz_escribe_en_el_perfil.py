"""PUNTO 0 del doc del 18-08 · «que cada pregunta escriba en el campo del perfil que le toca».

Lo que se medía antes de tocar nada, en producción, sobre 193 fichas: altura 33 %, edad
38 %, fecha de nacimiento 4 %, biotipo 5 %, experiencia entrenando 4 %. Y 184 de ellas con
el cuestionario dado por hecho. Las respuestas no se perdían del todo -- quedan en
`quiz_respuestas` y en `ajustes_macros` -- pero no llegaban al campo que lee la app, que es
lo que hace que el generador de rutinas vea «sin nivel» y el agente no vea el biotipo.

Tres averías distintas, una prueba por cada una:

  1. El alta escribía seis campos que la pantalla nunca manda, así que los dejaba vacíos y
     de paso borraba lo que hubiera de la migración de Calma.
  2. La experiencia entrenando y la actividad se contestan en el ajuste y se quedaban solo
     dentro de `ajustes_macros`, que es donde no las lee nadie más que el motor.
  3. Al cliente con entrenador y macros ya puestos, el ajuste le contesta 403 -- correcto,
     son sus macros y los lleva el equipo -- pero se llevaba por delante la altura, el
     biotipo y la experiencia que viajaban en la misma llamada.

Se corre con el backend vivo (REACT_APP_BACKEND_URL) y se limpia lo que crea.
"""
import uuid
from datetime import date

import pytest
import requests

from conftest import API

CLAVE = "Prueba1234"


def _hoy():
    return date.today().isoformat()


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
    """Usuarios de paso, registrados por la puerta de siempre y borrados al terminar."""
    creados = []

    def _alta(plan="nivel1"):
        correo = f"punto0-{uuid.uuid4().hex[:10]}@test.com"
        r = requests.post(f"{API}/auth/register",
                          json={"email": correo, "password": CLAVE, "name": "Punto Cero"},
                          timeout=30)
        assert r.status_code == 200, f"no se ha podido registrar: {r.status_code} {r.text[:200]}"
        datos = r.json()
        uid = datos["user"]["id"]
        # Como queda después de pagar, que es cuando se le pide el cuestionario.
        mongo.client_profiles.update_one({"user_id": uid},
                                         {"$set": {"plan": plan, "status": "activo"}})
        persona = {"email": correo, "user_id": uid,
                   "cabeceras": {"Authorization": f"Bearer {datos['access_token']}"}}
        creados.append(persona)
        return persona

    yield _alta

    for p in creados:
        uid, correo = p["user_id"], p["email"]
        for coleccion in ("users", "client_profiles", "macro_history", "quiz_respuestas",
                          "macro_revisiones", "diets", "weight_series", "body_fat_series"):
            try:
                mongo[coleccion].delete_many({"user_id": uid})
            except Exception:      # noqa: BLE001  una colección que no exista no es un fallo
                pass
        mongo.leads.delete_many({"email": correo})


def perfil_de(mongo, persona):
    return mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0}) or {}


# Lo que manda la pantalla del alta, tal cual (QuestionnairePage.jsx:1184).
def alta_como_la_manda_la_pantalla(persona, **extra):
    cuerpo = {"name": "Punto Cero", "email": persona["email"], "phone": "600000000",
              "goal": "definicion", "sex": "hombre", "weight": 80.0, "body_fat": 20.0}
    cuerpo.update(extra)
    return requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                         json=cuerpo, timeout=60)


# Lo que manda el ajuste, tal cual (QuestionnairePage.jsx:1143).
def ajuste_como_lo_manda_la_pantalla(persona, **extra):
    cuerpo = {"actividad_diaria": "moderado", "deporte_extra": False,
              "facilidad_engordar": "normal", "apetito": "normal", "cuesta_definir": "normal",
              "training_experience": "avanzado", "sigue_dieta": False,
              "dieta_confirmada": False, "como_va": None,
              "biotype": "mesomorfo", "height": 178}
    cuerpo.update(extra)
    return requests.post(f"{API}/clients/ajustar-macros", headers=persona["cabeceras"],
                         json=cuerpo, timeout=60)


class TestElAltaNoBorraNiSeInventa:

    def test_el_alta_no_borra_lo_que_ya_tenia_la_ficha(self, alta, mongo):
        """El caso de los 160 que vinieron de Calma con su altura y su edad puestas."""
        persona = alta()
        mongo.client_profiles.update_one(
            {"user_id": persona["user_id"]},
            {"$set": {"height": 181.0, "age": 41, "biotype": "endomorfo",
                      "training_experience": "avanzado", "activity_level": "moderado"}})

        r = alta_como_la_manda_la_pantalla(persona)
        assert r.status_code == 200, f"el alta devuelve {r.status_code}: {r.text[:200]}"

        p = perfil_de(mongo, persona)
        for campo, valor in (("height", 181.0), ("age", 41), ("biotype", "endomorfo"),
                             ("training_experience", "avanzado"),
                             ("activity_level", "moderado")):
            assert p.get(campo) == valor, (
                f"el alta le ha borrado «{campo}»: tenía {valor!r} y ahora vale "
                f"{p.get(campo)!r}. La pantalla no manda ese campo, así que no puede escribirlo")

    def test_el_alta_guarda_lo_que_si_le_mandan(self, alta, mongo):
        """Y cuando el dato sí viaja, tiene que llegar al perfil (y la edad, calculada)."""
        persona = alta()
        r = alta_como_la_manda_la_pantalla(
            persona, height=175.0, birthdate="1990-05-20", biotype="mesomorfo",
            training_experience="intermedio")
        assert r.status_code == 200, f"el alta devuelve {r.status_code}: {r.text[:200]}"

        p = perfil_de(mongo, persona)
        assert p.get("height") == 175.0, "la altura que manda la pantalla no llega al perfil"
        assert p.get("birthdate") == "1990-05-20", "la fecha de nacimiento no llega al perfil"
        assert p.get("age"), "con fecha de nacimiento, la edad tiene que salir sola"
        assert p.get("biotype") == "mesomorfo", "el biotipo no llega al perfil"
        assert p.get("training_experience") == "intermedio", (
            "la experiencia entrenando no llega al perfil, que es de donde la lee el "
            "generador de rutinas")


class TestElAjusteSubeLoQueNoSonMacros:

    def test_la_experiencia_y_la_actividad_llegan_al_perfil(self, alta, mongo):
        """Se contestan en el ajuste y las lee gente que no sabe de `ajustes_macros`."""
        persona = alta(plan="nivel1")            # autogestión: el ajuste está permitido
        alta_como_la_manda_la_pantalla(persona)
        r = ajuste_como_lo_manda_la_pantalla(persona)
        assert r.status_code == 200, f"el ajuste devuelve {r.status_code}: {r.text[:200]}"

        p = perfil_de(mongo, persona)
        assert p.get("training_experience") == "avanzado", (
            "la experiencia se queda dentro de `ajustes_macros`: el generador de rutinas "
            "lee `training_experience` y ahí sigue vacío, o sea «sin nivel»")
        assert p.get("activity_level") == "moderado", (
            "la actividad diaria no sube al perfil: la calculadora del cliente la usa para "
            "rellenarse sola cuando no hay respuestas del quiz")
        assert p.get("biotype") == "mesomorfo" and p.get("height") == 178.0

    def test_el_403_de_los_macros_no_se_lleva_por_delante_el_perfil(self, alta, mongo):
        """Cliente con entrenador y macros puestos por una persona: no se le tocan los
        macros, pero lo que ha contestado se guarda igual."""
        persona = alta(plan="gold")              # personalizado
        alta_como_la_manda_la_pantalla(persona)
        perfil = perfil_de(mongo, persona)
        # Su último apunte del historial lo escribió alguien: eso es lo que cierra la puerta.
        # Upsert y con la fecha de HOY: el alta ya dejó su propia fila de ese día y
        # `macro_history` tiene un índice único por cliente y fecha, que llegó a dev con la
        # copia de producción del 18-08. Insertar otra se cae con un duplicado.
        mongo.macro_history.update_one(
            {"client_id": perfil.get("id"), "effective_date": _hoy()},
            {"$set": {"id": str(uuid.uuid4()), "user_id": persona["user_id"],
                      "training": {"protein": 200, "carbs": 250, "fat": 60},
                      "rest": {"protein": 200, "carbs": 150, "fat": 60},
                      "origen": "coach", "changed_by": "una persona"}},
            upsert=True)
        mongo.client_profiles.update_one(
            {"user_id": persona["user_id"]},
            {"$unset": {"biotype": "", "height": "", "training_experience": "",
                        "activity_level": ""}})

        r = ajuste_como_lo_manda_la_pantalla(persona)
        assert r.status_code == 403, (
            f"a un plan con entrenador y macros puestos el ajuste tiene que decirle que no, "
            f"y devuelve {r.status_code}")

        p = perfil_de(mongo, persona)
        assert p.get("biotype") == "mesomorfo", (
            "el 403 se ha llevado por delante el biotipo que acababa de contestar")
        assert p.get("height") == 178.0, "el 403 se ha llevado por delante la altura"
        assert p.get("training_experience") == "avanzado", (
            "el 403 se ha llevado por delante la experiencia entrenando")

    def test_los_macros_siguen_protegidos(self, alta, mongo):
        """Y que quede claro que lo anterior no abre la puerta: los macros no se tocan."""
        persona = alta(plan="gold")
        alta_como_la_manda_la_pantalla(persona)
        perfil = perfil_de(mongo, persona)
        # Upsert y con la fecha de HOY: el alta ya dejó su propia fila de ese día y
        # `macro_history` tiene un índice único por cliente y fecha, que llegó a dev con la
        # copia de producción del 18-08. Insertar otra se cae con un duplicado.
        mongo.macro_history.update_one(
            {"client_id": perfil.get("id"), "effective_date": _hoy()},
            {"$set": {"id": str(uuid.uuid4()), "user_id": persona["user_id"],
                      "training": {"protein": 200, "carbs": 250, "fat": 60},
                      "rest": {"protein": 200, "carbs": 150, "fat": 60},
                      "origen": "coach", "changed_by": "una persona"}},
            upsert=True)
        antes = perfil_de(mongo, persona).get("macros_training")

        ajuste_como_lo_manda_la_pantalla(persona)

        assert perfil_de(mongo, persona).get("macros_training") == antes, (
            "guardar los datos del perfil antes del candado ha acabado tocando los macros")
