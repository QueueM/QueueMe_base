import uuid

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.categoriesapp.models import Category
from apps.companiesapp.models import Company
from apps.employeeapp.models import Employee
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import (
    Specialist,
    SpecialistService,
    SpecialistWorkingHours,
)


class SpecialistViewSetTests(TestCase):
    """Test the SpecialistViewSet."""

    def setUp(self):
        # Create client
        self.client = APIClient()

        # Create necessary objects
        self.owner = User.objects.create_user(
            phone_number="1234567890",
            password="testpass",
            user_type="admin",
            is_staff=True,
            is_verified=True,
            profile_completed=True,
        )
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

        # Create shop manager
        self.manager_user = User.objects.create_user(
            phone_number="9876543210",
            password="testpass",
            user_type="employee",
            is_verified=True,
            profile_completed=True,
        )
        self.manager = Employee.objects.create(
            user=self.manager_user,
            shop=self.shop,
            first_name="Manager",
            last_name="Test",
            position="manager",
        )

        # Create employee
        self.employee_user = User.objects.create_user(
            phone_number="5555555555",
            password="testpass",
            user_type="employee",
            is_verified=True,
            profile_completed=True,
        )
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

        # Add service to specialist
        self.specialist_service = SpecialistService.objects.create(
            specialist=self.specialist, service=self.service, is_primary=True
        )

        # Create working hours
        self.working_hours = SpecialistWorkingHours.objects.create(
            specialist=self.specialist,
            weekday=0,
            from_hour="09:00:00",
            to_hour="17:00:00",
            is_off=False,
        )

        # Create customer user
        self.customer = User.objects.create_user(
            phone_number="1111111111",
            password="testpass",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        # Set up roles and permissions
        from apps.rolesapp.models import Permission, Role, UserRole

        # Create necessary permissions
        self.view_specialist_perm = Permission.objects.create(
            resource="specialist", action="view"
        )
        self.edit_specialist_perm = Permission.objects.create(
            resource="specialist", action="edit"
        )
        self.verify_specialist_perm = Permission.objects.create(
            resource="specialist", action="verify"
        )

        # Create roles
        self.admin_role = Role.objects.create(name="Admin", role_type="queue_me_admin")
        self.admin_role.permissions.add(
            self.view_specialist_perm,
            self.edit_specialist_perm,
            self.verify_specialist_perm,
        )

        self.shop_manager_role = Role.objects.create(
            name="Shop Manager", role_type="shop_manager", shop=self.shop
        )
        self.shop_manager_role.permissions.add(
            self.view_specialist_perm, self.edit_specialist_perm
        )

        # Assign roles
        UserRole.objects.create(user=self.owner, role=self.admin_role)

        UserRole.objects.create(user=self.manager_user, role=self.shop_manager_role)

    def test_list_specialists(self):
        """Test listing specialists."""
        # Customer can view specialists
        self.client.force_authenticate(user=self.customer)

        url = reverse("specialist-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_retrieve_specialist(self):
        """Test retrieving a specialist."""
        # Customer can view specialist details
        self.client.force_authenticate(user=self.customer)

        url = reverse("specialist-detail", args=[self.specialist.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.specialist.id))
        self.assertEqual(response.data["first_name"], self.employee.first_name)
        self.assertEqual(response.data["last_name"], self.employee.last_name)
        self.assertEqual(response.data["bio"], self.specialist.bio)

    def test_create_specialist(self):
        """Test creating a specialist."""
        # Create a new employee to convert to specialist
        new_employee_user = User.objects.create_user(
            phone_number="9999999999",
            password="testpass",
            user_type="employee",
            is_verified=True,
            profile_completed=True,
        )
        new_employee = Employee.objects.create(
            user=new_employee_user,
            shop=self.shop,
            first_name="New",
            last_name="Employee",
        )

        # Manager can create specialist
        self.client.force_authenticate(user=self.manager_user)

        url = reverse("specialist-list")
        data = {
            "employee_id": str(new_employee.id),
            "bio": "New specialist bio",
            "experience_years": 3,
            "experience_level": "intermediate",
            "service_ids": [str(self.service.id)],
            "working_hours": [
                {
                    "weekday": 0,
                    "from_hour": "10:00:00",
                    "to_hour": "18:00:00",
                    "is_off": False,
                }
            ],
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Specialist.objects.count(), 2)

        # Check that specialist was created correctly
        specialist = Specialist.objects.get(employee=new_employee)
        self.assertEqual(specialist.bio, "New specialist bio")
        self.assertEqual(specialist.experience_years, 3)
        self.assertEqual(specialist.experience_level, "intermediate")

        # Check that service was added
        self.assertEqual(specialist.specialist_services.count(), 1)
        self.assertEqual(specialist.specialist_services.first().service, self.service)

        # Check that working hours were created
        self.assertTrue(
            SpecialistWorkingHours.objects.filter(
                specialist=specialist,
                weekday=0,
                from_hour="10:00:00",
                to_hour="18:00:00",
            ).exists()
        )

    def test_update_specialist(self):
        """Test updating a specialist."""
        # Manager can update specialist
        self.client.force_authenticate(user=self.manager_user)

        url = reverse("specialist-detail", args=[self.specialist.id])
        data = {
            "bio": "Updated bio",
            "experience_years": 10,
            "experience_level": "expert",
        }

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that specialist was updated
        self.specialist.refresh_from_db()
        self.assertEqual(self.specialist.bio, "Updated bio")
        self.assertEqual(self.specialist.experience_years, 10)
        self.assertEqual(self.specialist.experience_level, "expert")

    def test_customer_cannot_create_specialist(self):
        """Test that customers cannot create specialists."""
        self.client.force_authenticate(user=self.customer)

        url = reverse("specialist-list")
        data = {
            "employee_id": str(uuid.uuid4()),
            "bio": "New specialist bio",
            "experience_years": 3,
            "experience_level": "intermediate",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SpecialistServicesViewTests(TestCase):
    """Test the SpecialistServicesView."""

    def setUp(self):
        # Create the same setup as above, but without the APIClient.force_authenticate calls
        self.client = APIClient()

        # Create necessary objects
        self.owner = User.objects.create_user(
            phone_number="1234567890",
            password="testpass",
            user_type="admin",
            is_staff=True,
            is_verified=True,
            profile_completed=True,
        )
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

        # Create a second service
        self.service2 = Service.objects.create(
            name="Test Service 2",
            shop=self.shop,
            category=self.category,
            price=150.00,
            duration=90,
            service_location="in_shop",
        )

        # Create employee
        self.employee_user = User.objects.create_user(
            phone_number="5555555555",
            password="testpass",
            user_type="employee",
            is_verified=True,
            profile_completed=True,
        )
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

        # Add service to specialist
        self.specialist_service = SpecialistService.objects.create(
            specialist=self.specialist, service=self.service, is_primary=True
        )

        # Set up permissions
        from apps.rolesapp.models import Permission, Role, UserRole

        # Create necessary permissions
        self.view_specialist_perm = Permission.objects.create(
            resource="specialist", action="view"
        )
        self.edit_specialist_perm = Permission.objects.create(
            resource="specialist", action="edit"
        )

        # Create roles
        self.admin_role = Role.objects.create(name="Admin", role_type="queue_me_admin")
        self.admin_role.permissions.add(
            self.view_specialist_perm, self.edit_specialist_perm
        )

        # Assign roles
        UserRole.objects.create(user=self.owner, role=self.admin_role)

    def test_list_specialist_services(self):
        """Test listing a specialist's services."""
        # Anyone can view specialist services
        url = reverse("specialist-services", args=[self.specialist.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["service"], str(self.service.id))

    def test_add_service_to_specialist(self):
        """Test adding a service to a specialist."""
        # Admin can add services
        self.client.force_authenticate(user=self.owner)

        url = reverse("specialist-services", args=[self.specialist.id])
        data = {
            "service_id": str(self.service2.id),
            "is_primary": False,
            "proficiency_level": 4,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that service was added
        self.assertEqual(
            SpecialistService.objects.filter(specialist=self.specialist).count(), 2
        )

        # Check details of added service
        new_service = SpecialistService.objects.get(
            specialist=self.specialist, service=self.service2
        )
        self.assertEqual(new_service.is_primary, False)
        self.assertEqual(new_service.proficiency_level, 4)

    def test_update_specialist_service(self):
        """Test updating a specialist service."""
        # Admin can update services
        self.client.force_authenticate(user=self.owner)

        url = reverse(
            "specialist-service-detail",
            args=[self.specialist.id, self.specialist_service.id],
        )
        data = {"is_primary": True, "proficiency_level": 5, "custom_duration": 45}

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that service was updated
        self.specialist_service.refresh_from_db()
        self.assertEqual(self.specialist_service.is_primary, True)
        self.assertEqual(self.specialist_service.proficiency_level, 5)
        self.assertEqual(self.specialist_service.custom_duration, 45)
