"""
Test suite for Target Calculator (Capa de Targets) - JG12 Platform
Tests the automatic macro calculation based on weight, sex, body fat %, and goal.
Uses Jesús Gallego's tables (macros_tables.json) with 404 combinations.

Endpoints tested:
- POST /api/calculator/targets - Calculate macros
- POST /api/calculator/targets/apply - Calculate and apply to profile
- GET /api/calculator/test-targets - Internal engine tests
- GET /api/macros - Verify applied macros
- POST /api/chatbot/start - Verify chatbot reads auto-calculated macros
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CLIENT_EMAIL = "clientedemo@test.com"
CLIENT_PASSWORD = "demo123"
ADMIN_EMAIL = "alvaro@test.com"
ADMIN_PASSWORD = "Alvaro123"


class TestTargetCalculatorSetup:
    """Setup and authentication tests"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, client_token):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {client_token}"}


class TestTargetCalculatorCanonical(TestTargetCalculatorSetup):
    """Test canonical case: Hombre 80kg 20%BF volumen"""
    
    def test_canonical_hombre_80kg_20bf_volumen(self, auth_headers):
        """
        Canonical test case: Hombre 80kg 20%BF volumen
        Expected: P_e=190, H_e=170, G_e=60, P_pe=45, H_pe=50, P_d=225, H_d=170, G_d=60
        """
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 80,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "macros" in data
        assert "entreno" in data["macros"]
        assert "perientreno" in data["macros"]
        assert "descanso" in data["macros"]
        
        # Verify canonical values - Entreno
        entreno = data["macros"]["entreno"]
        assert entreno["proteina"] == 190, f"P_e expected 190, got {entreno['proteina']}"
        assert entreno["hidratos"] == 170, f"H_e expected 170, got {entreno['hidratos']}"
        assert entreno["grasa"] == 60, f"G_e expected 60, got {entreno['grasa']}"
        
        # Verify canonical values - Perientreno
        peri = data["macros"]["perientreno"]
        assert peri["proteina"] == 45, f"P_pe expected 45, got {peri['proteina']}"
        assert peri["hidratos"] == 50, f"H_pe expected 50, got {peri['hidratos']}"
        
        # Verify canonical values - Descanso
        descanso = data["macros"]["descanso"]
        assert descanso["proteina"] == 225, f"P_d expected 225, got {descanso['proteina']}"
        assert descanso["hidratos"] == 170, f"H_d expected 170, got {descanso['hidratos']}"
        assert descanso["grasa"] == 60, f"G_d expected 60, got {descanso['grasa']}"
        
        # Verify lookup snapping
        assert data["lookup"]["peso_snap"] == 80
        assert data["lookup"]["bf_snap"] == 20
        
        print("✅ Canonical case H80 BF20 volumen: All macros match expected values")


