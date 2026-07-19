"""Tests del flag descartar_sin_objetivo de POST /calculator/refit-diet
(adaptar una dieta favorita al tipo de dia actual, entreno <-> descanso).

Reglas:
- Con el flag, las comidas SIN target en el dia destino y SIN hueco en periworkout
  (Intra/Post en descanso, Intra con opcion_peri solo_post) se vacian y sus
  alimentos van a excluidos con motivo 'sin_objetivo_en_dia'.
- Sin el flag, comportamiento historico intacto: esas comidas se copian tal cual.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

CLIENT_EMAIL = "clientedemo@test.com"
CLIENT_PASSWORD = "demo123"

FECHA = "2026-07-19"


def _item(food):
    return {
        "alimento_id": food["id"],
        "nombre": food["nombre"],
        "cantidad_g": 150,
        "macros_efectivos": {"P": 0, "H": 0, "G": 0},
    }


class TestRefitAdaptTipoDia:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        r = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL, "password": CLIENT_PASSWORD,
        })
        assert r.status_code == 200, f"Login failed: {r.text}"
        self.session.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})

        # Alimentos reales para montar las comidas del payload.
        def buscar(q):
            res = self.session.get(f"{BASE_URL}/api/calculator/search", params={"q": q, "limit": 1})
            assert res.status_code == 200, res.text
            alimentos = res.json().get("alimentos") or []
            assert alimentos, f"Sin resultados para '{q}'"
            return alimentos[0]

        self.pollo = buscar("pollo")
        self.arroz = buscar("arroz")
        yield
        self.session.close()

    def _comidas_entreno(self):
        """Favorita tipica de entreno: 4 comidas + Intra + Post."""
        return {
            "C1": {"alimentos": [_item(self.pollo), _item(self.arroz)]},
            "C2": {"alimentos": [_item(self.pollo)]},
            "C3": {"alimentos": [_item(self.arroz)]},
            "C4": {"alimentos": [_item(self.pollo)]},
            "Intra": {"alimentos": [_item(self.arroz)]},
            "Post": {"alimentos": [_item(self.pollo)]},
        }

    def _refit(self, tipo_dia, comidas, flag=None, opcion_peri="intra_post"):
        body = {
            "fecha": FECHA,
            "tipo_dia": tipo_dia,
            "num_comidas": 4,
            "momento_entreno": 1,
            "opcion_peri": opcion_peri,
            "comidas": comidas,
        }
        if flag is not None:
            body["descartar_sin_objetivo"] = flag
        r = self.session.post(f"{BASE_URL}/api/calculator/refit-diet", json=body)
        assert r.status_code == 200, r.text
        return r.json()

    def test_entreno_a_descanso_con_flag_quita_peri(self):
        res = self._refit("descanso", self._comidas_entreno(), flag=True)
        # Intra/Post vaciados (si quedaran alimentos ocultos, el autosave los persistiria)
        assert res["comidas"]["Intra"]["alimentos"] == []
        assert res["comidas"]["Post"]["alimentos"] == []
        # ... y avisados en excluidos con su motivo
        peri_excl = [e for e in res["excluidos"] if e.get("motivo") == "sin_objetivo_en_dia"]
        assert {e["meal"] for e in peri_excl} == {"Intra", "Post"}
        # El dia de descanso no reparte peri
        assert res["distribution"].get("periworkout") in ({}, None)
        # Las comidas regulares vienen refitadas hacia su target de descanso
        for mk in ("C1", "C2", "C3", "C4"):
            assert mk in res["distribution"]["comidas"]
            for al in res["comidas"][mk]["alimentos"]:
                assert al["cantidad_g"] > 0
                assert "macros_efectivos" in al

    def test_entreno_a_descanso_sin_flag_conserva_peri(self):
        comidas = self._comidas_entreno()
        res = self._refit("descanso", comidas, flag=None)
        # Regresion: sin flag, el peri se copia tal cual (comportamiento historico)
        assert len(res["comidas"]["Intra"]["alimentos"]) == 1
        assert len(res["comidas"]["Post"]["alimentos"]) == 1
        assert res["comidas"]["Intra"]["alimentos"][0]["cantidad_g"] == 150
        assert not any(e.get("motivo") == "sin_objetivo_en_dia" for e in res["excluidos"])

    def test_descanso_a_entreno_con_flag(self):
        comidas = {k: v for k, v in self._comidas_entreno().items() if k not in ("Intra", "Post")}
        res = self._refit("entrenamiento", comidas, flag=True)
        # Nada que excluir: todas las comidas tienen target en entreno
        assert not any(e.get("motivo") == "sin_objetivo_en_dia" for e in res["excluidos"])
        assert "Intra" not in res["comidas"] and "Post" not in res["comidas"]
        # El dia de entreno si reparte peri (el front avisa de que queda vacio)
        assert res["distribution"]["periworkout"]

    def test_cuadrar_una_comida_sin_flag_intacto(self):
        res = self._refit("entrenamiento", {"C1": {"alimentos": [_item(self.pollo), _item(self.arroz)]}})
        assert len(res["comidas"]) == 1
        assert res["comidas"]["C1"]["alimentos"], "La comida debe volver refitada"

    def test_intra_con_solo_post_y_flag(self):
        comidas = {
            "C1": {"alimentos": [_item(self.pollo)]},
            "Intra": {"alimentos": [_item(self.arroz)]},
            "Post": {"alimentos": [_item(self.pollo)]},
        }
        res = self._refit("entrenamiento", comidas, flag=True, opcion_peri="solo_post")
        # Intra no existe con solo_post: se vacia y se avisa; Post se conserva tal cual
        assert res["comidas"]["Intra"]["alimentos"] == []
        assert any(e["meal"] == "Intra" and e.get("motivo") == "sin_objetivo_en_dia"
                   for e in res["excluidos"])
        assert len(res["comidas"]["Post"]["alimentos"]) == 1
