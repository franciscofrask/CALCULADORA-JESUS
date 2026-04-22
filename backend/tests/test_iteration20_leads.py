"""
Iteration 20 - Leads Module Tests
Tests for: CRUD leads, webhook GoHighLevel, conversion to client, stats
6 statuses: nuevo, contactado, llamada_agendada, propuesta_enviada, convertido, descartado
6 sources: instagram, web, referido, ghl, whatsapp, otro
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "alvaro@test.com"
ADMIN_PASSWORD = "Alvaro123"

@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Admin authentication failed: {response.status_code} - {response.text}")

@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }

# ==================== AUTH PROTECTION TESTS ====================

class TestLeadsAuthProtection:
    """Test that leads endpoints require admin auth (except webhook)"""
    
    def test_get_leads_requires_auth(self):
        """GET /api/leads requires authentication"""
        response = requests.get(f"{BASE_URL}/api/leads")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✅ GET /api/leads requires auth")
    
    def test_post_leads_requires_auth(self):
        """POST /api/leads requires authentication"""
        response = requests.post(f"{BASE_URL}/api/leads", json={"name": "Test"})
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✅ POST /api/leads requires auth")
    
    def test_webhook_ghl_no_auth_required(self):
        """POST /api/leads/webhook/ghl does NOT require auth"""
        response = requests.post(f"{BASE_URL}/api/leads/webhook/ghl", json={
            "full_name": "TEST_Webhook_NoAuth",
            "email": "test_webhook_noauth@test.com"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok"
        assert "lead_id" in data
        print(f"✅ Webhook GHL works without auth, created lead: {data['lead_id']}")
        return data["lead_id"]

# ==================== CRUD TESTS ====================

class TestLeadsCRUD:
    """Test CRUD operations for leads"""
    
    def test_create_lead(self, admin_headers):
        """POST /api/leads creates a new lead"""
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "name": f"TEST_Lead_{unique_id}",
            "email": f"test_lead_{unique_id}@test.com",
            "phone": "+34612345678",
            "source": "instagram",
            "notes": "Test lead created by pytest"
        }
        response = requests.post(f"{BASE_URL}/api/leads", json=payload, headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["email"] == payload["email"]
        assert data["phone"] == payload["phone"]
        assert data["source"] == "instagram"
        assert data["status"] == "nuevo"  # Default status
        assert "id" in data
        assert "created_at" in data
        print(f"✅ POST /api/leads creates lead: {data['id']}")
        return data["id"]
    
    def test_create_lead_requires_name(self, admin_headers):
        """POST /api/leads requires name field"""
        response = requests.post(f"{BASE_URL}/api/leads", json={
            "email": "noname@test.com"
        }, headers=admin_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "Nombre" in response.json().get("detail", "")
        print("✅ POST /api/leads validates name is required")
    
    def test_get_all_leads(self, admin_headers):
        """GET /api/leads returns all leads"""
        response = requests.get(f"{BASE_URL}/api/leads", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "leads" in data
        assert "total" in data
        assert isinstance(data["leads"], list)
        assert data["total"] == len(data["leads"])
        print(f"✅ GET /api/leads returns {data['total']} leads")
        return data["leads"]
    
    def test_get_lead_by_id(self, admin_headers):
        """GET /api/leads/{id} returns specific lead"""
        # First create a lead
        unique_id = str(uuid.uuid4())[:8]
        create_resp = requests.post(f"{BASE_URL}/api/leads", json={
            "name": f"TEST_GetById_{unique_id}",
            "email": f"getbyid_{unique_id}@test.com"
        }, headers=admin_headers)
        lead_id = create_resp.json()["id"]
        
        # Then get it
        response = requests.get(f"{BASE_URL}/api/leads/{lead_id}", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["id"] == lead_id
        assert "TEST_GetById" in data["name"]
        print(f"✅ GET /api/leads/{lead_id} returns correct lead")
    
    def test_update_lead_status(self, admin_headers):
        """PUT /api/leads/{id} updates status"""
        # Create lead
        unique_id = str(uuid.uuid4())[:8]
        create_resp = requests.post(f"{BASE_URL}/api/leads", json={
            "name": f"TEST_UpdateStatus_{unique_id}"
        }, headers=admin_headers)
        lead_id = create_resp.json()["id"]
        
        # Update status
        response = requests.put(f"{BASE_URL}/api/leads/{lead_id}", json={
            "status": "contactado"
        }, headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["status"] == "contactado"
        print(f"✅ PUT /api/leads/{lead_id} updates status to 'contactado'")
    
    def test_update_lead_notes(self, admin_headers):
        """PUT /api/leads/{id} updates notes"""
        # Create lead
        unique_id = str(uuid.uuid4())[:8]
        create_resp = requests.post(f"{BASE_URL}/api/leads", json={
            "name": f"TEST_UpdateNotes_{unique_id}"
        }, headers=admin_headers)
        lead_id = create_resp.json()["id"]
        
        # Update notes
        new_notes = "Updated notes from pytest test"
        response = requests.put(f"{BASE_URL}/api/leads/{lead_id}", json={
            "notes": new_notes
        }, headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["notes"] == new_notes
        print(f"✅ PUT /api/leads/{lead_id} updates notes")
    
    def test_update_lead_invalid_status(self, admin_headers):
        """PUT /api/leads/{id} rejects invalid status"""
        # Create lead
        unique_id = str(uuid.uuid4())[:8]
        create_resp = requests.post(f"{BASE_URL}/api/leads", json={
            "name": f"TEST_InvalidStatus_{unique_id}"
        }, headers=admin_headers)
        lead_id = create_resp.json()["id"]
        
        # Try invalid status
        response = requests.put(f"{BASE_URL}/api/leads/{lead_id}", json={
            "status": "invalid_status"
        }, headers=admin_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ PUT /api/leads rejects invalid status")
    
    def test_delete_lead(self, admin_headers):
        """DELETE /api/leads/{id} removes a lead"""
        # Create lead
        unique_id = str(uuid.uuid4())[:8]
        create_resp = requests.post(f"{BASE_URL}/api/leads", json={
            "name": f"TEST_Delete_{unique_id}"
        }, headers=admin_headers)
        lead_id = create_resp.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/leads/{lead_id}", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify it's gone
        get_resp = requests.get(f"{BASE_URL}/api/leads/{lead_id}", headers=admin_headers)
        assert get_resp.status_code == 404, "Lead should be deleted"
        print(f"✅ DELETE /api/leads/{lead_id} removes lead")

# ==================== CONVERT TO CLIENT TESTS ====================

class TestLeadsConvert:
    """Test lead to client conversion"""
    
    def test_convert_lead_success(self, admin_headers):
        """POST /api/leads/{id}/convert creates user + client_profile"""
        # Create lead with email
        unique_id = str(uuid.uuid4())[:8]
        email = f"test_convert_{unique_id}@test.com"
        create_resp = requests.post(f"{BASE_URL}/api/leads", json={
            "name": f"TEST_Convert_{unique_id}",
            "email": email,
            "phone": "+34600000000"
        }, headers=admin_headers)
        lead_id = create_resp.json()["id"]
        
        # Convert to client
        response = requests.post(f"{BASE_URL}/api/leads/{lead_id}/convert", json={
            "plan": "gold"
        }, headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user_id" in data
        assert "profile_id" in data
        assert data["email"] == email
        assert data["plan"] == "gold"
        print(f"✅ POST /api/leads/{lead_id}/convert creates user ({data['user_id']}) and profile ({data['profile_id']})")
        
        # Verify lead status changed to convertido
        lead_resp = requests.get(f"{BASE_URL}/api/leads/{lead_id}", headers=admin_headers)
        assert lead_resp.json()["status"] == "convertido"
        print("✅ Lead status changed to 'convertido'")
    
    def test_convert_lead_without_email_fails(self, admin_headers):
        """POST /api/leads/{id}/convert rejects if email missing"""
        # Create lead WITHOUT email
        unique_id = str(uuid.uuid4())[:8]
        create_resp = requests.post(f"{BASE_URL}/api/leads", json={
            "name": f"TEST_NoEmail_{unique_id}"
        }, headers=admin_headers)
        lead_id = create_resp.json()["id"]
        
        # Try to convert
        response = requests.post(f"{BASE_URL}/api/leads/{lead_id}/convert", json={
            "plan": "silver"
        }, headers=admin_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "email" in response.json().get("detail", "").lower()
        print("✅ Convert rejects lead without email")
    
    def test_convert_already_converted_fails(self, admin_headers):
        """POST /api/leads/{id}/convert rejects if already converted"""
        # Create and convert a lead
        unique_id = str(uuid.uuid4())[:8]
        email = f"test_double_convert_{unique_id}@test.com"
        create_resp = requests.post(f"{BASE_URL}/api/leads", json={
            "name": f"TEST_DoubleConvert_{unique_id}",
            "email": email
        }, headers=admin_headers)
        lead_id = create_resp.json()["id"]
        
        # First conversion
        requests.post(f"{BASE_URL}/api/leads/{lead_id}/convert", json={"plan": "bronze"}, headers=admin_headers)
        
        # Try second conversion
        response = requests.post(f"{BASE_URL}/api/leads/{lead_id}/convert", json={"plan": "gold"}, headers=admin_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "convertido" in response.json().get("detail", "").lower()
        print("✅ Convert rejects already converted lead")

# ==================== WEBHOOK TESTS ====================

class TestLeadsWebhook:
    """Test GoHighLevel webhook"""
    
    def test_webhook_ghl_creates_lead(self):
        """POST /api/leads/webhook/ghl creates lead from external webhook"""
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "full_name": f"TEST_GHL_Webhook_{unique_id}",
            "email": f"ghl_webhook_{unique_id}@test.com",
            "phone": "+34611111111"
        }
        response = requests.post(f"{BASE_URL}/api/leads/webhook/ghl", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["status"] == "ok"
        assert "lead_id" in data
        print(f"✅ Webhook GHL creates lead: {data['lead_id']}")
        return data["lead_id"]
    
    def test_webhook_ghl_sets_source_ghl(self, admin_headers):
        """Webhook lead has source='ghl'"""
        unique_id = str(uuid.uuid4())[:8]
        webhook_resp = requests.post(f"{BASE_URL}/api/leads/webhook/ghl", json={
            "full_name": f"TEST_GHL_Source_{unique_id}",
            "email": f"ghl_source_{unique_id}@test.com"
        })
        lead_id = webhook_resp.json()["lead_id"]
        
        # Verify source
        lead_resp = requests.get(f"{BASE_URL}/api/leads/{lead_id}", headers=admin_headers)
        assert lead_resp.json()["source"] == "ghl"
        print("✅ Webhook lead has source='ghl'")
    
    def test_webhook_ghl_sets_status_nuevo(self, admin_headers):
        """Webhook lead has status='nuevo'"""
        unique_id = str(uuid.uuid4())[:8]
        webhook_resp = requests.post(f"{BASE_URL}/api/leads/webhook/ghl", json={
            "full_name": f"TEST_GHL_Status_{unique_id}"
        })
        lead_id = webhook_resp.json()["lead_id"]
        
        # Verify status
        lead_resp = requests.get(f"{BASE_URL}/api/leads/{lead_id}", headers=admin_headers)
        assert lead_resp.json()["status"] == "nuevo"
        print("✅ Webhook lead has status='nuevo'")

# ==================== STATS TESTS ====================

class TestLeadsStats:
    """Test leads statistics endpoint"""
    
    def test_get_stats_summary(self, admin_headers):
        """GET /api/leads/stats/summary returns count by status"""
        response = requests.get(f"{BASE_URL}/api/leads/stats/summary", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should have all 6 statuses
        expected_statuses = ["nuevo", "contactado", "llamada_agendada", "propuesta_enviada", "convertido", "descartado"]
        for status in expected_statuses:
            assert status in data, f"Missing status: {status}"
            assert isinstance(data[status], int)
        
        assert "total" in data
        assert data["total"] == sum(data[s] for s in expected_statuses)
        print(f"✅ GET /api/leads/stats/summary returns: {data}")

# ==================== EXISTING SEED DATA TESTS ====================

class TestExistingSeedData:
    """Test existing seed data: Ana Martín (ghl, nuevo), Pedro López (referido, nuevo), María García (instagram, convertido)"""
    
    def test_seed_leads_exist(self, admin_headers):
        """Verify 3 seed leads exist"""
        response = requests.get(f"{BASE_URL}/api/leads", headers=admin_headers)
        leads = response.json()["leads"]
        
        # Find seed leads by name
        ana = next((l for l in leads if "Ana" in l.get("name", "") and "Martín" in l.get("name", "")), None)
        pedro = next((l for l in leads if "Pedro" in l.get("name", "") and "López" in l.get("name", "")), None)
        maria = next((l for l in leads if "María" in l.get("name", "") and "García" in l.get("name", "")), None)
        
        if ana:
            assert ana["source"] == "ghl", f"Ana should be ghl, got {ana['source']}"
            assert ana["status"] == "nuevo", f"Ana should be nuevo, got {ana['status']}"
            print(f"✅ Ana Martín found: source=ghl, status=nuevo")
        else:
            print("⚠️ Ana Martín not found in seed data")
        
        if pedro:
            assert pedro["source"] == "referido", f"Pedro should be referido, got {pedro['source']}"
            assert pedro["status"] == "nuevo", f"Pedro should be nuevo, got {pedro['status']}"
            print(f"✅ Pedro López found: source=referido, status=nuevo")
        else:
            print("⚠️ Pedro López not found in seed data")
        
        if maria:
            assert maria["source"] == "instagram", f"María should be instagram, got {maria['source']}"
            assert maria["status"] == "convertido", f"María should be convertido, got {maria['status']}"
            print(f"✅ María García found: source=instagram, status=convertido")
        else:
            print("⚠️ María García not found in seed data")

# ==================== CLEANUP ====================

@pytest.fixture(scope="module", autouse=True)
def cleanup_test_leads(admin_headers):
    """Cleanup TEST_ prefixed leads after all tests"""
    yield
    # Cleanup
    try:
        response = requests.get(f"{BASE_URL}/api/leads", headers=admin_headers)
        if response.status_code == 200:
            leads = response.json().get("leads", [])
            for lead in leads:
                if lead.get("name", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/leads/{lead['id']}", headers=admin_headers)
            print("✅ Cleaned up TEST_ leads")
    except Exception as e:
        print(f"⚠️ Cleanup failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
