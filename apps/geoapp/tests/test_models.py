from django.contrib.gis.geos import Point
from django.test import TestCase

from ..models import Area, City, Country, Location


class CountryModelTest(TestCase):
    """Test the Country model"""

    def setUp(self):
        self.country = Country.objects.create(name="Saudi Arabia", code="SA", is_active=True)

    def test_country_creation(self):
        """Test creating a country"""
        self.assertEqual(self.country.name, "Saudi Arabia")
        self.assertEqual(self.country.code, "SA")
        self.assertTrue(self.country.is_active)

    def test_string_representation(self):
        """Test country string representation"""
        self.assertEqual(str(self.country), "Saudi Arabia")


class CityModelTest(TestCase):
    """Test the City model"""

    def setUp(self):
        self.country = Country.objects.create(name="Saudi Arabia", code="SA")

        # Create city with coordinates for Riyadh
        self.city = City.objects.create(
            name="Riyadh",
            country=self.country,
            location=Point(46.6753, 24.7136),
            population=7000000,
            area_km2=1913,
        )

    def test_city_creation(self):
        """Test creating a city"""
        self.assertEqual(self.city.name, "Riyadh")
        self.assertEqual(self.city.country.name, "Saudi Arabia")
        self.assertEqual(self.city.location.x, 46.6753)  # longitude
        self.assertEqual(self.city.location.y, 24.7136)  # latitude
        self.assertEqual(self.city.population, 7000000)

    def test_string_representation(self):
        """Test city string representation"""
        self.assertEqual(str(self.city), "Riyadh, Saudi Arabia")

    def test_unique_together_constraint(self):
        """Test that city and country combo must be unique"""
        with self.assertRaises(Exception):
            # Try to create a duplicate city
            City.objects.create(name="Riyadh", country=self.country)


class LocationModelTest(TestCase):
    """Test the Location model"""

    def setUp(self):
        self.country = Country.objects.create(name="Saudi Arabia", code="SA")

        self.city = City.objects.create(name="Riyadh", country=self.country)

        # Create location for a mall in Riyadh
        self.location = Location.objects.create(
            address_line1="Kingdom Centre Mall",
            city=self.city,
            country=self.country,
            postal_code="12214",
            coordinates=Point(46.6846, 24.7116),
            place_name="Kingdom Centre",
            place_type="shopping_mall",
        )

    def test_location_creation(self):
        """Test creating a location"""
        self.assertEqual(self.location.address_line1, "Kingdom Centre Mall")
        self.assertEqual(self.location.city.name, "Riyadh")
        self.assertEqual(self.location.country.name, "Saudi Arabia")
        self.assertEqual(self.location.coordinates.x, 46.6846)  # longitude
        self.assertEqual(self.location.coordinates.y, 24.7116)  # latitude

    def test_string_representation(self):
        """Test location string representation"""
        self.assertEqual(str(self.location), "Kingdom Centre Mall, Riyadh")

    def test_latitude_longitude_properties(self):
        """Test the latitude and longitude properties"""
        self.assertEqual(self.location.latitude, 24.7116)
        self.assertEqual(self.location.longitude, 46.6846)

    def test_create_from_latlong(self):
        """Test creating a location from latitude and longitude"""
        location = Location.create_from_latlong(
            lat=24.7136,
            lng=46.6753,
            city_id=self.city.id,
            address_line1="Al Faisaliah Tower",
        )

        self.assertEqual(location.latitude, 24.7136)
        self.assertEqual(location.longitude, 46.6753)
        self.assertEqual(location.address_line1, "Al Faisaliah Tower")

    def test_country_consistency(self):
        """Test that country is consistent with city"""
        new_country = Country.objects.create(name="UAE", code="AE")

        # Set a different country (should be ignored on save)
        self.location.country = new_country
        self.location.save()

        # Refresh from database
        self.location.refresh_from_db()

        # Should have the same country as the city
        self.assertEqual(self.location.country.id, self.city.country.id)


class AreaModelTest(TestCase):
    """Test the Area model"""

    def setUp(self):
        from django.contrib.gis.geos import MultiPolygon, Polygon

        self.country = Country.objects.create(name="Saudi Arabia", code="SA")

        self.city = City.objects.create(name="Riyadh", country=self.country)

        # Create a simple polygon for a district
        coords = (
            (46.65, 24.70),
            (46.75, 24.70),
            (46.75, 24.80),
            (46.65, 24.80),
            (46.65, 24.70),
        )
        polygon = Polygon(coords)
        multipolygon = MultiPolygon(polygon)

        self.area = Area.objects.create(
            name="Al Olaya District",
            description="Central business district in Riyadh",
            boundary=multipolygon,
            area_type="district",
            city=self.city,
        )

    def test_area_creation(self):
        """Test creating an area"""
        self.assertEqual(self.area.name, "Al Olaya District")
        self.assertEqual(self.area.city.name, "Riyadh")
        self.assertEqual(self.area.area_type, "district")

        # Check that the boundary is a MultiPolygon
        from django.contrib.gis.geos import MultiPolygon

        self.assertIsInstance(self.area.boundary, MultiPolygon)

    def test_string_representation(self):
        """Test area string representation"""
        self.assertEqual(str(self.area), "Al Olaya District (district)")
