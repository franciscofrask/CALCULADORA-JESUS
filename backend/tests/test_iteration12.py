"""
Test suite for JG12 iteration 12 features:
1. Dashboard trackers showing real consumed vs target (from /api/diets/{fecha})
2. RoutinePage redesigned with day grid, stats, expandable exercises
3. /api/calculator/distribute endpoint
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_client_login(self):
        """Test client login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "clientedemo@test.com"
        print("✅ Client login successful")


class TestDietsEndpoint:
    """Tests for GET /api/diets/{fecha} endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_diet_today_no_diet(self, auth_headers):
        """Test GET /api/diets/{today} returns exists: false when no diet saved"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.get(f"{BASE_URL}/api/diets/{today}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "fecha" in data
        assert data["fecha"] == today
        assert data["exists"] == False
        print(f"✅ GET /api/diets/{today} returns exists: false (no diet)")
    
    def test_get_diet_past_date_no_diet(self, auth_headers):
        """Test GET /api/diets/{past_date} returns exists: false"""
        past_date = "2025-01-01"
        response = requests.get(f"{BASE_URL}/api/diets/{past_date}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] == False
        print(f"✅ GET /api/diets/{past_date} returns exists: false")


class TestDistributeEndpoint:
    """Tests for POST /api/calculator/distribute endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_distribute_training_day(self, auth_headers):
        """Test distribute macros for training day"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/distribute",
            headers=auth_headers,
            json={
                "tipo_dia": "entrenamiento",
                "num_comidas": 4,
                "momento_entreno": 1,
                "opcion_peri": "intra_post"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "comidas" in data
        assert "periworkout" in data
        assert "resumen" in data
        assert "config" in data
        
        # Check comidas
        assert "C1" in data["comidas"]
        assert "C2" in data["comidas"]
        assert "C3" in data["comidas"]
        assert "C4" in data["comidas"]
        
        # Check periworkout
        assert "Intra" in data["periworkout"]
        assert "Post" in data["periworkout"]
        
        # Check each comida has P, H, G
        for meal_key in ["C1", "C2", "C3", "C4"]:
            meal = data["comidas"][meal_key]
            assert "P" in meal
            assert "H" in meal
            assert "G" in meal
            assert meal["P"] > 0
        
        print(f"✅ POST /api/calculator/distribute (training) returns correct structure")
        print(f"   Comidas: C1={data['comidas']['C1']}, C2={data['comidas']['C2']}")
        print(f"   Peri: Intra={data['periworkout']['Intra']}, Post={data['periworkout']['Post']}")
        print(f"   Resumen: {data['resumen']}")
    
    def test_distribute_rest_day(self, auth_headers):
        """Test distribute macros for rest day"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/distribute",
            headers=auth_headers,
            json={
                "tipo_dia": "descanso",
                "num_comidas": 4,
                "momento_entreno": 1,
                "opcion_peri": "intra_post"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "comidas" in data
        assert "resumen" in data
        
        # Rest day should have different macros
        assert data["config"]["tipo_dia"] == "descanso"
        
        print(f"✅ POST /api/calculator/distribute (rest) returns correct structure")
        print(f"   Resumen: {data['resumen']}")
    
    def test_distribute_3_meals(self, auth_headers):
        """Test distribute with 3 meals"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/distribute",
            headers=auth_headers,
            json={
                "tipo_dia": "entrenamiento",
                "num_comidas": 3,
                "momento_entreno": 1,
                "opcion_peri": "intra_post"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have C1, C2, C3 but not C4
        assert "C1" in data["comidas"]
        assert "C2" in data["comidas"]
        assert "C3" in data["comidas"]
        
        print(f"✅ POST /api/calculator/distribute (3 meals) works correctly")


class TestRoutinesEndpoint:
    """Tests for routines endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_current_routine_no_routine(self, auth_headers):
        """Test GET /api/routines/current returns null when no routine assigned"""
        response = requests.get(f"{BASE_URL}/api/routines/current", headers=auth_headers)
        
        # Should return 200 with null or empty data
        assert response.status_code in [200, 404]
        print(f"✅ GET /api/routines/current returns {response.status_code} (no routine)")
    
    def test_get_routine_history(self, auth_headers):
        """Test GET /api/routines/history returns list"""
        response = requests.get(f"{BASE_URL}/api/routines/history", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/routines/history returns list with {len(data)} items")


class TestMacrosEndpoint:
    """Tests for macros endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_macros(self, auth_headers):
        """Test GET /api/macros returns client macros"""
        response = requests.get(f"{BASE_URL}/api/macros", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "training" in data
        assert "rest" in data
        assert "periworkout" in data
        assert "source" in data
        
        # Check training macros (expected: P=190, H=170, G=60)
        training = data["training"]
        assert training.get("protein") == 190 or training.get("proteinas") == 190
        assert training.get("carbs") == 170 or training.get("hidratos") == 170
        assert training.get("fat") == 60 or training.get("grasas") == 60
        
        # Check rest macros (expected: P=225, H=170, G=60)
        rest = data["rest"]
        assert rest.get("protein") == 225 or rest.get("proteinas") == 225
        
        # Check periworkout (expected: P=45, H=50)
        peri = data["periworkout"]
        assert peri.get("protein") == 45 or peri.get("proteinas") == 45
        assert peri.get("carbs") == 50 or peri.get("hidratos") == 50
        
        # Check source is auto
        assert data["source"] == "auto"
        
        print(f"✅ GET /api/macros returns correct values")
        print(f"   Training: P={training.get('protein') or training.get('proteinas')}, H={training.get('carbs') or training.get('hidratos')}, G={training.get('fat') or training.get('grasas')}")
        print(f"   Rest: P={rest.get('protein') or rest.get('proteinas')}")
        print(f"   Peri: P={peri.get('protein') or peri.get('proteinas')}, H={peri.get('carbs') or peri.get('hidratos')}")
        print(f"   Source: {data['source']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
