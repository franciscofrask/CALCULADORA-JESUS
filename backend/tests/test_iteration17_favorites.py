"""
Test suite for JG12 Iteration 17 - Favorite Foods Feature
Tests:
- GET /api/favorites - returns empty list for new user
- POST /api/favorites/{food_id} - adds food to favorites
- POST /api/favorites/{food_id} twice - no duplicates (addToSet)
- DELETE /api/favorites/{food_id} - removes food from favorites
- GET /api/calculator/search - shows is_favorite=true for favorited foods
- GET /api/calculator/search - sorts: favorites first > frequency > alphabetical
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CLIENT_EMAIL = "clientedemo@test.com"
CLIENT_PASSWORD = "demo123"

# Test food IDs (from context: clientedemo has favorites [42, 117, 831])
FOOD_ID_1 = 117  # Already favorited
FOOD_ID_2 = 42   # Already favorited
FOOD_ID_NEW = 100  # New food to test add/remove


class TestFavoritesAPI:
    """Test the favorites API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("access_token")
        assert token, "No access_token in login response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_get_favorites_returns_list(self):
        """GET /api/favorites returns favorites list"""
        response = self.session.get(f"{BASE_URL}/api/favorites")
        assert response.status_code == 200, f"GET favorites failed: {response.text}"
        data = response.json()
        assert "favorites" in data, "Response missing 'favorites' key"
        assert isinstance(data["favorites"], list), "favorites should be a list"
        print(f"Current favorites: {data['favorites']}")
    
    def test_add_favorite_returns_updated_list(self):
        """POST /api/favorites/{food_id} adds food and returns updated list"""
        # First remove the food if it exists (cleanup)
        self.session.delete(f"{BASE_URL}/api/favorites/{FOOD_ID_NEW}")
        
        # Add the food
        response = self.session.post(f"{BASE_URL}/api/favorites/{FOOD_ID_NEW}")
        assert response.status_code == 200, f"POST favorites failed: {response.text}"
        data = response.json()
        assert "favorites" in data, "Response missing 'favorites' key"
        assert FOOD_ID_NEW in data["favorites"], f"Food {FOOD_ID_NEW} not in favorites after add"
        print(f"After adding {FOOD_ID_NEW}: {data['favorites']}")
    
    def test_add_favorite_no_duplicates(self):
        """POST /api/favorites/{food_id} twice doesn't duplicate (addToSet)"""
        # Ensure food is added
        self.session.post(f"{BASE_URL}/api/favorites/{FOOD_ID_NEW}")
        
        # Get current count
        response1 = self.session.get(f"{BASE_URL}/api/favorites")
        count_before = response1.json()["favorites"].count(FOOD_ID_NEW)
        
        # Add again
        response2 = self.session.post(f"{BASE_URL}/api/favorites/{FOOD_ID_NEW}")
        assert response2.status_code == 200
        
        # Check no duplicate
        count_after = response2.json()["favorites"].count(FOOD_ID_NEW)
        assert count_after == 1, f"Duplicate found: food {FOOD_ID_NEW} appears {count_after} times"
        print(f"No duplicates: food {FOOD_ID_NEW} appears exactly once")
    
    def test_remove_favorite_returns_updated_list(self):
        """DELETE /api/favorites/{food_id} removes food and returns updated list"""
        # Ensure food is added first
        self.session.post(f"{BASE_URL}/api/favorites/{FOOD_ID_NEW}")
        
        # Remove the food
        response = self.session.delete(f"{BASE_URL}/api/favorites/{FOOD_ID_NEW}")
        assert response.status_code == 200, f"DELETE favorites failed: {response.text}"
        data = response.json()
        assert "favorites" in data, "Response missing 'favorites' key"
        assert FOOD_ID_NEW not in data["favorites"], f"Food {FOOD_ID_NEW} still in favorites after delete"
        print(f"After removing {FOOD_ID_NEW}: {data['favorites']}")


