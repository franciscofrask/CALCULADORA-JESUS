"""EL CIERRE DEL BÁSICO · bloque 3 del doc del cuestionario (18-08).

«Comidas que puedes comer hoy · con el menú autoajustable ya puesto, montado con las
preferencias que dio en el alta.» Para que eso sea verdad, lo que contesta en las dos
pantallas de comida del básico -- las proteínas que come y sus intolerancias -- tiene que
acabar donde la app mira cuando monta comida: `food_preferences` y `avoided_categories` /
`avoided_keywords`.

Si se quedan guardadas en un campo suyo aparte, el primer menú sale de un catálogo
genérico y le puede plantar lácteos a una intolerante el día uno.
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
def alta(mongo):
    creados = []

    def _alta(plan="calculadora_jp"):
        correo = f"cierre-{uuid.uuid4().hex[:10]}@test.com"
        r = requests.post(f"{API}/auth/register",
                          json={"email": correo, "password": CLAVE, "name": "Cierre Prueba"},
                          timeout=30)
        assert r.status_code == 200, f"no se ha podido registrar: {r.status_code}"
        datos = r.json()
        uid = datos["user"]["id"]
        mongo.client_profiles.update_one({"user_id": uid},
                                         {"$set": {"plan": plan, "status": "activo"}})
        persona = {"email": correo, "user_id": uid,
                   "cabeceras": {"Authorization": f"Bearer {datos['access_token']}"}}
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


def alta_con(persona, **comida):
    cuerpo = {"name": "Cierre Prueba", "email": persona["email"], "goal": "definicion",
              "sex": "mujer", "weight": 62.0, "body_fat": 30.0, "height": 165.0}
    cuerpo.update(comida)
    return requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                         json=cuerpo, timeout=60)


class TestLoQueDiceDeComidaLlegaALaCalculadora:

    def test_las_proteinas_que_come_quedan_como_preferencias(self, alta, mongo):
        persona = alta()
        r = alta_con(persona, proteinas_habituales=["aves", "pescado", "huevos", "ternera"])
        assert r.status_code == 200, r.text[:200]

        prefs = requests.get(f"{API}/user/preferences", headers=persona["cabeceras"],
                             timeout=30).json()
        assert set(prefs["food_preferences"]) >= {"aves", "pescados", "huevos", "vacuno"}, (
            f"lo que dice que come no llega a sus preferencias: {prefs}. Su primer menú se "
            "monta de un catálogo genérico")
        assert prefs["has_preferences"] is True

    def test_la_intolerante_total_a_la_lactosa_no_come_lacteos(self, alta, mongo):
        persona = alta()
        r = alta_con(persona, proteinas_habituales=["aves", "pescado", "huevos"],
                     alergias=["lactosa"], lactosa="total")
        assert r.status_code == 200, r.text[:200]

        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert "lacteos" in (p.get("avoided_categories") or []), (
            "dice que no tolera nada de lactosa y los lácteos siguen entrando en sus menús")

    def test_quien_tolera_algun_lacteo_no_se_queda_sin_ellos(self, alta, mongo):
        """No se bloquea de más: el que tolera el yogur o el queso curado los sigue viendo."""
        persona = alta()
        alta_con(persona, proteinas_habituales=["aves", "lacteos", "huevos"],
                 alergias=["lactosa"], lactosa="tolera_algo")
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert "lacteos" not in (p.get("avoided_categories") or [])

    def test_la_celiaca_no_come_pan_ni_pasta(self, alta, mongo):
        persona = alta()
        alta_con(persona, proteinas_habituales=["aves", "pescado", "huevos"],
                 alergias=["gluten"], gluten="celiaquia")
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        evitados = p.get("avoided_categories") or []
        assert {"panes", "pasta"} <= set(evitados), (
            f"celiaquía diagnosticada y el pan y la pasta siguen entrando: {evitados}")

    def test_lo_que_escribe_en_otra_se_evita_por_su_nombre(self, alta, mongo):
        persona = alta()
        alta_con(persona, proteinas_habituales=["aves", "pescado", "huevos"],
                 alergias=["otra"], alergia_otra="marisco, frutos secos")
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        palabras = p.get("avoided_keywords") or []
        assert "marisco" in palabras and "frutos secos" in palabras, (
            f"lo que escribe como alergia no se evita en ningún sitio: {palabras}")

    def test_su_primer_dia_no_lleva_lo_que_no_puede_comer(self, alta, mongo):
        """La prueba de verdad del bloque 3, y la que se cayó al mirarla: el día que se
        monta solo salía de las recetas que cuadran y de nada más, así que a una
        intolerante total a la lactosa le plantaba queso en la primera comida el mismo día
        que acababa de decir que no lo tolera."""
        persona = alta()
        r = alta_con(persona, proteinas_habituales=["aves", "pescado", "huevos", "lacteos"],
                     alergias=["lactosa"], lactosa="total")
        assert r.status_code == 200, r.text[:200]

        dia = requests.post(f"{API}/calculator/montar-dia", headers=persona["cabeceras"],
                            json={"guardar": True}, timeout=90)
        assert dia.status_code == 200, f"no se le monta el primer día: {dia.text[:200]}"

        lacteos = []
        for comida in (dia.json().get("comidas") or {}).values():
            for a in comida.get("alimentos") or []:
                if str(a.get("categorias", "")).split(".")[0].strip() == "5":
                    lacteos.append(a.get("nombre"))
        assert not lacteos, (
            f"su primer día lleva lácteos y es intolerante total: {lacteos}. Es el primer "
            "día, que es el que decide si vuelve")

    def test_no_se_pisan_las_preferencias_que_ya_tenia(self, alta, mongo):
        """Quien las eligió en Nutrición antes de contratar se queda con las suyas."""
        persona = alta()
        mongo.client_profiles.update_one(
            {"user_id": persona["user_id"]},
            {"$set": {"food_preferences": ["verduras", "fruta", "legumbres"]}})
        alta_con(persona, proteinas_habituales=["aves", "cerdo", "embutido"])
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert p["food_preferences"] == ["verduras", "fruta", "legumbres"], (
            "el alta le ha pisado las preferencias que ya había elegido")
