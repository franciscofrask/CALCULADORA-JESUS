"""EL ALTA DEL DOC DEL 23-08 («El alta · textos definitivos»): lo que el backend
sostiene de los 26 puntos.

Lo de pantalla (candados, portadas de bloque, repaso) se verifica en navegador; aquí va
lo que escribe y calcula el servidor: la fusión de vetos, el veto de lactosa con el
vocabulario viejo, la foto del carrusel fuera del perfil, el «pásala» como respuesta,
los menús de mañana y pasado, y la cuarta respuesta de «¿engordas?» en el motor.
"""
import base64
import uuid
from datetime import date, timedelta

import pytest
import requests

from conftest import API

CLAVE = "Prueba1234"

# Un PNG de 1x1, para la foto del carrusel de grasa.
PNG_1x1 = ("data:image/png;base64,"
           "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


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
        correo = f"doc2308-{uuid.uuid4().hex[:10]}@test.com"
        r = requests.post(f"{API}/auth/register",
                          json={"email": correo, "password": CLAVE, "name": "Doc 2308"},
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
                          "diets", "weight_series", "body_fat_series", "client_photos"):
            try:
                mongo[coleccion].delete_many({"user_id": p["user_id"]})
            except Exception:      # noqa: BLE001
                pass
        mongo.leads.delete_many({"email": p["email"]})


def cuerpo_minimo(persona, **extra):
    base = {"name": "Doc 2308", "email": persona["email"], "phone": "600222333",
            "goal": "volumen", "sex": "hombre", "weight": 80.0, "body_fat": 20.0,
            "height": 178.0}
    base.update(extra)
    return base


class TestLaFusionDeVetos:
    """Punto 14: lo que marca en exclusiones + lo que sale de sus intolerancias, JUNTOS."""

    def test_exclusiones_e_intolerancia_acaban_donde_lee_la_calculadora(self, alta):
        persona = alta()
        r = requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                          json=cuerpo_minimo(persona,
                                             alergias=["lactosa"], lactosa="total",
                                             avoided_categories=["casqueria"],
                                             avoided_keywords=["atun"]),
                          timeout=60)
        assert r.status_code == 200, r.text[:200]
        prefs = requests.get(f"{API}/user/preferences", headers=persona["cabeceras"],
                             timeout=30).json()
        assert "casqueria" in prefs["avoided_categories"], "la categoría marcada se perdió"
        assert "lacteos" in prefs["avoided_categories"], (
            "la intolerancia total a la lactosa no vetó los lácteos")
        assert "atun" in prefs["avoided_keywords"], "la palabra buscada se perdió"

    def test_el_veto_de_lactosa_entiende_el_vocabulario_viejo(self, alta):
        """Punto 15: las fichas migradas dicen `nada` donde hoy se dice `total`. Con la
        comparación solo contra `total`, a esa gente el veto no se le aplicaba NUNCA."""
        persona = alta()
        r = requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                          json=cuerpo_minimo(persona, alergias=["lactosa"], lactosa="nada"),
                          timeout=60)
        assert r.status_code == 200, r.text[:200]
        prefs = requests.get(f"{API}/user/preferences", headers=persona["cabeceras"],
                             timeout=30).json()
        assert "lacteos" in prefs["avoided_categories"], (
            "lactosa='nada' (vocabulario viejo) tiene que vetar lácteos igual que 'total'")


class TestLaFotoDelCarrusel:
    """Punto 1: la foto que sube ya no se pierde, y no engorda el documento del perfil."""

    def test_va_a_client_photos_y_en_el_perfil_queda_solo_el_id(self, alta, mongo):
        persona = alta()
        r = requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                          json=cuerpo_minimo(persona, foto_grasa=PNG_1x1,
                                             foto_mejor_momento=PNG_1x1),
                          timeout=60)
        assert r.status_code == 200, r.text[:200]
        perfil = mongo.client_profiles.find_one({"user_id": persona["user_id"]})
        assert perfil.get("foto_grasa_id"), "la foto del carrusel no dejó id en la ficha"
        assert perfil.get("foto_mejor_momento_id"), "la de mejor forma tampoco"
        assert not perfil.get("foto_grasa"), "el base64 no puede quedarse en el perfil"
        assert not perfil.get("foto_mejor_momento"), (
            "la de mejor forma seguía incrustada en base64 en el perfil")
        doc = mongo.client_photos.find_one({"id": perfil["foto_grasa_id"]})
        assert doc and doc.get("uso") == "alta_grasa", "la foto sin su marca de uso"
        assert doc.get("en_r2") or doc.get("data"), "la foto sin binario ni objeto en R2"

    def test_las_fotos_del_alta_no_se_cuelan_en_la_lista_de_progreso(self, alta, mongo):
        persona = alta()
        requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                      json=cuerpo_minimo(persona, foto_grasa=PNG_1x1), timeout=60)
        fotos = requests.get(f"{API}/reports/photos", headers=persona["cabeceras"],
                             timeout=30).json()
        lista = fotos if isinstance(fotos, list) else fotos.get("photos") or fotos.get("fotos") or []
        assert all(not (f.get("uso")) for f in lista), (
            "una foto del alta salió en la lista de fotos de progreso")


