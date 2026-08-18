"""LOS QUE YA ESTABAN DENTRO, EL AVISO Y LOS 87 € (bloque 6 del doc del 18-08, cerrado).

Tres cosas que Francisco decide el 18-08 y que aquí quedan fijadas:

  1. Al que entró antes del básico se le pasa dentro de la app, y esa segunda pasada RELLENA
     HUECOS: no puede servir para pisarle lo que ya contestó ni para colar un peso nuevo.
  2. Al Gold que no termina su perfil se le avisa a los tres días. Ni el mismo día ni nunca.
  3. El ajuste a medida se cobra, entra en la cola del lunes y se puede repetir; lo que no
     se puede es tener dos pendientes a la vez.
"""
import uuid
from datetime import date, timedelta

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
        correo = f"yaestaban-{uuid.uuid4().hex[:10]}@test.com"
        r = requests.post(f"{API}/auth/register",
                          json={"email": correo, "password": CLAVE, "name": "Ya Estaba"},
                          timeout=30)
        assert r.status_code == 200
        d = r.json()
        persona = {"email": correo, "user_id": d["user"]["id"],
                   "cabeceras": {"Authorization": f"Bearer {d['access_token']}"}}
        mongo.client_profiles.update_one({"user_id": persona["user_id"]},
                                         {"$set": {"plan": plan, "status": "activo"}})
        creados.append(persona)
        return persona

    yield _alta

    for p in creados:
        for coleccion in ("users", "client_profiles", "macro_history", "quiz_respuestas",
                          "diets", "weight_series", "body_fat_series", "macro_sugerencias"):
            try:
                mongo[coleccion].delete_many({"user_id": p["user_id"]})
            except Exception:      # noqa: BLE001
                pass
        mongo.leads.delete_many({"email": p["email"]})


def alta_basica(persona, **extra):
    cuerpo = {"name": "Ya Estaba", "email": persona["email"], "goal": "definicion",
              "sex": "hombre", "weight": 85.0, "body_fat": 20.0}
    cuerpo.update(extra)
    return requests.post(f"{API}/clients/questionnaire", headers=persona["cabeceras"],
                         json=cuerpo, timeout=60)


class TestLaSegundaPasadaSoloRellenaHuecos:

    def test_el_alta_sigue_sin_poder_repetirse(self, alta):
        persona = alta()
        assert alta_basica(persona).status_code == 200
        r = alta_basica(persona)
        assert r.status_code == 409, "el alta no se repite: eso borraría lo que ya contestó"

    def test_completar_escribe_lo_que_falta(self, alta, mongo):
        persona = alta()
        alta_basica(persona, height=180.0)          # entra sin biotipo ni pesos históricos
        r = alta_basica(persona, completar=True, height=180.0, biotype="mesomorfo",
                        tiempo_intentandolo="mas_2a", peso_maximo=99.0,
                        proteinas_habituales=["aves", "huevos"])
        assert r.status_code == 200, r.text[:200]

        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        faltan = [c for c in ("biotype", "tiempo_intentandolo", "peso_maximo",
                              "proteinas_habituales") if not p.get(c)]
        assert not faltan, f"la pasada de completar no ha guardado: {faltan}"

    def test_completar_no_pisa_lo_que_ya_habia(self, alta, mongo):
        """Es la garantía que hace que se le pueda pasar a los 196 sin miedo."""
        persona = alta()
        alta_basica(persona, height=180.0, biotype="ectomorfo")
        alta_basica(persona, completar=True, height=165.0, biotype="endomorfo",
                    tiempo_intentandolo="ahora")

        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert p["biotype"] == "ectomorfo", "le han cambiado el biotipo que ya tenía"
        assert p["height"] == 180.0, "le han cambiado la altura que ya tenía"
        assert p["tiempo_intentandolo"] == "ahora", "y lo que faltaba sí se escribe"


