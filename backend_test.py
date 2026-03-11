#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime
from typing import Optional, Dict, Any

class FitnessAPITester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client_token = None
        self.admin_token = None
        self.test_client_id = None
        self.test_profile_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None, 
                 use_admin_token: bool = False) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint.lstrip('/')}"
        test_headers = {'Content-Type': 'application/json'}
        
        # Add auth token if available
        if use_admin_token and self.admin_token:
            test_headers['Authorization'] = f'Bearer {self.admin_token}'
        elif self.client_token and not use_admin_token:
            test_headers['Authorization'] = f'Bearer {self.client_token}'
            
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                self.failed_tests.append({
                    'test': name,
                    'expected': expected_status,
                    'actual': response.status_code,
                    'response': response.text[:500]
                })
                try:
                    return False, response.json() if response.content else {}
                except:
                    return False, {'error': response.text}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({
                'test': name,
                'error': str(e)
            })
            return False, {}

    def test_api_health(self):
        """Test API is running"""
        return self.run_test("API Health Check", "GET", "/", 200)

    def test_get_plans(self):
        """Test get available plans"""
        return self.run_test("Get Plans", "GET", "/plans", 200)

    def test_user_registration(self):
        """Test user registration flow"""
        test_data = {
            "email": f"testuser_{datetime.now().strftime('%H%M%S')}@test.com",
            "password": "test123456",
            "name": "Test User",
            "phone": "+34600123456"
        }
        
        success, response = self.run_test("User Registration", "POST", "/auth/register", 200, test_data)
        if success and response.get('access_token'):
            self.client_token = response['access_token']
            self.test_client_id = response['user']['id']
            print(f"   User ID: {self.test_client_id}")
        return success, response

    def test_user_login_valid(self):
        """Test user login with valid credentials"""
        login_data = {
            "email": "cliente@test.com",
            "password": "test123"
        }
        
        success, response = self.run_test("User Login (Valid)", "POST", "/auth/login", 200, login_data)
        if success and response.get('access_token'):
            self.client_token = response['access_token']
        return success, response

    def test_user_login_invalid(self):
        """Test user login with invalid credentials"""
        login_data = {
            "email": "invalid@test.com",
            "password": "wrongpassword"
        }
        return self.run_test("User Login (Invalid)", "POST", "/auth/login", 401, login_data)

    def test_admin_login(self):
        """Test admin login"""
        admin_data = {
            "email": "admin@12en12.com",
            "password": "admin123"
        }
        
        success, response = self.run_test("Admin Login", "POST", "/auth/login", 200, admin_data)
        if success and response.get('access_token'):
            self.admin_token = response['access_token']
            print(f"   Admin logged in successfully")
        return success, response

    def test_get_user_profile(self):
        """Test get current user profile"""
        return self.run_test("Get User Profile", "GET", "/auth/me", 200)

    def test_create_client_profile(self):
        """Test create client profile with plan selection"""
        profile_data = {
            "plan": "silver",
            "price": 99
        }
        
        success, response = self.run_test("Create Client Profile", "POST", "/clients/profile", 200, profile_data)
        if success and response.get('id'):
            self.test_profile_id = response['id']
            print(f"   Profile ID: {self.test_profile_id}")
        return success, response

    def test_get_client_profile(self):
        """Test get client profile"""
        return self.run_test("Get Client Profile", "GET", "/clients/profile", 200)

    def test_update_client_profile(self):
        """Test update client profile"""
        update_data = {
            "weight": 75.5,
            "height": 180,
            "age": 30,
            "sex": "male",
            "goal": "muscle_gain",
            "training_days": 4
        }
        return self.run_test("Update Client Profile", "PUT", "/clients/profile", 200, update_data)

    def test_get_macros(self):
        """Test get macros"""
        return self.run_test("Get Macros", "GET", "/macros", 200)

    def test_update_macros(self):
        """Test update macros"""
        macros_data = {
            "training": {
                "protein": 150,
                "carbs": 200,
                "fat": 70
            },
            "rest": {
                "protein": 130,
                "carbs": 150,
                "fat": 65
            },
            "note": "Macros for muscle gain"
        }
        return self.run_test("Update Macros", "PUT", "/macros", 200, macros_data)

    def test_get_foods(self):
        """Test get foods for calculator"""
        return self.run_test("Get Foods", "GET", "/calculator/foods", 200)

    def test_calculate_meal(self):
        """Test calculate meal macros"""
        meal_data = [
            {"calories": 165, "protein": 31, "carbs": 0, "fat": 3.6, "quantity": 150},  # 150g chicken
            {"calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3, "quantity": 100}  # 100g rice
        ]
        return self.run_test("Calculate Meal", "POST", "/calculator/meal", 200, meal_data)

    def test_get_current_routine(self):
        """Test get current routine"""
        return self.run_test("Get Current Routine", "GET", "/routines/current", 200)

    def test_create_report(self):
        """Test create client report"""
        report_data = {
            "weight": 76.2,
            "measurements": {
                "chest": 100,
                "waist": 85,
                "arms": 38
            },
            "training_compliance": 90,
            "nutrition_compliance": 85,
            "sleep_quality": 8,
            "energy_level": 7,
            "stress_level": 3,
            "notes": "Great progress this week!"
        }
        return self.run_test("Create Report", "POST", "/reports", 200, report_data)

    def test_get_reports(self):
        """Test get reports"""
        return self.run_test("Get Reports", "GET", "/reports", 200)

    def test_send_message(self):
        """Test send message"""
        if not self.admin_token:
            print("   Skipping - Admin token not available")
            return True, {}
            
        message_data = {
            "receiver_id": "admin_user_id",
            "content": "Hello, this is a test message from client"
        }
        return self.run_test("Send Message", "POST", "/messages", 200, message_data)

    def test_get_messages(self):
        """Test get messages"""
        return self.run_test("Get Messages", "GET", "/messages", 200)

    def test_admin_dashboard_stats(self):
        """Test admin dashboard stats"""
        return self.run_test("Admin Dashboard Stats", "GET", "/admin/dashboard", 200, use_admin_token=True)

    def test_admin_get_clients(self):
        """Test admin get clients"""
        return self.run_test("Admin Get Clients", "GET", "/admin/clients", 200, use_admin_token=True)

    def test_admin_client_detail(self):
        """Test admin get client detail"""
        if not self.test_profile_id:
            print("   Skipping - No test profile ID available")
            return True, {}
        return self.run_test("Admin Client Detail", "GET", f"/admin/clients/{self.test_profile_id}", 200, use_admin_token=True)

    def test_generate_ai_routine(self):
        """Test AI routine generation"""
        if not self.test_profile_id:
            print("   Skipping - No test profile ID available")
            return True, {}
            
        routine_data = {
            "client_id": self.test_profile_id,
            "instructions": "Create a muscle building routine for intermediate level"
        }
        return self.run_test("Generate AI Routine", "POST", "/admin/routines/generate", 200, routine_data, use_admin_token=True)

    def test_simulate_payment(self):
        """Test payment simulation"""
        return self.run_test("Simulate Payment", "POST", "/payments/simulate?amount=99", 200)

    def run_all_tests(self):
        """Run comprehensive API tests"""
        print("=" * 60)
        print("🧪 Starting 12EN12 Fitness Platform API Tests")
        print("=" * 60)
        
        # Health check
        self.test_api_health()
        self.test_get_plans()
        
        # Authentication tests
        self.test_user_registration()
        self.test_user_login_valid()
        self.test_user_login_invalid()
        self.test_admin_login()
        
        # User profile tests
        if self.client_token:
            self.test_get_user_profile()
            self.test_create_client_profile()
            self.test_get_client_profile()
            self.test_update_client_profile()
        
        # Nutrition tests
        if self.client_token:
            self.test_get_macros()
            self.test_update_macros()
            self.test_get_foods()
            self.test_calculate_meal()
        
        # Routine tests
        if self.client_token:
            self.test_get_current_routine()
        
        # Report tests
        if self.client_token:
            self.test_create_report()
            self.test_get_reports()
        
        # Message tests
        if self.client_token:
            self.test_send_message()
            self.test_get_messages()
        
        # Payment tests
        if self.client_token:
            self.test_simulate_payment()
        
        # Admin tests
        if self.admin_token:
            self.test_admin_dashboard_stats()
            self.test_admin_get_clients()
            self.test_admin_client_detail()
            self.test_generate_ai_routine()
        
        # Print results
        print("\n" + "=" * 60)
        print("📊 Test Results Summary")
        print("=" * 60)
        print(f"Total tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for i, test in enumerate(self.failed_tests, 1):
                print(f"{i}. {test.get('test', 'Unknown')}")
                if 'expected' in test:
                    print(f"   Expected: {test['expected']}, Got: {test['actual']}")
                if 'error' in test:
                    print(f"   Error: {test['error']}")
                print()
        
        return self.tests_passed == self.tests_run

def main():
    """Main test execution"""
    base_url = "https://nutrition-hub-136.preview.emergentagent.com"
    
    tester = FitnessAPITester(base_url)
    
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n💥 Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())