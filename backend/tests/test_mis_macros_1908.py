# -*- coding: utf-8 -*-
"""El bloque 09 del doc 19-08: «Mis macros».

La regla en una línea: la pestaña solo la ve quien se los calcula; el histórico es de
todos y lo que cambia por plan es DÓNDE se ve. El servidor manda ahora las dos fechas de
la cabecera (última revisión y próxima) y las entradas para cualquiera que las tenga.
"""
import os
import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://127.0.0.1:8000").rstrip("/") + "/api"


def _entrar(email):
    try:
        r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo123"}, timeout=10)
    except requests.ConnectionError:
        pytest.skip("backend apagado")
    if r.status_code != 200:
        pytest.skip(f"no se pudo entrar como {email}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def autogestion():
    return _entrar("prueba.calculadora@test.com")


@pytest.fixture(scope="module")
def con_coach():
    return _entrar("clientedemo@test.com")


class TestElHistorialEsDeTodos:
    def test_autogestion_recibe_su_historial_y_las_fechas(self, autogestion):
        d = requests.get(f"{BASE}/macros/historial", headers=autogestion, timeout=15).json()
        assert d["con_historico"] is True
        assert len(d["entradas"]) >= 2
        # La cabecera del doc: «Última revisión: ... · Próxima: ...»
        assert d["ultima_revision"], "la fecha del ajuste vigente"
        assert d["proxima_revision"] and d["proxima_revision"] > d["ultima_revision"], \
            "la próxima sale de la última más el ritmo del plan"

    def test_el_de_coach_tambien_lo_recibe_para_evolucion(self, con_coach):
        # Su pestaña ya no existe, pero el dato sí: Evolución lo pinta con la misma tabla.
        d = requests.get(f"{BASE}/macros/historial", headers=con_coach, timeout=15).json()
        assert d["con_historico"] is True
        assert isinstance(d["entradas"], list)

    def test_la_escalera_marca_lo_que_cambio(self, autogestion):
        d = requests.get(f"{BASE}/macros/historial", headers=autogestion, timeout=15).json()
        vigente = d["entradas"][0]
        # El sembrado de la cuenta de prueba: −20 H en entreno y −10 G en descanso.
        assert vigente["cambios"]["entreno"].get("hidratos")
        assert vigente["cambios"]["descanso"].get("grasa")