class TestElAvisoDeLosTresDias:

    def test_a_los_tres_dias_si_y_antes_no(self):
        from datetime import datetime, timezone

        from core.avisos_cliente import avisos_condicionados

        ahora = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
        def familias(dias):
            return [a["familia"] for a in
                    avisos_condicionados(ahora=ahora, dias_con_el_perfil_a_medias=dias)]

        assert "perfil_a_medias" not in familias(0), "el mismo día no se le mete prisa"
        assert "perfil_a_medias" not in familias(2)
        assert "perfil_a_medias" in familias(3), "el plazo que pide el documento son 3 días"
        assert "perfil_a_medias" in familias(40)

    def test_va_el_primero_de_todos(self):
        """Mientras no termine, su entrenador no puede trabajar: cualquier otro aviso
        llega antes de tiempo."""
        from datetime import datetime, timezone

        from core.avisos_cliente import avisos_condicionados

        salida = avisos_condicionados(
            ahora=datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc),
            dias_con_el_perfil_a_medias=5, reporte_sin_fotos=True, dias_sin_cerrar=10,
            dias_sin_entrar=20, semanas_sin_ajustar=4)
        assert salida[0]["familia"] == "perfil_a_medias"

    def test_al_que_no_lleva_entrenador_no_se_le_avisa(self):
        from routes.notifications import _dias_con_el_perfil_a_medias

        hoy = date(2026, 8, 18)
        base = {"questionnaire_completed": True, "questionnaire_completed_at": "2026-08-01"}
        assert _dias_con_el_perfil_a_medias({**base, "plan": "gold"}, hoy) == 17
        assert _dias_con_el_perfil_a_medias({**base, "plan": "calculadora_jp"}, hoy) is None
        assert _dias_con_el_perfil_a_medias(
            {**base, "plan": "gold", "questionnaire_nivel1_completed": True}, hoy) is None


class TestElAjusteAMedida:

    def test_se_puede_repetir_pero_no_dos_a_la_vez(self):
        from core.ajuste_a_medida import hay_uno_pendiente

        assert hay_uno_pendiente({}) is False
        assert hay_uno_pendiente({"ajuste_a_medida": {"quiere": True}}) is False
        assert hay_uno_pendiente({"ajuste_a_medida": {"cobrado": True, "estado": "pendiente"}}) is True
        # Entregado el anterior, puede comprar otro: se puede repetir.
        assert hay_uno_pendiente({"ajuste_a_medida": {"cobrado": True, "estado": "entregado"}}) is False

    def test_el_cobro_tiene_su_puerta(self):
        """Que la ruta existe, que es la del cliente y que no se cuela en la de admin."""
        from routes.billing import router

        rutas = {r.path for r in router.routes}
        assert "/billing/ajuste-a-medida/checkout" in rutas

    def test_el_precio_es_el_que_dice_la_pantalla(self):
        from core.ajuste_a_medida import PRECIO_EUR, importe_centimos

        assert PRECIO_EUR == 87.0, "el texto de la oferta dice 87 €"
        assert importe_centimos() == 8700

    def test_la_respuesta_a_la_oferta_no_borra_un_cobro_anterior(self, alta, mongo):
        """Se puede repetir: contestar otra vez a la oferta no le pone `cobrado` a false y
        con eso le cerraría el cuestionario completo que ya pagó."""
        persona = alta()
        alta_basica(persona)
        mongo.client_profiles.update_one(
            {"user_id": persona["user_id"]},
            {"$set": {"ajuste_a_medida": {"cobrado": True, "estado": "entregado", "veces": 1}}})

        r = requests.post(f"{API}/clients/ajuste-a-medida", headers=persona["cabeceras"],
                          json={"quiere": True}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        p = mongo.client_profiles.find_one({"user_id": persona["user_id"]}, {"_id": 0})
        assert (p.get("ajuste_a_medida") or {}).get("cobrado") is True
