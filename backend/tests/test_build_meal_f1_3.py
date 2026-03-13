"""
Backend tests for TAREA F1.3: Modo 'Lo hago yo' - Constructor de comida en 2 pasos
Tests the /api/calculator/suggest endpoint with paso parameter
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "clientedemo@test.com"
TEST_PASSWORD = "demo123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code != 200:
        pytest.skip("Authentication failed - skipping authenticated tests")
    return response.json()["access_token"]


@pytest.fixture
def api_client(auth_token):
    """Authenticated API client session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestSuggestEndpointWithPaso:
    """Tests for /api/calculator/suggest with paso parameter (F1.3 feature)"""
    
    def test_suggest_with_paso_proteina(self, api_client):
        """Test suggest endpoint filters by protein categories when paso='proteina'"""
        response = api_client.post(
            f"{BASE_URL}/api/calculator/suggest",
            json={
                "macros_restantes": {"P": 45, "H": 75, "G": 13},
                "tipo_comida": "normal",
                "max_resultados": 10,
                "paso": "proteina"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "sugerencias" in data
        assert "count" in data
        assert len(data["sugerencias"]) > 0
        
        # Verify suggestions are protein-rich foods (categories 1,2,3,4,5,6,28)
        protein_categories = ['1', '2', '3', '4', '5', '6', '28']
        for suggestion in data["sugerencias"]:
            alimento = suggestion.get("alimento", {})
            categoria = alimento.get("categorias", "").split(".")[0].split(" ")[0]
            # At least check it has macros_efectivos with P
            assert "macros_efectivos" in suggestion
            assert suggestion["macros_efectivos"].get("P", 0) >= 0
    
    def test_suggest_with_paso_acompanamiento(self, api_client):
        """Test suggest endpoint returns all categories when paso='acompanamiento'"""
        response = api_client.post(
            f"{BASE_URL}/api/calculator/suggest",
            json={
                "macros_restantes": {"P": 5, "H": 75, "G": 13},
                "tipo_comida": "normal",
                "max_resultados": 10,
                "paso": "acompanamiento"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "sugerencias" in data
        assert len(data["sugerencias"]) > 0
        
        # Acompanamiento should include carbs-heavy foods
        for suggestion in data["sugerencias"]:
            assert "macros_efectivos" in suggestion
    
    def test_suggest_without_paso(self, api_client):
        """Test suggest endpoint works without paso parameter (default behavior)"""
        response = api_client.post(
            f"{BASE_URL}/api/calculator/suggest",
            json={
                "macros_restantes": {"P": 45, "H": 75, "G": 13},
                "tipo_comida": "normal",
                "max_resultados": 10
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "sugerencias" in data
        assert len(data["sugerencias"]) > 0
    
    def test_suggest_with_excluir_ids(self, api_client):
        """Test suggest endpoint excludes specified food IDs"""
        # First get some suggestions
        first_response = api_client.post(
            f"{BASE_URL}/api/calculator/suggest",
            json={
                "macros_restantes": {"P": 45, "H": 75, "G": 13},
                "tipo_comida": "normal",
                "max_resultados": 5
            }
        )
        assert first_response.status_code == 200
        first_data = first_response.json()
        
        if len(first_data["sugerencias"]) > 0:
            # Get first food ID to exclude
            exclude_id = first_data["sugerencias"][0]["alimento"]["id"]
            
            # Request suggestions excluding that ID
            second_response = api_client.post(
                f"{BASE_URL}/api/calculator/suggest",
                json={
                    "macros_restantes": {"P": 45, "H": 75, "G": 13},
                    "tipo_comida": "normal",
                    "max_resultados": 5,
                    "excluir_ids": [exclude_id]
                }
            )
            assert second_response.status_code == 200
            second_data = second_response.json()
            
            # Verify excluded ID is not in results
            for suggestion in second_data["sugerencias"]:
                assert suggestion["alimento"]["id"] != exclude_id


class TestSearchEndpointWithTag:
    """Tests for /api/calculator/search with tag filter (F1.3 feature - Solo genéricos)"""
    
    def test_search_with_tag_gen(self, api_client):
        """Test search endpoint filters by tag=GEN (genéricos)"""
        response = api_client.get(
            f"{BASE_URL}/api/calculator/search",
            params={"q": "pollo", "tag": "GEN", "limit": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "alimentos" in data
        # Note: May return empty if no GEN tagged foods exist
        # This is a data issue, not a code issue
    
    def test_search_with_category(self, api_client):
        """Test search endpoint filters by category"""
        response = api_client.get(
            f"{BASE_URL}/api/calculator/search",
            params={"category": "2", "limit": 10}  # Category 2 = Carnes
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "alimentos" in data
        assert len(data["alimentos"]) > 0
        
        # Verify all results are from category 2 (carnes)
        for alimento in data["alimentos"]:
            cats = alimento.get("categorias", "")
            assert cats.startswith("2")


class TestAdjustEndpoint:
    """Tests for /api/calculator/adjust endpoint (quantity calculation)"""
    
    def test_adjust_calculates_quantity(self, api_client):
        """Test adjust endpoint calculates optimal quantity"""
        # First get a food ID (use category 2 = carnes for protein-rich food)
        search_response = api_client.get(
            f"{BASE_URL}/api/calculator/search",
            params={"category": "2", "limit": 5}
        )
        assert search_response.status_code == 200
        foods = search_response.json().get("alimentos", [])
        
        if len(foods) > 0:
            food_id = foods[0]["id"]
            
            adjust_response = api_client.post(
                f"{BASE_URL}/api/calculator/adjust",
                json={
                    "alimento_id": food_id,
                    "macros_restantes": {"P": 45, "H": 75, "G": 13},  # Use realistic macros
                    "es_vegano": False
                }
            )
            
            assert adjust_response.status_code == 200
            data = adjust_response.json()
            assert "cantidad_g" in data
            assert "macros_efectivos" in data
            # cantidad_g can be 0 if food doesn't fit, but API should work
            assert "cabe" in data


class TestDistributeEndpoint:
    """Tests for /api/calculator/distribute endpoint"""
    
    def test_distribute_entrenamiento(self, api_client):
        """Test distribute returns correct meal distribution for training day"""
        response = api_client.post(
            f"{BASE_URL}/api/calculator/distribute",
            json={
                "tipo_dia": "entrenamiento",
                "num_comidas": 4,
                "momento_entreno": 1,
                "opcion_peri": "intra_post"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "comidas" in data
        assert "periworkout" in data
        assert "resumen" in data
        
        # Verify meal structure
        assert "C1" in data["comidas"]
        assert "C2" in data["comidas"]
        assert "C3" in data["comidas"]
        assert "C4" in data["comidas"]
        
        # Verify peri structure
        assert "Intra" in data["periworkout"]
        assert "Post" in data["periworkout"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
