from datetime import time, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.packageapp.models import Package, PackageAvailability, PackageService
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


class PackageViewSetTests(TestCase):
    def setUp(self):
        # Create test user with permissions
        self.user = User.objects.create_user(
            phone_number="1234567890", is_verified=True, user_type="admin"
        )

        # Create shop
        self.shop = Shop.objects.create(
            name="Test Shop", phone_number="9876543210", username="testshop"
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

        # Create a package
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
        self.availability = PackageAvailability.objects.create(
            package=self.package,
            weekday=0,  # Sunday
            from_hour=time(9, 0),
            to_hour=time(17, 0),
            is_closed=False,
        )

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # API endpoints
        self.package_list_url = reverse("package-list")
        self.package_detail_url = reverse("package-detail", kwargs={"pk": self.package.id})
        self.package_services_url = reverse("package-services", kwargs={"pk": self.package.id})

    def test_get_package_list(self):
        """Test retrieving a list of packages"""
        response = self.client.get(self.package_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Test Package")

    def test_get_package_by_shop(self):
        """Test retrieving packages for a specific shop"""
        url = f"{self.package_list_url}?shop_id={self.shop.id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        # Create another shop and package
        shop2 = Shop.objects.create(
            name="Another Shop", phone_number="5556667777", username="anothershop"
        )

        Package.objects.create(
            shop=shop2,
            name="Another Package",
            description="Another Package Description",
            price=300,
            discount_percentage=10,
            is_active=True,
        )

        # Get packages for first shop only
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Test Package")

    def test_get_package_detail(self):
        """Test retrieving a specific package"""
        response = self.client.get(self.package_detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Package")
        self.assertEqual(response.data["price"], "200.00")
        self.assertEqual(response.data["discount_percentage"], 20)

    def test_create_package(self):
        """Test creating a new package"""
        data = {
            "shop_id": str(self.shop.id),
            "name": "New Package",
            "description": "New Package Description",
            "price": "250.00",
            "discount_percentage": 15,
            "service_ids": [str(self.service1.id), str(self.service2.id)],
            "is_active": True,
        }

        response = self.client.post(self.package_list_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Package")
        self.assertEqual(response.data["price"], "250.00")

        # Check the package was created in the database
        self.assertEqual(Package.objects.count(), 2)

        # Check services were assigned to the package
        new_package = Package.objects.get(name="New Package")
        package_services = PackageService.objects.filter(package=new_package)
        self.assertEqual(package_services.count(), 2)

    def test_update_package(self):
        """Test updating an existing package"""
        data = {
            "name": "Updated Package",
            "description": "Updated Description",
            "price": "300.00",
            "discount_percentage": 25,
            "is_active": True,
        }

        response = self.client.patch(self.package_detail_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Package")
        self.assertEqual(response.data["price"], "300.00")
        self.assertEqual(response.data["discount_percentage"], 25)

        # Verify database was updated
        self.package.refresh_from_db()
        self.assertEqual(self.package.name, "Updated Package")

        # Update services
        data = {"service_ids": [str(self.service1.id)]}  # Only include the first service

        response = self.client.patch(self.package_detail_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check services were updated
        package_services = PackageService.objects.filter(package=self.package)
        self.assertEqual(package_services.count(), 1)
        self.assertEqual(package_services[0].service.id, self.service1.id)

    def test_delete_package(self):
        """Test deleting a package"""
        response = self.client.delete(self.package_detail_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify package was deleted
        with self.assertRaises(Package.DoesNotExist):
            Package.objects.get(id=self.package.id)

        # Verify package services were deleted
        self.assertEqual(PackageService.objects.filter(package_id=self.package.id).count(), 0)

    def test_get_package_services(self):
        """Test retrieving services for a package"""
        response = self.client.get(self.package_services_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Check service details
        service_names = [service["name"] for service in response.data]
        self.assertIn("Service 1", service_names)
        self.assertIn("Service 2", service_names)


class PackageAvailabilityViewTests(TestCase):
    def setUp(self):
        # Create test user with permissions
        self.user = User.objects.create_user(
            phone_number="1234567890", is_verified=True, user_type="customer"
        )

        # Create shop
        self.shop = Shop.objects.create(
            name="Test Shop", phone_number="9876543210", username="testshop"
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

        # Create a package
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
        self.availability = PackageAvailability.objects.create(
            package=self.package,
            weekday=0,  # Sunday
            from_hour=time(9, 0),
            to_hour=time(17, 0),
            is_closed=False,
        )

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # API endpoints
        self.availability_url = reverse("package-availability", kwargs={"pk": self.package.id})
        self.booking_url = reverse("package-book", kwargs={"pk": self.package.id})

    def test_get_package_availability(self):
        """Test retrieving available time slots for a package"""
        # Specify date parameter - use a Sunday to match availability
        # Find the next Sunday
        today = timezone.now().date()
        days_until_sunday = (6 - today.weekday()) % 7  # 6 is Sunday in Python's weekday()
        next_sunday = today + timedelta(days=days_until_sunday)

        url = f"{self.availability_url}?date={next_sunday.isoformat()}"

        # Mock service availability in this test
        with patch(
            "apps.serviceapp.services.availability_service.AvailabilityService.get_service_availability"
        ) as mock_get:
            # Return mock available slots
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
            ]
            mock_get.return_value = mock_slots

            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), len(mock_slots))
            self.assertEqual(response.data[0]["start"], "09:00")
            self.assertEqual(response.data[0]["end"], "09:30")

    def test_book_package(self):
        """Test booking a package"""
        data = {
            "specialist_id": str(self.specialist.id),
            "date": timezone.now().date().isoformat(),
            "start_time": "10:00",
        }

        # Mock the package booking service
        with patch(
            "apps.packageapp.services.package_booking_service.PackageBookingService.book_package"
        ) as mock_book:
            # Mock successful booking
            mock_appointments = [MagicMock(), MagicMock()]
            mock_book.return_value = mock_appointments

            response = self.client.post(self.booking_url, data, format="json")

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(len(response.data["appointments"]), 2)

            # Verify the service was called with correct parameters
            mock_book.assert_called_once()
            call_args = mock_book.call_args[1]
            self.assertEqual(call_args["customer_id"], self.user.id)
            self.assertEqual(call_args["package_id"], self.package.id)
            self.assertEqual(call_args["specialist_id"], self.specialist.id)
            self.assertEqual(call_args["date_str"], data["date"])
            self.assertEqual(call_args["start_time_str"], data["start_time"])

    def test_book_package_specialist_unavailable(self):
        """Test booking fails when specialist is unavailable"""
        data = {
            "specialist_id": str(self.specialist.id),
            "date": timezone.now().date().isoformat(),
            "start_time": "10:00",
        }

        # Mock the package booking service to raise an error
        with patch(
            "apps.packageapp.services.package_booking_service.PackageBookingService.book_package"
        ) as mock_book:
            mock_book.side_effect = ValueError("Specialist is not available for this time slot")

            response = self.client.post(self.booking_url, data, format="json")

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("detail", response.data)
            self.assertIn("Specialist is not available", response.data["detail"])
