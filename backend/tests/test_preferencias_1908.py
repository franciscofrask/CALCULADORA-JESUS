# -*- coding: utf-8 -*-
"""El bloque 07 del doc 19-08: las preferencias.

Tres piezas del lado del servidor:

1. «Con lo que has marcado podemos cuadrarte»: la comprobación en vivo le pregunta al
   MOTOR de sugerencias con el catálogo recortado a lo marcado. Sin categorías no se
   cuadra nada; con solo arroces salen los hidratos pero no la proteína; los caprichos no
   cuadran una comida normal.

2. Los tres ajustes de la app (tema, modo de macros, vista) viajan a la ficha: es lo que
   hace que sobrevivan al cambio de móvil. Un valor desconocido no escribe nada.

3. «Cómo quieres tu día»: los tres selectores por defecto persisten en la ficha por el
   endpoint de siempre (diet-config).
"""
import os
import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://127.0.0.1:8000").rstrip("/") + "/api"


@pytest.fixture(scope="module")
def cab():
    try:
        r = requests.post(f"{BASE}/auth/login",
                          json={"email": "clientedemo@test.com", "password": "demo123"}, timeout=10)
    except requests.ConnectionError:
        pytest.skip("backend apagado")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _cuadra(cab, marcadas):
    r = requests.post(f"{BASE}/calculator/preferencias/cuadra",
                      json={"marcadas": marcadas}, headers=cab, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


class TestPodemosCuadrarte:
    def test_sin_nada_marcado_no_se_cuadra_nada(self, cab):
        assert _cuadra(cab, []) == {"proteina": False, "hidratos": False}

    def test_con_aves_sale_la_proteina(self, cab):
        assert _cuadra(cab, ["aves"])["proteina"] is True

    def test_con_solo_arroces_salen_los_hidratos_pero_no_la_proteina(self, cab):
        r = _cuadra(cab, ["arroces"])
        assert r["hidratos"] is True
        assert r["proteina"] is False

    def test_los_caprichos_no_cuadran_una_comida_normal(self, cab):
        # El filtro por tipo de comida es el del motor: chocolate no es un plato.
        assert _cuadra(cab, ["chocolates"]) == {"proteina": False, "hidratos": False}

    def test_sin_lista_da_400(self, cab):
        r = requests.post(f"{BASE}/calculator/preferencias/cuadra",
                          json={"marcadas": "aves"}, headers=cab, timeout=10)
        assert r.status_code == 400

    def test_acepta_codigos_de_calma(self, cab):
        # Un migrado guarda '21' donde la pantalla dice 'arroces': la traducción es la
        # misma que usa el resto de la app (core/preferencias.a_nombres).
        r = _cuadra(cab, ["21"])
        assert r["hidratos"] is True


class TestAjustesEnLaFicha:
    def _perfil(self, cab):
        r = requests.get(f"{BASE}/clients/profile", headers=cab, timeout=10)
        assert r.status_code == 200
        return r.json()

    def test_los_tres_viajan_y_vuelven(self, cab):
        r = requests.post(f"{BASE}/user/ajustes-app", headers=cab, timeout=10,
                          json={"tema": "dark", "modo_macros": "reales", "vista": "continua"})
        assert r.status_code == 200
        assert sorted(r.json()["guardado"]) == ["modo_macros", "tema", "vista"]
        ajustes = self._perfil(cab).get("ajustes_app") or {}
        assert ajustes.get("tema") == "dark"
        assert ajustes.get("modo_macros") == "reales"
        assert ajustes.get("vista") == "continua"

    def test_un_valor_raro_no_pisa_lo_guardado(self, cab):
        requests.post(f"{BASE}/user/ajustes-app", headers=cab, timeout=10,
                      json={"tema": "light"})
        r = requests.post(f"{BASE}/user/ajustes-app", headers=cab, timeout=10,
                          json={"tema": "fucsia", "cualquier_cosa": 1})
        assert r.status_code == 200
        assert r.json()["guardado"] == []
        assert (self._perfil(cab).get("ajustes_app") or {}).get("tema") == "light"

    def test_el_recorrido_de_la_primera_vez_viaja_a_la_ficha(self, cab):
        # Doc 21-08, apartado 23: visto/saltado en la ficha, para que el recorrido
        # no se vuelva a ofrecer solo aunque el cliente cambie de movil.
        r = requests.post(f"{BASE}/user/ajustes-app", headers=cab, timeout=10,
                          json={"recorrido": "saltado"})
        assert r.status_code == 200
        assert r.json()["guardado"] == ["recorrido"]
        assert (self._perfil(cab).get("ajustes_app") or {}).get("recorrido") == "saltado"
        # un valor raro no pisa lo guardado
        r = requests.post(f"{BASE}/user/ajustes-app", headers=cab, timeout=10,
                          json={"recorrido": "luego"})
        assert r.json()["guardado"] == []
        assert (self._perfil(cab).get("ajustes_app") or {}).get("recorrido") == "saltado"

    def test_limpieza(self, cab):
        # La base de dev se queda como estaba: sin los ajustes de esta prueba.
        import pymongo
        from dotenv import dotenv_values
        cfg = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
        db = pymongo.MongoClient(cfg["MONGO_URL"])[cfg["DB_NAME"]]
        me = requests.get(f"{BASE}/auth/me", headers=cab, timeout=10).json()
        db.client_profiles.update_one({"user_id": me["id"]}, {"$unset": {"ajustes_app": ""}})


class TestComoQuieresTuDia:
    def test_los_tres_selectores_persisten(self, cab):
        r = requests.patch(f"{BASE}/user/diet-config", headers=cab, timeout=10,
                           json={"num_comidas": 3, "momento_entreno": 0, "opcion_peri": "solo_post"})
        assert r.status_code == 200
        cfg = requests.get(f"{BASE}/user/diet-config", headers=cab, timeout=10).json()
        assert cfg["num_comidas"] == 3
        assert cfg["momento_entreno"] == 0          # «en ayunas» es 0, y 0 no es «vacío»
        assert cfg["opcion_peri"] == "solo_post"
        # y de vuelta a lo de siempre, que es la base del demo
        requests.patch(f"{BASE}/user/diet-config", headers=cab, timeout=10,
                       json={"num_comidas": 4, "momento_entreno": 1, "opcion_peri": "intra_post"})
