"""EL CALLEJÓN SIN SALIDA DEL AJUSTE (18-08).

Francisco, terminando el cuestionario: «Calcular mis macros → Faltan tus datos de partida
(peso, grasa y objetivo). Completa el alta primero.»

Y el alta NO se puede completar: contesta 409 a quien ya la hizo. O sea que quien llegaba
ahí no tenía ninguna forma de salir desde la app.

No era un caso raro: medido en producción el 18-08, de 187 clientes activos hay 104 sin
objetivo, 63 sin porcentaje de grasa y 8 sin peso -- 124 a los que les falta alguno de los
tres, casi todos de la migración de Calma.

El arreglo tiene dos mitades y las dos se prueban aquí: el cuestionario los pregunta antes
de llegar al final, y la puerta que los guarda existe.
"""
import uuid
from pathlib import Path

import pytest
import requests

from conftest import API

RAIZ = Path(__file__).resolve().parents[2]
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
def sin_datos_de_partida(mongo):
    """Un cliente como los 124: el alta dada por hecha y la ficha sin lo básico."""
    creados = []

    def _alta():
        correo = f"callejon-{uuid.uuid4().hex[:10]}@test.com"
        r = requests.post(f"{API}/auth/register",
                          json={"email": correo, "password": CLAVE, "name": "Callejon"},
                          timeout=30)
        assert r.status_code == 200
        d = r.json()
        persona = {"email": correo, "user_id": d["user"]["id"],
                   "cabeceras": {"Authorization": f"Bearer {d['access_token']}"}}
        mongo.client_profiles.update_one(
            {"user_id": persona["user_id"]},
            {"$set": {"plan": "calculadora_jp", "status": "activo",
                      "questionnaire_completed": True},
             "$unset": {"weight": "", "body_fat": "", "goal": ""}})
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


def test_sin_los_tres_el_ajuste_no_puede_calcular(sin_datos_de_partida):
    """El 400 sigue estando -- no se puede calcular sin ellos -- pero ahora dice CUÁL falta
    y no manda a repetir un alta que no se puede repetir."""
    persona = sin_datos_de_partida()
    r = requests.post(f"{API}/clients/ajustar-macros", headers=persona["cabeceras"],
                      json={"actividad_diaria": "normal"}, timeout=30)
    assert r.status_code == 400
    detalle = r.json()["detail"]
    assert "tu peso" in detalle and "tu objetivo" in detalle, detalle
    assert "Completa el alta primero" not in detalle, (
        "sigue mandando a repetir el alta, que contesta 409: es un callejón sin salida")


def test_y_puede_darlos_sin_repetir_el_alta(sin_datos_de_partida, mongo):
    """La salida: la misma puerta de «nos faltan cosas tuyas», que rellena huecos."""
    persona = sin_datos_de_partida()
    r = requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"], timeout=60,
                      json={"completar": True, "name": "Callejon", "email": persona["email"],
                            "goal": "definicion", "sex": "hombre", "weight": 84.0,
                            "body_fat": 20.0})
    assert r.status_code == 200, r.text[:200]

    p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
    assert p.get("weight") == 84.0 and p.get("body_fat") == 20.0 and p.get("goal") == "definicion"

    # Y ahora sí calcula. (Con las tres que el motor necesita: el ajuste tiene su propia
    # lista de obligatorias, y esa sí se le preguntan en el recorrido.)
    r = requests.post(f"{API}/clients/ajustar-macros", headers=persona["cabeceras"],
                      json={"actividad_diaria": "normal", "deporte_extra": False,
                            "facilidad_engordar": "normal"}, timeout=60)
    assert r.status_code == 200, r.text[:200]


def test_el_cuestionario_los_pregunta_antes_de_llegar_al_final():
    """La otra mitad: que no llegue a ver el error. Si alguien quita esto, vuelven los 124."""
    pagina = (RAIZ / "frontend/src/pages/QuestionnairePage.jsx").read_text(encoding="utf-8")
    assert "const faltaLaBase" in pagina, "el ajuste ya no comprueba si le falta la base"
    i = pagina.find("const preguntasDeAjuste")
    assert "laBaseQueFalta" in pagina[i:i + 200], (
        "las preguntas que le faltan ya no van delante del ajuste")


def test_no_se_le_piden_las_fotos_que_ya_tiene():
    """Y ninguna pantalla se queda pidiendo lo que el cliente acaba de dar: si ya tiene sus
    fotos y sus medidas, esa pantalla no sale, y si deja de hacer falta con él dentro, se
    pasa sola."""
    pagina = (RAIZ / "frontend/src/pages/QuestionnairePage.jsx").read_text(encoding="utf-8")
    i = pagina.find("const visible = (s) =>")
    assert i > 0
    bloque = pagina[i:i + 400]
    assert "yaTieneMedidas && yaTieneFotos" in bloque, (
        "la pantalla de fotos y medidas vuelve a salirle a quien ya las tiene")
    # Y el salto solo, que vive con los demás hooks (detrás del `return` de «ya completaste
    # el cuestionario» React no deja llamar a un hook: el proyecto no compila).
    assert "if (sobra) setIdx" in pagina, (
        "un paso que deja de hacer falta con el cliente dentro se queda en pantalla")
