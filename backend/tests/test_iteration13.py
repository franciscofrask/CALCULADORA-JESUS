"""
JG12 Iteration 13 - Backend Tests
=================================
Tests for:
1. NutritionPage refactored components (DaySummary, ConfigSection, MealCard)
2. RoutinePage with 7-day routine (5 training, 2 rest)
3. Dashboard rest day detection (Wednesday = rest)
4. Macros and diet endpoints
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
        """Get client token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    def test_client_login(self):
        """Test client login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "clientedemo@test.com"
        print("✅ Client login successful")


class TestMacros:
    """Macros endpoint tests"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        return response.json()["access_token"]
    
    def test_get_macros(self, client_token):
        """Test GET /api/macros returns correct values"""
        response = requests.get(
            f"{BASE_URL}/api/macros",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check training macros
        assert "training" in data
        assert data["training"]["protein"] == 190
        assert data["training"]["carbs"] == 170
        assert data["training"]["fat"] == 60
        
        # Check rest macros
        assert "rest" in data
        assert data["rest"]["protein"] == 225
        assert data["rest"]["carbs"] == 170
        assert data["rest"]["fat"] == 60
        
        # Check periworkout macros
        assert "periworkout" in data
        assert data["periworkout"]["protein"] == 45
        assert data["periworkout"]["carbs"] == 50
        
        # Check source
        assert data["source"] == "auto"
        
        print("✅ Macros endpoint returns correct values")


class TestRoutines:
    """Routine endpoint tests"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        return response.json()["access_token"]
    
    def test_get_current_routine(self, client_token):
        """Test GET /api/routines/current returns 7-day routine"""
        response = requests.get(
            f"{BASE_URL}/api/routines/current",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check routine exists
        assert data is not None, "Routine should exist"
        assert "days" in data
        assert len(data["days"]) == 7, "Should have 7 days"
        
        # Check day structure
        days_map = {d["day"].lower(): d for d in data["days"]}
        
        # Verify training days (5)
        training_days = ["lunes", "martes", "jueves", "viernes", "sábado"]
        for day in training_days:
            assert day in days_map, f"{day} should exist"
            assert days_map[day]["is_rest"] == False, f"{day} should be training day"
            assert len(days_map[day]["exercises"]) > 0, f"{day} should have exercises"
        
        # Verify rest days (2)
        rest_days = ["miércoles", "domingo"]
        for day in rest_days:
            assert day in days_map, f"{day} should exist"
            assert days_map[day]["is_rest"] == True, f"{day} should be rest day"
        
        # Verify exercise counts
        assert len(days_map["lunes"]["exercises"]) == 4, "Lunes should have 4 exercises"
        assert len(days_map["martes"]["exercises"]) == 5, "Martes should have 5 exercises"
        assert len(days_map["jueves"]["exercises"]) == 5, "Jueves should have 5 exercises"
        assert len(days_map["viernes"]["exercises"]) == 5, "Viernes should have 5 exercises"
        assert len(days_map["sábado"]["exercises"]) == 4, "Sábado should have 4 exercises"
        
        # Verify trainer notes
        assert "trainer_notes" in data
        assert "Semana de volumen" in data["trainer_notes"]
        
        print("✅ Routine has correct 7-day structure (5 training, 2 rest)")
    
    def test_routine_has_cardio(self, client_token):
        """Test routine has cardio on martes and sábado"""
        response = requests.get(
            f"{BASE_URL}/api/routines/current",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        data = response.json()
        days_map = {d["day"].lower(): d for d in data["days"]}
        
        # Martes should have LISS cardio
        assert days_map["martes"]["cardio"] is not None
        assert days_map["martes"]["cardio"]["type"] == "LISS"
        
        # Sábado should have HIIT cardio
        assert days_map["sábado"]["cardio"] is not None
        assert days_map["sábado"]["cardio"]["type"] == "HIIT"
        
        print("✅ Routine has cardio on martes (LISS) and sábado (HIIT)")
    
    def test_routine_history(self, client_token):
        """Test GET /api/routines/history"""
        response = requests.get(
            f"{BASE_URL}/api/routines/history",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Routine history returns {len(data)} routines")


class TestDiets:
    """Diet endpoint tests"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        return response.json()["access_token"]
    
    def test_get_today_diet(self, client_token):
        """Test GET /api/diets/{today} returns exists:false when no diet"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.get(
            f"{BASE_URL}/api/diets/{today}",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return exists: false if no diet saved
        assert "exists" in data
        # Note: exists could be true or false depending on if diet was saved
        print(f"✅ Diet for {today}: exists={data.get('exists')}")


class TestCalculatorDistribute:
    """Calculator distribute endpoint tests"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "clientedemo@test.com",
            "password": "demo123"
        })
        return response.json()["access_token"]
    
    def test_distribute_training_day(self, client_token):
        """Test POST /api/calculator/distribute for training day"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/distribute",
            headers={"Authorization": f"Bearer {client_token}"},
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
        
        # Check meals exist
        assert "C1" in data["comidas"]
        assert "C2" in data["comidas"]
        assert "C3" in data["comidas"]
        assert "C4" in data["comidas"]
        
        # Check periworkout
        assert "Intra" in data["periworkout"]
        assert "Post" in data["periworkout"]
        
        # Check resumen totals
        assert data["resumen"]["P_total"] > 0
        assert data["resumen"]["H_total"] > 0
        assert data["resumen"]["G_total"] > 0
        
        print("✅ Distribute endpoint works for training day")
    
    def test_distribute_rest_day(self, client_token):
        """Test POST /api/calculator/distribute for rest day"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/distribute",
            headers={"Authorization": f"Bearer {client_token}"},
            json={
                "tipo_dia": "descanso",
                "num_comidas": 4,
                "momento_entreno": 1,
                "opcion_peri": "intra_post"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Rest day should have higher protein (225 vs 190)
        assert data["resumen"]["P_total"] == 225
        
        # Rest day should have empty periworkout (no Intra/Post)
        assert data["periworkout"] == {} or len(data["periworkout"]) == 0
        
        # Rest day kcal should be 2120
        assert data["resumen"]["kcal_total"] == 2120
        
        print("✅ Distribute endpoint works for rest day (P=225, kcal=2120)")
    
    def test_distribute_3_meals(self, client_token):
        """Test POST /api/calculator/distribute with 3 meals"""
        response = requests.post(
            f"{BASE_URL}/api/calculator/distribute",
            headers={"Authorization": f"Bearer {client_token}"},
            json={
                "tipo_dia": "entrenamiento",
                "num_comidas": 3,
                "momento_entreno": 1,
                "opcion_peri": "intra_post"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have C1, C2, C3 but NOT C4
        assert "C1" in data["comidas"]
        assert "C2" in data["comidas"]
        assert "C3" in data["comidas"]
        assert "C4" not in data["comidas"] or data["comidas"]["C4"]["P"] == 0
        
        print("✅ Distribute endpoint works with 3 meals")


class TestHealthEndpoint:
    """Health check tests"""
    
    def test_health(self):
        """Test /api/health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✅ Health endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
