from django.contrib.gis.geos import Point
from django.test import TestCase

from ..models import City, Country, Location
from ..services.distance_service import DistanceService
from ..services.geo_service import GeoService
from ..services.travel_time_service import TravelTimeService


class DistanceServiceTest(TestCase):
    """Test the Distance Service"""

    def test_haversine_distance(self):
        """Test Haversine distance calculation between two points"""
        # Coordinates for Riyadh (Kingdom Centre) and Jeddah (Red Sea Mall)
        riyadh_lat, riyadh_lng = 24.7116, 46.6846
        jeddah_lat, jeddah_lng = 21.6231, 39.1104

        # Calculate distance
        distance = DistanceService.calculate_haversine_distance(
            riyadh_lat, riyadh_lng, jeddah_lat, jeddah_lng
        )

        # Expected distance is approximately 850 km
        self.assertAlmostEqual(distance, 850, delta=50)

    def test_distance_matrix_by_coordinates(self):
        """Test calculating distance matrix by coordinates"""
        # Origin: Riyadh
        origin_lat, origin_lng = 24.7116, 46.6846

        # Destinations: Jeddah, Dammam
        destinations = [(21.6231, 39.1104), (26.4207, 50.0888)]  # Jeddah  # Dammam

        # Calculate distance matrix
        result = DistanceService.calculate_distance_matrix_by_coordinates(
            origin_lat, origin_lng, destinations, include_travel_time=True
        )

        # Check structure and values
        self.assertEqual(len(result), 2)

        # Check Jeddah distance (approximately 850 km)
        self.assertAlmostEqual(result[0]["distance_km"], 850, delta=50)

        # Check Dammam distance (approximately 400 km)
        self.assertAlmostEqual(result[1]["distance_km"], 400, delta=50)

        # Check that travel times are included
        self.assertIn("travel_time_minutes", result[0])
        self.assertIn("travel_time_minutes", result[1])


class GeoServiceTest(TestCase):
    """Test the Geo Service"""

    def setUp(self):
        # Create test data
        self.country = Country.objects.create(name="Saudi Arabia", code="SA")

        # Create Riyadh city
        self.riyadh = City.objects.create(
            name="Riyadh", country=self.country, location=Point(46.6753, 24.7136)
        )

        # Create Jeddah city
        self.jeddah = City.objects.create(
            name="Jeddah", country=self.country, location=Point(39.1925, 21.4858)
        )

        # Create locations in Riyadh
        self.loc_riyadh_1 = Location.objects.create(
            address_line1="Kingdom Centre",
            city=self.riyadh,
            country=self.country,
            coordinates=Point(46.6846, 24.7116),
        )

        self.loc_riyadh_2 = Location.objects.create(
            address_line1="Al Faisaliah Tower",
            city=self.riyadh,
            country=self.country,
            coordinates=Point(46.6853, 24.6908),
        )

        # Create location in Jeddah
        self.loc_jeddah = Location.objects.create(
            address_line1="Red Sea Mall",
            city=self.jeddah,
            country=self.country,
            coordinates=Point(39.1104, 21.6231),
        )

    def test_is_same_city_by_locations(self):
        """Test checking if two locations are in the same city"""
        # Same city (Riyadh)
        result = GeoService.is_same_city_by_locations(self.loc_riyadh_1.id, self.loc_riyadh_2.id)
        self.assertTrue(result)

        # Different cities (Riyadh and Jeddah)
        result = GeoService.is_same_city_by_locations(self.loc_riyadh_1.id, self.loc_jeddah.id)
        self.assertFalse(result)

    def test_is_same_city_by_coordinates(self):
        """Test checking if coordinates are in the same city"""
        # Same area in Riyadh
        result = GeoService.is_same_city_by_coordinates(
            24.7116, 46.6846, 24.6908, 46.6853  # Kingdom Centre  # Al Faisaliah Tower
        )
        self.assertTrue(result)

        # Different cities (Riyadh and Jeddah)
        result = GeoService.is_same_city_by_coordinates(
            24.7116, 46.6846, 21.6231, 39.1104  # Riyadh  # Jeddah
        )
        self.assertFalse(result)


class TravelTimeServiceTest(TestCase):
    """Test the Travel Time Service"""

    def test_estimate_travel_time(self):
        """Test estimating travel time between points"""
        # Riyadh to Dammam (around 400 km)
        origin = Point(46.6846, 24.7116)  # Riyadh
        destination = Point(50.0888, 26.4207)  # Dammam

        # Test with different modes
        driving_time = TravelTimeService.estimate_travel_time(origin, destination, mode="driving")

        # Driving should take around 4-5 hours
        self.assertTrue(240 <= driving_time <= 360)

        # Walking should take way longer
        walking_time = TravelTimeService.estimate_travel_time(origin, destination, mode="walking")

        # Should be much longer than driving
        self.assertTrue(walking_time > driving_time * 5)

    def test_get_eta(self):
        """Test calculating estimated time of arrival"""
        import datetime

        # Riyadh to Jeddah (around 850 km)
        origin = Point(46.6846, 24.7116)  # Riyadh
        destination = Point(39.1104, 21.6231)  # Jeddah

        # Set departure time to noon
        noon = datetime.datetime(2023, 1, 1, 12, 0, 0)

        # Calculate ETA
        eta = TravelTimeService.get_eta(origin, destination, noon)

        # Should be several hours later (around 8-9 hours for driving)
        self.assertTrue(eta > noon + datetime.timedelta(hours=7))
        self.assertTrue(eta < noon + datetime.timedelta(hours=12))


class GeospatialQueryServiceTest(TestCase):
    """Test the Geospatial Query Service"""

    def setUp(self):
        # Create test data
        self.country = Country.objects.create(name="Saudi Arabia", code="SA")

        self.riyadh = City.objects.create(
            name="Riyadh", country=self.country, location=Point(46.6753, 24.7136)
        )

        # Create sample shop data
        from apps.shopapp.models import Shop

        # Import requires creating a shop location first
        self.shop_location = Location.objects.create(
            address_line1="Test Shop Location",
            city=self.riyadh,
            country=self.country,
            coordinates=Point(46.6846, 24.7116),
        )

        # Now create a shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            location=self.shop_location,
            # ... other required fields
        )

    def test_find_nearby_entities(self):
        """Test finding nearby entities"""
        # This test requires actual shop data from shopapp
        # Mock the response or use a more comprehensive fixture

        # Skip test if shop model isn't available
