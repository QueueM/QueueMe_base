from datetime import time

from django.test import TestCase

from apps.authapp.models import User
from apps.categoriesapp.models import Category
from apps.companiesapp.models import Company
from apps.employeeapp.models import Employee
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import (
    PortfolioItem,
    Specialist,
    SpecialistService,
    SpecialistWorkingHours,
)


class SpecialistModelTests(TestCase):
    """Test the Specialist model."""

    def setUp(self):
        # Create user for company owner
        self.owner = User.objects.create(phone_number="1234567890", user_type="admin")

        # Create company
        self.company = Company.objects.create(
            name="Test Company", owner=self.owner, contact_phone="1234567890"
        )

        # Create shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="1234567890",
            username="testshop",
        )

        # Create category
        self.category = Category.objects.create(name="Test Category")

        # Create service
        self.service = Service.objects.create(
            name="Test Service",
            shop=self.shop,
            category=self.category,
            price=100.00,
            duration=60,
            service_location="in_shop",
        )

        # Create employee user
        self.employee_user = User.objects.create(phone_number="0987654321", user_type="employee")

        # Create employee
        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Test",
            last_name="Employee",
        )

        # Create specialist
        self.specialist = Specialist.objects.create(
            employee=self.employee,
            bio="Test bio",
            experience_years=5,
            experience_level="senior",
        )

    def test_specialist_creation(self):
        """Test creating a specialist."""
        self.assertEqual(self.specialist.employee, self.employee)
        self.assertEqual(self.specialist.bio, "Test bio")
        self.assertEqual(self.specialist.experience_years, 5)
        self.assertEqual(self.specialist.experience_level, "senior")
        self.assertEqual(self.specialist.is_verified, False)
        self.assertEqual(self.specialist.avg_rating, 0)
        self.assertEqual(self.specialist.total_bookings, 0)

    def test_specialist_str_method(self):
        """Test the string representation of a specialist."""
        expected_str = f"{self.employee.first_name} {self.employee.last_name}"
        self.assertEqual(str(self.specialist), expected_str)

    def test_get_shop_method(self):
        """Test getting the shop a specialist belongs to."""
        self.assertEqual(self.specialist.get_shop(), self.shop)

    def test_update_rating_method(self):
        """Test updating a specialist's rating based on reviews."""
        # Create review model instance using ContentType
        from django.contrib.contenttypes.models import ContentType

        from apps.reviewapp.models import Review

        specialist_type = ContentType.objects.get_for_model(Specialist)

        # Create some reviews
        Review.objects.create(
            content_type=specialist_type,
            object_id=str(self.specialist.id),
            rating=4,
            title="Good",
            comment="Good specialist",
            created_by=self.owner,
        )

        Review.objects.create(
            content_type=specialist_type,
            object_id=str(self.specialist.id),
            rating=5,
            title="Excellent",
            comment="Excellent specialist",
            created_by=self.owner,
        )

        # Update rating
        self.specialist.update_rating()

        # Rating should be average of all reviews
        self.assertEqual(self.specialist.avg_rating, 4.5)


class SpecialistServiceModelTests(TestCase):
    """Test the SpecialistService model."""

    def setUp(self):
        # Create the same setup as above
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
        self.specialist = Specialist.objects.create(
            employee=self.employee,
            bio="Test bio",
            experience_years=5,
            experience_level="senior",
        )

        # Create specialist service
        self.specialist_service = SpecialistService.objects.create(
            specialist=self.specialist,
            service=self.service,
            is_primary=True,
            proficiency_level=4,
            custom_duration=45,
        )

    def test_specialist_service_creation(self):
        """Test creating a specialist service."""
        self.assertEqual(self.specialist_service.specialist, self.specialist)
        self.assertEqual(self.specialist_service.service, self.service)
        self.assertEqual(self.specialist_service.is_primary, True)
        self.assertEqual(self.specialist_service.proficiency_level, 4)
        self.assertEqual(self.specialist_service.custom_duration, 45)
        self.assertEqual(self.specialist_service.booking_count, 0)

    def test_specialist_service_str_method(self):
        """Test the string representation of a specialist service."""
        expected_str = f"{self.employee.first_name} - {self.service.name}"
        self.assertEqual(str(self.specialist_service), expected_str)

    def test_get_effective_duration_method(self):
        """Test getting the effective duration of a service."""
        # With custom duration
        self.assertEqual(self.specialist_service.get_effective_duration(), 45)

        # Without custom duration
        self.specialist_service.custom_duration = None
        self.specialist_service.save()
        self.assertEqual(self.specialist_service.get_effective_duration(), 60)

    def test_increment_booking_count_method(self):
        """Test incrementing the booking count for a service."""
        self.assertEqual(self.specialist_service.booking_count, 0)
        self.assertEqual(self.specialist.total_bookings, 0)

        self.specialist_service.increment_booking_count()

        self.assertEqual(self.specialist_service.booking_count, 1)

        # Refresh specialist from database
        self.specialist.refresh_from_db()
        self.assertEqual(self.specialist.total_bookings, 1)


