import datetime

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.categoriesapp.models import Category
from apps.companiesapp.models import Company
from apps.employeeapp.models import Employee
from apps.serviceapp.models import (
    Service,
    ServiceAvailability,
    ServiceException,
    ServiceFAQ,
    ServiceOverview,
)
from apps.serviceapp.services.availability_service import AvailabilityService
from apps.serviceapp.services.service_service import ServiceService
from apps.shopapp.models import Shop, ShopHours
from apps.specialistsapp.models import (
    Specialist,
    SpecialistService,
    SpecialistWorkingHours,
)


class AvailabilityServiceTest(TestCase):
    """Test the AvailabilityService"""

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

        # Create shop hours (all days 9AM-5PM, closed Friday)
        for weekday in range(7):
            ShopHours.objects.create(
                shop=self.shop,
                weekday=weekday,
                from_hour="09:00:00",
                to_hour="17:00:00",
                is_closed=(weekday == 5),  # Friday is closed
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
            slot_granularity=30,
            buffer_before=0,
            buffer_after=0,
            service_location="in_shop",
            has_custom_availability=False,
        )

        # Create employee for specialist
        self.employee_user = User.objects.create(
            phone_number="9876543210", user_type="employee"
        )

        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Test",
            last_name="Specialist",
        )

        # Create specialist
        self.specialist = Specialist.objects.create(employee=self.employee)

        # Link specialist to service
        self.specialist_service = SpecialistService.objects.create(
            specialist=self.specialist, service=self.service
        )

        # Create specialist working hours (all days 9AM-5PM, off Friday)
        for weekday in range(7):
            SpecialistWorkingHours.objects.create(
                specialist=self.specialist,
                weekday=weekday,
                from_hour="09:00:00",
                to_hour="17:00:00",
                is_off=(weekday == 5),  # Friday is off
            )

    def test_get_service_availability(self):
        """Test getting available time slots for a service"""
        # Test for a valid day (Monday, weekday=1)
        today = timezone.now().date()

        # Find a future Monday
        days_ahead = 1 - today.weekday()
        if days_ahead <= 0:  # If today is Monday or later, go to next week
            days_ahead += 7

        future_monday = today + datetime.timedelta(days=days_ahead)

        # Get availability
        slots = AvailabilityService.get_service_availability(
            self.service.id, future_monday
        )

        # Should have slots from 9AM to 4PM (last slot starts at 4PM, ends at 5PM)
        self.assertTrue(len(slots) > 0)

        # Verify first slot
        first_slot = slots[0]
        self.assertEqual(first_slot["start"], "09:00")
        self.assertEqual(first_slot["duration"], 60)

        # Test for a day when shop is closed (Friday, weekday=5)
        # Find a future Friday
        days_ahead = 5 - today.weekday()
        if days_ahead <= 0:  # If today is Friday or later, go to next week
            days_ahead += 7

        future_friday = today + datetime.timedelta(days=days_ahead)

        # Get availability
        slots = AvailabilityService.get_service_availability(
            self.service.id, future_friday
        )

        # Should have no slots
        self.assertEqual(len(slots), 0)

    def test_custom_availability(self):
        """Test service with custom availability"""
        # Enable custom availability
        self.service.has_custom_availability = True
        self.service.save()

        # Create custom availability (10AM-3PM on Monday)
        ServiceAvailability.objects.create(
            service=self.service,
            weekday=1,  # Monday
            from_hour="10:00:00",
            to_hour="15:00:00",
            is_closed=False,
        )

        # Find a future Monday
        today = timezone.now().date()
        days_ahead = 1 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7

        future_monday = today + datetime.timedelta(days=days_ahead)

        # Get availability
        slots = AvailabilityService.get_service_availability(
            self.service.id, future_monday
        )

        # Should have slots from 10AM to 2PM (last slot starts at 2PM, ends at 3PM)
        self.assertTrue(len(slots) > 0)

        # Verify first slot
        first_slot = slots[0]
        self.assertEqual(first_slot["start"], "10:00")

        # Verify last slot
        last_slot = slots[-1]
        self.assertEqual(last_slot["start"], "14:00")

    def test_service_exception(self):
        """Test service with exception day"""
        # Find a future Monday
        today = timezone.now().date()
        days_ahead = 1 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7

        future_monday = today + datetime.timedelta(days=days_ahead)

        # Create exception (closed on this Monday)
        ServiceException.objects.create(
            service=self.service, date=future_monday, is_closed=True
        )

        # Get availability
        slots = AvailabilityService.get_service_availability(
            self.service.id, future_monday
        )

        # Should have no slots
        self.assertEqual(len(slots), 0)

        # Create exception (special hours on this Monday: 11AM-2PM)
        ServiceException.objects.filter(
            service=self.service, date=future_monday
        ).update(is_closed=False, from_hour="11:00:00", to_hour="14:00:00")

        # Get availability again
        slots = AvailabilityService.get_service_availability(
            self.service.id, future_monday
        )

        # Should have slots from 11AM to 1PM (last slot starts at 1PM, ends at 2PM)
        self.assertTrue(len(slots) > 0)

        # Verify first slot
        first_slot = slots[0]
        self.assertEqual(first_slot["start"], "11:00")

        # Verify last slot
        last_slot = slots[-1]
        self.assertEqual(last_slot["start"], "13:00")


