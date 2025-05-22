from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.employeeapp.models import Employee, EmployeeLeave, EmployeeWorkingHours
from apps.shopapp.models import Shop


class EmployeeModelTest(TestCase):
    """Test employee model"""

    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create(phone_number="1234567890", user_type="employee")

        # Create shop (mock)
        self.shop = Shop.objects.create(
            id="550e8400-e29b-41d4-a716-446655440000", name="Test Shop"  # Mock UUID
        )

        # Create employee
        self.employee = Employee.objects.create(
            user=self.user,
            shop=self.shop,
            first_name="John",
            last_name="Doe",
            position="specialist",
        )

    def test_employee_creation(self):
        """Test employee creation"""
        self.assertEqual(self.employee.first_name, "John")
        self.assertEqual(self.employee.last_name, "Doe")
        self.assertEqual(self.employee.position, "specialist")
        self.assertEqual(self.employee.shop, self.shop)
        self.assertEqual(self.employee.user, self.user)

    def test_employee_str(self):
        """Test employee string representation"""
        self.assertEqual(str(self.employee), "John Doe (Specialist)")

    def test_employee_full_name(self):
        """Test employee full_name property"""
        self.assertEqual(self.employee.full_name, "John Doe")

    def test_employee_is_manager(self):
        """Test employee is_manager property"""
        self.assertFalse(self.employee.is_manager)

        # Change to manager
        self.employee.position = "manager"
        self.employee.save()

        # Refresh from DB
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.is_manager)


class EmployeeWorkingHoursTest(TestCase):
    """Test employee working hours model"""

    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create(phone_number="1234567890", user_type="employee")

        # Create shop (mock)
        self.shop = Shop.objects.create(
            id="550e8400-e29b-41d4-a716-446655440000", name="Test Shop"  # Mock UUID
        )

        # Create employee
        self.employee = Employee.objects.create(
            user=self.user,
            shop=self.shop,
            first_name="John",
            last_name="Doe",
            position="specialist",
        )

    def test_working_hours_creation(self):
        """Test working hours creation"""
        working_hours = EmployeeWorkingHours.objects.create(
            employee=self.employee,
            weekday=0,  # Sunday
            from_hour="09:00:00",
            to_hour="17:00:00",
        )

        self.assertEqual(working_hours.weekday, 0)
        self.assertEqual(working_hours.from_hour.strftime("%H:%M"), "09:00")
        self.assertEqual(working_hours.to_hour.strftime("%H:%M"), "17:00")
        self.assertFalse(working_hours.is_day_off)

    def test_invalid_hours(self):
        """Test validation for invalid hours"""
        # End time before start time
        with self.assertRaises(ValidationError):
            hours = EmployeeWorkingHours(
                employee=self.employee,
                weekday=0,
                from_hour="17:00:00",
                to_hour="09:00:00",
            )
            hours.full_clean()

    def test_break_time_validation(self):
        """Test validation for break times"""
        # Break end before break start
        with self.assertRaises(ValidationError):
            hours = EmployeeWorkingHours(
                employee=self.employee,
                weekday=0,
                from_hour="09:00:00",
                to_hour="17:00:00",
                break_start="13:00:00",
                break_end="12:00:00",
            )
            hours.full_clean()

        # Break outside working hours
        with self.assertRaises(ValidationError):
            hours = EmployeeWorkingHours(
                employee=self.employee,
                weekday=0,
                from_hour="09:00:00",
                to_hour="17:00:00",
                break_start="08:00:00",
                break_end="08:30:00",
            )
            hours.full_clean()


class EmployeeLeaveTest(TestCase):
    """Test employee leave model"""

    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create(phone_number="1234567890", user_type="employee")

        # Create approver user
        self.approver = User.objects.create(
            phone_number="9876543210", user_type="admin"
        )

        # Create shop (mock)
        self.shop = Shop.objects.create(
            id="550e8400-e29b-41d4-a716-446655440000", name="Test Shop"  # Mock UUID
        )

        # Create employee
        self.employee = Employee.objects.create(
            user=self.user,
            shop=self.shop,
            first_name="John",
            last_name="Doe",
            position="specialist",
        )

    def test_leave_creation(self):
        """Test leave creation"""
        start_date = timezone.now().date()
        end_date = start_date + timezone.timedelta(days=5)

        leave = EmployeeLeave.objects.create(
            employee=self.employee,
            leave_type="vacation",
            start_date=start_date,
            end_date=end_date,
            reason="Annual vacation",
        )

        self.assertEqual(leave.leave_type, "vacation")
        self.assertEqual(leave.start_date, start_date)
        self.assertEqual(leave.end_date, end_date)
        self.assertEqual(leave.reason, "Annual vacation")
        self.assertEqual(leave.status, "pending")

    def test_leave_approval(self):
        """Test leave approval"""
        start_date = timezone.now().date()
        end_date = start_date + timezone.timedelta(days=5)

        leave = EmployeeLeave.objects.create(
            employee=self.employee,
            leave_type="vacation",
            start_date=start_date,
            end_date=end_date,
        )

        # Approve leave
        leave.status = "approved"
        leave.approved_by = self.approver
        leave.save()

        # Refresh from DB
        leave.refresh_from_db()
        self.assertEqual(leave.status, "approved")
        self.assertEqual(leave.approved_by, self.approver)

    def test_invalid_dates(self):
        """Test validation for invalid dates"""
        start_date = timezone.now().date()
        end_date = start_date - timezone.timedelta(days=5)  # End before start

        with self.assertRaises(ValidationError):
            leave = EmployeeLeave(
                employee=self.employee,
                leave_type="vacation",
                start_date=start_date,
                end_date=end_date,
            )
            leave.full_clean()