class TestElPasalaEsUnaRespuesta:
    """Punto 3: «Si no, pásala» no es un olvido; no se le vuelve a pedir."""

    def test_la_marca_llega_a_la_ficha(self, alta):
        persona = alta()
        r = requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                          json=cuerpo_minimo(persona, mejor_forma_pasada=True), timeout=60)
        assert r.status_code == 200, r.text[:200]
        perfil = requests.get(f"{API}/clients/profile", headers=persona["cabeceras"],
                              timeout=30).json()
        assert perfil.get("mejor_forma_pasada") is True
        assert not perfil.get("peso_mejor_momento")


class TestLosMenusDeArranque:
    """Punto 18: mañana y pasado se escriben de verdad, cuadrados y guardados."""

    def test_montar_dia_con_fecha_deja_el_dia_puesto(self, alta):
        persona = alta()
        requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                      json=cuerpo_minimo(persona), timeout=60)
        manana = (date.today() + timedelta(days=1)).isoformat()
        r = requests.post(f"{API}/calculator/montar-dia", headers=persona["cabeceras"],
                          json={"fecha": manana, "guardar": True, "tipo_dia": "entrenamiento",
                                "num_comidas": 4, "momento_entreno": 1},
                          timeout=120)
        assert r.status_code == 200, r.text[:200]
        assert r.json().get("guardada") is True
        dia = requests.get(f"{API}/diets/{manana}", headers=persona["cabeceras"],
                           timeout=30).json()
        montadas = [c for c in (dia.get("comidas") or {}).values() if c.get("alimentos")]
        assert len(montadas) >= 2, f"el día de mañana quedó a medias: {len(montadas)} comidas"


class TestElMotorConLaCuartaRespuesta:
    """Punto 7: «No, nada, me cuesta mucho coger peso» cobra el +20 % igual que casi_no."""

    def test_nada_sube_como_casi_no_y_el_veto_sigue(self):
        from macro_engine import calcular_macros_v2

        base = dict(peso=80, sexo="hombre", porcentaje_graso=20, objetivo="volumen")
        normal = calcular_macros_v2(**base, facilidad_engordar="normal")["macros"]
        nada = calcular_macros_v2(**base, facilidad_engordar="nada")["macros"]
        casi_no = calcular_macros_v2(**base, facilidad_engordar="casi_no")["macros"]
        veto = calcular_macros_v2(**base, facilidad_engordar="enseguida")["macros"]
        assert nada["entreno"]["hidratos"] == casi_no["entreno"]["hidratos"] > normal["entreno"]["hidratos"]
        assert nada["descanso"]["hidratos"] == casi_no["descanso"]["hidratos"] > normal["descanso"]["hidratos"]
        assert veto["entreno"]["hidratos"] == normal["entreno"]["hidratos"], (
            "el veto de «engordo enseguida» tiene que seguir intacto")


class TestLaEntregaDiceLasSemanas:
    """Punto 17: «Próxima revisión en N semanas: fecha» — los días los decide el plan."""

    def test_ajustar_macros_devuelve_los_dias_de_revision(self, alta):
        from core.plan_access import dias_hasta_la_revision

        persona = alta(plan="nivel1")
        requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                      json=cuerpo_minimo(persona), timeout=60)
        r = requests.post(f"{API}/clients/ajustar-macros", headers=persona["cabeceras"],
                          json={"actividad_diaria": "sedentario", "deporte_extra": False,
                                "facilidad_engordar": "normal"},
                          timeout=60)
        assert r.status_code == 200, r.text[:200]
        entrega = r.json().get("entrega") or {}
        assert entrega.get("revision_en_dias") == dias_hasta_la_revision("nivel1")
        assert entrega.get("proxima_revision"), "sin la fecha no hay frase que pintar"