class TestTargetCalculatorMujer(TestTargetCalculatorSetup):
    """Test female cases"""
    
    def test_mujer_60kg_25bf_definicion(self, auth_headers):
        """Mujer 60kg 25%BF definición - should return valid macros"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 60,
                "sexo": "mujer",
                "porcentaje_graso": 25,
                "objetivo": "definición"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        
        # Verify macros are positive
        assert data["macros"]["entreno"]["proteina"] > 0
        assert data["macros"]["entreno"]["hidratos"] > 0
        assert data["macros"]["entreno"]["grasa"] > 0
        
        # Verify lookup snapping for mujer
        assert data["lookup"]["peso_snap"] == 60
        assert data["lookup"]["bf_snap"] == 25
        
        print(f"✅ Mujer 60kg 25%BF definición: P_e={data['macros']['entreno']['proteina']}, H_e={data['macros']['entreno']['hidratos']}, G_e={data['macros']['entreno']['grasa']}")


class TestTargetCalculatorSnapping(TestTargetCalculatorSetup):
    """Test weight and BF snapping to nearest step"""
    
    def test_peso_intermedio_82kg_snap_to_80(self, auth_headers):
        """Peso intermedio 82kg should snap to 80"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 82,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lookup"]["peso_snap"] == 80, f"Expected snap to 80, got {data['lookup']['peso_snap']}"
        print("✅ Peso 82kg snapped to 80kg correctly")
    
    def test_bf_intermedio_22_snap_to_20(self, auth_headers):
        """BF intermedio 22% should snap to 20%"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 80,
                "sexo": "hombre",
                "porcentaje_graso": 22,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lookup"]["bf_snap"] == 20, f"Expected snap to 20, got {data['lookup']['bf_snap']}"
        print("✅ BF 22% snapped to 20% correctly")
    
    def test_peso_fuera_rango_alto_130kg_snap_to_120(self, auth_headers):
        """Peso fuera de rango alto 130kg should clamp to 120"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 130,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lookup"]["peso_snap"] == 120, f"Expected clamp to 120, got {data['lookup']['peso_snap']}"
        print("✅ Peso 130kg clamped to 120kg correctly")
    
    def test_peso_fuera_rango_bajo_55kg_snap_to_60(self, auth_headers):
        """Peso fuera de rango bajo 55kg (hombre) should clamp to 60"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 55,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lookup"]["peso_snap"] == 60, f"Expected clamp to 60, got {data['lookup']['peso_snap']}"
        print("✅ Peso 55kg (hombre) clamped to 60kg correctly")
    
    def test_mujer_peso_bajo_45kg_snap_to_50(self, auth_headers):
        """Mujer peso bajo 45kg should clamp to 50"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 45,
                "sexo": "mujer",
                "porcentaje_graso": 25,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lookup"]["peso_snap"] == 50, f"Expected clamp to 50, got {data['lookup']['peso_snap']}"
        print("✅ Mujer peso 45kg clamped to 50kg correctly")
    
    def test_bf_fuera_rango_bajo_8_snap_to_10(self, auth_headers):
        """BF fuera de rango bajo 8% (hombre) should clamp to 10%"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 80,
                "sexo": "hombre",
                "porcentaje_graso": 8,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lookup"]["bf_snap"] == 10, f"Expected clamp to 10, got {data['lookup']['bf_snap']}"
        print("✅ BF 8% (hombre) clamped to 10% correctly")


class TestTargetCalculatorApply(TestTargetCalculatorSetup):
    """Test applying targets to client profile"""
    
    def test_apply_targets_to_profile(self, auth_headers):
        """Apply targets and verify macros_source is 'auto'"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets/apply",
            json={
                "peso": 80,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Apply failed: {response.text}"
        data = response.json()
        
        assert data["applied"] == True
        assert "targets" in data
        assert "profile_macros" in data
        
        # Verify profile_macros format
        pm = data["profile_macros"]
        assert "macros_training" in pm
        assert "macros_rest" in pm
        assert "macros_periworkout" in pm
        
        # Verify training macros match canonical values
        assert pm["macros_training"]["protein"] == 190
        assert pm["macros_training"]["carbs"] == 170
        assert pm["macros_training"]["fat"] == 60
        
        print("✅ Targets applied to profile successfully")
    
    def test_verify_macros_after_apply(self, auth_headers):
        """Verify GET /api/macros returns applied macros with source='auto'"""
        # First apply targets
        requests.post(
            f"{BASE_URL}/api/calculator/targets/apply",
            json={
                "peso": 80,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        # Then verify via GET /api/macros
        response = requests.get(f"{BASE_URL}/api/macros", headers=auth_headers)
        
        assert response.status_code == 200, f"GET macros failed: {response.text}"
        data = response.json()
        
        assert data["source"] == "auto", f"Expected source='auto', got {data['source']}"
        assert data["training"]["protein"] == 190 or data["training"]["proteinas"] == 190
        
        print("✅ GET /api/macros returns auto-calculated macros correctly")


class TestTargetCalculatorChatbot(TestTargetCalculatorSetup):
    """Test chatbot reads auto-calculated macros"""
    
    def test_chatbot_reads_auto_macros(self, auth_headers):
        """POST /api/chatbot/start should read macros from profile"""
        # First apply targets
        requests.post(
            f"{BASE_URL}/api/calculator/targets/apply",
            json={
                "peso": 80,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        # Then start chatbot
        response = requests.post(f"{BASE_URL}/api/chatbot/start", headers=auth_headers)
        
        assert response.status_code == 200, f"Chatbot start failed: {response.text}"
        data = response.json()
        
        assert "macros" in data
        macros = data["macros"]
        
        # Verify chatbot received the auto-calculated macros
        assert macros["p_entreno"] == 190, f"Expected p_entreno=190, got {macros['p_entreno']}"
        assert macros["h_entreno"] == 170, f"Expected h_entreno=170, got {macros['h_entreno']}"
        assert macros["g_entreno"] == 60, f"Expected g_entreno=60, got {macros['g_entreno']}"
        
        print("✅ Chatbot reads auto-calculated macros correctly")


class TestTargetCalculatorInternalTests(TestTargetCalculatorSetup):
    """Test internal engine tests"""
    
    def test_internal_engine_tests(self, auth_headers):
        """GET /api/calculator/test-targets should pass all 22 tests"""
        response = requests.get(f"{BASE_URL}/api/calculator/test-targets", headers=auth_headers)
        
        assert response.status_code == 200, f"Test-targets failed: {response.text}"
        data = response.json()
        
        assert data["all_passed"] == True, f"Internal tests failed: {data.get('failed_tests', [])}"
        assert data["total"] >= 20, f"Expected at least 20 tests, got {data['total']}"
        
        print(f"✅ Internal engine tests: {data['passed']}/{data['total']} passed")


class TestTargetCalculatorInvariant(TestTargetCalculatorSetup):
    """Test invariant: P and G same for volumen and definición, only H changes"""
    
    def test_invariant_p_g_same_h_different(self, auth_headers):
        """P and G should be same for volumen and definición, only H changes"""
        # Get volumen
        vol_response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 80,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        vol_data = vol_response.json()
        
        # Get definición
        def_response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 80,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "definición"
            },
            headers=auth_headers
        )
        def_data = def_response.json()
        
        # Verify P entreno same
        assert vol_data["macros"]["entreno"]["proteina"] == def_data["macros"]["entreno"]["proteina"], \
            f"P entreno should be same: vol={vol_data['macros']['entreno']['proteina']}, def={def_data['macros']['entreno']['proteina']}"
        
        # Verify G entreno same
        assert vol_data["macros"]["entreno"]["grasa"] == def_data["macros"]["entreno"]["grasa"], \
            f"G entreno should be same: vol={vol_data['macros']['entreno']['grasa']}, def={def_data['macros']['entreno']['grasa']}"
        
        # Verify H entreno different
        assert vol_data["macros"]["entreno"]["hidratos"] != def_data["macros"]["entreno"]["hidratos"], \
            f"H entreno should be different: vol={vol_data['macros']['entreno']['hidratos']}, def={def_data['macros']['entreno']['hidratos']}"
        
        print(f"✅ Invariant verified: P={vol_data['macros']['entreno']['proteina']} (same), G={vol_data['macros']['entreno']['grasa']} (same), H_vol={vol_data['macros']['entreno']['hidratos']} vs H_def={def_data['macros']['entreno']['hidratos']} (different)")


class TestTargetCalculatorValidation(TestTargetCalculatorSetup):
    """Test validation and error handling"""
    
    def test_missing_required_fields(self, auth_headers):
        """Should return 400 when required fields are missing"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 80,
                "sexo": "hombre"
                # Missing porcentaje_graso and objetivo
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Missing fields returns 400 correctly")
    
    def test_invalid_sexo(self, auth_headers):
        """Should return 400 for invalid sexo"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 80,
                "sexo": "invalid",
                "porcentaje_graso": 20,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Invalid sexo returns 400 correctly")
    
    def test_invalid_objetivo(self, auth_headers):
        """Should return 400 for invalid objetivo"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 80,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "invalid"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Invalid objetivo returns 400 correctly")
    
    def test_objetivo_with_accent(self, auth_headers):
        """Should accept 'definición' with accent"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 80,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "definición"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ 'definición' with accent accepted correctly")


class TestTargetCalculatorDerivation(TestTargetCalculatorSetup):
    """Test mass derivation calculations"""
    
    def test_masa_trabajo_calculation(self, auth_headers):
        """Verify masa_grasa, masa_magra, masa_trabajo calculations"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/targets",
            json={
                "peso": 80,
                "sexo": "hombre",
                "porcentaje_graso": 20,
                "objetivo": "volumen"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        derivacion = data["derivacion"]
        
        # masa_grasa = 80 * 0.20 = 16
        assert derivacion["masa_grasa"] == 16.0, f"Expected masa_grasa=16, got {derivacion['masa_grasa']}"
        
        # masa_magra = 80 - 16 = 64
        assert derivacion["masa_magra"] == 64.0, f"Expected masa_magra=64, got {derivacion['masa_magra']}"
        
        # masa_trabajo = 64 / 0.85 ≈ 75.29
        assert abs(derivacion["masa_trabajo"] - 75.29) < 0.1, f"Expected masa_trabajo≈75.29, got {derivacion['masa_trabajo']}"
        
        print(f"✅ Derivation correct: masa_grasa={derivacion['masa_grasa']}, masa_magra={derivacion['masa_magra']}, masa_trabajo={derivacion['masa_trabajo']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
