"""
Test F1.4: Diet Features - Recent Diets, Diet Save/Load, Macros Calculation
Tests the backend APIs for ingredient editing, diet persistence, and repeat from another day functionality
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


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
        
        # Check that all results have category 2
        for food in data["alimentos"]:
            assert food.get("categorias", "").startswith("2"), f"Food should be in category 2: {food.get('nombre')}"
        
        print(f"✅ Food search by category works: found {len(data['alimentos'])} meat items")


# Run tests if called directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
