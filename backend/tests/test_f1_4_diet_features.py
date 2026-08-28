"""
Test F1.4: Diet Features - Recent Diets, Diet Save/Load, Macros Calculation
Tests the backend APIs for ingredient editing, diet persistence, and repeat from another day functionality
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

# UNA SOLA ENTRADA PARA LAS CLASES NUEVAS. Cada clase de este fichero entra por su cuenta,
# que son diez accesos para leer la misma lista. El token se pide una vez y se reparte.
_TOKEN = None


def _cabeceras_cliente():
    global _TOKEN
    if _TOKEN is None:
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "clientedemo@test.com", "password": "demo123"},
                          timeout=30)
        assert r.status_code == 200, f"Login failed: {r.text}"
        _TOKEN = r.json()["access_token"]
    return {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}


class TestAuthentication:
    """Authentication tests for getting token"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    def test_login_success(self, auth_token):
        """Test that login works with demo credentials"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✅ Login successful, token obtained")


class TestDietsRecentEndpoint:
    """Test GET /api/diets/recent endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_get_recent_diets_endpoint_exists(self, headers):
        """Test that /api/diets/recent endpoint exists and returns 200"""
        response = requests.get(f"{BASE_URL}/api/diets/recent", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✅ GET /api/diets/recent endpoint exists and returns 200")
    
    def test_get_recent_diets_returns_valid_structure(self, headers):
        """Test that response has correct structure: {diets: [], count: int}"""
        response = requests.get(f"{BASE_URL}/api/diets/recent", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "diets" in data, "Response should have 'diets' key"
        assert "count" in data, "Response should have 'count' key"
        assert isinstance(data["diets"], list), "'diets' should be a list"
        assert isinstance(data["count"], int), "'count' should be an integer"
        print(f"✅ Response structure is valid: {{diets: list, count: {data['count']}}}")
    
    def test_recent_diets_limit_parameter(self, headers):
        """Test that limit parameter works"""
        response = requests.get(f"{BASE_URL}/api/diets/recent?limit=5", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["diets"]) <= 5, "Limit parameter should restrict results"
        print(f"✅ Limit parameter works, got {len(data['diets'])} diets (limit=5)")
    
    def test_recent_diets_entries_have_required_fields(self, headers):
        """Test that each diet entry has required fields for repeat modal"""
        response = requests.get(f"{BASE_URL}/api/diets/recent", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        if len(data["diets"]) > 0:
            diet = data["diets"][0]
            required_fields = ["fecha", "tipo_dia", "num_comidas", "comidas_resumen", "comidas"]
            for field in required_fields:
                assert field in diet, f"Diet entry should have '{field}' field"
            print(f"✅ Diet entries have all required fields: {required_fields}")
        else:
            print("⚠️ No diets found to verify fields - need to create test data first")


class TestRepetirMiraAtras:
    """Punto 210 del 28-08: «Repetir un día» ofrecía días del año que viene.

    La lista salía ordenada por fecha descendente y cortada a 14 SIN TECHO, así que lo
    primero que veía el cliente eran los días con fecha más lejana en el FUTURO -- en la
    cuenta de Jesús, 145 días por delante de hoy, 40 de ellos de 2027, casi todos de la
    migración de Calma. «Bajé la lista entera y no hay ni un día de 2026.»

    Repetir es mirar atrás: de hoy hacia el pasado, y empezando por el último día MONTADO
    (un día guardado vacío no se puede repetir y no debe ocupar sitio).
    """

    @pytest.fixture(scope="class")
    def headers(self):
        return _cabeceras_cliente()

    @staticmethod
    def _pedir(headers, **params):
        r = requests.get(f"{BASE_URL}/api/diets/recent", headers=headers, params=params, timeout=90)
        assert r.status_code == 200, r.text
        return r.json().get("diets") or []

    def test_ni_un_dia_por_delante_de_hoy(self, headers):
        hoy = datetime.now().strftime("%Y-%m-%d")
        dias = self._pedir(headers, limit=14, para=hoy, hoy_cliente=hoy)
        futuros = [d["fecha"] for d in dias if d["fecha"] > hoy]
        assert not futuros, f"la lista ofrece días del futuro: {futuros}"

    def test_tampoco_desde_un_dia_pasado(self, headers):
        """El techo es HOY, no el día abierto: quien arregla el lunes puede repetir el
        miércoles que ya montó, pero nunca un día que aún no ha vivido."""
        hoy = datetime.now().strftime("%Y-%m-%d")
        hace4 = (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d")
        dias = self._pedir(headers, limit=14, para=hace4, hoy_cliente=hoy)
        futuros = [d["fecha"] for d in dias if d["fecha"] > hoy]
        assert not futuros, f"desde un día pasado sigue ofreciendo futuro: {futuros}"

    def test_de_hoy_hacia_atras_y_sin_saltos(self, headers):
        hoy = datetime.now().strftime("%Y-%m-%d")
        fechas = [d["fecha"] for d in self._pedir(headers, limit=14, para=hoy, hoy_cliente=hoy)]
        assert fechas == sorted(fechas, reverse=True), f"la lista no va hacia atrás: {fechas}"

    def test_los_dias_vacios_no_ocupan_sitio(self, headers):
        """«Empezando por el último día montado»: un día guardado sin un solo alimento no
        se puede repetir, y antes se llevaba una de las catorce plazas."""
        hoy = datetime.now().strftime("%Y-%m-%d")
        dias = self._pedir(headers, limit=14, para=hoy, hoy_cliente=hoy)
        vacios = [d["fecha"] for d in dias
                  if not any((m or {}).get("alimentos") for m in (d.get("comidas") or {}).values())]
        assert not vacios, f"la lista ofrece días sin nada montado: {vacios}"


class TestLosDiasTraenSusMacros:
    """Punto 211 del 28-08: todos los días a repetir decían «0 P · 0 H · 0 G».

    «Incluso los que ponen 6 comidas. O esos días están vacíos, y entonces no deberían
    ofrecerse, o los macros no se están leyendo.»

    Eran las dos cosas. La lista sumaba el campo `macros_efectivos` de cada alimento
    guardado, y ese campo muchas veces no está: en la cuenta de Jesús, los 116 días que
    vinieron de Calma no lo tienen ni uno. Ahora los cuenta el servidor con el motor de
    siempre (`calibracion_dia`), así que la fila enseña el MISMO número que se ve al abrir
    ese día. Y un día que de verdad no suma nada no se ofrece: «es la única información
    que sirve para decidir».
    """

    @pytest.fixture(scope="class")
    def headers(self):
        return _cabeceras_cliente()

    @pytest.fixture(scope="class")
    def dias(self, headers):
        hoy = datetime.now().strftime("%Y-%m-%d")
        r = requests.get(f"{BASE_URL}/api/diets/recent", headers=headers,
                         params={"limit": 14, "para": hoy, "hoy_cliente": hoy}, timeout=90)
        assert r.status_code == 200, r.text
        return r.json().get("diets") or []

    def test_cada_dia_trae_sus_macros(self, dias):
        if not dias:
            pytest.skip("la cuenta de prueba no tiene días montados")
        sin = [d["fecha"] for d in dias if not isinstance(d.get("macros"), dict)]
        assert not sin, f"días servidos sin macros: {sin}"

    def test_ninguno_sale_a_cero(self, dias):
        if not dias:
            pytest.skip("la cuenta de prueba no tiene días montados")
        ceros = [d["fecha"] for d in dias
                 if sum(float((d.get("macros") or {}).get(m) or 0) for m in "PHG") <= 0]
        assert not ceros, f"días ofrecidos a 0 P · 0 H · 0 G: {ceros}"

    def test_el_mismo_numero_que_al_abrir_el_dia(self, headers, dias):
        """Una fuente, un número: lo que dice la fila y lo que dice el día son lo mismo.

        La cuenta se hace como la hacen los tres números de la cabecera de Nutrición, que
        es con lo que el cliente compara la fila: la proteína y los hidratos INCLUYEN el
        perientreno (su presupuesto va dentro de `P_total` y `H_total`) y la grasa no.
        `servido_comidas` deja el peri fuera de los tres, así que aquí se le suma.
        """
        if not dias:
            pytest.skip("la cuenta de prueba no tiene días montados")
        for d in dias[:5]:
            r = requests.get(f"{BASE_URL}/api/diets/{d['fecha']}", headers=headers, timeout=60)
            assert r.status_code == 200, r.text
            servido = r.json().get("servido_comidas") or {}
            peri = (d.get("servido_comidas") or {})
            esperado = {
                "P": float(servido.get("P") or 0) + sum(float((peri.get(k) or {}).get("P") or 0) for k in ("Intra", "Post")),
                "H": float(servido.get("H") or 0) + sum(float((peri.get(k) or {}).get("H") or 0) for k in ("Intra", "Post")),
                "G": float(servido.get("G") or 0),
            }
            for m in "PHG":
                a = round(float((d.get("macros") or {}).get(m) or 0))
                b = round(esperado[m])
                assert a == b, f"{d['fecha']} {m}: la lista dice {a} y el día {b}"


class TestLaEtiquetaElige:
    """Punto 212 del 28-08: la etiqueta ENCAJA la llevaban todos.

    «Si lo lleva el cien por cien, la etiqueta no dice nada. Y encajar con 0 macros no se
    puede saber. Que salga sólo en los que encajan, y que los que no digan por qué: +12 H,
    o otro día si era de descanso y hoy toca entrenar.»

    Estas pruebas van contra la regla, con los números de la maqueta del propio documento:
    día de 175 P · 80 H · 50 G.
    """

    @staticmethod
    def _regla(macros, objetivo, tipo, tipo_hoy):
        import sys, os as _os
        sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        from routes.diets import _como_encaja
        return _como_encaja(macros, objetivo, tipo, tipo_hoy)

    OBJETIVO = {"P": 175, "H": 80, "G": 50}

    def test_el_que_clava_encaja(self):
        r = self._regla({"P": 176, "H": 80, "G": 50}, self.OBJETIVO, "entrenamiento", "entrenamiento")
        assert r["encaja"] is True and r["motivo"] is None

    def test_dentro_del_margen_tambien(self):
        r = self._regla({"P": 174, "H": 79, "G": 51}, self.OBJETIVO, "entrenamiento", "entrenamiento")
        assert r["encaja"] is True

    def test_se_canta_lo_que_sobra_aunque_falte_mas(self):
        """El caso de la maqueta: 158 · 92 · 47. Falta 17 de proteína y sobran 12 de
        hidratos, y la etiqueta dice «+12 H»: lo que falta se completa añadiendo, lo que
        sobra hay que quitarlo."""
        r = self._regla({"P": 158, "H": 92, "G": 47}, self.OBJETIVO, "entrenamiento", "entrenamiento")
        assert r["encaja"] is False
        assert r["motivo"] == "desvio"
        assert (r["macro"], r["desvio"]) == ("H", 12)

    def test_si_no_sobra_nada_se_canta_lo_que_falta(self):
        r = self._regla({"P": 120, "H": 78, "G": 49}, self.OBJETIVO, "entrenamiento", "entrenamiento")
        assert r["motivo"] == "desvio"
        assert (r["macro"], r["desvio"]) == ("P", -55)

    def test_otro_tipo_de_dia_manda_sobre_los_numeros(self):
        r = self._regla({"P": 175, "H": 80, "G": 50}, self.OBJETIVO, "descanso", "entrenamiento")
        assert r["encaja"] is False and r["motivo"] == "otro_dia"

    def test_sin_macros_no_se_inventa_etiqueta(self):
        r = self._regla({"P": 175, "H": 80, "G": 50}, None, "entrenamiento", "entrenamiento")
        assert r["encaja"] is False and r["motivo"] is None

    def test_en_la_lista_de_verdad_no_lo_llevan_todos(self):
        """Y contra la app: la etiqueta tiene que discriminar, que es para lo que está."""
        cab = _cabeceras_cliente()
        hoy = datetime.now().strftime("%Y-%m-%d")
        r = requests.get(f"{BASE_URL}/api/diets/recent", headers=cab,
                         params={"limit": 14, "para": hoy, "hoy_cliente": hoy}, timeout=90)
        assert r.status_code == 200, r.text
        dias = r.json().get("diets") or []
        if len(dias) < 2:
            pytest.skip("hacen falta al menos dos días para ver si discrimina")
        assert not all(d.get("encaja") for d in dias), "ENCAJA lo lleva el cien por cien otra vez"
        for d in dias:
            if not d.get("encaja") and d.get("motivo") == "desvio":
                assert d.get("macro") in ("P", "H", "G") and d.get("desvio") is not None


class TestDietSaveAndLoad:
    """Test diet save and load functionality"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_save_diet(self, headers):
        """Test POST /api/diets - save a diet"""
        # Use tomorrow's date for test to avoid conflicts
        test_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        diet_data = {
            "fecha": test_date,
            "tipo_dia": "entrenamiento",
            "num_comidas": 4,
            "momento_entreno": 1,
            "opcion_peri": "intra_post",
            "comidas": {
                "C1": {
                    "alimentos": [
                        {
                            "alimento_id": 2045,
                            "nombre": "TEST_Pechuga de pollo",
                            "cantidad_g": 200,
                            "macros_efectivos": {"P": 42, "H": 0, "G": 2}
                        }
                    ]
                }
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/diets", json=diet_data, headers=headers)
        assert response.status_code == 200, f"Save diet failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert data["fecha"] == test_date
        print(f"✅ Diet saved successfully for date {test_date}")
        
        # Verify by loading
        load_response = requests.get(f"{BASE_URL}/api/diets/{test_date}", headers=headers)
        assert load_response.status_code == 200
        loaded_diet = load_response.json()
        assert loaded_diet.get("exists") == True
        assert "comidas" in loaded_diet
        print(f"✅ Diet verified by loading")
    
    def test_load_diet_nonexistent(self, headers):
        """Test GET /api/diets/{fecha} for non-existent date"""
        response = requests.get(f"{BASE_URL}/api/diets/1999-01-01", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("exists") == False
        print("✅ Non-existent diet returns exists=False")


class TestMacrosCalculation:
    """Test macros calculation endpoints for ingredient editing"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_macros_efectivos_calculation(self, headers):
        """Test POST /api/calculator/macros-efectivos - used when changing quantity"""
        response = requests.post(f"{BASE_URL}/api/calculator/macros-efectivos", json={
            "alimento_id": 830,  # Fiambre de pechuga de pollo (meat with protein)
            "cantidad_g": 150,
            "es_vegano": False
        }, headers=headers)
        
        assert response.status_code == 200, f"Macros calculation failed: {response.text}"
        data = response.json()
        
        assert "efectivos" in data, "Response should have 'efectivos' macros"
        assert "P" in data["efectivos"], "Efectivos should have P (protein)"
        assert "H" in data["efectivos"], "Efectivos should have H (carbs)"
        assert "G" in data["efectivos"], "Efectivos should have G (fat)"
        
        print(f"✅ Macros calculation works: P={data['efectivos']['P']}, H={data['efectivos']['H']}, G={data['efectivos']['G']}")
    
    def test_macros_change_with_quantity(self, headers):
        """Test that macros scale correctly with quantity changes"""
        # Use food ID 830 - Fiambre de pechuga de pollo with protein=20 per 100g
        # Get macros for 100g
        resp_100 = requests.post(f"{BASE_URL}/api/calculator/macros-efectivos", json={
            "alimento_id": 830,
            "cantidad_g": 100,
            "es_vegano": False
        }, headers=headers)
        assert resp_100.status_code == 200
        macros_100 = resp_100.json()["efectivos"]
        
        # Get macros for 200g
        resp_200 = requests.post(f"{BASE_URL}/api/calculator/macros-efectivos", json={
            "alimento_id": 830,
            "cantidad_g": 200,
            "es_vegano": False
        }, headers=headers)
        assert resp_200.status_code == 200
        macros_200 = resp_200.json()["efectivos"]
        
        # Protein for 200g should be approximately 2x protein for 100g
        ratio = macros_200["P"] / macros_100["P"] if macros_100["P"] > 0 else 0
        assert 1.9 < ratio < 2.1, f"Macros should scale: expected ~2x, got {ratio}x"
        print(f"✅ Macros scale correctly with quantity: 100g={macros_100['P']}P, 200g={macros_200['P']}P (ratio={ratio:.2f})")


class TestDistribution:
    """Test macro distribution endpoint used by NutritionPage"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_distribute_macros(self, headers):
        """Test POST /api/calculator/distribute"""
        response = requests.post(f"{BASE_URL}/api/calculator/distribute", json={
            "tipo_dia": "entrenamiento",
            "num_comidas": 4,
            "momento_entreno": 1,
            "opcion_peri": "intra_post"
        }, headers=headers)
        
        assert response.status_code == 200, f"Distribution failed: {response.text}"
        data = response.json()
        
        assert "comidas" in data, "Response should have 'comidas'"
        assert "periworkout" in data, "Response should have 'periworkout' for training days"
        assert "resumen" in data, "Response should have 'resumen'"
        
        print(f"✅ Macro distribution works: {len(data.get('comidas', {}))} comidas, resumen: {data.get('resumen', {})}")


class TestFoodSearch:
    """Test food search endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_search_foods_by_category(self, headers):
        """Test GET /api/calculator/search with category filter"""
        # Category 2 = Carnes (meats)
        response = requests.get(f"{BASE_URL}/api/calculator/search?category=2&limit=5", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "alimentos" in data
        assert len(data["alimentos"]) > 0, "Should return foods for category 2 (meats)"
        
        # Pertenecer a la categoría 2 es tenerla en CUALQUIER posición de la cadena: las
        # etiquetas transversales del catálogo (YA, TOP, 40...) van delante y un alimento
        # como «Caldo de cocido» es «40 | 2.2.3 | ...». El startswith de antes daba por
        # malo lo que el buscador hace bien.
        for food in data["alimentos"]:
            partes = [p.strip() for p in str(food.get("categorias", "")).split("|")]
            es_de_cat2 = any(p == "2" or p.startswith("2.") for p in partes)
            assert es_de_cat2, f"Food should be in category 2: {food.get('nombre')} ({food.get('categorias')})"
        
        print(f"✅ Food search by category works: found {len(data['alimentos'])} meat items")


# Run tests if called directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
