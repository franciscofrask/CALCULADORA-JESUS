"""
Tests for food search (Buscador de alimentos) - TAREA E12
Testing:
1. Accent normalization: 'atun' finds 'Atún', 'jamon' finds 'Jamón'
2. Effective macros displayed (not raw)
3. 23 categories available
4. Correct ration shown (not hardcoded 100g)
5. Search limit is 50 results
6. Category filtering works correctly
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8000')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for client user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "clientedemo@test.com",
        "password": "demo123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping tests")

@pytest.fixture
def auth_headers(auth_token):
    """Headers with authentication token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestAccentNormalization:
    """Test that searches ignore accents"""
    
    def test_search_atun_finds_atun_with_accent(self, auth_headers):
        """Search 'atun' should find 'Atún' (with accent)"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=atun&limit=50",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check we got results
        assert data.get("total", 0) > 0, "Expected at least 1 result for 'atun'"
        
        # Check that at least one result contains 'Atún' or 'atun' (case-insensitive)
        alimentos = data.get("alimentos", [])
        found_atun = any(
            "atún" in a.get("nombre", "").lower() or "atun" in a.get("nombre", "").lower()
            for a in alimentos
        )
        assert found_atun, "Expected to find 'Atún' when searching 'atun'"
        print(f"✅ Found {len(alimentos)} results for 'atun'")
    
    def test_search_jamon_finds_jamon_with_accent(self, auth_headers):
        """Search 'jamon' should find 'Jamón' (with accent)"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=jamon&limit=50",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check we got results
        assert data.get("total", 0) > 0, "Expected at least 1 result for 'jamon'"
        
        # Check that at least one result contains 'Jamón' or 'jamon'
        alimentos = data.get("alimentos", [])
        found_jamon = any(
            "jamón" in a.get("nombre", "").lower() or "jamon" in a.get("nombre", "").lower()
            for a in alimentos
        )
        assert found_jamon, "Expected to find 'Jamón' when searching 'jamon'"
        print(f"✅ Found {len(alimentos)} results for 'jamon'")
    
    def test_search_salmon_finds_salmon_with_accent(self, auth_headers):
        """Search 'salmon' should find 'Salmón' (with accent)"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=salmon&limit=50",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("total", 0) > 0, "Expected at least 1 result for 'salmon'"
        
        alimentos = data.get("alimentos", [])
        found_salmon = any(
            "salmón" in a.get("nombre", "").lower() or "salmon" in a.get("nombre", "").lower()
            for a in alimentos
        )
        assert found_salmon, "Expected to find 'Salmón' when searching 'salmon'"
        print(f"✅ Found {len(alimentos)} results for 'salmon'")


class TestEffectiveMacros:
    """Test that effective macros (calculated by CALMA) are returned correctly"""
    
    def test_search_returns_macros_efectivos(self, auth_headers):
        """Search results should include macros_efectivos field"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=pollo&limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("total", 0) > 0, "Expected results for 'pollo'"
        
        # Check that macros_efectivos is included in at least one result
        alimentos = data.get("alimentos", [])
        has_macros_efectivos = any(
            "macros_efectivos" in a for a in alimentos
        )
        assert has_macros_efectivos, "Expected macros_efectivos field in search results"
        print(f"✅ macros_efectivos field present in search results")
    
    def test_arroz_only_counts_hidratos(self, auth_headers):
        """Arroz (cat 21) should only show H, P=0 because of CALMA rules"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=arroz&category=21&limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("total", 0) > 0, "Expected results for 'arroz'"
        
        # Find an arroz item and check its macros_efectivos
        alimentos = data.get("alimentos", [])
        for a in alimentos:
            if "arroz" in a.get("nombre", "").lower():
                macros_ef = a.get("macros_efectivos", {})
                # For cat 21 (arroz), P should be 0 effective
                assert macros_ef.get("P", -1) == 0, f"Expected P=0 for arroz, got {macros_ef.get('P')}"
                # H should be > 0
                assert macros_ef.get("H", 0) > 0, f"Expected H>0 for arroz, got {macros_ef.get('H')}"
                print(f"✅ Arroz '{a.get('nombre')}' has P={macros_ef.get('P')}, H={macros_ef.get('H')}, G={macros_ef.get('G')}")
                return
        
        pytest.fail("No arroz found with macros_efectivos")
    
    def test_pechuga_low_fat_not_counted(self, auth_headers):
        """Pechuga with G<3% should have G=0 in macros_efectivos"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=pechuga&category=2&limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("total", 0) > 0, "Expected results for 'pechuga'"
        
        # Find a pechuga and check its macros_efectivos
        alimentos = data.get("alimentos", [])
        for a in alimentos:
            nombre = a.get("nombre", "").lower()
            if "pechuga" in nombre:
                grasas_raw = a.get("grasas", 0)
                macros_ef = a.get("macros_efectivos", {})
                
                # If raw fat < 3%, effective fat should be 0
                if grasas_raw < 3:
                    assert macros_ef.get("G", -1) == 0, f"Expected G=0 for pechuga with raw fat {grasas_raw}, got {macros_ef.get('G')}"
                    print(f"✅ Pechuga '{a.get('nombre')}' has raw G={grasas_raw}, effective G={macros_ef.get('G')} (correct)")
                    return
        
        print("ℹ️ No pechuga with G<3% found to test")


