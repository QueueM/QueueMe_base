from datetime import time, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.categoriesapp.models import Category
from apps.companiesapp.models import Company
from apps.employeeapp.models import Employee
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop, ShopHours
from apps.specialistsapp.models import (
    PortfolioItem,
    Specialist,
    SpecialistService,
    SpecialistWorkingHours,
)
from apps.specialistsapp.services.availability_service import AvailabilityService
from apps.specialistsapp.services.specialist_ranker import SpecialistRanker
from apps.specialistsapp.services.specialist_service import SpecialistService as SpecialistManager


class AvailabilityServiceTests(TestCase):
    """Test the AvailabilityService."""

    def setUp(self):
        # Create necessary objects
        self.owner = User.objects.create(phone_number="1234567890", user_type="admin")
        self.company = Company.objects.create(
            name="Test Company", owner=self.owner, contact_phone="1234567890"
        )
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="1234567890",
            username="testshop",
        )

        # Create shop hours for Sunday (weekday 0)
        self.shop_hours = ShopHours.objects.create(
            shop=self.shop,
            weekday=0,  # Sunday
            from_hour=time(9, 0),  # 9:00 AM
            to_hour=time(17, 0),  # 5:00 PM
            is_closed=False,
        )

        self.category = Category.objects.create(name="Test Category")
        self.service = Service.objects.create(
            name="Test Service",
            shop=self.shop,
            category=self.category,
            price=100.00,
            duration=60,
            slot_granularity=30,
            buffer_before=5,
            buffer_after=5,
            service_location="in_shop",
        )
        self.employee_user = User.objects.create(phone_number="0987654321", user_type="employee")
        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Test",
            last_name="Employee",
        )
        self.specialist = Specialist.objects.create(
            employee=self.employee,
            bio="Test bio",
            experience_years=5,
            experience_level="senior",
        )

        # Create specialist service
        self.specialist_service = SpecialistService.objects.create(
            specialist=self.specialist, service=self.service, is_primary=True
        )

        # Create working hours for Sunday (weekday 0)
        self.working_hours = SpecialistWorkingHours.objects.create(
            specialist=self.specialist,
            weekday=0,  # Sunday
            from_hour=time(10, 0),  # 10:00 AM
            to_hour=time(16, 0),  # 4:00 PM
            is_off=False,
        )

        # Create the availability service
        self.availability_service = AvailabilityService()

        # Next Sunday date
        today = timezone.now().date()
        days_until_sunday = (6 - today.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7  # If today is Sunday, get next Sunday
        self.next_sunday = today + timedelta(days=days_until_sunday)

    def test_get_specialist_availability(self):
        """Test getting specialist availability for a date."""
        # Get availability for next Sunday
        availability = self.availability_service.get_specialist_availability(
            self.specialist.id, self.next_sunday
        )

        # Check that availability is returned
        self.assertIsInstance(availability, list)

        # Should have slots available (specialist works 10-16, service is 60 min,
        # granularity is 30 min, so should have slots at 10:00, 10:30, 11:00, etc. up to 15:00)
        self.assertTrue(len(availability) > 0)

        # Check that the first slot is at 10:00
        self.assertEqual(availability[0]["start"], "10:00")

        # Check that the last slot is at 15:00 (not 15:30, because with 60 min duration
        # a slot starting at 15:30 would end at 16:30, which is after working hours)
        self.assertEqual(availability[-1]["start"], "15:00")

        # Check that each slot has available services
        for slot in availability:
            self.assertTrue("available_services" in slot)
            self.assertTrue(len(slot["available_services"]) > 0)

            # Check service details
            service = slot["available_services"][0]
            self.assertEqual(service["id"], str(self.service.id))
            self.assertEqual(service["name"], self.service.name)
            self.assertEqual(service["duration"], self.service.duration)
            self.assertEqual(service["price"], float(self.service.price))

    def test_availability_respects_shop_hours(self):
        """Test that availability respects shop hours."""
        # Change specialist working hours to be outside shop hours
        self.working_hours.from_hour = time(8, 0)  # 8:00 AM (shop opens at 9)
        self.working_hours.to_hour = time(18, 0)  # 6:00 PM (shop closes at 5)
        self.working_hours.save()

        # Get availability for next Sunday
        availability = self.availability_service.get_specialist_availability(
            self.specialist.id, self.next_sunday
        )

        # Check that availability is returned
        self.assertIsInstance(availability, list)

        # Check that the first slot is at 9:00 (not 8:00, because shop opens at 9)
        self.assertEqual(availability[0]["start"], "09:00")

        # Check that the last slot should be at 16:00 at the latest
        # (not 17:00, because with 60 min duration, it would end at 18:00)
        last_start_time = availability[-1]["start"]
        last_hour, last_minute = map(int, last_start_time.split(":"))
        self.assertTrue(last_hour < 17)

    def test_availability_respects_working_hours(self):
        """Test that availability respects specialist working hours."""
        # Change shop hours to be wider than specialist hours
        self.shop_hours.from_hour = time(8, 0)  # 8:00 AM
        self.shop_hours.to_hour = time(20, 0)  # 8:00 PM
        self.shop_hours.save()

        # Get availability for next Sunday
        availability = self.availability_service.get_specialist_availability(
            self.specialist.id, self.next_sunday
        )

        # Check that availability is returned
        self.assertIsInstance(availability, list)

        # Check that the first slot is at 10:00 (not 8:00, because specialist starts at 10)
        self.assertEqual(availability[0]["start"], "10:00")

        # Check that the last slot is at 15:00 (not later, because specialist ends at 16)
        self.assertEqual(availability[-1]["start"], "15:00")

    def test_availability_with_day_off(self):
        """Test that no availability is returned for days off."""
        # Mark Sunday as day off
        self.working_hours.is_off = True
        self.working_hours.save()

        # Get availability for next Sunday
        availability = self.availability_service.get_specialist_availability(
            self.specialist.id, self.next_sunday
        )

        # Should have no slots available
        self.assertEqual(len(availability), 0)

    def test_availability_with_shop_closed(self):
        """Test that no availability is returned when shop is closed."""
        # Mark shop as closed on Sunday
        self.shop_hours.is_closed = True
        self.shop_hours.save()

        # Get availability for next Sunday
        availability = self.availability_service.get_specialist_availability(
            self.specialist.id, self.next_sunday
        )

        # Should have no slots available
        self.assertEqual(len(availability), 0)


class SpecialistManagerTests(TestCase):
    """Test the SpecialistService (manager)."""

    def setUp(self):
        # Create necessary objects
        self.owner = User.objects.create(phone_number="1234567890", user_type="admin")
        self.company = Company.objects.create(
            name="Test Company", owner=self.owner, contact_phone="1234567890"
        )
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="1234567890",
            username="testshop",
        )
        self.category = Category.objects.create(name="Test Category")
        self.service = Service.objects.create(
            name="Test Service",
            shop=self.shop,
            category=self.category,
            price=100.00,
            duration=60,
            service_location="in_shop",
        )
        self.employee_user = User.objects.create(phone_number="0987654321", user_type="employee")
        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Test",
            last_name="Employee",
        )

        # Create specialist manager
        self.specialist_manager = SpecialistManager()

    def test_create_specialist(self):
        """Test creating a specialist."""
        # Create specialist data
        data = {
            "bio": "Test bio",
            "experience_years": 5,
            "experience_level": "senior",
            "service_ids": [str(self.service.id)],
        }

        # Create specialist
        specialist = self.specialist_manager.create_specialist(self.employee, data)

        # Check that specialist was created correctly
        self.assertEqual(specialist.employee, self.employee)
        self.assertEqual(specialist.bio, "Test bio")
        self.assertEqual(specialist.experience_years, 5)
        self.assertEqual(specialist.experience_level, "senior")

        # Check that service was added
        specialist_services = SpecialistService.objects.filter(specialist=specialist)
        self.assertEqual(specialist_services.count(), 1)
        self.assertEqual(specialist_services.first().service, self.service)
        self.assertEqual(specialist_services.first().is_primary, True)

        # Check that working hours were created
        working_hours = SpecialistWorkingHours.objects.filter(specialist=specialist)
        self.assertEqual(working_hours.count(), 7)  # One for each day of the week

    def test_update_specialist(self):
        """Test updating a specialist."""
        # Create specialist
        specialist = Specialist.objects.create(
            employee=self.employee,
            bio="Original bio",
            experience_years=1,
            experience_level="junior",
        )

        # Create category for expertise
        category = Category.objects.create(name="Expertise Category")

        # Update data
        data = {
            "bio": "Updated bio",
            "experience_years": 10,
            "experience_level": "expert",
            "expertise_ids": [str(category.id)],
        }

        # Update specialist
        updated_specialist = self.specialist_manager.update_specialist(specialist, data)

        # Check that specialist was updated correctly
        self.assertEqual(updated_specialist.bio, "Updated bio")
        self.assertEqual(updated_specialist.experience_years, 10)
        self.assertEqual(updated_specialist.experience_level, "expert")

        # Check that expertise was updated
        self.assertEqual(updated_specialist.expertise.count(), 1)
        self.assertEqual(updated_specialist.expertise.first(), category)

    def test_verify_specialist(self):
        """Test verifying a specialist."""
        # Create specialist
        specialist = Specialist.objects.create(
            employee=self.employee,
            bio="Test bio",
            experience_years=5,
            experience_level="senior",
            is_verified=False,
        )

        # Verify specialist
        verified_specialist = self.specialist_manager.verify_specialist(specialist)

        # Check that specialist was verified
        self.assertTrue(verified_specialist.is_verified)
        self.assertIsNotNone(verified_specialist.verified_at)

    def test_add_service(self):
        """Test adding a service to a specialist."""
        # Create specialist
        specialist = Specialist.objects.create(
            employee=self.employee,
            bio="Test bio",
            experience_years=5,
            experience_level="senior",
        )

        # Add service
        specialist_service = self.specialist_manager.add_service(
            specialist, self.service, {"is_primary": True, "proficiency_level": 5}
        )

        # Check that service was added correctly
        self.assertEqual(specialist_service.specialist, specialist)
        self.assertEqual(specialist_service.service, self.service)
        self.assertEqual(specialist_service.is_primary, True)
        self.assertEqual(specialist_service.proficiency_level, 5)

    def test_update_service(self):
        """Test updating a specialist service."""
        # Create specialist
        specialist = Specialist.objects.create(
            employee=self.employee,
            bio="Test bio",
            experience_years=5,
            experience_level="senior",
        )

        # Create specialist service
        specialist_service = SpecialistService.objects.create(
            specialist=specialist,
            service=self.service,
            is_primary=False,
            proficiency_level=3,
        )

        # Update data
        data = {"is_primary": True, "proficiency_level": 5, "custom_duration": 45}

        # Update service
        updated_service = self.specialist_manager.update_service(specialist_service, data)

        # Check that service was updated correctly
        self.assertEqual(updated_service.is_primary, True)
        self.assertEqual(updated_service.proficiency_level, 5)
        self.assertEqual(updated_service.custom_duration, 45)


