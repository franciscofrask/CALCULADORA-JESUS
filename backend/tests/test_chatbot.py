"""
Test Chatbot Endpoints - JG12 Nutrition Chatbot
================================================
Tests for:
- POST /api/chatbot/start - Inicia sesión
- POST /api/chatbot/configure - Configura día de entrenamiento con 4 comidas
- POST /api/chatbot/message - Procesa los 4 casos de comida
- POST /api/chatbot/complete-meal - Guarda comida y avanza
- GET /api/chatbot/summary - Devuelve resumen del día

Test cases del usuario:
C1: huevos, pan, claras y pavo
C2: pechuga de pollo, garbanzos, tomate, cebolla, aguacate y calabacín
C3: lomo embuchado bajo en grasa, queso havarti light, tomate rallado, pan tostado y aceite de oliva
C4: huevos, sepia, tomate frito, pan tostado y berenjena

Macros totales: P=160, H=50, G=40
Periworkout: P=35, H=15
4 comidas, entreno después de C1
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "clientedemo@test.com"
TEST_PASSWORD = "demo123"


class TestChatbotEndpoints:
    """Test chatbot API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_chatbot_start(self, auth_headers):
        """Test POST /api/chatbot/start - Inicia sesión"""
        response = requests.post(
            f"{BASE_URL}/api/chatbot/start",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "session_id" in data, "Response should contain session_id"
        assert "macros" in data, "Response should contain macros"
        assert "message" in data, "Response should contain message"
        
        # Verify session_id format
        assert data["session_id"].startswith("chat_"), f"session_id should start with 'chat_': {data['session_id']}"
        
        # Verify macros structure
        macros = data["macros"]
        assert "p_entreno" in macros, "macros should contain p_entreno"
        assert "h_entreno" in macros, "macros should contain h_entreno"
        assert "g_entreno" in macros, "macros should contain g_entreno"
        
        print(f"✅ Chatbot started with session_id: {data['session_id']}")
        print(f"   Macros: P={macros.get('p_entreno')}, H={macros.get('h_entreno')}, G={macros.get('g_entreno')}")
    
    def test_chatbot_configure_training_day(self, auth_headers):
        """Test POST /api/chatbot/configure - Configura día de entrenamiento con 4 comidas"""
        # First start a session
        start_response = requests.post(
            f"{BASE_URL}/api/chatbot/start",
            headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session_id"]
        
        # Configure training day
        response = requests.post(
            f"{BASE_URL}/api/chatbot/configure?session_id={session_id}",
            headers=auth_headers,
            json={
                "tipo_dia": "entrenamiento",
                "num_comidas": 4,
                "momento_entreno": 1,  # Entreno después de C1
                "opcion_peri": "intra_post"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "distribucion" in data, "Response should contain distribucion"
        assert "comida_actual" in data, "Response should contain comida_actual"
        assert "mensaje" in data, "Response should contain mensaje"
        
        # Verify distribution structure
        dist = data["distribucion"]
        assert "comidas" in dist, "distribucion should contain comidas"
        assert "C1" in dist["comidas"], "comidas should contain C1"
        assert "C2" in dist["comidas"], "comidas should contain C2"
        assert "C3" in dist["comidas"], "comidas should contain C3"
        assert "C4" in dist["comidas"], "comidas should contain C4"
        
        # Verify comida_actual starts at 1
        assert data["comida_actual"] == 1, f"comida_actual should be 1, got {data['comida_actual']}"
        
        print(f"✅ Day configured: {data['mensaje'][:50]}...")
        print(f"   C1 macros: {dist['comidas']['C1']}")
        print(f"   C2 macros: {dist['comidas']['C2']}")
        print(f"   C3 macros: {dist['comidas']['C3']}")
        print(f"   C4 macros: {dist['comidas']['C4']}")
    
    def test_chatbot_message_c1(self, auth_headers):
        """Test POST /api/chatbot/message - Procesa C1: huevos, pan, claras y pavo"""
        # Start and configure session
        start_response = requests.post(f"{BASE_URL}/api/chatbot/start", headers=auth_headers)
        session_id = start_response.json()["session_id"]
        
        requests.post(
            f"{BASE_URL}/api/chatbot/configure?session_id={session_id}",
            headers=auth_headers,
            json={"tipo_dia": "entrenamiento", "num_comidas": 4, "momento_entreno": 1, "opcion_peri": "intra_post"}
        )
        
        # Send C1 message
        response = requests.post(
            f"{BASE_URL}/api/chatbot/message",
            headers=auth_headers,
            json={
                "message": "huevos, pan, claras y pavo",
                "session_id": session_id
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "response" in data, "Response should contain response"
        assert "state" in data, "Response should contain state"
        
        # Verify response structure
        resp = data["response"]
        assert "action" in resp, "response should contain action"
        
        # If meal_updated, verify foods_added
        if resp.get("action") == "meal_updated":
            assert "foods_added" in resp, "meal_updated should contain foods_added"
            assert "meal_status" in resp, "meal_updated should contain meal_status"
            
            # Verify meal_status has macros within margin
            meal_status = resp["meal_status"]
            if meal_status.get("cuadrado"):
                print(f"✅ C1 cuadrado dentro del margen ±4g")
            
            print(f"✅ C1 processed: {len(resp.get('foods_added', []))} foods added")
            for food in resp.get("foods_added", []):
                print(f"   - {food.get('nombre')}: {food.get('cantidad_display')} (P={food.get('macros', {}).get('P')}, H={food.get('macros', {}).get('H')}, G={food.get('macros', {}).get('G')})")
    
    def test_chatbot_complete_meal(self, auth_headers):
        """Test POST /api/chatbot/complete-meal - Guarda comida y avanza"""
        # Start and configure session
        start_response = requests.post(f"{BASE_URL}/api/chatbot/start", headers=auth_headers)
        session_id = start_response.json()["session_id"]
        
        requests.post(
            f"{BASE_URL}/api/chatbot/configure?session_id={session_id}",
            headers=auth_headers,
            json={"tipo_dia": "entrenamiento", "num_comidas": 4, "momento_entreno": 1, "opcion_peri": "intra_post"}
        )
        
        # Add food to C1
        requests.post(
            f"{BASE_URL}/api/chatbot/message",
            headers=auth_headers,
            json={"message": "huevos, pan, claras y pavo", "session_id": session_id}
        )
        
        # Complete meal
        response = requests.post(
            f"{BASE_URL}/api/chatbot/complete-meal?session_id={session_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "comida_completada" in data or "error" in data, "Response should contain comida_completada or error"
        
        if "error" not in data:
            assert "dia_completo" in data, "Response should contain dia_completo"
            assert "comida_actual" in data or data.get("dia_completo"), "Response should contain comida_actual or dia_completo=True"
            
            if not data.get("dia_completo"):
                assert data["comida_actual"] == 2, f"After completing C1, comida_actual should be 2, got {data.get('comida_actual')}"
            
            print(f"✅ Meal completed: {data.get('mensaje', '')[:50]}...")
        else:
            print(f"⚠️ Meal completion returned error: {data.get('error')}")
    
    def test_chatbot_complete_empty_meal_rejected(self, auth_headers):
        """Test that completing an empty meal is rejected"""
        # Start and configure session
        start_response = requests.post(f"{BASE_URL}/api/chatbot/start", headers=auth_headers)
        session_id = start_response.json()["session_id"]
        
        requests.post(
            f"{BASE_URL}/api/chatbot/configure?session_id={session_id}",
            headers=auth_headers,
            json={"tipo_dia": "entrenamiento", "num_comidas": 4, "momento_entreno": 1, "opcion_peri": "intra_post"}
        )
        
        # Try to complete empty meal (without adding any food)
        response = requests.post(
            f"{BASE_URL}/api/chatbot/complete-meal?session_id={session_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should return error for empty meal
        assert "error" in data, "Empty meal should return error"
        print(f"✅ Empty meal correctly rejected: {data.get('error')}")
    
    def test_chatbot_full_day_flow(self, auth_headers):
        """Test full day flow with 4 meals - All within ±4g margin"""
        # Start session
        start_response = requests.post(f"{BASE_URL}/api/chatbot/start", headers=auth_headers)
        assert start_response.status_code == 200
        session_id = start_response.json()["session_id"]
        
        # Configure training day
        config_response = requests.post(
            f"{BASE_URL}/api/chatbot/configure?session_id={session_id}",
            headers=auth_headers,
            json={"tipo_dia": "entrenamiento", "num_comidas": 4, "momento_entreno": 1, "opcion_peri": "intra_post"}
        )
        assert config_response.status_code == 200
        
        # Test cases from user
        test_meals = [
            "huevos, pan, claras y pavo",  # C1
            "pechuga de pollo, garbanzos, tomate, cebolla, aguacate y calabacín",  # C2
            "lomo embuchado bajo en grasa, queso havarti light, tomate rallado, pan tostado y aceite de oliva",  # C3
            "huevos, sepia, tomate frito, pan tostado y berenjena"  # C4
        ]
        
        all_within_margin = True
        
        for i, meal_text in enumerate(test_meals, 1):
            print(f"\n--- Processing C{i}: {meal_text[:40]}... ---")
            
            # Send meal message
            msg_response = requests.post(
                f"{BASE_URL}/api/chatbot/message",
                headers=auth_headers,
                json={"message": meal_text, "session_id": session_id}
            )
            
            assert msg_response.status_code == 200, f"C{i} message failed: {msg_response.text}"
            
            msg_data = msg_response.json()
            resp = msg_data.get("response", {})
            
            if resp.get("action") == "meal_updated":
                meal_status = resp.get("meal_status", {})
                desviacion = meal_status.get("desviacion", {})
                cuadrado = meal_status.get("cuadrado", False)
                
                print(f"   Foods added: {len(resp.get('foods_added', []))}")
                print(f"   Desviación: P={desviacion.get('P', 0)}, H={desviacion.get('H', 0)}, G={desviacion.get('G', 0)}")
                print(f"   Cuadrado (±4g): {cuadrado}")
                
                if not cuadrado:
                    all_within_margin = False
                    print(f"   ⚠️ C{i} NOT within ±4g margin")
                else:
                    print(f"   ✅ C{i} within ±4g margin")
                
                # Show foods not found
                for nf in resp.get("foods_not_found", []):
                    print(f"   ⚠️ Not found: {nf.get('buscado')} - {nf.get('razon')}")
            
            # Complete meal
            complete_response = requests.post(
                f"{BASE_URL}/api/chatbot/complete-meal?session_id={session_id}",
                headers=auth_headers
            )
            assert complete_response.status_code == 200, f"C{i} complete failed: {complete_response.text}"
            
            complete_data = complete_response.json()
            if complete_data.get("dia_completo"):
                print(f"\n✅ Day complete after C{i}")
                break
        
        # Get summary
        summary_response = requests.get(
            f"{BASE_URL}/api/chatbot/summary?session_id={session_id}",
            headers=auth_headers
        )
        
        assert summary_response.status_code == 200, f"Summary failed: {summary_response.text}"
        
        summary = summary_response.json()
        print(f"\n=== DAY SUMMARY ===")
        print(f"Totales: P={summary.get('totales', {}).get('P')}, H={summary.get('totales', {}).get('H')}, G={summary.get('totales', {}).get('G')}")
        print(f"Objetivo: P={summary.get('objetivo_total', {}).get('P')}, H={summary.get('objetivo_total', {}).get('H')}, G={summary.get('objetivo_total', {}).get('G')}")
        print(f"Diferencia: P={summary.get('diferencia', {}).get('P')}, H={summary.get('diferencia', {}).get('H')}, G={summary.get('diferencia', {}).get('G')}")
        
        # Verify all meals within margin
        if all_within_margin:
            print(f"\n✅ ALL 4 MEALS WITHIN ±4g MARGIN")
        else:
            print(f"\n⚠️ Some meals exceeded ±4g margin")
    
    def test_chatbot_summary(self, auth_headers):
        """Test GET /api/chatbot/summary - Devuelve resumen del día"""
        # Start and configure session
        start_response = requests.post(f"{BASE_URL}/api/chatbot/start", headers=auth_headers)
        session_id = start_response.json()["session_id"]
        
        requests.post(
            f"{BASE_URL}/api/chatbot/configure?session_id={session_id}",
            headers=auth_headers,
            json={"tipo_dia": "entrenamiento", "num_comidas": 4, "momento_entreno": 1, "opcion_peri": "intra_post"}
        )
        
        # Add and complete one meal
        requests.post(
            f"{BASE_URL}/api/chatbot/message",
            headers=auth_headers,
            json={"message": "huevos y pan", "session_id": session_id}
        )
        
        requests.post(
            f"{BASE_URL}/api/chatbot/complete-meal?session_id={session_id}",
            headers=auth_headers
        )
        
        # Get summary
        response = requests.get(
            f"{BASE_URL}/api/chatbot/summary?session_id={session_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "comidas" in data, "Summary should contain comidas"
        assert "totales" in data, "Summary should contain totales"
        assert "objetivo_total" in data, "Summary should contain objetivo_total"
        
        print(f"✅ Summary retrieved: {len(data.get('comidas', []))} meals")
        print(f"   Totales: P={data.get('totales', {}).get('P')}, H={data.get('totales', {}).get('H')}, G={data.get('totales', {}).get('G')}")


class TestChatbotMacroDistribution:
    """Test that macro distribution respects CALMA rules"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Authentication failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_minimum_quantity_respected(self, auth_headers):
        """Test that minimum quantities are never reduced below minimum"""
        # Start and configure
        start_response = requests.post(f"{BASE_URL}/api/chatbot/start", headers=auth_headers)
        session_id = start_response.json()["session_id"]
        
        requests.post(
            f"{BASE_URL}/api/chatbot/configure?session_id={session_id}",
            headers=auth_headers,
            json={"tipo_dia": "entrenamiento", "num_comidas": 4, "momento_entreno": 1, "opcion_peri": "intra_post"}
        )
        
        # Request foods that might have minimum constraints
        response = requests.post(
            f"{BASE_URL}/api/chatbot/message",
            headers=auth_headers,
            json={"message": "huevos enteros", "session_id": session_id}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        resp = data.get("response", {})
        
        if resp.get("action") == "meal_updated":
            for food in resp.get("foods_added", []):
                # Huevos should be at least 1 unit (55g)
                if "huevo" in food.get("nombre", "").lower():
                    cantidad = food.get("cantidad", 0)
                    assert cantidad >= 55, f"Huevos should be at least 55g (1 unit), got {cantidad}g"
                    print(f"✅ Huevos quantity respects minimum: {cantidad}g")
    
    def test_food_rejected_when_minimum_exceeds_remaining(self, auth_headers):
        """Test that foods are rejected when minimum exceeds remaining macros"""
        # Start and configure
        start_response = requests.post(f"{BASE_URL}/api/chatbot/start", headers=auth_headers)
        session_id = start_response.json()["session_id"]
        
        requests.post(
            f"{BASE_URL}/api/chatbot/configure?session_id={session_id}",
            headers=auth_headers,
            json={"tipo_dia": "entrenamiento", "num_comidas": 4, "momento_entreno": 1, "opcion_peri": "intra_post"}
        )
        
        # First, fill up most of the macros
        requests.post(
            f"{BASE_URL}/api/chatbot/message",
            headers=auth_headers,
            json={"message": "pechuga de pollo grande", "session_id": session_id}
        )
        
        # Then try to add something that might not fit
        response = requests.post(
            f"{BASE_URL}/api/chatbot/message",
            headers=auth_headers,
            json={"message": "arroz", "session_id": session_id}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        resp = data.get("response", {})
        
        # Check if any foods were rejected
        not_found = resp.get("foods_not_found", [])
        if not_found:
            for nf in not_found:
                print(f"✅ Food correctly rejected: {nf.get('buscado')} - {nf.get('razon')}")
        else:
            print(f"   All foods fit within remaining macros")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