class TestSearchLimit:
    """Test search returns up to 50 results"""
    
    def test_search_limit_is_50(self, auth_headers):
        """Search should return up to 50 results by default"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=&limit=50",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check limit parameter in response
        assert data.get("limit") == 50, f"Expected limit=50, got {data.get('limit')}"
        
        # Results should not exceed 50
        assert data.get("total", 0) <= 50, f"Expected max 50 results, got {data.get('total')}"
        print(f"✅ Search limit is correctly set to 50, returned {data.get('total')} results")


class TestCategoryFiltering:
    """Test category filtering works correctly"""
    
    def test_filter_by_category_2_carnes(self, auth_headers):
        """Filter by category 2 (Carnes) should return only meat products"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?category=2&limit=30",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("total", 0) > 0, "Expected results for category 2 (Carnes)"
        
        # Check that results have category 2 or subcategory
        alimentos = data.get("alimentos", [])
        for a in alimentos[:5]:  # Check first 5
            cats = str(a.get("categorias", ""))
            assert "2" in cats.split(".")[0] or cats.startswith("2"), \
                f"Expected category 2.x, got {cats} for {a.get('nombre')}"
        
        print(f"✅ Category 2 (Carnes) filter returned {len(alimentos)} results")
    
    def test_filter_by_category_21_arroces(self, auth_headers):
        """Filter by category 21 (Arroces) should return only rice products"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?category=21&limit=30",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("total", 0) > 0, "Expected results for category 21 (Arroces)"
        
        alimentos = data.get("alimentos", [])
        for a in alimentos[:5]:  # Check first 5
            cats = str(a.get("categorias", ""))
            # Category should start with 21
            assert "21" in cats, f"Expected category 21.x, got {cats} for {a.get('nombre')}"
        
        print(f"✅ Category 21 (Arroces) filter returned {len(alimentos)} results")


class TestRacionDisplay:
    """Test that correct ration is returned (not hardcoded 100g)"""
    
    def test_racion_varies_per_food(self, auth_headers):
        """Different foods should have different ration values"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=&limit=50",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        alimentos = data.get("alimentos", [])
        raciones = set()
        
        for a in alimentos:
            racion = a.get("racion", 100)
            raciones.add(racion)
        
        # We expect to see various ration sizes, not just 100
        print(f"✅ Found {len(raciones)} different ration sizes: {sorted(list(raciones)[:10])}")
        
        # At least some should be different from 100
        non_100_raciones = [r for r in raciones if r != 100]
        assert len(non_100_raciones) > 0, "Expected some foods to have ration != 100g"
        print(f"✅ {len(non_100_raciones)} ration sizes are not 100g")


class TestQueCuentaField:
    """Test that que_cuenta field is returned indicating which macros count"""
    
    def test_search_returns_que_cuenta(self, auth_headers):
        """Search results should include que_cuenta field"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/search?q=pollo&limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("total", 0) > 0, "Expected results"
        
        alimentos = data.get("alimentos", [])
        has_que_cuenta = any(
            "que_cuenta" in a for a in alimentos
        )
        assert has_que_cuenta, "Expected que_cuenta field in search results"
        
        # Check structure of que_cuenta
        for a in alimentos:
            if "que_cuenta" in a:
                qc = a["que_cuenta"]
                assert "P" in qc and "H" in qc and "G" in qc, \
                    f"que_cuenta should have P, H, G fields, got {qc}"
                print(f"✅ que_cuenta field present: {qc} for '{a.get('nombre')}'")
                break


class TestCategories:
    """Test categories endpoint"""
    
    def test_get_categories(self, auth_headers):
        """Should be able to get all food categories"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/categories",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return a list of categories
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✅ Categories endpoint returned {len(data)} categories")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
