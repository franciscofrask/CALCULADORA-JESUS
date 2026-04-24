"""
Test suite for JG12 Iteration 21 - Nutrition Calculator Unit Display Bug Fixes
Tests the search API returns correct unidades and racion fields for foods
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestNutritionSearchAPI:
    """Tests for /api/calculator/search endpoint - unit foods vs gram foods"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_search_manzana_returns_unit_foods(self):
        """Search 'manzana' should return foods with unidades=true and racion>0"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search",
            params={"q": "manzana", "limit": 10},
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "alimentos" in data
        
        # Find Manzana mediana (id=380)
        manzana_mediana = next(
            (f for f in data["alimentos"] if "Manzana mediana" in f.get("nombre", "")),
            None
        )
        assert manzana_mediana is not None, "Manzana mediana not found in search results"
        
        # Verify unit food properties
        assert manzana_mediana.get("unidades") == True, "Manzana mediana should have unidades=true"
        assert manzana_mediana.get("racion") == 180, f"Manzana mediana racion should be 180, got {manzana_mediana.get('racion')}"
    
    def test_search_aceite_returns_unit_foods(self):
        """Search 'aceite' should return unit foods (cucharada)"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search",
            params={"q": "aceite", "limit": 10},
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "alimentos" in data
        
        # Find Aceite de oliva cucharada (id=3)
        aceite = next(
            (f for f in data["alimentos"] if "Aceite de oliva virgen extra una cucharada sopera" in f.get("nombre", "")),
            None
        )
        assert aceite is not None, "Aceite de oliva cucharada not found"
        
        # Verify unit food properties
        assert aceite.get("unidades") == True, "Aceite cucharada should have unidades=true"
        assert aceite.get("racion") == 10, f"Aceite cucharada racion should be 10, got {aceite.get('racion')}"
    
    def test_search_pollo_returns_gram_foods(self):
        """Search 'pollo' should return foods with unidades=false"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search",
            params={"q": "pollo", "limit": 10},
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "alimentos" in data
        
        # Find a pollo item
        pollo = next(
            (f for f in data["alimentos"] if "pollo" in f.get("nombre", "").lower() and "Carne" in f.get("nombre", "")),
            None
        )
        assert pollo is not None, "Pollo item not found"
        
        # Verify gram food properties
        assert pollo.get("unidades") == False, "Pollo should have unidades=false"
        assert pollo.get("racion") == 100, f"Pollo racion should be 100, got {pollo.get('racion')}"
    
    def test_search_huevos_returns_unit_foods(self):
        """Search 'huevos' should return unit foods"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search",
            params={"q": "huevos cocidos", "limit": 10},
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "alimentos" in data
        
        # Find huevos cocidos
        huevos = next(
            (f for f in data["alimentos"] if "Huevos cocidos" in f.get("nombre", "")),
            None
        )
        if huevos:
            # Verify unit food properties
            assert huevos.get("unidades") == True, "Huevos cocidos should have unidades=true"
            assert huevos.get("racion") == 60, f"Huevos cocidos racion should be 60, got {huevos.get('racion')}"
    
    def test_search_arroz_returns_gram_foods(self):
        """Search 'arroz' should return foods with unidades=false"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search",
            params={"q": "arroz blanco", "limit": 10},
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "alimentos" in data
        
        # Find arroz blanco
        arroz = next(
            (f for f in data["alimentos"] if "Arroz blanco" in f.get("nombre", "")),
            None
        )
        if arroz:
            # Verify gram food properties
            assert arroz.get("unidades") == False, "Arroz blanco should have unidades=false"


class TestMacrosEfectivosAPI:
    """Tests for /api/calculator/macros-efectivos endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_macros_efectivos_for_unit_food(self):
        """Test macros calculation for unit food (Manzana mediana id=380)"""
        # 1 unit = 180g for Manzana mediana
        response = requests.post(
            f"{BASE_URL}/api/calculator/macros-efectivos",
            json={
                "alimento_id": 380,
                "cantidad_g": 180,  # 1 unit
                "es_vegano": False
            },
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "efectivos" in data
        
        # Manzana has ~10g carbs per 100g, so 180g should have ~18g carbs
        efectivos = data["efectivos"]
        assert efectivos.get("H", 0) > 10, f"Expected H > 10g for 180g manzana, got {efectivos.get('H')}"
    
    def test_macros_efectivos_for_gram_food(self):
        """Test macros calculation for gram food (Pollo)"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/macros-efectivos",
            json={
                "alimento_id": 117,  # Carne picada de pechuga pollo
                "cantidad_g": 100,
                "es_vegano": False
            },
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "efectivos" in data
        
        # Pollo has ~20g protein per 100g
        efectivos = data["efectivos"]
        assert efectivos.get("P", 0) > 15, f"Expected P > 15g for 100g pollo, got {efectivos.get('P')}"


class TestDietSaveAPI:
    """Tests for /api/diets endpoint - saving diet with unit foods"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_save_diet_with_unit_food(self):
        """Test saving diet with unit food stores cantidad_g correctly"""
        import datetime
        test_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        
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
                            "alimento_id": 380,
                            "nombre": "Manzana mediana",
                            "cantidad_g": 180,  # 1 unit
                            "unidades": True,
                            "racion": 180,
                            "macros_efectivos": {"P": 0, "H": 32, "G": 0}
                        }
                    ]
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/diets",
            json=diet_data,
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed to save diet: {response.text}"
        
        # Verify the saved diet
        get_response = requests.get(
            f"{BASE_URL}/api/diets/{test_date}",
            headers=self.headers
        )
        assert get_response.status_code == 200
        
        saved_diet = get_response.json()
        assert saved_diet.get("exists") == True
        
        # Check the food was saved with correct cantidad_g
        c1_foods = saved_diet.get("comidas", {}).get("C1", {}).get("alimentos", [])
        assert len(c1_foods) > 0, "No foods saved in C1"
        
        manzana = c1_foods[0]
        assert manzana.get("cantidad_g") == 180, f"Expected cantidad_g=180, got {manzana.get('cantidad_g')}"
        assert manzana.get("unidades") == True, "Expected unidades=True"
        assert manzana.get("racion") == 180, f"Expected racion=180, got {manzana.get('racion')}"
