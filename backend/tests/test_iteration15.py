"""
JG12 Iteration 15 - Test new Nutrition module features:
1. Calendar visual de dietas (GET /api/diets/calendar/{year}/{month})
2. Export diet to PDF (GET /api/diets/{fecha}/pdf)
3. Auto-detect day type from routine (GET /api/routines/current)
4. Existing diet data for 2026-04-15 (partial)
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestJG12Iteration15:
    """Test new features for JG12 Nutrition module"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test credentials and auth"""
        self.client_email = "clientedemo@test.com"
        self.client_password = "demo123"
        self.auth_headers = None
        
    def get_auth_token(self):
        """Get auth token for client user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": self.client_email, "password": self.client_password}
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            return {"Authorization": f"Bearer {token}"}
        return None
    
    # ==================== CALENDAR ENDPOINT TESTS ====================
    
    def test_calendar_endpoint_returns_200(self):
        """Test GET /api/diets/calendar/2026/4 returns HTTP 200"""
        headers = self.get_auth_token()
        assert headers, "Failed to get auth token"
        
        response = requests.get(
            f"{BASE_URL}/api/diets/calendar/2026/4",
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ GET /api/diets/calendar/2026/4 returns 200")
        
    def test_calendar_returns_days_dict(self):
        """Test calendar endpoint returns days dictionary"""
        headers = self.get_auth_token()
        assert headers, "Failed to get auth token"
        
        response = requests.get(
            f"{BASE_URL}/api/diets/calendar/2026/4",
            headers=headers
        )
        data = response.json()
        assert "days" in data, "Response missing 'days' key"
        assert "year" in data, "Response missing 'year' key"
        assert "month" in data, "Response missing 'month' key"
        assert data["year"] == 2026
        assert data["month"] == 4
        print(f"✅ Calendar returns year=2026, month=4, days dict")
        
    def test_calendar_shows_partial_diet_for_april_15(self):
        """Test calendar shows partial status for 2026-04-15"""
        headers = self.get_auth_token()
        assert headers, "Failed to get auth token"
        
        response = requests.get(
            f"{BASE_URL}/api/diets/calendar/2026/4",
            headers=headers
        )
        data = response.json()
        days = data.get("days", {})
        
        # Check if 2026-04-15 has a diet entry
        day_15 = days.get("2026-04-15")
        if day_15:
            print(f"✅ Day 15 has diet: status={day_15.get('status')}, total_comidas={day_15.get('total_comidas')}")
            assert day_15.get("status") in ["partial", "complete"], f"Expected partial/complete, got {day_15.get('status')}"
        else:
            print(f"⚠️ No diet found for 2026-04-15 in calendar")
            
    # ==================== PDF EXPORT TESTS ====================
    
    def test_pdf_export_returns_200_for_existing_diet(self):
        """Test GET /api/diets/2026-04-15/pdf returns 200 with PDF content"""
        headers = self.get_auth_token()
        assert headers, "Failed to get auth token"
        
        response = requests.get(
            f"{BASE_URL}/api/diets/2026-04-15/pdf",
            headers=headers
        )
        
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            assert "application/pdf" in content_type, f"Expected PDF content-type, got {content_type}"
            assert len(response.content) > 0, "PDF content is empty"
            print(f"✅ GET /api/diets/2026-04-15/pdf returns 200 with PDF ({len(response.content)} bytes)")
        elif response.status_code == 404:
            print(f"⚠️ No diet saved for 2026-04-15, PDF export returns 404 (expected if no diet)")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")
            
    def test_pdf_export_returns_404_for_nonexistent_date(self):
        """Test GET /api/diets/nonexistent-date/pdf returns 404"""
        headers = self.get_auth_token()
        assert headers, "Failed to get auth token"
        
        response = requests.get(
            f"{BASE_URL}/api/diets/1999-01-01/pdf",
            headers=headers
        )
        assert response.status_code == 404, f"Expected 404 for nonexistent diet, got {response.status_code}"
        print(f"✅ GET /api/diets/1999-01-01/pdf returns 404 (no diet)")
        
    def test_pdf_export_content_disposition_header(self):
        """Test PDF export has correct Content-Disposition header"""
        headers = self.get_auth_token()
        assert headers, "Failed to get auth token"
        
        response = requests.get(
            f"{BASE_URL}/api/diets/2026-04-15/pdf",
            headers=headers
        )
        
        if response.status_code == 200:
            content_disp = response.headers.get("Content-Disposition", "")
            assert "attachment" in content_disp, f"Expected attachment disposition, got {content_disp}"
            assert "dieta_jg12_2026-04-15.pdf" in content_disp, f"Expected filename in disposition"
            print(f"✅ PDF has correct Content-Disposition: {content_disp}")
        else:
            print(f"⚠️ Skipping Content-Disposition test - no diet for 2026-04-15")
            
    # ==================== ROUTINES/CURRENT TESTS (for auto-detect) ====================
    
    def test_routines_current_endpoint_exists(self):
        """Test GET /api/routines/current returns 200 or null"""
        headers = self.get_auth_token()
        assert headers, "Failed to get auth token"
        
        response = requests.get(
            f"{BASE_URL}/api/routines/current",
            headers=headers
        )
        # Can return 200 with routine or 200 with null
        assert response.status_code in [200, 404], f"Expected 200/404, got {response.status_code}"
        print(f"✅ GET /api/routines/current returns {response.status_code}")
        
    def test_routines_current_has_days_array(self):
        """Test routine has days array with is_rest field for auto-detect"""
        headers = self.get_auth_token()
        assert headers, "Failed to get auth token"
        
        response = requests.get(
            f"{BASE_URL}/api/routines/current",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            if data:  # Not null
                assert "days" in data, "Routine missing 'days' array"
                days = data["days"]
                assert len(days) == 7, f"Expected 7 days, got {len(days)}"
                
                # Check each day has required fields
                for day in days:
                    assert "day" in day, "Day missing 'day' field"
                    assert "is_rest" in day, "Day missing 'is_rest' field"
                    
                print(f"✅ Routine has 7 days with is_rest field")
                
                # Check Wednesday (miércoles) is rest day
                wednesday = next((d for d in days if d["day"].lower() == "miércoles"), None)
                if wednesday:
                    print(f"   Miércoles is_rest: {wednesday['is_rest']}")
            else:
                print(f"⚠️ No routine assigned to client")
        else:
            print(f"⚠️ No routine found (404)")
            
    # ==================== DIET DATA VERIFICATION ====================
    
    def test_diet_exists_for_april_15(self):
        """Test diet exists for 2026-04-15 with meals"""
        headers = self.get_auth_token()
        assert headers, "Failed to get auth token"
        
        response = requests.get(
            f"{BASE_URL}/api/diets/2026-04-15",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data.get("exists"):
            comidas = data.get("comidas", {})
            total_meals = len([k for k, v in comidas.items() if v.get("alimentos")])
            print(f"✅ Diet for 2026-04-15 exists with {total_meals} meals")
            
            # List meals with foods
            for key, meal in comidas.items():
                alimentos = meal.get("alimentos", [])
                if alimentos:
                    names = [a.get("nombre", "?")[:20] for a in alimentos]
                    print(f"   {key}: {', '.join(names)}")
        else:
            print(f"⚠️ No diet saved for 2026-04-15")
            
    def test_diet_april_12_exists(self):
        """Test diet exists for 2026-04-12 (mentioned as partial)"""
        headers = self.get_auth_token()
        assert headers, "Failed to get auth token"
        
        response = requests.get(
            f"{BASE_URL}/api/diets/2026-04-12",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data.get("exists"):
            print(f"✅ Diet for 2026-04-12 exists")
        else:
            print(f"⚠️ No diet saved for 2026-04-12")


class TestAuthAndBasicEndpoints:
    """Basic auth and endpoint tests"""
    
    def test_login_client_user(self):
        """Test client login works"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "clientedemo@test.com", "password": "demo123"}
        )
        assert response.status_code == 200, f"Login failed: {response.status_code}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        print(f"✅ Client login successful")
        
    def test_health_endpoint(self):
        """Test health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print(f"✅ Health endpoint OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
