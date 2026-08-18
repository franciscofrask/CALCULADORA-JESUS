"""EL BÁSICO · bloque 2 del doc del cuestionario (18-08).

«24 pantallas en hombre, 22 en mujer. Una pregunta por pantalla, sin títulos de sección.»
Lo hace todo el mundo y es la única vez que se le pregunta: «a los que no llevan plan
personalizado no se les vuelve a preguntar nunca más». Por eso lo que se conteste aquí
tiene que acabar en su ficha, no en un cuestionario de segunda fila.

Y va con cinco preguntas MÁS de las que pide el documento (decisión de Francisco, 18-08):
el deporte y las cuatro de la dieta, que son las que mueven los macros y el documento se
llevaba al completo, que solo hacen los de entrenador.
"""
import uuid
from pathlib import Path

import pytest
import requests

from conftest import API

CLAVE = "Prueba1234"
FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src"


def fuente(relativo: str) -> str:
    return (FRONT / relativo).read_text(encoding="utf-8")


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
        correo = f"basico-{uuid.uuid4().hex[:10]}@test.com"
        r = requests.post(f"{API}/auth/register",
                          json={"email": correo, "password": CLAVE, "name": "Basico Prueba"},
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


# Lo que manda la pantalla al terminar el básico, con una respuesta en cada pregunta.
def basico_entero(persona):
    return {
        "name": "Basico Prueba", "email": persona["email"], "phone": "600111222",
        "goal": "definicion", "sex": "hombre", "weight": 80.0, "body_fat": 20.0,
        "birthdate": "1990-05-20", "height": 178.0, "biotype": "mesomorfo",
        "training_experience": "intermedio",
        "profesion": "Policía nacional", "como_me_conociste": "instagram",
        "proteinas_habituales": ["aves", "huevos", "pescado"],
        "peso_maximo": 95.0, "peso_maximo_ano": 2019, "peso_maximo_nota": "Época mala",
        "peso_mejor_momento": 74.0, "peso_mejor_momento_ano": 2021,
        "peso_minimo": 68.0, "peso_minimo_ano": 2015,
        "alergias": ["lactosa"], "lactosa": "parcial",
        "dietas_previas": "Hice keto seis meses", "tiempo_intentandolo": "mas_2a",
        "motivo_apuntarse": "Llevo años dando vueltas y quiero orden",
    }


class TestLoQueSeContestaAcabaEnLaFicha:

    def test_las_veinticuatro_respuestas_llegan_al_perfil(self, alta, mongo):
        """La avería del punto 0, pero al revés: ahora se pregunta más, y hay que
        comprobar que TODO lo que se pregunta tiene su campo y llega."""
        persona = alta()
        r = requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                          json=basico_entero(persona), timeout=60)
        assert r.status_code == 200, f"el alta devuelve {r.status_code}: {r.text[:200]}"

        p = requests.get(f"{API}/clients/profile", headers=persona["cabeceras"],
                         timeout=30).json()
        esperado = {
            "profesion": "Policía nacional", "como_me_conociste": "instagram",
            "proteinas_habituales": ["aves", "huevos", "pescado"],
            "peso_maximo": 95.0, "peso_maximo_ano": 2019, "peso_maximo_nota": "Época mala",
            "peso_mejor_momento": 74.0, "peso_mejor_momento_ano": 2021,
            "peso_minimo": 68.0, "peso_minimo_ano": 2015,
            "alergias": ["lactosa"], "lactosa": "parcial",
            "dietas_previas": "Hice keto seis meses", "tiempo_intentandolo": "mas_2a",
            "motivo_apuntarse": "Llevo años dando vueltas y quiero orden",
            "birthdate": "1990-05-20", "height": 178.0, "biotype": "mesomorfo",
            "training_experience": "intermedio",
        }
        perdidos = {c: v for c, v in esperado.items() if p.get(c) != v}
        assert not perdidos, (
            f"lo que contestó en el básico no llega a su ficha: {perdidos}. Es la única vez "
            "que se le pregunta, así que lo que se pierda aquí se pierde para siempre")
        assert p.get("age"), "con fecha de nacimiento, la edad tiene que salir sola"


class TestElOrdenYLasPantallasDelDocumento:
    """El recorrido lo compone la pantalla, así que esto se mira en el fuente."""

    def test_estan_las_cinco_pantallas_nuevas(self):
        pagina = fuente("pages/QuestionnairePage.jsx")
        for trozo, que_es in (("'contacto'", "los cinco datos de contacto"),
                              ("'ocupacion'", "la profesión con el sedentarismo"),
                              ("'peso_hito'", "los pesos con su año"),
                              ("proteinas_habituales", "las proteínas habituales"),
                              ("como_me_conociste", "cómo me has conocido")):
            assert trozo in pagina, f"falta la pantalla del básico: {que_es}"

    def test_el_basico_va_en_el_orden_del_documento(self):
        pagina = fuente("pages/QuestionnairePage.jsx")
        i = pagina.find("const EL_BASICO")
        assert i > 0, "el básico ya no se compone en un solo sitio"
        bloque = pagina[i:pagina.find("];", i)]
        orden = [bloque.find(x) for x in ("'contacto'", "q('goal')", "q('weight')",
                                          "'peso_hito'", "'ocupacion'",
                                          "q('training_experience')", "q('biotype')",
                                          "q('dietas_previas')", "proteinas_habituales",
                                          "como_me_conociste", "q('motivo_apuntarse')")]
        assert all(x > 0 for x in orden), f"falta alguna pantalla en el básico: {orden}"
        assert orden == sorted(orden), (
            "el básico no va en el orden del documento: primero quién es, luego el objetivo, "
            "luego sus números, luego su historia y al final por qué está aquí")

    def test_las_cinco_que_mueven_macros_siguen_en_el_basico(self):
        """Decisión del 18-08: no se tocan, se quedan sumadas a las del documento."""
        pagina = fuente("pages/QuestionnairePage.jsx")
        i = pagina.find("const EL_BASICO")
        bloque = pagina[i:pagina.find("];", i)]
        for clave in ("deporte_extra", "sigue_dieta", "tiempo_dieta", "como_va",
                      "hambre_saturacion"):
            assert f"q('{clave}')" in bloque, (
                f"«{clave}» ha desaparecido del básico: al que no lleva entrenador se le "
                "calcularían los macros con menos información que antes")

    def test_el_completo_no_repite_lo_que_ya_esta_en_el_basico(self):
        pagina = fuente("pages/QuestionnairePage.jsx")
        assert "YA_ESTAN_EN_EL_BASICO" in pagina, (
            "el cuestionario largo vuelve a preguntar lo que ya se contestó en el básico")
