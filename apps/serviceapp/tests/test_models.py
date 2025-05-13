from django.test import TestCase

from apps.authapp.models import User
from apps.categoriesapp.models import Category
from apps.companiesapp.models import Company
from apps.serviceapp.models import Service, ServiceAvailability
from apps.shopapp.models import Shop


class ServiceModelTest(TestCase):
    """Test the Service model"""

    def setUp(self):
        # Create test user
        self.user = User.objects.create(phone_number="1234567890", user_type="admin")

        # Create test company
        self.company = Company.objects.create(
            name="Test Company", owner=self.user, contact_phone="9876543210"
        )

        # Create test shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="5555555555",
            username="testshop",
        )

        # Create test category
        self.category = Category.objects.create(name="Test Category")

        # Create test service
        self.service = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Test Service",
            description="Test Description",
            price=100.00,
            duration=60,
            service_location="in_shop",
        )

    def test_service_creation(self):
        """Test creating a service"""
        service = Service.objects.get(id=self.service.id)
        self.assertEqual(service.name, "Test Service")
        self.assertEqual(service.price, 100.00)
        self.assertEqual(service.price_halalas, 10000)
        self.assertEqual(service.duration, 60)
        self.assertEqual(service.slot_granularity, 30)  # Default value
        self.assertEqual(service.service_location, "in_shop")

    def test_service_total_duration(self):
        """Test the total_duration property"""
        # Default buffers are 0
        self.assertEqual(self.service.total_duration, 60)

        # Update buffers
        self.service.buffer_before = 10
        self.service.buffer_after = 5
        self.service.save()

        self.assertEqual(self.service.total_duration, 75)

    def test_service_price_halalas_calculation(self):
        """Test the price_halalas calculation"""
        # Test on creation
        service = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Price Test",
            price=123.45,
            duration=30,
            service_location="in_shop",
        )
        self.assertEqual(service.price_halalas, 12345)

        # Test on update
        service.price = 99.99
        service.save()
        self.assertEqual(service.price_halalas, 9999)

    def test_service_is_available(self):
        """Test the is_available property"""
        # Default status is active
        self.assertTrue(self.service.is_available)

        # Change status
        self.service.status = "inactive"
        self.service.save()
        self.assertFalse(self.service.is_available)


class ServiceAvailabilityTest(TestCase):
    """Test the ServiceAvailability model"""

    def setUp(self):
        # Create test user
        self.user = User.objects.create(phone_number="1234567890", user_type="admin")

        # Create test company
        self.company = Company.objects.create(
            name="Test Company", owner=self.user, contact_phone="9876543210"
        )

        # Create test shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="5555555555",
            username="testshop",
        )

        # Create test category
        self.category = Category.objects.create(name="Test Category")

        # Create test service
        self.service = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Test Service",
            description="Test Description",
            price=100.00,
            duration=60,
            service_location="in_shop",
            has_custom_availability=True,
        )

    def test_availability_creation(self):
        """Test creating service availability"""
        availability = ServiceAvailability.objects.create(
            service=self.service,
            weekday=0,  # Sunday
            from_hour="09:00:00",
            to_hour="17:00:00",
            is_closed=False,
        )

        self.assertEqual(availability.weekday, 0)
        self.assertEqual(str(availability.from_hour), "09:00:00")
        self.assertEqual(str(availability.to_hour), "17:00:00")
        self.assertFalse(availability.is_closed)

    def test_availability_string_representation(self):
        """Test the string representation"""
        availability = ServiceAvailability.objects.create(
            service=self.service,
            weekday=0,  # Sunday
            from_hour="09:00:00",
            to_hour="17:00:00",
            is_closed=False,
        )

        self.assertIn("Test Service", str(availability))
        self.assertIn("Sunday", str(availability))
        self.assertIn("09:00", str(availability))
        self.assertIn("05:00", str(availability))
