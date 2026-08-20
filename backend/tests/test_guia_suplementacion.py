# -*- coding: utf-8 -*-
"""El bloque 08 del doc 19-08: la guía de suplementación.

- La guía la ven todos, con sus fichas de la web (Qué es · ¿Cuándo? · ¿Cuánto? · notas)
  y el descuento GALLEGOVIP de FullGas al 20 %.
- La general compuesta de cinco líneas murió: sin protocolo propio, /current ya no
  inventa una pauta (`es_generica` no vuelve a salir).
- Quién ve qué: el del plan personalizado sin protocolo todavía ve el aviso («la guía
  básica»); el de autogestión no ve promesa y ve la oferta de los 87 al final.
- El partidor de fichas no inventa: sin rótulos, todo es «qué es».
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
    return _entrar("prueba.gold@test.com")


class TestLaGuia:
    def test_trae_las_fichas_y_el_descuento(self, autogestion):
        r = requests.get(f"{BASE}/supplements/guia", headers=autogestion, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        # Las fichas de la GUÍA son las de la web (28 el 20-08), no los bloques de
        # protocolo del coach: si esto vuelve a dar cientos, alguien reconectó la fuente
        # equivocada.
        unicas = {f["id"] for s in d["secciones"] for f in s["suplementos"]} | {f["id"] for f in d["sin_seccion"]}
        assert 20 <= len(unicas) <= 60, f"la guía de la web ronda las 28 fichas, no {len(unicas)}"
        assert d["descuento"]["codigo"] == "GALLEGOVIP"
        assert d["descuento"]["tienda"] == "FullGas"
        assert d["descuento"]["porcentaje"] == 20

    def test_el_texto_de_entrada_es_el_de_la_web(self, autogestion):
        d = requests.get(f"{BASE}/supplements/guia", headers=autogestion, timeout=15).json()
        texto = d.get("texto_entrada") or ""
        assert "los suplementos que más utilizo y recomiendo" in texto
        assert "GALLEGOVIP" in texto, "el IMPORTANTE del descuento va dentro, sin cambiarlo"

    def test_la_creatina_esta_en_basicos_y_en_rendimiento(self, autogestion):
        # Una ficha puede vivir en varias categorías, como en la web.
        d = requests.get(f"{BASE}/supplements/guia", headers=autogestion, timeout=15).json()
        por = {s["clave"]: {f["nombre"] for f in s["suplementos"]} for s in d["secciones"]}
        assert "Monohidrato de creatina" in por["basicos"]
        assert "Monohidrato de creatina" in por["rendimiento"]
        # y el reparto de la web se respeta
        assert "Berberina 500" in por["salud"]
        assert "Melatonina" in por["descanso"]

    def test_las_ocho_secciones_en_su_orden(self, autogestion):
        d = requests.get(f"{BASE}/supplements/guia", headers=autogestion, timeout=15).json()
        nombres = [s["nombre"] for s in d["secciones"]]
        assert nombres == ["Básicos", "Alimentos", "Rendimiento", "Salud", "Volumen", "Definición", "Descanso"]
        salud = next(s for s in d["secciones"] if s["clave"] == "salud")
        assert salud["subfiltros"] == ["Colesterol", "Digestivo", "Glucosa", "Hepático", "Salud ósea", "Sistema inmune"]

    def test_la_explicacion_de_basicos_es_la_literal(self, autogestion):
        d = requests.get(f"{BASE}/supplements/guia", headers=autogestion, timeout=15).json()
        basicos = next(s for s in d["secciones"] if s["clave"] == "basicos")
        assert "os que sí o sí te recomendaría" in (basicos["explicacion"] or "")
        # y las otras seis también llegaron de la web
        d2 = requests.get(f"{BASE}/supplements/guia", headers=autogestion, timeout=15).json()
        assert all(s.get("explicacion") for s in d2["secciones"]), "las siete explicaciones, literales"

    def test_una_ficha_lleva_cuando_cuanto_y_notas(self, autogestion):
        d = requests.get(f"{BASE}/supplements/guia", headers=autogestion, timeout=15).json()
        fichas = d["sin_seccion"] + [f for s in d["secciones"] for f in s["suplementos"]]
        sin_pauta = [f["nombre"] for f in fichas if not (f.get("cuando") and f.get("cuanto"))]
        assert not sin_pauta, f"toda ficha de la guía trae su ¿Cuándo? y su ¿Cuánto?: {sin_pauta}"
        assert any("frío" in (f.get("que_es") or "") for f in fichas), \
            "las notas sueltas viajan («Guárdalo siempre en frío»)"


class TestQuienVeQue:
    def test_autogestion_sin_promesa_y_con_la_oferta(self, autogestion):
        d = requests.get(f"{BASE}/supplements/guia", headers=autogestion, timeout=15).json()
        assert d["aviso_plan_personalizado"] is False
        assert d["oferta_87"] is True

    def test_plan_personalizado_sin_protocolo_ve_el_aviso_y_no_la_oferta(self, con_coach):
        d = requests.get(f"{BASE}/supplements/guia", headers=con_coach, timeout=15).json()
        assert d["aviso_plan_personalizado"] is True
        assert d["oferta_87"] is False


class TestLaGeneralMurio:
    def test_sin_protocolo_propio_current_no_compone_nada(self, con_coach):
        r = requests.get(f"{BASE}/supplements/current", headers=con_coach, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json() or {}
        assert not d.get("es_generica"), "la general compuesta se retiró (doc 19-08)"
        assert not d.get("actual"), "sin pauta propia no hay nada que marcar: lo suyo es la guía"


class TestElPartidorNoInventa:
    def test_partir_ficha(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from core.guia_suplementacion import partir_ficha
        p = partir_ficha("Proteína de suero. ¿Cuándo? Tras entrenar · ¿Cuánto? 1 cacito")
        assert p == {"que_es": "Proteína de suero.", "cuando": "Tras entrenar", "cuanto": "1 cacito"}
        assert partir_ficha("Solo un texto") == {"que_es": "Solo un texto", "cuando": None, "cuanto": None}
        assert partir_ficha("") == {"que_es": None, "cuando": None, "cuanto": None}
