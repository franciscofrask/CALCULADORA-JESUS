"""EL COMPLETO · bloque 4 del doc del cuestionario (18-08).

«21 pantallas, después de ver sus macros. No repite nada del básico.»

Lo que se comprueba aquí es lo que no se ve mirando la pantalla:

  1. Que lo que contesta LLEGA A DONDE SE LEE. Dos respuestas del completo -- el material y
     la lesión -- las usa el generador de rutinas, que no mira dentro de `nivel1` sino
     `equipment` e `injuries` del perfil. Esos dos campos nacían vacíos al registrarse y no
     los rellenaba nadie: todo el mundo caía en el grupo «gimnasio completo, sin lesiones».

  2. Que el que pasó por el básico PUEDE ENVIARLO. Sus alergias son una lista desde el
     18-08 y el modelo del completo esperaba un texto: el envío moría con un 422 y las
     veinte respuestas se perdían de golpe.

  3. Que lo médico y el descanso se guardan, que es lo que faltaba entero.
"""
import uuid

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
def gold(mongo):
    """Un cliente con entrenador, que es quien hace el completo."""
    creados = []

    def _alta(con_basico=True):
        correo = f"completo-{uuid.uuid4().hex[:10]}@test.com"
        r = requests.post(f"{API}/auth/register",
                          json={"email": correo, "password": CLAVE, "name": "Completo Prueba"},
                          timeout=30)
        assert r.status_code == 200, f"no se ha podido registrar: {r.status_code}"
        datos = r.json()
        uid = datos["user"]["id"]
        mongo.client_profiles.update_one({"user_id": uid},
                                         {"$set": {"plan": "gold", "status": "activo"}})
        persona = {"email": correo, "user_id": uid,
                   "cabeceras": {"Authorization": f"Bearer {datos['access_token']}"}}
        creados.append(persona)
        if con_basico:
            requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                          timeout=60, json={
                              "name": "Completo Prueba", "email": correo, "goal": "definicion",
                              "sex": "hombre", "weight": 88.0, "body_fat": 22.0, "height": 180.0,
                              "alergias": ["lactosa"], "lactosa": "total",
                              "proteinas_habituales": ["aves", "pescado", "huevos"],
                          })
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


def enviar_completo(persona, **campos):
    cuerpo = {"material": ["gimnasio_completo"], "entrena_ahora": "si"}
    cuerpo.update(campos)
    return requests.post(f"{API}/clients/questionnaire/nivel1", headers=persona["cabeceras"],
                         json=cuerpo, timeout=60)


class TestLoQueContestaLlegaAdondeSeLee:

    def test_el_material_llega_al_generador_de_rutinas(self, gold, mongo):
        persona = gold()
        r = enviar_completo(persona, material=["mancuernas", "bandas"])
        assert r.status_code == 200, r.text[:200]

        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert p.get("equipment") == ["mancuernas", "bandas"], (
            f"el material se queda dentro de nivel1 y el generador de rutinas lee "
            f"`equipment`, que sigue en {p.get('equipment')}: le monta una rutina de "
            "gimnasio completo a quien entrena en casa con dos mancuernas")

    def test_la_lesion_llega_con_lo_que_escribio_no_con_un_si(self, gold, mongo):
        persona = gold()
        enviar_completo(persona, lesion="si", lesion_cual="Hombro derecho, manguito",
                        lesion_tiempo="dos años",
                        ejercicios_imposibles="Press militar y fondos")

        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        lesiones = p.get("injuries") or []
        assert "Hombro derecho, manguito" in lesiones and "Press militar y fondos" in lesiones, (
            f"las lesiones no llegan a `injuries`: {lesiones}. Las rutinas se agrupan por ahí, "
            "así que entra en el grupo de los que no tienen ninguna")

    def test_el_que_no_tiene_lesiones_se_queda_sin_ninguna(self, gold, mongo):
        """Y no con la de la vez anterior: decir que no también es una respuesta."""
        persona = gold()
        mongo.client_profiles.update_one({"user_id": persona["user_id"]},
                                         {"$set": {"injuries": ["rodilla vieja"]}})
        enviar_completo(persona, lesion="no")
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert p.get("injuries") == []


class TestElQuePasoPorElBasicoPuedeEnviarlo:

    def test_las_alergias_en_lista_no_tumban_el_envio(self, gold):
        """El fallo que se llevaba las veinte respuestas por delante."""
        persona = gold()
        r = enviar_completo(persona, alergias=["lactosa", "gluten"], lactosa="total")
        assert r.status_code == 200, (
            f"el completo devuelve {r.status_code} a quien hizo el básico: {r.text[:200]}. "
            "Al cliente le sale «Error al guardar el perfil» y pierde todo lo contestado")

    def test_y_el_texto_libre_de_siempre_sigue_valiendo(self, gold):
        """El que entró antes del básico contesta sus alergias escribiéndolas."""
        persona = gold(con_basico=False)
        r = enviar_completo(persona, alergias="marisco y frutos secos")
        assert r.status_code == 200, r.text[:200]


class TestLoMedicoYElDescanso:

    def test_se_guarda_lo_que_no_se_preguntaba(self, gold, mongo):
        """Las pantallas 6, 7, 10, 11 y 14: estaban en el cuestionario de siempre y
        desaparecieron. Hoy se le monta una rutina y una dieta sin saber si tiene una
        patología que se lo desaconseje o si está medicado."""
        persona = gold()
        r = enviar_completo(
            persona,
            patologia="si", patologia_detalle="Hipertensión controlada",
            medicacion="si", medicacion_detalle="Enalapril 10 mg desde 2021",
            horas_sueno="5_6", ayuda_dormir="benzos_sin_pauta",
            suplementos_veto="Nada con cafeína",
            farmacologia_uso="quemagrasas", farmacologia_detalle="Ozempic desde marzo",
        )
        assert r.status_code == 200, r.text[:200]

        n = (mongo.client_profiles.find_one({"user_id": persona["user_id"]}) or {}).get("nivel1") or {}
        faltan = [c for c in ("patologia", "patologia_detalle", "medicacion",
                              "medicacion_detalle", "horas_sueno", "ayuda_dormir",
                              "suplementos_veto", "farmacologia_uso", "farmacologia_detalle")
                  if not n.get(c)]
        assert not faltan, (
            f"el completo pregunta estas y no se guardan: {faltan}. El equipo lee la ficha y "
            "no ve lo que acaba de contar")

    def test_el_perfil_queda_marcado_como_completo(self, gold, mongo):
        persona = gold()
        enviar_completo(persona)
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert p.get("questionnaire_nivel1_completed") is True