class ServiceServiceTest(TestCase):
    """Test the ServiceService"""

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

        # Create employee for specialist
        self.employee_user = User.objects.create(
            phone_number="9876543210", user_type="employee"
        )

        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Test",
            last_name="Specialist",
        )

        # Create specialist
        self.specialist = Specialist.objects.create(employee=self.employee)

    def test_create_service(self):
        """Test creating a service"""
        service_data = {
            "shop_id": self.shop.id,
            "category_id": self.category.id,
            "name": "New Service",
            "description": "New Description",
            "price": 150.00,
            "duration": 90,
            "service_location": "in_shop",
        }

        # Create service
        service = ServiceService.create_service(
            service_data,
            availability_data=[
                {
                    "weekday": 0,
                    "from_hour": "09:00:00",
                    "to_hour": "17:00:00",
                    "is_closed": False,
                }
            ],
            specialist_ids=[str(self.specialist.id)],
        )

        # Verify service
        self.assertEqual(service.name, "New Service")
        self.assertEqual(service.price, 150.00)
        self.assertEqual(service.duration, 90)

        # Verify availability was created
        self.assertTrue(service.has_custom_availability)
        self.assertEqual(ServiceAvailability.objects.filter(service=service).count(), 1)

        # Verify specialist was assigned
        self.assertTrue(
            SpecialistService.objects.filter(
                service=service, specialist=self.specialist
            ).exists()
        )

    def test_update_service(self):
        """Test updating a service"""
        # Create a service first
        service = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Test Service",
            description="Test Description",
            price=100.00,
            duration=60,
            service_location="in_shop",
        )

        # Update data
        update_data = {"name": "Updated Service", "price": 120.00, "duration": 45}

        # Update service
        updated = ServiceService.update_service(service.id, update_data)

        # Verify updates
        self.assertEqual(updated.name, "Updated Service")
        self.assertEqual(updated.price, 120.00)
        self.assertEqual(updated.duration, 45)

    def test_duplicate_service(self):
        """Test duplicating a service"""
        # Create a service with detailed configuration
        service = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Original Service",
            description="Original Description",
            price=100.00,
            duration=60,
            service_location="in_shop",
            has_custom_availability=True,
        )

        # Add availability
        ServiceAvailability.objects.create(
            service=service,
            weekday=0,
            from_hour="09:00:00",
            to_hour="17:00:00",
            is_closed=False,
        )

        # Add FAQs
        ServiceFAQ.objects.create(
            service=service, question="Test Question", answer="Test Answer", order=0
        )

        # Add overview
        ServiceOverview.objects.create(service=service, title="Test Overview", order=0)

        # Assign specialist
        SpecialistService.objects.create(service=service, specialist=self.specialist)

        # Duplicate service
        duplicate = ServiceService.duplicate_service(
            service.id, new_name="Duplicated Service"
        )

        # Verify basic info
        self.assertEqual(duplicate.name, "Duplicated Service")
        self.assertEqual(duplicate.price, 100.00)
        self.assertEqual(duplicate.duration, 60)

        # Verify availability was duplicated
        self.assertEqual(
            ServiceAvailability.objects.filter(service=duplicate).count(),
            ServiceAvailability.objects.filter(service=service).count(),
        )

        # Verify FAQs were duplicated
        self.assertEqual(
            ServiceFAQ.objects.filter(service=duplicate).count(),
            ServiceFAQ.objects.filter(service=service).count(),
        )

        # Verify overviews were duplicated
        self.assertEqual(
            ServiceOverview.objects.filter(service=duplicate).count(),
            ServiceOverview.objects.filter(service=service).count(),
        )

        # Verify specialist was assigned
        self.assertEqual(
            SpecialistService.objects.filter(service=duplicate).count(),
            SpecialistService.objects.filter(service=service).count(),
        )
