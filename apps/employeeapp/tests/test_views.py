import uuid
from datetime import datetime, timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.authapp.models import User
from apps.employeeapp.models import Employee, EmployeeLeave, EmployeeWorkingHours
from apps.shopapp.models import Shop


class EmployeeViewSetTest(APITestCase):
    """Test employee viewset"""

    def setUp(self):
        """Set up test data"""
        # Create admin user
        self.admin_user = User.objects.create_user(
            phone_number="1111111111",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )

        # Create shop manager user
        self.manager_user = User.objects.create_user(
            phone_number="2222222222", user_type="employee"
        )

        # Create regular employee user
        self.employee_user = User.objects.create_user(
            phone_number="3333333333", user_type="employee"
        )

        # Create customer user
        self.customer_user = User.objects.create_user(
            phone_number="4444444444", user_type="customer"
        )

        # Create shop
        self.shop = Shop.objects.create(id=uuid.uuid4(), name="Test Shop")

        # Create manager employee
        self.manager = Employee.objects.create(
            user=self.manager_user,
            shop=self.shop,
            first_name="Manager",
            last_name="User",
            position="manager",
        )

        # Create regular employee
        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Employee",
            last_name="User",
            position="specialist",
        )

        # Set up clients
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin_user)

        self.manager_client = APIClient()
        self.manager_client.force_authenticate(user=self.manager_user)

        self.employee_client = APIClient()
        self.employee_client.force_authenticate(user=self.employee_user)

        self.customer_client = APIClient()
        self.customer_client.force_authenticate(user=self.customer_user)

        # Set up URLs
        self.list_url = reverse("employee-list")
        self.detail_url = reverse("employee-detail", args=[self.employee.id])
        self.me_url = reverse("employee-me")

    def test_employee_list(self):
        """Test listing employees"""
        # Admin should see all employees
        response = self.admin_client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

        # Manager should see employees from their shop
        # Note: In real app, this would check permissions via rolesapp
        response = self.manager_client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Customer should not access employees
        response = self.customer_client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_detail(self):
        """Test retrieving employee details"""
        # Admin should see employee details
        response = self.admin_client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Employee")

        # Employee should see their own details
        response = self.employee_client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Customer should not access employee details
        response = self.customer_client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_me(self):
        """Test retrieving current employee profile"""
        # Employee should see their own profile
        response = self.employee_client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Employee")

        # Customer should get 404 (no employee profile)
        response = self.customer_client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_employee(self):
        """Test creating a new employee"""
        # Admin should be able to create employee
        new_employee_data = {
            "first_name": "New",
            "last_name": "Employee",
            "position": "cashier",
            "phone_number": "5555555555",
            "shop": str(self.shop.id),
        }

        response = self.admin_client.post(
            self.list_url, new_employee_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Employee.objects.count(), 3)

        # Verify employee was created with correct data
        new_employee = Employee.objects.get(first_name="New")
        self.assertEqual(new_employee.last_name, "Employee")
        self.assertEqual(new_employee.position, "cashier")


class EmployeeWorkingHoursViewSetTest(APITestCase):
    """Test employee working hours viewset"""

    def setUp(self):
        """Set up test data"""
        # Create admin user
        self.admin_user = User.objects.create_user(
            phone_number="1111111111",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )

        # Create employee user
        self.employee_user = User.objects.create_user(
            phone_number="3333333333", user_type="employee"
        )

        # Create shop
        self.shop = Shop.objects.create(id=uuid.uuid4(), name="Test Shop")

        # Create employee
        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Employee",
            last_name="User",
            position="specialist",
        )

        # Set up clients
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin_user)

        self.employee_client = APIClient()
        self.employee_client.force_authenticate(user=self.employee_user)

        # Set up URLs
        self.list_url = reverse("employee-working-hours-list", args=[self.employee.id])

    def test_list_working_hours(self):
        """Test listing working hours"""
        # Create some working hours
        for weekday in range(7):
            EmployeeWorkingHours.objects.create(
                employee=self.employee,
                weekday=weekday,
                from_hour="09:00:00",
                to_hour="17:00:00",
                is_day_off=(weekday == 5),  # Friday off
            )

        # Admin should see all working hours
        response = self.admin_client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 7)

        # Employee should see their own working hours
        response = self.employee_client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 7)

    def test_create_working_hours(self):
        """Test creating working hours"""
        working_hours_data = {
            "weekday": 0,  # Sunday
            "from_hour": "09:00",
            "to_hour": "17:00",
            "is_day_off": False,
        }

        # Admin should be able to create working hours
        response = self.admin_client.post(
            self.list_url, working_hours_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify working hours were created
        working_hours = EmployeeWorkingHours.objects.get(
            employee=self.employee, weekday=0
        )
        self.assertEqual(working_hours.from_hour.strftime("%H:%M"), "09:00")
        self.assertEqual(working_hours.to_hour.strftime("%H:%M"), "17:00")
        self.assertFalse(working_hours.is_day_off)


class EmployeeLeaveViewSetTest(APITestCase):
    """Test employee leave viewset"""

    def setUp(self):
        """Set up test data"""
        # Create admin user
        self.admin_user = User.objects.create_user(
            phone_number="1111111111",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )

        # Create manager user
        self.manager_user = User.objects.create_user(
            phone_number="2222222222", user_type="employee"
        )

        # Create employee user
        self.employee_user = User.objects.create_user(
            phone_number="3333333333", user_type="employee"
        )

        # Create shop
        self.shop = Shop.objects.create(id=uuid.uuid4(), name="Test Shop")

        # Create manager
        self.manager = Employee.objects.create(
            user=self.manager_user,
            shop=self.shop,
            first_name="Manager",
            last_name="User",
            position="manager",
        )

        # Create employee
        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Employee",
            last_name="User",
            position="specialist",
        )

        # Set up clients
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin_user)

        self.manager_client = APIClient()
        self.manager_client.force_authenticate(user=self.manager_user)

        self.employee_client = APIClient()
        self.employee_client.force_authenticate(user=self.employee_user)

        # Set up URLs
        self.list_url = reverse("employee-leaves-list", args=[self.employee.id])

    def test_list_leaves(self):
        """Test listing leaves"""
        # Create leave request
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=5)

        leave = EmployeeLeave.objects.create(
            employee=self.employee,
            leave_type="vacation",
            start_date=start_date,
            end_date=end_date,
            reason="Annual vacation",
        )

        # Admin should see leave
        response = self.admin_client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        # Employee should see their own leave
        response = self.employee_client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_leave(self):
        """Test creating leave request"""
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=5)

        leave_data = {
            "leave_type": "vacation",
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "reason": "Annual vacation",
        }

        # Employee should be able to create leave request
        response = self.employee_client.post(self.list_url, leave_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify leave was created
        leave = EmployeeLeave.objects.get(employee=self.employee)
        self.assertEqual(leave.leave_type, "vacation")
        self.assertEqual(leave.status, "pending")  # Default status
