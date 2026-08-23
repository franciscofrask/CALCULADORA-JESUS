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
                              ("'exclusiones'", "lo que no quiere ver en el plato (doc 23-08)"),
                              ("como_me_conociste", "cómo me has conocido")):
            assert trozo in pagina, f"falta la pantalla del básico: {que_es}"

    def test_el_basico_va_en_el_orden_del_documento(self):
        """El orden del doc del 23-08 («El alta · textos definitivos»), que sustituye al
        del 18-08: fuera «el peso más bajo», entrenador y dietas fusionadas, y las
        exclusiones en el sitio de las proteínas."""
        pagina = fuente("pages/QuestionnairePage.jsx")
        i = pagina.find("const EL_BASICO")
        assert i > 0, "el básico ya no se compone en un solo sitio"
        bloque = pagina[i:pagina.find("];", i)]
        # Los hitos de peso se definen arriba, en `PESO_HITOS`, porque los usan los dos
        # cuestionarios: el básico se los pregunta a todo el mundo y el completo solo al que
        # entró antes de que el básico existiera.
        orden = [bloque.find(x) for x in ("'contacto'", "q('goal')", "q('weight')",
                                          "PESO_HITOS", "'ocupacion'",
                                          "q('training_experience')",
                                          "PREGUNTA_DEL_ENTRENADOR_ANTERIOR",
                                          "q('biotype')", "'exclusiones'",
                                          "como_me_conociste", "q('motivo_apuntarse')")]
        assert all(x > 0 for x in orden), f"falta alguna pantalla en el básico: {orden}"
        assert orden == sorted(orden), (
            "el básico no va en el orden del documento: primero quién es, luego el objetivo, "
            "luego sus números, luego su historia y al final por qué está aquí")
        # Y lo que el doc del 23-08 QUITA no puede volver a colarse:
        assert "q('dietas_previas')" not in bloque, (
            "«¿Has hecho dietas antes?» volvió al básico: se fusionó con la del entrenador "
            "(punto 13 del doc del 23-08)")
        assert "peso_minimo" not in bloque, (
            "«el peso más bajo» volvió al básico y el punto 4 del doc del 23-08 la quita entera")
        assert "proteinas_habituales" not in bloque, (
            "las proteínas volvieron al básico: en su lugar van las exclusiones "
            "(punto 14 del doc del 23-08)")

    def test_el_deporte_se_queda_y_las_cuatro_de_la_dieta_se_van(self):
        """Punto 26 del doc del 19-08, que revierte la decisión del 18-08: «¿Practicas
        otro deporte?» se queda en el básico (la necesita el motor) y las cuatro de la
        dieta se van al cuestionario largo. «Sé lo que implica: al de autogestión se le
        calcularán los macros desde la tabla, sin ajustar por lo que ya come. Está
        decidido así.»"""
        pagina = fuente("pages/QuestionnairePage.jsx")
        i = pagina.find("const EL_BASICO")
        bloque = pagina[i:pagina.find("];", i)]
        assert "q('deporte_extra')" in bloque, (
            "«deporte_extra» ha desaparecido del básico y sin ella el servidor no calcula")
        for clave in ("sigue_dieta", "tiempo_dieta", "como_va", "hambre_saturacion"):
            assert f"q('{clave}')" not in bloque, (
                f"«{clave}» sigue en el básico y el punto 26 la manda al cuestionario largo")
        # Y en el largo están, referenciadas del ajuste (no copiadas).
        i2 = pagina.find("delAjuste('sigue_dieta')")
        assert i2 > -1 and i2 > pagina.find("const STEPS_NIVEL1"), (
            "las cuatro de la dieta no están en el cuestionario largo: se perdieron")

    def test_el_completo_no_repite_lo_que_ya_esta_en_el_basico(self):
        pagina = fuente("pages/QuestionnairePage.jsx")
        assert "YA_ESTAN_EN_EL_BASICO" in pagina, (
            "el cuestionario largo vuelve a preguntar lo que ya se contestó en el básico")