class SpecialistWorkingHoursModelTests(TestCase):
    """Test the SpecialistWorkingHours model."""

    def setUp(self):
        # Create the same setup as above
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

        # Create working hours for Sunday
        self.working_hours = SpecialistWorkingHours.objects.create(
            specialist=self.specialist,
            weekday=0,  # Sunday
            from_hour=time(9, 0),  # 9:00 AM
            to_hour=time(17, 0),  # 5:00 PM
            is_off=False,
        )

        # Create shop hours for Sunday
        from apps.shopapp.models import ShopHours

        self.shop_hours = ShopHours.objects.create(
            shop=self.shop,
            weekday=0,  # Sunday
            from_hour=time(8, 0),  # 8:00 AM
            to_hour=time(20, 0),  # 8:00 PM
            is_closed=False,
        )

    def test_working_hours_creation(self):
        """Test creating working hours."""
        self.assertEqual(self.working_hours.specialist, self.specialist)
        self.assertEqual(self.working_hours.weekday, 0)
        self.assertEqual(self.working_hours.from_hour, time(9, 0))
        self.assertEqual(self.working_hours.to_hour, time(17, 0))
        self.assertEqual(self.working_hours.is_off, False)

    def test_working_hours_str_method(self):
        """Test the string representation of working hours."""
        expected_str = (
            f"{self.employee.first_name} {self.employee.last_name} - Sunday: 09:00 AM - 05:00 PM"
        )
        self.assertEqual(str(self.working_hours), expected_str)

    def test_overlaps_with_shop_hours_method(self):
        """Test checking if working hours overlap with shop hours."""
        # Working hours within shop hours
        self.assertTrue(self.working_hours.overlaps_with_shop_hours())

        # Update working hours to outside shop hours
        self.working_hours.from_hour = time(7, 0)  # 7:00 AM
        self.working_hours.to_hour = time(21, 0)  # 9:00 PM
        self.working_hours.save()

        # Now it shouldn't overlap (starts before shop opens and ends after it closes)
        self.assertFalse(self.working_hours.overlaps_with_shop_hours())


class PortfolioItemModelTests(TestCase):
    """Test the PortfolioItem model."""

    def setUp(self):
        # Create the same setup as above
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
        self.specialist = Specialist.objects.create(
            employee=self.employee,
            bio="Test bio",
            experience_years=5,
            experience_level="senior",
        )

        # Create portfolio item
        self.portfolio_item = PortfolioItem.objects.create(
            specialist=self.specialist,
            title="Test Portfolio",
            description="Test description",
            service=self.service,
            category=self.category,
            is_featured=True,
        )

    def test_portfolio_item_creation(self):
        """Test creating a portfolio item."""
        self.assertEqual(self.portfolio_item.specialist, self.specialist)
        self.assertEqual(self.portfolio_item.title, "Test Portfolio")
        self.assertEqual(self.portfolio_item.description, "Test description")
        self.assertEqual(self.portfolio_item.service, self.service)
        self.assertEqual(self.portfolio_item.category, self.category)
        self.assertEqual(self.portfolio_item.is_featured, True)
        self.assertEqual(self.portfolio_item.likes_count, 0)

    def test_portfolio_item_str_method(self):
        """Test the string representation of a portfolio item."""
        expected_str = f"{self.employee.first_name} - Test Portfolio"
        self.assertEqual(str(self.portfolio_item), expected_str)

    def test_thumbnail_url_method(self):
        """Test getting the thumbnail URL of a portfolio item."""
        # Without image
        self.assertIsNone(self.portfolio_item.thumbnail_url())

        # With image (would require mocking the image file)
        # Not testing here as it would require more complex setup
