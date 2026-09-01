"""LO QUE CONTESTÓ EN SUS REPORTES DE CALMA TIENE QUE LLEGAR A LA PANTALLA.

Cada reporte mensual de Calma trae, además del peso, ocho respuestas y el comentario del
cliente. De los 3.404 reportes de producción, 3.149 tenían por nota «Importado de Calma» y
ninguna respuesta: la migración se trajo el número y tiró lo que la persona había escrito.

Y hay un segundo sitio donde se perdía, que es el que prueba esto: aunque estén escritas en
la base, `ReportResponse` ignora lo que no declara, así que si el campo no está en el modelo
el cliente no las ve nunca y no salta ningún error.
"""
import uuid

import pytest
import requests

from conftest import API

CLAVE = "Prueba1234"

RESPUESTAS = {
    "compromiso": "Mi compromiso es máximo, dentro de mis posibilidades estoy dando lo mejor de mí",
    "cumplimientoEntrenamiento": "Sí, en este apartado no he fallado absolutamente nada",
    "cumplimientoDieta": "La he hecho bastante bien, pero no he sido todo lo estricto que debería",
    "descanso": "No, duermo sin problema",
}


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
def cliente_con_reporte(mongo):
    correo = f"calmarep-{uuid.uuid4().hex[:10]}@test.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": correo, "password": CLAVE, "name": "Calma Prueba"},
                      timeout=30)
    assert r.status_code == 200, f"no se ha podido registrar: {r.status_code}"
    datos = r.json()
    uid = datos["user"]["id"]
    perfil = mongo.client_profiles.find_one({"user_id": uid})
    # CON PLAN ACTIVO, O NO ENTRA A NINGUNA PANTALLA.
    #
    # Desde el 29-08 hay candado de plan (`core/candado_de_plan.py`): sin plan, cualquier
    # ruta de cliente devuelve 402 «Necesitas un plan activo para usar la aplicación». Este
    # fixture registraba un usuario recien hecho y nada mas, asi que los tres tests de aqui
    # se quedaron en rojo pidiendo `/reports` como alguien que todavia no es cliente. Lo que
    # se prueba aqui son las respuestas de Calma, no el candado: se le da un plan y ya.
    mongo.client_profiles.update_one(
        {"id": perfil["id"]},
        {"$set": {"plan": "nivel2", "status": "active",
                  "access_until": "2099-01-01T00:00:00+00:00"}})
    reporte = {
        "id": str(uuid.uuid4()),
        "client_id": perfil["id"],
        "weight": 82.0,
        "notes": "Este mes lo he llevado bien, aunque la última semana me costó",
        "calma_respuestas": RESPUESTAS,
        "photo_urls_calma": ["archivosFormularios/mensuales/x/2026-08-17_Frente.jpeg"],
        "created_at": "2026-07-15T12:00:00+00:00",
        "calma_migrated": True,
    }
    mongo.reports.insert_one(dict(reporte))

    yield {"cabeceras": {"Authorization": f"Bearer {datos['access_token']}"},
           "user_id": uid, "client_id": perfil["id"], "email": correo, "reporte": reporte}

    mongo.reports.delete_many({"client_id": perfil["id"]})
    for coleccion in ("users", "client_profiles", "macro_history", "quiz_respuestas"):
        mongo[coleccion].delete_many({"user_id": uid})
    mongo.leads.delete_many({"email": correo})


def test_las_respuestas_de_calma_salen_por_la_api(cliente_con_reporte):
    r = requests.get(f"{API}/reports", headers=cliente_con_reporte["cabeceras"], timeout=30)
    assert r.status_code == 200, r.text[:200]
    reportes = r.json()
    mio = next((x for x in reportes if x["id"] == cliente_con_reporte["reporte"]["id"]), None)
    assert mio, "el reporte no sale en su lista"
    assert mio.get("calma_respuestas") == RESPUESTAS, (
        f"lo que contestó no llega a la pantalla: {mio.get('calma_respuestas')}. Está escrito "
        "en la base y el modelo lo tira sin dar ningún error")


def test_su_comentario_no_se_sustituye_por_una_etiqueta(cliente_con_reporte):
    r = requests.get(f"{API}/reports", headers=cliente_con_reporte["cabeceras"], timeout=30)
    mio = next(x for x in r.json() if x["id"] == cliente_con_reporte["reporte"]["id"])
    assert mio["notes"] == cliente_con_reporte["reporte"]["notes"]
    assert mio["notes"] != "Importado de Calma"


def test_las_fotos_de_calma_van_por_su_campo_y_no_por_photos(cliente_con_reporte):
    """`photos` guarda ids de client_photos y de ahí tira el informe mensual: meterle rutas
    del almacén de Calma lo rompería. Por eso van aparte."""
    r = requests.get(f"{API}/reports", headers=cliente_con_reporte["cabeceras"], timeout=30)
    mio = next(x for x in r.json() if x["id"] == cliente_con_reporte["reporte"]["id"])
    assert mio.get("photo_urls_calma"), "las rutas de sus fotos no llegan"
    assert not mio.get("photos")
