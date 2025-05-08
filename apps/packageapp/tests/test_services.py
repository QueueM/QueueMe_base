from datetime import time, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.bookingapp.models import Appointment
from apps.packageapp.models import Package, PackageAvailability, PackageService
from apps.packageapp.services.bundle_optimizer import BundleOptimizer
from apps.packageapp.services.package_availability import PackageAvailabilityService
from apps.packageapp.services.package_booking_service import PackageBookingService
from apps.packageapp.services.package_service import PackageService
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


class TestPackageService(TestCase):
    def setUp(self):
        # Create test shop
        self.shop_owner = User.objects.create(
            phone_number="9876543210", user_type="admin", is_verified=True
        )
        self.shop = Shop.objects.create(
            name="Test Shop", phone_number="1234567890", username="testshop"
        )

        # Create services
        self.service1 = Service.objects.create(
            shop=self.shop,
            name="Service 1",
            price=100,
            duration=30,
            service_location="in_shop",
        )

        self.service2 = Service.objects.create(
            shop=self.shop,
            name="Service 2",
            price=150,
            duration=45,
            service_location="in_shop",
        )

        # Create package
        self.package = Package.objects.create(
            shop=self.shop,
            name="Test Package",
            description="Test Package Description",
            price=200,
            discount_percentage=20,
            is_active=True,
        )

        # Add services to package
        self.package_service1 = PackageService.objects.create(
            package=self.package, service=self.service1, order=1
        )

        self.package_service2 = PackageService.objects.create(
            package=self.package, service=self.service2, order=2
        )

    def test_get_package_by_id(self):
        """Test retrieving a package by ID"""
        package = PackageService.get_package_by_id(self.package.id)
        self.assertEqual(package, self.package)

        # Test with non-existent ID
        with self.assertRaises(Package.DoesNotExist):
            PackageService.get_package_by_id("00000000-0000-0000-0000-000000000000")

    def test_get_shop_packages(self):
        """Test retrieving all packages for a shop"""
        packages = PackageService.get_shop_packages(self.shop.id)
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0], self.package)

        # Create another package
        Package.objects.create(
            shop=self.shop,
            name="Another Package",
            description="Another Package Description",
            price=300,
            discount_percentage=10,
            is_active=True,
        )

        packages = PackageService.get_shop_packages(self.shop.id)
        self.assertEqual(len(packages), 2)

    def test_create_package(self):
        """Test creating a new package with services"""
        service_ids = [self.service1.id, self.service2.id]

        new_package = PackageService.create_package(
            shop_id=self.shop.id,
            name="New Package",
            description="New Package Description",
            price=250,
            discount_percentage=15,
            service_ids=service_ids,
            is_active=True,
        )

        # Check package was created
        self.assertIsNotNone(new_package)
        self.assertEqual(new_package.name, "New Package")
        self.assertEqual(new_package.price, 250)

        # Check services were added to package
        package_services = PackageService.objects.filter(package=new_package)
        self.assertEqual(package_services.count(), 2)

        # Check service IDs match
        added_service_ids = [ps.service.id for ps in package_services]
        self.assertIn(str(self.service1.id), added_service_ids)
        self.assertIn(str(self.service2.id), added_service_ids)

    def test_update_package(self):
        """Test updating an existing package"""
        # Only update package details
        updated_package = PackageService.update_package(
            package_id=self.package.id,
            name="Updated Package",
            description="Updated Description",
            price=300,
            discount_percentage=25,
            service_ids=None,
            is_active=True,
        )

        # Check package was updated
        self.assertEqual(updated_package.name, "Updated Package")
        self.assertEqual(updated_package.price, 300)
        self.assertEqual(updated_package.discount_percentage, 25)

        # Services should remain the same
        package_services = PackageService.objects.filter(package=updated_package)
        self.assertEqual(package_services.count(), 2)

        # Update services
        service3 = Service.objects.create(
            shop=self.shop,
            name="Service 3",
            price=200,
            duration=60,
            service_location="in_shop",
        )

        updated_package = PackageService.update_package(
            package_id=self.package.id,
            name="Updated Package",
            description="Updated Description",
            price=400,
            discount_percentage=30,
            service_ids=[str(service3.id)],
            is_active=True,
        )

        # Check services were updated
        package_services = PackageService.objects.filter(package=updated_package)
        self.assertEqual(package_services.count(), 1)
        self.assertEqual(package_services[0].service.id, service3.id)

    def test_delete_package(self):
        """Test deleting a package"""
        result = PackageService.delete_package(self.package.id)
        self.assertTrue(result)

        # Check package was deleted
        with self.assertRaises(Package.DoesNotExist):
            Package.objects.get(id=self.package.id)

        # Check package services were deleted
        self.assertEqual(
            PackageService.objects.filter(package_id=self.package.id).count(), 0
        )

    def test_get_package_services(self):
        """Test retrieving services for a package"""
        services = PackageService.get_package_services(self.package.id)
        self.assertEqual(len(services), 2)

        # Check services are correct
        service_ids = [service.id for service in services]
        self.assertIn(self.service1.id, service_ids)
        self.assertIn(self.service2.id, service_ids)


