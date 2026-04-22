"""
Iteration 18 - Admin Dashboard Stats & Upcoming Payments Tests
Tests for:
- GET /api/admin/dashboard-stats (new v2 endpoint with KPIs)
- GET /api/admin/upcoming-payments (next 7 days payments)
- GET /api/admin/dashboard (legacy backwards compatibility)
- Auth protection (admin only, reject client tokens)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "alvaro@test.com"
ADMIN_PASSWORD = "Alvaro123"
CLIENT_EMAIL = "clientedemo@test.com"
CLIENT_PASSWORD = "demo123"


class TestAdminAuth:
    """Test admin authentication and token retrieval"""
    
    def test_admin_login_success(self):
        """Admin can login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert data.get("user", {}).get("role") in ["admin", "trainer"], f"User role is not admin: {data}"
        print(f"✅ Admin login success, role: {data.get('user', {}).get('role')}")
    
    def test_client_login_success(self):
        """Client can login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert response.status_code == 200, f"Client login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert data.get("user", {}).get("role") == "client", f"User role is not client: {data}"
        print(f"✅ Client login success, role: {data.get('user', {}).get('role')}")


@pytest.fixture
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.text}")
    return response.json().get("access_token")


@pytest.fixture
def client_token():
    """Get client auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLIENT_EMAIL,
        "password": CLIENT_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Client login failed: {response.text}")
    return response.json().get("access_token")


class TestDashboardStatsEndpoint:
    """Tests for GET /api/admin/dashboard-stats"""
    
    def test_dashboard_stats_returns_all_kpis(self, admin_token):
        """Dashboard stats returns total_clients, active_clients, at_risk_clients, inactive_clients, mrr, plans"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Dashboard stats failed: {response.text}"
        data = response.json()
        
        # Check all required fields exist
        required_fields = ["total_clients", "active_clients", "at_risk_clients", "inactive_clients", "mrr", "plans"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✅ Dashboard stats has all KPI fields: {list(data.keys())}")
    
    def test_dashboard_stats_plans_structure(self, admin_token):
        """Plans object has gold, silver, bronze, elm counts"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        plans = data.get("plans", {})
        required_plans = ["gold", "silver", "bronze", "elm"]
        for plan in required_plans:
            assert plan in plans, f"Missing plan: {plan}"
            assert isinstance(plans[plan], int), f"Plan {plan} count is not int: {plans[plan]}"
        
        print(f"✅ Plans structure correct: {plans}")
    
    def test_dashboard_stats_values_match_expected(self, admin_token):
        """Verify expected values: 4 total, 4 active, 0 risk, 0 bajas, 496€ MRR"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Based on context: 4 clients, 2 gold (149€), 2 silver (99€) = 496€ MRR
        assert data["total_clients"] == 4, f"Expected 4 total clients, got {data['total_clients']}"
        assert data["active_clients"] == 4, f"Expected 4 active clients, got {data['active_clients']}"
        assert data["at_risk_clients"] == 0, f"Expected 0 at-risk clients, got {data['at_risk_clients']}"
        # inactive_clients counts status in [inactivo, baja, cancelado]
        assert data["mrr"] == 496, f"Expected 496€ MRR, got {data['mrr']}"
        
        print(f"✅ Dashboard stats values match: total={data['total_clients']}, active={data['active_clients']}, mrr={data['mrr']}€")
    
    def test_dashboard_stats_plan_distribution(self, admin_token):
        """Verify plan distribution: Gold 2, Silver 2"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        plans = data.get("plans", {})
        assert plans.get("gold") == 2, f"Expected 2 gold, got {plans.get('gold')}"
        assert plans.get("silver") == 2, f"Expected 2 silver, got {plans.get('silver')}"
        
        print(f"✅ Plan distribution correct: gold={plans['gold']}, silver={plans['silver']}")
    
    def test_dashboard_stats_requires_admin_auth(self, client_token):
        """Client token should be rejected (401/403)"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard-stats",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403 for client token, got {response.status_code}"
        print(f"✅ Dashboard stats correctly rejects client token: {response.status_code}")
    
    def test_dashboard_stats_no_auth_rejected(self):
        """No auth should be rejected"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard-stats")
        assert response.status_code in [401, 403, 422], f"Expected auth error, got {response.status_code}"
        print(f"✅ Dashboard stats correctly rejects no auth: {response.status_code}")


