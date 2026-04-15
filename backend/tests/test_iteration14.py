"""
JG12 Iteration 14 - E2E Test Suite
Tests the critical bug fix in /api/calculator/search endpoint:
- Returns 'alimentos' key (not 'results')
- Calculates macros_efectivos via CALMA engine
- Tests diet save/retrieve flow
- Tests dashboard consumed macros calculation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSearchEndpointFix:
    """Tests for the critical /api/calculator/search bug fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_search_returns_alimentos_key(self):
        """CRITICAL: Search should return 'alimentos' key, not 'results'"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=pechuga&limit=5",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # CRITICAL: Must have 'alimentos' key
        assert "alimentos" in data, "Response must have 'alimentos' key"
        assert "results" not in data, "Response should NOT have 'results' key (old format)"
        assert "total" in data
        assert len(data["alimentos"]) > 0, "Should find foods matching 'pechuga'"
    
    def test_search_returns_macros_efectivos(self):
        """CRITICAL: Each food must have macros_efectivos calculated"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=pechuga&limit=3",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for food in data["alimentos"]:
            assert "macros_efectivos" in food, f"Food {food['nombre']} missing macros_efectivos"
            me = food["macros_efectivos"]
            assert "P" in me, "macros_efectivos must have P"
            assert "H" in me, "macros_efectivos must have H"
            assert "G" in me, "macros_efectivos must have G"
            assert "kcal" in me, "macros_efectivos must have kcal"
            
            # Protein foods should have P > 0
            if "pollo" in food["nombre"].lower() or "pechuga" in food["nombre"].lower():
                assert me["P"] > 0, f"Protein food {food['nombre']} should have P > 0"
    
    def test_search_arroz_has_carbs(self):
        """Search for arroz should return foods with H > 0"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=arroz+blanco&limit=5",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["alimentos"]) > 0, "Should find arroz blanco"
        
        # At least one should have H > 0
        has_carbs = any(f["macros_efectivos"]["H"] > 0 for f in data["alimentos"])
        assert has_carbs, "Arroz should have H > 0 in macros_efectivos"
    
    def test_search_with_category_filter(self):
        """Search supports category filter"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=&category=2.2&limit=5",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "alimentos" in data
        # Category 2.2 is aves (poultry)
        for food in data["alimentos"]:
            assert "2.2" in food.get("categorias", ""), f"Food should be in category 2.2"
    
    def test_search_with_tipo_comida_intra(self):
        """Search supports tipo_comida=intra filter"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=&tipo_comida=intra&limit=10",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return alimentos key even if empty
        assert "alimentos" in data
        assert "total" in data


class TestDietSaveAndRetrieve:
    """Tests for diet save and retrieve flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_today_diet_exists(self):
        """GET /api/diets/2026-04-15 returns saved diet with exists:true"""
        response = requests.get(
            f"{BASE_URL}/api/diets/2026-04-15",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("exists") == True, "Diet should exist for 2026-04-15"
        assert "comidas" in data
        assert "C1" in data["comidas"], "Should have C1 meal"
        assert "C2" in data["comidas"], "Should have C2 meal"
    
    def test_diet_has_correct_macros(self):
        """Diet foods have macros_efectivos embedded"""
        response = requests.get(
            f"{BASE_URL}/api/diets/2026-04-15",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # C1 should have 2 foods
        c1_foods = data["comidas"]["C1"]["alimentos"]
        assert len(c1_foods) == 2, "C1 should have 2 foods"
        
        # First food: pollo 200g P=42
        pollo = c1_foods[0]
        assert pollo["cantidad_g"] == 200
        assert pollo["macros_efectivos"]["P"] == 42
        
        # Second food: arroz 70g H=53.9
        arroz = c1_foods[1]
        assert arroz["cantidad_g"] == 70
        assert abs(arroz["macros_efectivos"]["H"] - 53.9) < 0.1
        
        # C2 should have 1 food
        c2_foods = data["comidas"]["C2"]["alimentos"]
        assert len(c2_foods) == 1
        
        # C2 food: pollo 150g P=30 G=6
        pollo2 = c2_foods[0]
        assert pollo2["cantidad_g"] == 150
        assert pollo2["macros_efectivos"]["P"] == 30
        assert pollo2["macros_efectivos"]["G"] == 6
    
    def test_diet_consumed_totals(self):
        """Calculate total consumed macros from diet"""
        response = requests.get(
            f"{BASE_URL}/api/diets/2026-04-15",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        total_p = 0
        total_h = 0
        total_g = 0
        
        for meal_key, meal_data in data["comidas"].items():
            for food in meal_data.get("alimentos", []):
                me = food.get("macros_efectivos", {})
                total_p += me.get("P", 0)
                total_h += me.get("H", 0)
                total_g += me.get("G", 0)
        
        # Expected: P=72, H=53.9, G=6
        assert abs(total_p - 72) < 0.1, f"Total P should be 72, got {total_p}"
        assert abs(total_h - 53.9) < 0.1, f"Total H should be 53.9, got {total_h}"
        assert abs(total_g - 6) < 0.1, f"Total G should be 6, got {total_g}"
        
        # Calculate kcal
        kcal = total_p * 4 + total_h * 4 + total_g * 9
        assert abs(kcal - 558) < 2, f"Total kcal should be ~558, got {kcal}"
    
    def test_save_diet_endpoint(self):
        """POST /api/diets saves diet correctly"""
        test_date = "2026-04-16"
        
        # Save a test diet
        diet_data = {
            "fecha": test_date,
            "tipo_dia": "descanso",
            "num_comidas": 4,
            "momento_entreno": 1,
            "opcion_peri": "intra_post",
            "comidas": {
                "C1": {
                    "alimentos": [
                        {
                            "alimento_id": 117,
                            "nombre": "Test Pollo",
                            "cantidad_g": 100,
                            "macros_efectivos": {"P": 21, "H": 0, "G": 0}
                        }
                    ]
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/diets",
            headers=self.headers,
            json=diet_data
        )
        assert response.status_code == 200
        
        # Verify it was saved
        get_response = requests.get(
            f"{BASE_URL}/api/diets/{test_date}",
            headers=self.headers
        )
        assert get_response.status_code == 200
        saved = get_response.json()
        assert saved.get("exists") == True
        assert saved["tipo_dia"] == "descanso"
        
        # Cleanup - delete test diet
        requests.delete(f"{BASE_URL}/api/diets/{test_date}", headers=self.headers)


class TestMacrosEndpoint:
    """Tests for /api/macros endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_macros_rest_day_targets(self):
        """GET /api/macros returns correct rest day targets"""
        response = requests.get(
            f"{BASE_URL}/api/macros",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Rest day targets: P=225, H=170, G=60, 2120kcal
        rest = data.get("rest") or data.get("macros_rest")
        assert rest is not None, "Should have rest day macros"
        
        p = rest.get("protein") or rest.get("proteinas")
        h = rest.get("carbs") or rest.get("hidratos")
        g = rest.get("fat") or rest.get("grasas")
        
        assert p == 225, f"Rest P should be 225, got {p}"
        assert h == 170, f"Rest H should be 170, got {h}"
        assert g == 60, f"Rest G should be 60, got {g}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