class TestPackageAvailabilityService(TestCase):
    def setUp(self):
        # Create test data
        self.shop_owner = User.objects.create(
            phone_number="9876543210", user_type="admin", is_verified=True
        )
        self.shop = Shop.objects.create(
            name="Test Shop", phone_number="1234567890", username="testshop"
        )

        # Create services
        self.service1 = Service.objects.create(
            shop=self.shop,
            name="Service 1",
            price=100,
            duration=30,
            service_location="in_shop",
        )

        self.service2 = Service.objects.create(
            shop=self.shop,
            name="Service 2",
            price=150,
            duration=45,
            service_location="in_shop",
        )

        # Create specialist
        self.user = User.objects.create(
            phone_number="5554443333", user_type="employee", is_verified=True
        )

        self.specialist = Specialist.objects.create(
            employee_id=self.user.id, bio="Test specialist"
        )

        # Create package
        self.package = Package.objects.create(
            shop=self.shop,
            name="Test Package",
            description="Test Package Description",
            price=200,
            discount_percentage=20,
            is_active=True,
        )

        # Add services to package
        self.package_service1 = PackageService.objects.create(
            package=self.package, service=self.service1, order=1
        )

        self.package_service2 = PackageService.objects.create(
            package=self.package, service=self.service2, order=2
        )

        # Set up package availability
        today = timezone.now().date()
        self.availability = PackageAvailability.objects.create(
            package=self.package,
            weekday=today.weekday(),
            from_hour=time(9, 0),  # 9:00 AM
            to_hour=time(17, 0),  # 5:00 PM
            is_closed=False,
        )

    @patch(
        "apps.serviceapp.services.availability_service.AvailabilityService.get_service_availability"
    )
    def test_get_package_availability(self, mock_get_service_availability):
        """Test getting available time slots for a package"""
        # Mock service availability
        mock_slots = [
            {
                "start": "09:00",
                "end": "09:30",
                "duration": 30,
                "buffer_before": 5,
                "buffer_after": 5,
            },
            {
                "start": "10:00",
                "end": "10:30",
                "duration": 30,
                "buffer_before": 5,
                "buffer_after": 5,
            },
            {
                "start": "11:00",
                "end": "11:30",
                "duration": 30,
                "buffer_before": 5,
                "buffer_after": 5,
            },
        ]

        mock_get_service_availability.return_value = mock_slots

        # Get availability for package
        date = timezone.now().date()
        availability = PackageAvailabilityService.get_package_availability(
            self.package.id, date
        )

        # Should have been called for each service in the package
        self.assertEqual(mock_get_service_availability.call_count, 2)

        # Check returned slots
        self.assertEqual(len(availability), 3)
        self.assertEqual(availability[0]["start"], "09:00")
        self.assertEqual(availability[0]["end"], "09:30")

    def test_is_package_available(self):
        """Test checking if a package is available on a specific day"""
        # Test package is available today
        today = timezone.now().date()
        is_available = PackageAvailabilityService.is_package_available(
            self.package.id, today
        )
        self.assertTrue(is_available)

        # Set package to closed today
        self.availability.is_closed = True
        self.availability.save()

        # Test package is not available
        is_available = PackageAvailabilityService.is_package_available(
            self.package.id, today
        )
        self.assertFalse(is_available)

        # Test for a day without explicit availability (should default to shop hours)
        tomorrow = today + timedelta(days=1)
        is_available = PackageAvailabilityService.is_package_available(
            self.package.id, tomorrow
        )
        # Assuming shop is open by default
        self.assertTrue(is_available)

    def test_get_package_duration(self):
        """Test calculating total duration for a package"""
        # Total duration should be sum of service durations (30 + 45 = 75)
        duration = PackageAvailabilityService.get_package_duration(self.package.id)
        self.assertEqual(duration, 75)

        # Test with a package that has no services
        empty_package = Package.objects.create(
            shop=self.shop,
            name="Empty Package",
            description="No services",
            price=100,
            discount_percentage=10,
            is_active=True,
        )

        duration = PackageAvailabilityService.get_package_duration(empty_package.id)
        self.assertEqual(duration, 0)