class SpecialistRankerTests(TestCase):
    """Test the SpecialistRanker service."""

    def setUp(self):
        # Create necessary objects for multiple specialists
        self.owner = User.objects.create(phone_number="1234567890", user_type="admin")
        self.company = Company.objects.create(
            name="Test Company", owner=self.owner, contact_phone="1234567890"
        )
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="1234567890",
            username="testshop",
        )
        self.category = Category.objects.create(name="Test Category")
        self.service = Service.objects.create(
            name="Test Service",
            shop=self.shop,
            category=self.category,
            price=100.00,
            duration=60,
            service_location="in_shop",
        )

        # Create specialists with different ratings and experience
        self.specialists = []
        for i in range(5):
            employee_user = User.objects.create(phone_number=f"123456789{i}", user_type="employee")
            employee = Employee.objects.create(
                user=employee_user,
                shop=self.shop,
                first_name=f"Test{i}",
                last_name=f"Employee{i}",
            )
            specialist = Specialist.objects.create(
                employee=employee,
                bio=f"Test bio {i}",
                experience_years=i + 1,
                experience_level=[
                    "junior",
                    "intermediate",
                    "senior",
                    "expert",
                    "expert",
                ][i],
                avg_rating=(i + 1),  # Ratings from 1 to 5
                total_bookings=i * 10,  # Bookings 0, 10, 20, 30, 40
                is_verified=(i > 2),  # Last two are verified
            )

            # Add service to specialist
            SpecialistService.objects.create(
                specialist=specialist,
                service=self.service,
                is_primary=True,
                booking_count=i * 5,  # Bookings for this service: 0, 5, 10, 15, 20
            )

            # Add some portfolio items
            for j in range(i):
                PortfolioItem.objects.create(
                    specialist=specialist,
                    title=f"Portfolio {j}",
                    description=f"Description {j}",
                    is_featured=(j == 0),
                )

            self.specialists.append(specialist)

        # Create the ranker
        self.ranker = SpecialistRanker()

    def test_get_top_rated_specialists(self):
        """Test getting top rated specialists."""
        # Get top 3 specialists
        top_specialists = self.ranker.get_top_rated_specialists(limit=3)

        # Should have 3 specialists
        self.assertEqual(len(top_specialists), 3)

        # Should be ordered by our ranking algorithm (which prioritizes rating, bookings, etc.)
        # Specialist 4 should be first (highest rating and more bookings)
        self.assertEqual(top_specialists[0].id, self.specialists[4].id)

        # Then specialist 3, then specialist 2
        self.assertEqual(top_specialists[1].id, self.specialists[3].id)
        self.assertEqual(top_specialists[2].id, self.specialists[2].id)

    def test_rank_specialists_for_service(self):
        """Test ranking specialists for a specific service."""
        # Get top specialists for the service
        service_specialists = self.ranker.rank_specialists_for_service(self.service.id, limit=3)

        # Should have specialists that provide this service
        self.assertEqual(len(service_specialists), 3)

        # Should be ordered by service-specific ranking
        self.assertEqual(service_specialists[0].id, self.specialists[4].id)
        self.assertEqual(service_specialists[1].id, self.specialists[3].id)
        self.assertEqual(service_specialists[2].id, self.specialists[2].id)

    def test_get_similar_specialists(self):
        """Test finding specialists similar to a given specialist."""
        # Get specialists similar to specialist 2
        similar_specialists = self.ranker.get_similar_specialists(self.specialists[2].id, limit=2)

        # Should have 2 specialists
        self.assertEqual(len(similar_specialists), 2)

        # Should not include the reference specialist
        for specialist in similar_specialists:
            self.assertNotEqual(specialist.id, self.specialists[2].id)

        # Should include specialists with similar services
        # Since all provide the same service, similarity will be based on other factors
        # like experience level and rating
