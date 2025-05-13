import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.categoriesapp.models import Category
from apps.companiesapp.models import Company
from apps.packageapp.models import Package, PackageAvailability, PackageFAQ, PackageService
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop


class PackageModelTests(TestCase):
    """Test cases for the Package model and related models."""

    def setUp(self):
        """Set up test data."""
        # Create a user (owner)
        self.user = User.objects.create(
            phone_number="1234567890", user_type="admin", is_verified=True
        )

        # Create a company
        self.company = Company.objects.create(
            name="Test Company", owner=self.user, contact_phone="9876543210"
        )

        # Create a shop
        self.shop = Shop.objects.create(
            company=self.company,
            name="Test Shop",
            phone_number="9876543210",
            username="testshop",
        )

        # Create a category
        self.category = Category.objects.create(name="Test Category")

        # Create services
        self.service1 = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Service 1",
            price=Decimal("100.00"),
            duration=60,
            service_location="in_shop",
        )

        self.service2 = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Service 2",
            price=Decimal("150.00"),
            duration=90,
            service_location="in_shop",
        )

        # Create a package
        self.package = Package.objects.create(
            shop=self.shop,
            name="Test Package",
            description="Test package description",
            original_price=Decimal("250.00"),  # Sum of service prices
            discounted_price=Decimal("200.00"),  # 20% discount
            package_location="in_shop",
            primary_category=self.category,
            status="active",
        )

        # Add services to package
        self.package_service1 = PackageService.objects.create(
            package=self.package, service=self.service1, sequence=0
        )

        self.package_service2 = PackageService.objects.create(
            package=self.package, service=self.service2, sequence=1
        )

    def test_package_creation(self):
        """Test creating a package."""
        self.assertEqual(self.package.name, "Test Package")
        self.assertEqual(self.package.shop, self.shop)
        self.assertEqual(self.package.original_price, Decimal("250.00"))
        self.assertEqual(self.package.discounted_price, Decimal("200.00"))

        # Check calculated fields
        self.assertEqual(self.package.discount_percentage, Decimal("20.00"))
        self.assertEqual(self.package.total_duration, 150)  # 60 + 90

    def test_package_service_relationship(self):
        """Test package-service relationship."""
        services = self.package.services.all()
        self.assertEqual(services.count(), 2)

        # Check ordering by sequence
        self.assertEqual(services.first().service, self.service1)
        self.assertEqual(services.last().service, self.service2)

    def test_package_is_available_property(self):
        """Test is_available property."""
        # Active package with no date restrictions should be available
        self.assertTrue(self.package.is_available)

        # Set future start date
        future_date = timezone.now().date() + datetime.timedelta(days=5)
        self.package.start_date = future_date
        self.package.save()

        # Should not be available yet
        self.assertFalse(self.package.is_available)

        # Reset start date and set past end date
        self.package.start_date = None
        self.package.end_date = timezone.now().date() - datetime.timedelta(days=1)
        self.package.save()

        # Should not be available anymore
        self.assertFalse(self.package.is_available)

        # Reset end date and set purchase limit
        self.package.end_date = None
        self.package.max_purchases = 10
        self.package.current_purchases = 5
        self.package.save()

        # Should be available (under limit)
        self.assertTrue(self.package.is_available)

        # Reach purchase limit
        self.package.current_purchases = 10
        self.package.save()

        # Should not be available (at limit)
        self.assertFalse(self.package.is_available)

        # Set inactive status
        self.package.current_purchases = 0
        self.package.status = "inactive"
        self.package.save()

        # Should not be available (inactive)
        self.assertFalse(self.package.is_available)

    def test_package_services_list_property(self):
        """Test services_list property."""
        services_list = self.package.services_list
        self.assertEqual(len(services_list), 2)
        self.assertEqual(services_list[0], self.service1)
        self.assertEqual(services_list[1], self.service2)

    def test_package_availability(self):
        """Test package availability."""
        # Create package availability
        avail = PackageAvailability.objects.create(
            package=self.package,
            weekday=0,  # Sunday
            from_hour="09:00:00",
            to_hour="17:00:00",
            is_closed=False,
        )

        self.assertEqual(str(avail), f"{self.package.name} - Sunday: 09:00 AM - 05:00 PM")

        # Create closed day
        closed = PackageAvailability.objects.create(
            package=self.package,
            weekday=5,  # Friday
            from_hour="09:00:00",
            to_hour="17:00:00",
            is_closed=True,
        )

        self.assertTrue(closed.is_closed)

    def test_package_faq(self):
        """Test package FAQ."""
        # Create FAQ
        faq = PackageFAQ.objects.create(
            package=self.package,
            question="Test question?",
            answer="Test answer.",
            order=0,
        )

        self.assertEqual(str(faq), f"{self.package.name} - Test question?")
        self.assertEqual(faq.answer, "Test answer.")

        # Create another FAQ with higher order
        faq2 = PackageFAQ.objects.create(
            package=self.package,
            question="Another question?",
            answer="Another answer.",
            order=1,
        )

        # Check ordering
        faqs = self.package.faqs.all()
        self.assertEqual(faqs.first(), faq)
        self.assertEqual(faqs.last(), faq2)

    def test_custom_duration_override(self):
        """Test custom duration override in package service."""
        # Set custom duration
        self.package_service1.custom_duration = 45  # Override 60 min
        self.package_service1.save()

        # Check effective duration
        self.assertEqual(self.package_service1.effective_duration, 45)

        # Check original duration is preserved on the service
        self.assertEqual(self.service1.duration, 60)

        # Check with no override
        self.assertEqual(
            self.package_service2.effective_duration, 90
        )  # Default to service duration
