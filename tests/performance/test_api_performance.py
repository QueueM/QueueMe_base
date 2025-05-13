# tests/performance/test_api_performance.py
"""
Performance tests for Queue Me API.

This module contains tests that measure the performance of critical API
endpoints to ensure they meet response time requirements under load.
"""

import random
import time

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.categoriesapp.models import Category
from apps.companiesapp.models import Company
from apps.employeeapp.models import Employee
from apps.geoapp.models import Location
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


class APIPerformanceTest(TestCase):
    """Test the performance of critical API endpoints."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data once for all test methods."""
        # Create users
        cls.admin_user = User.objects.create(
            phone_number="1111111111",
            user_type="admin",
            is_verified=True,
            profile_completed=True,
            is_staff=True,
        )

        cls.customers = []
        for i in range(20):
            customer = User.objects.create(
                phone_number=f"9{i:02d}8765432",
                user_type="customer",
                is_verified=True,
                profile_completed=True,
            )
            cls.customers.append(customer)

        # Create locations
        cls.locations = []
        for i in range(10):
            location = Location.objects.create(
                address=f"Address {i}",
                city="Riyadh",
                country="Saudi Arabia",
                latitude=24.7136 + (i * 0.01),
                longitude=46.6753 + (i * 0.01),
            )
            cls.locations.append(location)

        # Create companies
        cls.companies = []
        for i in range(5):
            company = Company.objects.create(
                name=f"Company {i}",
                contact_phone=f"8{i:02d}7654321",
                owner=cls.customers[i],
                location=cls.locations[i],
            )
            cls.companies.append(company)

        # Create shops
        cls.shops = []
        for i in range(10):
            company_index = i % len(cls.companies)
            shop = Shop.objects.create(
                company=cls.companies[company_index],
                name=f"Shop {i}",
                phone_number=f"7{i:02d}6543210",
                username=f"shop{i}",
                location=cls.locations[i],
            )
            cls.shops.append(shop)

        # Create categories
        cls.categories = []
        for i in range(5):
            category = Category.objects.create(name=f"Category {i}")
            cls.categories.append(category)

        # Create services
        cls.services = []
        for i in range(30):
            shop_index = i % len(cls.shops)
            category_index = i % len(cls.categories)
            service = Service.objects.create(
                shop=cls.shops[shop_index],
                category=cls.categories[category_index],
                name=f"Service {i}",
                price=50.00 + (i * 10),
                duration=30 + (i % 3) * 15,
                slot_granularity=15,
                buffer_before=5,
                buffer_after=5,
                service_location=["in_shop", "in_home", "both"][i % 3],
            )
            cls.services.append(service)

        # Create employees and specialists
        cls.employees = []
        cls.specialists = []
        for i in range(15):
            shop_index = i % len(cls.shops)

            employee_user = User.objects.create(
                phone_number=f"6{i:02d}5432109",
                user_type="employee",
                is_verified=True,
                profile_completed=True,
            )

            employee = Employee.objects.create(
                user=employee_user,
                shop=cls.shops[shop_index],
                first_name=f"Employee{i}",
                last_name=f"Last{i}",
                position=["manager", "specialist", "receptionist"][i % 3],
            )
            cls.employees.append(employee)

            # Create specialist for every other employee
            if i % 2 == 0:
                specialist = Specialist.objects.create(
                    employee=employee,
                    bio=f"Specialist bio {i}",
                    experience_years=1 + (i % 10),
                )
                cls.specialists.append(specialist)

        # Get a token for performance testing
        from apps.authapp.services.token_service import TokenService

        cls.customer_token = TokenService.get_tokens_for_user(cls.customers[0])["access"]

    def setUp(self):
        """Set up for each test method."""
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")

    def test_nearby_shops_performance(self):
        """Test performance of nearby shops endpoint."""
        lat, lng = 24.7136, 46.6753  # Riyadh coordinates

        # Record the start time
        start_time = time.time()

        # Send API request
        response = self.client.get(reverse("nearby-shops"), {"lat": lat, "lng": lng, "radius": 10})

        # Calculate response time
        response_time = time.time() - start_time

        # Assert status and performance
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 0.5, f"Nearby shops API too slow: {response_time:.3f}s")

        # Log the performance data
        print(f"Nearby shops API response time: {response_time:.3f}s")

    def test_service_availability_performance(self):
        """Test performance of service availability endpoint."""
        service = random.choice(self.services)
        tomorrow = (timezone.now() + timezone.timedelta(days=1)).date()

        # Record the start time
        start_time = time.time()

        # Send API request
        response = self.client.get(
            reverse("service-availability", args=[service.id]),
            {"date": tomorrow.isoformat()},
        )

        # Calculate response time
        response_time = time.time() - start_time

        # Assert status and performance
        self.assertEqual(response.status_code, 200)
        self.assertLess(
            response_time,
            0.3,
            f"Service availability API too slow: {response_time:.3f}s",
        )

        # Log the performance data
        print(f"Service availability API response time: {response_time:.3f}s")

    def test_service_listing_performance(self):
        """Test performance of service listing endpoint."""
        shop = random.choice(self.shops)

        # Record the start time
        start_time = time.time()

        # Send API request
        response = self.client.get(reverse("shop-services-list", args=[shop.id]))

        # Calculate response time
        response_time = time.time() - start_time

        # Assert status and performance
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 0.3, f"Service listing API too slow: {response_time:.3f}s")

        # Log the performance data
        print(f"Service listing API response time: {response_time:.3f}s")

    def test_shop_detail_performance(self):
        """Test performance of shop detail endpoint."""
        shop = random.choice(self.shops)

        # Record the start time
        start_time = time.time()

        # Send API request
        response = self.client.get(reverse("shops-detail", args=[shop.id]))

        # Calculate response time
        response_time = time.time() - start_time

        # Assert status and performance
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 0.3, f"Shop detail API too slow: {response_time:.3f}s")

        # Log the performance data
        print(f"Shop detail API response time: {response_time:.3f}s")

    def test_feed_performance(self):
        """Test performance of content feed endpoints."""
        # Test reels feed
        start_time = time.time()
        response = self.client.get(reverse("reels-feed"), {"feed_type": "for_you"})
        reels_response_time = time.time() - start_time

        self.assertEqual(response.status_code, 200)
        self.assertLess(
            reels_response_time,
            0.5,
            f"Reels feed API too slow: {reels_response_time:.3f}s",
        )
        print(f"Reels feed API response time: {reels_response_time:.3f}s")

        # Test stories feed
        start_time = time.time()
        response = self.client.get(reverse("stories-feed"))
        stories_response_time = time.time() - start_time

        self.assertEqual(response.status_code, 200)
        self.assertLess(
            stories_response_time,
            0.5,
            f"Stories feed API too slow: {stories_response_time:.3f}s",
        )
        print(f"Stories feed API response time: {stories_response_time:.3f}s")

    def test_search_performance(self):
        """Test performance of search endpoints."""
        # Record the start time
        start_time = time.time()

        # Send API request
        response = self.client.get(reverse("search"), {"q": "service"})

        # Calculate response time
        response_time = time.time() - start_time

        # Assert status and performance
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 0.5, f"Search API too slow: {response_time:.3f}s")

        # Log the performance data
        print(f"Search API response time: {response_time:.3f}s")


