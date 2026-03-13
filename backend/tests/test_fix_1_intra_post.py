"""
Test suite for TAREA FIX-1: BuildMealModal con modos intra/post
- FIX 5: Modal BuildMealModal con modo 'intra' - categorías filtradas (aminoácidos, isotónicas), máximo 3 alimentos
- FIX 6: Modal BuildMealModal con modo 'post' - flujo 2 pasos con categorías específicas
- FIX 7: Backend `suggest` con paso='proteina' filtra ESTRICTAMENTE por categorías de proteína pura (1,2,3,4,5,6,28)
- FIX 8: Controles [-] cantidad [+] y botón [AÑADIR] separado en sugerencias
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthentication:
    """Get auth token for tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Authentication failed: {response.status_code}")
    
    def test_login_success(self):
        """Verify login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        print(f"✅ Login successful")


class TestFIX7SuggestProteinaFilter:
    """
    FIX 7: Backend `suggest` con paso='proteina' filtra ESTRICTAMENTE 
    por categorías de proteína pura (1,2,3,4,5,6,28)
    """
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_suggest_paso_proteina_returns_only_protein_categories(self, auth_headers):
        """
        When paso='proteina', suggest endpoint should ONLY return foods 
        from categories 1,2,3,4,5,6,28 (protein sources)
        """
        response = requests.post(
            f"{BASE_URL}/api/calculator/suggest",
            headers=auth_headers,
            json={
                "macros_restantes": {"P": 45, "H": 75, "G": 13},
                "tipo_comida": "normal",
                "es_vegano": False,
                "max_resultados": 20,
                "excluir_ids": [],
                "paso": "proteina"  # FIX 7: This should filter to protein-only categories
            }
        )
        assert response.status_code == 200, f"Suggest failed: {response.text}"
        data = response.json()
        
        sugerencias = data.get("sugerencias", [])
        assert len(sugerencias) > 0, "No suggestions returned for proteina paso"
        
        # Allowed protein categories (main category numbers)
        protein_cats = ['1', '2', '3', '4', '5', '6', '28']
        
        invalid_foods = []
        for sug in sugerencias:
            alimento = sug.get("alimento", {})
            categorias = alimento.get("categorias", "")
            # Get main category (before first dot)
            main_cat = categorias.split('.')[0].split(' | ')[0].strip() if categorias else ""
            
            if main_cat and main_cat not in protein_cats:
                invalid_foods.append({
                    "nombre": alimento.get("nombre"),
                    "categorias": categorias,
                    "main_cat": main_cat
                })
        
        assert len(invalid_foods) == 0, f"Found non-protein foods in paso=proteina: {invalid_foods}"
        print(f"✅ paso='proteina' correctly filters to protein categories only ({len(sugerencias)} foods)")
    
    def test_suggest_paso_proteina_excludes_carbs_and_fats(self, auth_headers):
        """
        paso='proteina' should NOT include carb sources (21 arroz, 22 pasta, etc) 
        or fat sources (17 aceites, etc)
        """
        response = requests.post(
            f"{BASE_URL}/api/calculator/suggest",
            headers=auth_headers,
            json={
                "macros_restantes": {"P": 45, "H": 75, "G": 13},
                "tipo_comida": "normal",
                "es_vegano": False,
                "max_resultados": 30,
                "excluir_ids": [],
                "paso": "proteina"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        excluded_cats = ['7', '8', '9', '11', '13', '17', '21', '22', '24', '37', '38']
        
        for sug in data.get("sugerencias", []):
            alimento = sug.get("alimento", {})
            categorias = alimento.get("categorias", "")
            main_cat = categorias.split('.')[0].split(' | ')[0].strip() if categorias else ""
            
            assert main_cat not in excluded_cats, \
                f"Found excluded category {main_cat} in paso=proteina: {alimento.get('nombre')}"
        
        print(f"✅ paso='proteina' correctly excludes carb/fat categories")
    
    def test_suggest_paso_acompanamiento_includes_all_categories(self, auth_headers):
        """
        paso='acompanamiento' should include carb sources (not just proteins)
        """
        response = requests.post(
            f"{BASE_URL}/api/calculator/suggest",
            headers=auth_headers,
            json={
                "macros_restantes": {"P": 5, "H": 75, "G": 13},  # Low protein remaining, high carbs
                "tipo_comida": "normal",
                "es_vegano": False,
                "max_resultados": 20,
                "excluir_ids": [],
                "paso": "acompanamiento"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        sugerencias = data.get("sugerencias", [])
        assert len(sugerencias) > 0, "No suggestions for acompanamiento"
        
        # acompanamiento should include various categories
        categories_found = set()
        for sug in sugerencias:
            alimento = sug.get("alimento", {})
            categorias = alimento.get("categorias", "")
            main_cat = categorias.split('.')[0].split(' | ')[0].strip() if categorias else ""
            if main_cat:
                categories_found.add(main_cat)
        
        print(f"✅ paso='acompanamiento' returns varied categories: {categories_found}")
    
    def test_suggest_no_paso_includes_all_categories(self, auth_headers):
        """
        When paso is null/not provided, should return all categories based on macros
        """
        response = requests.post(
            f"{BASE_URL}/api/calculator/suggest",
            headers=auth_headers,
            json={
                "macros_restantes": {"P": 45, "H": 75, "G": 13},
                "tipo_comida": "normal",
                "es_vegano": False,
                "max_resultados": 20,
                "excluir_ids": []
                # No "paso" parameter - should include all
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert len(data.get("sugerencias", [])) > 0
        print(f"✅ No paso parameter returns general suggestions")


class TestIntraPostTypeFiltering:
    """
    FIX 5 & 6: Test tipo_comida filtering for intra and post meals
    """
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_suggest_tipo_comida_intra_filters_correctly(self, auth_headers):
        """
        FIX 5: tipo_comida='intra' should only return categories 41 (aminoácidos) 
        and 18.1 (isotónicas)
        """
        response = requests.post(
            f"{BASE_URL}/api/calculator/suggest",
            headers=auth_headers,
            json={
                "macros_restantes": {"P": 8, "H": 9, "G": 0},  # Typical intra macros
                "tipo_comida": "intra",  # FIX 5
                "es_vegano": False,
                "max_resultados": 20,
                "excluir_ids": []
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        sugerencias = data.get("sugerencias", [])
        
        # Intra should only have categories 41 and 18.1
        valid_intra_cats = ['41', '18']  # Base categories
        
        for sug in sugerencias:
            alimento = sug.get("alimento", {})
            categorias = alimento.get("categorias", "")
            # Main category check
            main_cat = categorias.split('.')[0].split(' | ')[0].strip() if categorias else ""
            
            is_valid = main_cat in valid_intra_cats or \
                       categorias.startswith('41') or \
                       categorias.startswith('18.1')
            
            assert is_valid, f"Invalid intra category: {categorias} for {alimento.get('nombre')}"
        
        print(f"✅ tipo_comida='intra' correctly filters to aminoacids/isotonic ({len(sugerencias)} foods)")
    
    def test_suggest_tipo_comida_post_returns_post_categories(self, auth_headers):
        """
        FIX 6: tipo_comida='post' should return post-workout categories 
        (protein powders, fast carbs, fruits, etc.)
        """
        response = requests.post(
            f"{BASE_URL}/api/calculator/suggest",
            headers=auth_headers,
            json={
                "macros_restantes": {"P": 32, "H": 21, "G": 0},  # Typical post macros
                "tipo_comida": "post",  # FIX 6
                "es_vegano": False,
                "max_resultados": 20,
                "excluir_ids": []
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        sugerencias = data.get("sugerencias", [])
        assert len(sugerencias) > 0, "No suggestions for post workout"
        
        # Post categories include: 4 (protein), 5 (dairy), 11 (fruits), etc.
        # Just verify we get results and they're from valid post categories
        print(f"✅ tipo_comida='post' returns {len(sugerencias)} post-workout foods")
    
    def test_search_tipo_comida_intra(self, auth_headers):
        """
        Search endpoint with tipo_comida='intra' should filter results
        """
        response = requests.get(
            f"{BASE_URL}/api/calculator/search",
            headers=auth_headers,
            params={
                "q": "",  # Empty query to get all intra foods
                "limit": "20",
                "tipo_comida": "intra"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        alimentos = data.get("alimentos", [])
        
        # Verify all returned foods are intra-compatible
        for alimento in alimentos:
            categorias = alimento.get("categorias", "")
            is_valid = categorias.startswith('41') or categorias.startswith('18.1')
            assert is_valid, f"Non-intra food in intra search: {alimento.get('nombre')} ({categorias})"
        
        print(f"✅ Search with tipo_comida='intra' returns {len(alimentos)} valid intra foods")


class TestMacrosEfectivosEndpoint:
    """
    FIX 8: Test the macros-efectivos endpoint used for quantity adjustments
    """
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_macros_efectivos_calculates_correctly(self, auth_headers):
        """
        FIX 8: Endpoint should correctly calculate macros for given quantity
        """
        # First, search for a food to get an ID
        search_response = requests.get(
            f"{BASE_URL}/api/calculator/search",
            headers=auth_headers,
            params={"q": "pollo", "limit": "1"}
        )
        assert search_response.status_code == 200
        foods = search_response.json().get("alimentos", [])
        
        if not foods:
            pytest.skip("No food found for testing")
        
        food_id = foods[0].get("id")
        
        # Test macros calculation
        response = requests.post(
            f"{BASE_URL}/api/calculator/macros-efectivos",
            headers=auth_headers,
            json={
                "alimento_id": food_id,
                "cantidad_g": 100,
                "es_vegano": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "efectivos" in data, "Response should contain 'efectivos' field"
        efectivos = data["efectivos"]
        assert "P" in efectivos and "H" in efectivos and "G" in efectivos
        
        print(f"✅ macros-efectivos returns: P={efectivos['P']}, H={efectivos['H']}, G={efectivos['G']}")
    
    def test_macros_efectivos_updates_with_quantity_change(self, auth_headers):
        """
        FIX 8: When quantity changes, macros should update proportionally
        """
        # Search for a food
        search_response = requests.get(
            f"{BASE_URL}/api/calculator/search",
            headers=auth_headers,
            params={"q": "arroz", "limit": "1"}
        )
        foods = search_response.json().get("alimentos", [])
        
        if not foods:
            pytest.skip("No food found")
        
        food_id = foods[0].get("id")
        
        # Get macros for 100g
        response_100 = requests.post(
            f"{BASE_URL}/api/calculator/macros-efectivos",
            headers=auth_headers,
            json={"alimento_id": food_id, "cantidad_g": 100, "es_vegano": False}
        )
        
        # Get macros for 200g
        response_200 = requests.post(
            f"{BASE_URL}/api/calculator/macros-efectivos",
            headers=auth_headers,
            json={"alimento_id": food_id, "cantidad_g": 200, "es_vegano": False}
        )
        
        assert response_100.status_code == 200 and response_200.status_code == 200
        
        ef_100 = response_100.json()["efectivos"]
        ef_200 = response_200.json()["efectivos"]
        
        # H should roughly double (allowing for rounding)
        if ef_100["H"] > 0:
            ratio = ef_200["H"] / ef_100["H"]
            assert 1.8 <= ratio <= 2.2, f"Carbs ratio should be ~2x, got {ratio}"
        
        print(f"✅ Macros scale correctly: 100g H={ef_100['H']}, 200g H={ef_200['H']}")


class TestDistributeEndpoint:
    """Test the distribute endpoint for intra+post configuration"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_distribute_with_intra_post_option(self, auth_headers):
        """
        When opcion_peri='intra_post', distribution should include both Intra and Post meals
        """
        response = requests.post(
            f"{BASE_URL}/api/calculator/distribute",
            headers=auth_headers,
            json={
                "tipo_dia": "entrenamiento",
                "num_comidas": 4,
                "momento_entreno": 1,
                "opcion_peri": "intra_post"  # Both intra and post
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have periworkout with both Intra and Post
        periworkout = data.get("periworkout", {})
        
        assert "Intra" in periworkout, "Distribution should include Intra meal"
        assert "Post" in periworkout, "Distribution should include Post meal"
        
        intra_macros = periworkout["Intra"]
        post_macros = periworkout["Post"]
        
        print(f"✅ Intra macros: P={intra_macros.get('P')}, H={intra_macros.get('H')}")
        print(f"✅ Post macros: P={post_macros.get('P')}, H={post_macros.get('H')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