class TestPackageBookingService(TestCase):
    def setUp(self):
        # Create test data
        self.customer = User.objects.create(
            phone_number="1112223333", user_type="customer", is_verified=True
        )

        self.shop_owner = User.objects.create(
            phone_number="9876543210", user_type="admin", is_verified=True
        )

        self.shop = Shop.objects.create(
            name="Test Shop", phone_number="1234567890", username="testshop"
        )

        # Create services
        self.service1 = Service.objects.create(
            shop=self.shop,
            name="Service 1",
            price=100,
            duration=30,
            service_location="in_shop",
        )

        self.service2 = Service.objects.create(
            shop=self.shop,
            name="Service 2",
            price=150,
            duration=45,
            service_location="in_shop",
        )

        # Create specialist
        self.specialist_user = User.objects.create(
            phone_number="5554443333", user_type="employee", is_verified=True
        )

        self.specialist = Specialist.objects.create(
            employee_id=self.specialist_user.id, bio="Test specialist"
        )

        # Create package
        self.package = Package.objects.create(
            shop=self.shop,
            name="Test Package",
            description="Test Package Description",
            price=200,
            discount_percentage=20,
            is_active=True,
        )

        # Add services to package
        self.package_service1 = PackageService.objects.create(
            package=self.package, service=self.service1, order=1
        )

        self.package_service2 = PackageService.objects.create(
            package=self.package, service=self.service2, order=2
        )

    @patch(
        "apps.serviceapp.services.availability_service.AvailabilityService.is_specialist_available"
    )
    @patch("apps.bookingapp.services.booking_service.BookingService.create_appointment")
    def test_book_package(self, mock_create_appointment, mock_is_specialist_available):
        """Test booking a package of services"""
        # Mock specialist availability
        mock_is_specialist_available.return_value = True

        # Mock appointment creation
        mock_appointments = [MagicMock() for _ in range(2)]
        mock_create_appointment.side_effect = mock_appointments

        # Book package
        date_str = timezone.now().date().strftime("%Y-%m-%d")
        start_time_str = "10:00"

        appointments = PackageBookingService.book_package(
            customer_id=self.customer.id,
            package_id=self.package.id,
            specialist_id=self.specialist.id,
            start_time_str=start_time_str,
            date_str=date_str,
        )

        # Check appointments were created
        self.assertEqual(len(appointments), 2)

        # Check specialist availability was checked
        self.assertEqual(mock_is_specialist_available.call_count, 2)

        # Check create_appointment was called for each service
        self.assertEqual(mock_create_appointment.call_count, 2)

        # Each service should be booked in sequence
        call_args_list = mock_create_appointment.call_args_list

        # First call should be for first service at 10:00
        self.assertEqual(call_args_list[0][1]["start_time_str"], "10:00")
        self.assertEqual(call_args_list[0][1]["service_id"], self.service1.id)

        # Second call should be for second service after first service completes (10:30 + buffer)
        self.assertEqual(call_args_list[1][1]["service_id"], self.service2.id)

    @patch(
        "apps.serviceapp.services.availability_service.AvailabilityService.is_specialist_available"
    )
    def test_book_package_specialist_unavailable(self, mock_is_specialist_available):
        """Test booking fails when specialist is unavailable"""
        # Mock specialist availability - first service ok, second service unavailable
        mock_is_specialist_available.side_effect = [True, False]

        # Book package
        date_str = timezone.now().date().strftime("%Y-%m-%d")
        start_time_str = "10:00"

        # Should raise ValueError
        with self.assertRaises(ValueError):
            PackageBookingService.book_package(
                customer_id=self.customer.id,
                package_id=self.package.id,
                specialist_id=self.specialist.id,
                start_time_str=start_time_str,
                date_str=date_str,
            )

    @patch("apps.bookingapp.services.booking_service.BookingService.cancel_appointment")
    def test_cancel_package_booking(self, mock_cancel_appointment):
        """Test cancelling all appointments in a package booking"""
        # Create mock appointments
        appointment1 = Appointment.objects.create(
            customer=self.customer,
            service=self.service1,
            specialist=self.specialist,
            shop=self.shop,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            status="scheduled",
            package_id=self.package.id,
        )

        appointment2 = Appointment.objects.create(
            customer=self.customer,
            service=self.service2,
            specialist=self.specialist,
            shop=self.shop,
            start_time=timezone.now() + timedelta(days=1, hours=1),
            end_time=timezone.now() + timedelta(days=1, hours=2),
            status="scheduled",
            package_id=self.package.id,
        )

        # Mock cancellation
        mock_cancel_appointment.return_value = MagicMock()

        # Cancel package booking
        result = PackageBookingService.cancel_package_booking(
            package_id=self.package.id,
            customer_id=self.customer.id,
            cancelled_by_id=self.customer.id,
            reason="Testing cancellation",
        )

        # Check both appointments were cancelled
        self.assertEqual(mock_cancel_appointment.call_count, 2)
        self.assertTrue(result)