class DatabasePerformanceTest(TestCase):
    """Test the performance of database operations."""

    def test_bulk_creation_performance(self):
        """Test performance of bulk database creation operations."""
        # Create a large number of users in bulk to test database performance
        start_time = time.time()

        users_to_create = []
        for i in range(1000):
            users_to_create.append(
                User(
                    phone_number=f"1{i:09d}",
                    user_type="customer",
                    is_verified=True,
                    profile_completed=True,
                )
            )

        User.objects.bulk_create(users_to_create)

        bulk_creation_time = time.time() - start_time

        self.assertLess(
            bulk_creation_time,
            2.0,
            f"Bulk creation too slow: {bulk_creation_time:.3f}s",
        )
        print(f"Bulk creation time for 1000 users: {bulk_creation_time:.3f}s")

    def test_complex_query_performance(self):
        """Test performance of complex database queries."""
        # Set up some test data
        location = Location.objects.create(
            address="Test Address",
            city="Riyadh",
            country="Saudi Arabia",
            latitude=24.7136,
            longitude=46.6753,
        )

        company = Company.objects.create(
            name="Test Company",
            contact_phone="1234567890",
            owner=User.objects.create(
                phone_number="1234567890",
                user_type="customer",
                is_verified=True,
                profile_completed=True,
            ),
            location=location,
        )

        # Create 100 shops with different ratings
        shops = []
        for i in range(100):
            shop = Shop.objects.create(
                company=company,
                name=f"Shop {i}",
                phone_number=f"1{i:08d}",
                username=f"shop{i}",
                location=location,
            )
            shops.append(shop)

        # Create 300 services across different shops
        services = []
        category = Category.objects.create(name="Test Category")
        for i in range(300):
            shop = shops[i % len(shops)]
            service = Service.objects.create(
                shop=shop,
                category=category,
                name=f"Service {i}",
                price=50.00 + (i * 0.5),
                duration=30 + (i % 3) * 15,
                slot_granularity=15,
                buffer_before=5,
                buffer_after=5,
                service_location=["in_shop", "in_home", "both"][i % 3],
            )
            services.append(service)

        # Test a complex query that joins multiple tables
        start_time = time.time()

        # Complex query with filtering, ordering, and annotations
        from django.db.models import Count, Q

        result = (
            Service.objects.filter(
                Q(shop__location__city="Riyadh") & (Q(price__gte=50) | Q(duration__lte=60))
            )
            .select_related("shop", "category", "shop__company")
            .annotate(shop_service_count=Count("shop__services", distinct=True))
            .order_by("-price")[:50]
        )

        # Force evaluation of the queryset
        list(result)

        query_time = time.time() - start_time

        self.assertLess(query_time, 0.5, f"Complex query too slow: {query_time:.3f}s")
        print(f"Complex query execution time: {query_time:.3f}s")
