"""El flujo del alta · bloque 1 del doc del cuestionario (18-08).

Tres cosas se comprueban aquí, que son las tres que pide ese bloque:

  1. «Se guarda pregunta a pregunta. Si cierra por la doce, vuelve a la doce.» Antes esto
     solo valía para el cuestionario de ajuste, que son nueve preguntas; el alta, que es el
     recorrido largo y el único que se hace una vez en la vida, era justo el que no se
     guardaba.
  2. Cada recorrido retoma el suyo: el alta y el ajuste escriben en el mismo sitio y el
     número de pantalla de uno no significa nada en el otro.
  3. «El cuestionario no se parte por momento, se parte por plan.» Al terminar, quien lleva
     entrenador elige entre empezar ya o terminar su perfil; quien no, sube fotos y medidas
     y recibe la oferta del ajuste a medida, que se apunta pero todavía no se cobra.

Se corre con el backend vivo (REACT_APP_BACKEND_URL) y borra lo que crea.
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

    def _alta(plan="nivel1"):
        correo = f"flujo-{uuid.uuid4().hex[:10]}@test.com"
        r = requests.post(f"{API}/auth/register",
                          json={"email": correo, "password": CLAVE, "name": "Flujo Prueba"},
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
                          "diets", "alerts"):
            try:
                mongo[coleccion].delete_many({"user_id": p["user_id"]})
            except Exception:      # noqa: BLE001
                pass
        mongo.leads.delete_many({"email": p["email"]})


class TestSeGuardaPreguntaAPregunta:

    def test_el_alta_a_medias_se_guarda(self, alta, mongo):
        persona = alta()
        r = requests.put(f"{API}/clients/ajuste-progreso", headers=persona["cabeceras"],
                         json={"respuestas": {"goal": "definicion", "weight": 80},
                               "paso": 12, "flujo": "alta"}, timeout=30)
        assert r.status_code == 200, f"no deja guardar el alta a medias: {r.text[:200]}"

        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        guardado = p.get("ajuste_macros_progreso") or {}
        assert guardado.get("paso") == 12, (
            "el alta se guarda sin la pantalla por la que iba: al volver empieza de cero")
        assert guardado.get("flujo") == "alta", (
            "el progreso no dice de qué recorrido es, así que el ajuste podría retomar el "
            "punto del alta y aterrizar en otra pregunta")
        assert guardado["respuestas"]["goal"] == "definicion"

    def test_el_recorrido_se_apunta_y_el_de_antes_cuenta_como_ajuste(self, alta, mongo):
        """Lo guardado antes del 18-08 no lleva `flujo` y solo puede ser del ajuste, que era
        el único que se guardaba. La pantalla lo trata así."""
        persona = alta()
        requests.put(f"{API}/clients/ajuste-progreso", headers=persona["cabeceras"],
                     json={"respuestas": {"actividad_diaria": "normal"}, "paso": 3},
                     timeout=30)
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert (p.get("ajuste_macros_progreso") or {}).get("flujo") == "ajuste"

        pagina = fuente("pages/QuestionnairePage.jsx")
        assert "guardado?.flujo || 'ajuste'" in pagina, (
            "la pantalla ya no trata lo guardado sin recorrido como del ajuste")


class TestLaOfertaDelFinal:

    def test_se_apunta_lo_que_contesta_y_no_le_cobra(self, alta, mongo):
        persona = alta(plan="calculadora_jp")
        r = requests.post(f"{API}/clients/ajuste-a-medida", headers=persona["cabeceras"],
                          json={"quiere": True}, timeout=30)
        assert r.status_code == 200, f"la oferta no se puede contestar: {r.text[:200]}"
        assert r.json().get("cobrado") is False, (
            "la oferta dice que ha cobrado, y todavía no hay cobro montado: falta decidir "
            "cómo se cobran los 87 €")

        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        pedido = p.get("ajuste_a_medida") or {}
        assert pedido.get("quiere") is True, "no queda apuntado que lo quiere"
        assert pedido.get("cobrado") is False
        assert pedido.get("respondido_at"), "sin fecha no se sabe cuándo lo pidió"

    def test_el_no_tambien_se_apunta(self, alta, mongo):
        """Cuánta gente la ve y dice que no vale tanto como saber quién compra."""
        persona = alta(plan="calculadora_jp")
        requests.post(f"{API}/clients/ajuste-a-medida", headers=persona["cabeceras"],
                      json={"quiere": False}, timeout=30)
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert (p.get("ajuste_a_medida") or {}).get("quiere") is False

    def test_la_respuesta_llega_a_la_pantalla(self, alta, mongo):
        """Guardarlo en la base no basta: el modelo del perfil ignora lo que no declara, y
        de este campo depende que se le abra el cuestionario completo al que lo compre."""
        persona = alta(plan="calculadora_jp")
        requests.post(f"{API}/clients/ajuste-a-medida", headers=persona["cabeceras"],
                      json={"quiere": True}, timeout=30)
        perfil = requests.get(f"{API}/clients/profile", headers=persona["cabeceras"],
                              timeout=30).json()
        assert "ajuste_a_medida" in perfil, (
            "la respuesta se guarda en la base pero no viaja al perfil: la pantalla no puede "
            "saber si lo compró, así que nunca le abriría el cuestionario completo")
        assert perfil["ajuste_a_medida"]["quiere"] is True

    def test_quien_lo_compra_hace_el_completo(self, alta, mongo):
        """«El que compra el ajuste de 87 € hace el completo, exactamente igual que un Gold».
        El interruptor es `cobrado`, y la pantalla lo mira: querer no es haber pagado."""
        pagina = fuente("pages/QuestionnairePage.jsx")
        assert "ajuste_a_medida?.cobrado" in pagina, (
            "quien compra el ajuste a medida no llega al cuestionario completo: la pantalla "
            "solo mira si su plan lleva entrenador")

        persona = alta(plan="calculadora_jp")
        requests.post(f"{API}/clients/ajuste-a-medida", headers=persona["cabeceras"],
                      json={"quiere": True}, timeout=30)
        perfil = requests.get(f"{API}/clients/profile", headers=persona["cabeceras"],
                              timeout=30).json()
        assert perfil["ajuste_a_medida"]["cobrado"] is False, (
            "pedirlo lo da por cobrado: entonces se le abre el completo sin haber pagado")

    def test_pedirla_avisa_al_equipo(self, alta, mongo):
        persona = alta(plan="calculadora_jp")
        requests.post(f"{API}/clients/ajuste-a-medida", headers=persona["cabeceras"],
                      json={"quiere": True}, timeout=30)
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        # Los avisos del equipo viven en la misma campana que los del cliente, marcados
        # con `equipo` y su `type` (core/avisos_equipo.py).
        avisos = list(mongo.notifications.find({"client_id": p.get("id")}))
        assert any(a.get("type") == "ajuste_a_medida" and a.get("equipo") for a in avisos), (
            f"pide el ajuste a medida y no se entera nadie del equipo: {avisos!r}")
        mongo.notifications.delete_many({"client_id": p.get("id")})


class TestElFinalSeParteporPlan:
    """El reparto vive en el fuente de la pantalla, que es quien compone el recorrido."""

    def test_quien_lleva_entrenador_elige(self):
        pagina = fuente("pages/QuestionnairePage.jsx")
        assert "elegir_perfil" in pagina, (
            "a quien lleva entrenador se le sigue metiendo de cabeza en el cuestionario "
            "largo sin preguntarle si quiere hacerlo ahora")
        assert "Empezar a usar la calculadora" in pagina

    def test_quien_no_lo_lleva_sube_fotos_y_recibe_la_oferta(self):
        pagina = fuente("pages/QuestionnairePage.jsx")
        assert "fotos_medidas" in pagina, "no se le piden las fotos ni las medidas al terminar"
        assert "oferta_ajuste" in pagina, "no se le ofrece el ajuste a medida"
        assert "87 €" in pagina, "la oferta no dice lo que cuesta"

    def test_el_reparto_va_por_plan_y_no_por_momento(self):
        pagina = fuente("pages/QuestionnairePage.jsx")
        # El cierre es lo que va detrás de los macros, y es donde se parte por plan. Vive
        # en `elCierre` desde que el alta pasó a ser el básico del documento.
        i = pagina.find("const elCierre")
        assert i > 0, "el cierre del alta ya no se compone en un solo sitio"
        bloque = pagina[i:i + 700]
        assert "tieneCoach" in bloque, (
            "el final del alta no mira el plan: el documento dice que el cuestionario se "
            "parte por plan, no por momento")