class TestUpcomingPaymentsEndpoint:
    """Tests for GET /api/admin/upcoming-payments"""
    
    def test_upcoming_payments_returns_structure(self, admin_token):
        """Upcoming payments returns upcoming array with correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/admin/upcoming-payments",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Upcoming payments failed: {response.text}"
        data = response.json()
        
        assert "upcoming" in data, "Missing 'upcoming' field"
        assert "total" in data, "Missing 'total' field"
        assert isinstance(data["upcoming"], list), "upcoming should be a list"
        
        print(f"✅ Upcoming payments structure correct: {len(data['upcoming'])} items")
    
    def test_upcoming_payments_item_structure(self, admin_token):
        """Each upcoming item has name, plan, price, next_payment"""
        response = requests.get(
            f"{BASE_URL}/api/admin/upcoming-payments",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # If there are items, check structure
        if data["upcoming"]:
            item = data["upcoming"][0]
            required_fields = ["name", "plan", "price", "next_payment"]
            for field in required_fields:
                assert field in item, f"Missing field in upcoming item: {field}"
            print(f"✅ Upcoming item structure correct: {list(item.keys())}")
        else:
            # Based on context, next_payment dates are in the past, so 0 upcoming is expected
            print(f"✅ No upcoming payments (expected - dates in past)")
    
    def test_upcoming_payments_empty_expected(self, admin_token):
        """Based on context, should return 0 upcoming (dates in past)"""
        response = requests.get(
            f"{BASE_URL}/api/admin/upcoming-payments",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Context says: "No upcoming payments because next_payment dates are in the past"
        assert data["total"] == 0, f"Expected 0 upcoming, got {data['total']}"
        assert len(data["upcoming"]) == 0, f"Expected empty upcoming list"
        
        print(f"✅ Upcoming payments correctly returns 0 (dates in past)")
    
    def test_upcoming_payments_requires_admin_auth(self, client_token):
        """Client token should be rejected"""
        response = requests.get(
            f"{BASE_URL}/api/admin/upcoming-payments",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403 for client token, got {response.status_code}"
        print(f"✅ Upcoming payments correctly rejects client token: {response.status_code}")


class TestLegacyDashboardEndpoint:
    """Tests for GET /api/admin/dashboard (legacy backwards compatibility)"""
    
    def test_legacy_dashboard_still_works(self, admin_token):
        """Legacy dashboard endpoint returns data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Legacy dashboard failed: {response.text}"
        data = response.json()
        
        # Should have basic fields
        assert "total_clients" in data, "Missing total_clients"
        assert "active_clients" in data, "Missing active_clients"
        assert "plans" in data, "Missing plans"
        assert "mrr" in data, "Missing mrr"
        
        print(f"✅ Legacy dashboard works: total={data['total_clients']}, mrr={data['mrr']}")
    
    def test_legacy_dashboard_has_clients_by_plan(self, admin_token):
        """Legacy dashboard has clients_by_plan for backwards compatibility"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Legacy endpoint should have clients_by_plan alias
        assert "clients_by_plan" in data, "Missing clients_by_plan (backwards compat)"
        
        print(f"✅ Legacy dashboard has clients_by_plan: {data['clients_by_plan']}")


class TestAdminClientsEndpoint:
    """Tests for GET /api/admin/clients (used by dashboard)"""
    
    def test_admin_clients_returns_list(self, admin_token):
        """Admin clients returns list of clients with user data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/clients",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Admin clients failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Should return a list"
        assert len(data) == 4, f"Expected 4 clients, got {len(data)}"
        
        # Check first client has required fields
        if data:
            client = data[0]
            assert "id" in client, "Missing client id"
            assert "user" in client, "Missing user data"
            assert "plan" in client, "Missing plan"
            assert "status" in client, "Missing status"
        
        print(f"✅ Admin clients returns {len(data)} clients with correct structure")
    
    def test_admin_clients_has_user_details(self, admin_token):
        """Each client has user object with name and email"""
        response = requests.get(
            f"{BASE_URL}/api/admin/clients",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        for client in data:
            user = client.get("user", {})
            assert "name" in user, f"Missing user name for client {client.get('id')}"
            assert "email" in user, f"Missing user email for client {client.get('id')}"
        
        print(f"✅ All clients have user name and email")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