class TestBundleOptimizer(TestCase):
    def setUp(self):
        # Create test shop
        self.shop = Shop.objects.create(
            name="Test Shop", phone_number="1234567890", username="testshop"
        )

        # Create services with different durations and prices
        self.service1 = Service.objects.create(
            shop=self.shop,
            name="Service 1",
            price=100,
            duration=30,
            service_location="in_shop",
        )

        self.service2 = Service.objects.create(
            shop=self.shop,
            name="Service 2",
            price=150,
            duration=45,
            service_location="in_shop",
        )

        self.service3 = Service.objects.create(
            shop=self.shop,
            name="Service 3",
            price=200,
            duration=60,
            service_location="in_shop",
        )

    def test_create_optimal_packages(self):
        """Test creating optimal service bundles"""
        services = [self.service1, self.service2, self.service3]

        # Create optimal bundles
        packages = BundleOptimizer.create_optimal_packages(self.shop.id, services)

        # Should create at least one package
        self.assertGreater(len(packages), 0)

        # First package should include all services with a discount
        all_services_package = packages[0]
        self.assertEqual(
            PackageService.objects.filter(package=all_services_package).count(), 3
        )

        # Package price should be less than sum of service prices (which is 450)
        self.assertLess(all_services_package.price, 450)

    def test_calculate_optimal_discount(self):
        """Test calculating optimal discount based on service count"""
        # Test with different service counts
        discount1 = BundleOptimizer._calculate_optimal_discount(1)
        discount2 = BundleOptimizer._calculate_optimal_discount(2)
        discount3 = BundleOptimizer._calculate_optimal_discount(3)
        discount4 = BundleOptimizer._calculate_optimal_discount(5)

        # More services should result in higher discount
        self.assertLess(discount1, discount2)
        self.assertLess(discount2, discount3)
        self.assertLess(discount3, discount4)

    def test_find_complementary_services(self):
        """Test finding complementary services based on booking patterns"""
        # This is a complex algorithm that would typically analyze historical
        # booking data to find commonly booked service combinations

        # For testing, we'd mock the analysis and just verify the method works
        with patch("apps.bookingapp.models.Appointment.objects.filter") as mock_filter:
            # Mock query results that would indicate services 1 and 2 are often booked together
            mock_filter.return_value.values.return_value.annotate.return_value.order_by.return_value = [
                {"service_id": self.service1.id, "service_id__count": 10},
                {"service_id": self.service2.id, "service_id__count": 8},
            ]

            complementary = BundleOptimizer.find_complementary_services(self.service3)

            # Should return services 1 and 2
            service_ids = [s.id for s in complementary]
            self.assertIn(self.service1.id, service_ids)
            self.assertIn(self.service2.id, service_ids)
