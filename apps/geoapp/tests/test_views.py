from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from ..models import City, Country, Location

User = get_user_model()


class GeoAPITest(TestCase):
    """Test the Geo API endpoints"""

    def setUp(self):
        """Set up test data and authenticate"""
        # Create user for authentication
        self.user = User.objects.create_user(
            phone_number="1234567890", password="testpass123"
        )

        # Set up API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test data
        self.country = Country.objects.create(name="Saudi Arabia", code="SA")

        self.riyadh = City.objects.create(
            name="Riyadh", country=self.country, location=Point(46.6753, 24.7136)
        )

        self.jeddah = City.objects.create(
            name="Jeddah", country=self.country, location=Point(39.1925, 21.4858)
        )

        self.location_riyadh = Location.objects.create(
            address_line1="Kingdom Centre",
            city=self.riyadh,
            country=self.country,
            coordinates=Point(46.6846, 24.7116),
        )

    def test_list_countries(self):
        """Test retrieving a list of countries"""
        url = reverse("country-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Saudi Arabia")

    def test_list_cities(self):
        """Test retrieving a list of cities"""
        url = reverse("city-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

        # Test filtering by country
        url = f"{url}?country={self.country.id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

        # Test search by name
        url = f"{reverse('city-list')}?search=Riyadh"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Riyadh")

    def test_create_location(self):
        """Test creating a new location"""
        url = reverse("location-list")
        data = {
            "address_line1": "Al Faisaliah Tower",
            "city": self.riyadh.id,
            "latitude": 24.6908,
            "longitude": 46.6853,
            "place_name": "Al Faisaliah",
            "place_type": "landmark",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["address_line1"], "Al Faisaliah Tower")
        self.assertEqual(response.data["latitude"], 24.6908)
        self.assertEqual(response.data["longitude"], 46.6853)

        # Verify it was created in database
        self.assertTrue(
            Location.objects.filter(address_line1="Al Faisaliah Tower").exists()
        )

    def test_check_city_match(self):
        """Test the check city match endpoint"""
        url = reverse("check-city-match")

        # Create a second location in Riyadh
        location2 = Location.objects.create(
            address_line1="Al Faisaliah Tower",
            city=self.riyadh,
            country=self.country,
            coordinates=Point(46.6853, 24.6908),
        )

        # Test with location IDs
        data = {
            "location1_id": str(self.location_riyadh.id),
            "location2_id": str(location2.id),
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_same_city"])

        # Test with coordinates
        data = {
            "latitude1": 24.7116,
            "longitude1": 46.6846,
            "latitude2": 24.6908,
            "longitude2": 46.6853,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_same_city"])

    def test_distance_matrix(self):
        """Test the distance matrix endpoint"""
        url = reverse("distance-matrix")

        # Create a second location in Jeddah
        location_jeddah = Location.objects.create(
            address_line1="Red Sea Mall",
            city=self.jeddah,
            country=self.country,
            coordinates=Point(39.1104, 21.6231),
        )

        # Test with location IDs
        data = {
            "origin_id": str(self.location_riyadh.id),
            "destination_ids": [str(location_jeddah.id)],
            "calculate_travel_time": True,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertIn("distance_km", response.data[0])
        self.assertIn("travel_time_minutes", response.data[0])

    def test_unauthorized_access(self):
        """Test that unauthenticated users cannot access the API"""
        # Create a new client without authentication
        client = APIClient()

        url = reverse("country-list")
        response = client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