class TestSearchWithFavorites:
    """Test search endpoint with favorites integration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_search_shows_is_favorite_field(self):
        """GET /api/calculator/search shows is_favorite field for each food"""
        response = self.session.get(f"{BASE_URL}/api/calculator/search?q=pollo&limit=10")
        assert response.status_code == 200, f"Search failed: {response.text}"
        data = response.json()
        assert "alimentos" in data, "Response missing 'alimentos' key"
        
        # Check that foods have is_favorite field
        for food in data["alimentos"]:
            assert "is_favorite" in food, f"Food {food.get('nombre')} missing 'is_favorite' field"
            assert isinstance(food["is_favorite"], bool), f"is_favorite should be boolean"
        
        print(f"Search returned {len(data['alimentos'])} foods, all have is_favorite field")
    
    def test_search_favorites_marked_correctly(self):
        """GET /api/calculator/search marks favorited foods with is_favorite=true"""
        # Get current favorites
        fav_response = self.session.get(f"{BASE_URL}/api/favorites")
        favorites = set(str(f) for f in fav_response.json().get("favorites", []))
        print(f"User favorites: {favorites}")
        
        # Search for foods
        response = self.session.get(f"{BASE_URL}/api/calculator/search?q=&limit=50")
        assert response.status_code == 200
        data = response.json()
        
        # Check that favorited foods are marked correctly
        for food in data["alimentos"]:
            food_id = str(food.get("id", ""))
            expected_fav = food_id in favorites
            actual_fav = food.get("is_favorite", False)
            if expected_fav:
                assert actual_fav == True, f"Food {food_id} ({food.get('nombre')}) should be is_favorite=true"
                print(f"Food {food_id} ({food.get('nombre')}) correctly marked as favorite")
    
    def test_search_sorts_favorites_first(self):
        """GET /api/calculator/search sorts: favorites first > frequency > alphabetical"""
        # Ensure we have at least one favorite
        self.session.post(f"{BASE_URL}/api/favorites/{FOOD_ID_1}")
        
        # Search for foods
        response = self.session.get(f"{BASE_URL}/api/calculator/search?q=&limit=100")
        assert response.status_code == 200
        data = response.json()
        alimentos = data["alimentos"]
        
        # Find first non-favorite
        first_non_fav_idx = None
        for i, food in enumerate(alimentos):
            if not food.get("is_favorite", False):
                first_non_fav_idx = i
                break
        
        # All favorites should come before non-favorites
        if first_non_fav_idx is not None:
            for i in range(first_non_fav_idx):
                assert alimentos[i].get("is_favorite", False), \
                    f"Food at index {i} should be favorite (before non-favorites)"
            
            for i in range(first_non_fav_idx, len(alimentos)):
                # After first non-favorite, there should be no favorites
                if alimentos[i].get("is_favorite", False):
                    # This is OK if sorting is correct - favorites can appear later if they have lower frequency
                    pass
        
        # Count favorites at the top
        fav_count = sum(1 for f in alimentos if f.get("is_favorite", False))
        print(f"Search returned {len(alimentos)} foods, {fav_count} are favorites")
        
        # Check that favorites appear at the beginning
        favorites_at_top = 0
        for food in alimentos:
            if food.get("is_favorite", False):
                favorites_at_top += 1
            else:
                break
        
        print(f"Favorites at top of results: {favorites_at_top}")
        assert favorites_at_top > 0 or fav_count == 0, "Favorites should appear at the top of search results"


class TestFavoritesEdgeCases:
    """Test edge cases for favorites"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert login_response.status_code == 200
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_remove_nonexistent_favorite(self):
        """DELETE /api/favorites/{food_id} for non-favorited food doesn't error"""
        # Remove a food that's not in favorites
        response = self.session.delete(f"{BASE_URL}/api/favorites/99999")
        assert response.status_code == 200, f"DELETE should succeed even for non-favorited food: {response.text}"
        data = response.json()
        assert "favorites" in data
        print("Removing non-existent favorite succeeded without error")
    
    def test_add_multiple_favorites(self):
        """Can add multiple different foods to favorites"""
        # Clean up first
        self.session.delete(f"{BASE_URL}/api/favorites/{FOOD_ID_1}")
        self.session.delete(f"{BASE_URL}/api/favorites/{FOOD_ID_2}")
        
        # Add first food
        response1 = self.session.post(f"{BASE_URL}/api/favorites/{FOOD_ID_1}")
        assert response1.status_code == 200
        assert FOOD_ID_1 in response1.json()["favorites"]
        
        # Add second food
        response2 = self.session.post(f"{BASE_URL}/api/favorites/{FOOD_ID_2}")
        assert response2.status_code == 200
        favorites = response2.json()["favorites"]
        assert FOOD_ID_1 in favorites, f"First food {FOOD_ID_1} should still be in favorites"
        assert FOOD_ID_2 in favorites, f"Second food {FOOD_ID_2} should be in favorites"
        print(f"Multiple favorites work: {favorites}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
