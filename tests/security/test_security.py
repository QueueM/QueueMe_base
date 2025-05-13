# tests/security/test_security.py
"""
Security tests for Queue Me API.

This module contains tests that verify the security measures implemented
in the Queue Me platform, including authentication, authorization,
input validation, and protection against common vulnerabilities.
"""

from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.authapp.models import OTP, User
from apps.bookingapp.models import Appointment
from apps.categoriesapp.models import Category
from apps.companiesapp.models import Company
from apps.employeeapp.models import Employee
from apps.geoapp.models import Location
from apps.rolesapp.models import Permission, Role, UserRole
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop


class AuthenticationSecurityTest(TestCase):
    """Test authentication security measures."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create(
            phone_number="1234567890",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        # Create test OTP
        expiry_time = timezone.now() + timedelta(minutes=10)
        self.otp = OTP.objects.create(
            phone_number="1234567890",
            code="123456",
            expires_at=expiry_time,
            is_used=False,
            user=self.user,
        )

    def test_otp_rate_limiting(self):
        """Test OTP request rate limiting."""
        # Send multiple OTP requests to trigger rate limiting
        for _ in range(6):  # Assuming rate limit is 5 requests per minute
            response = self.client.post(
                reverse("auth-request-otp"),
                {"phone_number": "9876543210"},
                format="json",
            )

        # The last request should be rate limited
        self.assertEqual(response.status_code, 429)

    def test_otp_expiry(self):
        """Test OTP expires after the specified period."""
        # Create an expired OTP
        expired_otp = OTP.objects.create(
            phone_number="9876543210",
            code="654321",
            expires_at=timezone.now() - timedelta(minutes=1),
            is_used=False,
        )

        # Try to verify with the expired OTP
        response = self.client.post(
            reverse("auth-verify-otp"),
            {"phone_number": "9876543210", "code": "654321"},
            format="json",
        )

        # Should fail verification
        self.assertEqual(response.status_code, 400)

    # tests/security/test_security.py (continued)
    def test_invalid_jwt_token(self):
        """Test system rejects invalid JWT tokens."""
        # Set an invalid token
        self.client.credentials(
            HTTP_AUTHORIZATION="Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )

        # Try to access a protected endpoint
        response = self.client.get(reverse("user-profile"))

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, 401)

    def test_token_expiry(self):
        """Test JWT tokens expire after configured lifetime."""
        import time

        from apps.authapp.services.token_service import TokenService

        # Generate a short-lived token for testing
        # Note: This requires modifying the token service to allow short lifetimes for testing
        token = TokenService.get_test_token_with_short_lifetime(self.user, lifetime_seconds=1)

        # Wait for token to expire
        time.sleep(2)

        # Try to use the expired token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get(reverse("user-profile"))

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, 401)

    def test_used_otp_rejected(self):
        """Test that an OTP can't be used twice."""
        # First verification (should succeed)
        response1 = self.client.post(
            reverse("auth-verify-otp"),
            {"phone_number": "1234567890", "code": "123456"},
            format="json",
        )

        self.assertEqual(response1.status_code, 200)

        # Second verification with same OTP (should fail)
        response2 = self.client.post(
            reverse("auth-verify-otp"),
            {"phone_number": "1234567890", "code": "123456"},
            format="json",
        )

        self.assertEqual(response2.status_code, 400)


class AuthorizationSecurityTest(TestCase):
    """Test authorization security measures."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create users with different roles
        self.customer = User.objects.create(
            phone_number="1234567890",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        self.employee_user = User.objects.create(
            phone_number="2345678901",
            user_type="employee",
            is_verified=True,
            profile_completed=True,
        )

        self.admin_user = User.objects.create(
            phone_number="3456789012",
            user_type="admin",
            is_verified=True,
            profile_completed=True,
            is_staff=True,
        )

        # Create location
        self.location = Location.objects.create(
            address="123 Test Street",
            city="Riyadh",
            country="Saudi Arabia",
            latitude=24.7136,
            longitude=46.6753,
        )

        # Create company and shop
        self.company = Company.objects.create(
            name="Test Company",
            contact_phone="4567890123",
            owner=self.customer,
            location=self.location,
        )

        self.shop = Shop.objects.create(
            company=self.company,
            name="Test Shop",
            phone_number="5678901234",
            username="testshop",
            location=self.location,
        )

        # Create employee
        self.employee = Employee.objects.create(
            user=self.employee_user,
            shop=self.shop,
            first_name="Test",
            last_name="Employee",
            position="manager",
        )

        # Create roles and permissions
        self.shop_manager_role = Role.objects.create(
            name="Shop Manager", role_type="shop_manager", shop=self.shop
        )

        # Add permissions
        for resource in ["booking", "service", "specialist", "employee"]:
            for action in ["view", "add", "edit", "delete"]:
                permission, _ = Permission.objects.get_or_create(resource=resource, action=action)
                self.shop_manager_role.permissions.add(permission)

        # Assign role to employee
        UserRole.objects.create(user=self.employee_user, role=self.shop_manager_role)

        # Create service
        self.category = Category.objects.create(name="Test Category")
        self.service = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Test Service",
            price=100.00,
            duration=60,
            slot_granularity=30,
            buffer_before=5,
            buffer_after=5,
            service_location="in_shop",
        )

        # Get tokens
        from apps.authapp.services.token_service import TokenService

        self.customer_token = TokenService.get_tokens_for_user(self.customer)["access"]
        self.employee_token = TokenService.get_tokens_for_user(self.employee_user)["access"]
        self.admin_token = TokenService.get_tokens_for_user(self.admin_user)["access"]

    def test_role_based_access_control(self):
        """Test that users can only access resources based on their roles."""
        # 1. Customer should not be able to access shop management endpoints
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.customer_token}")

        response = self.client.get(reverse("shop-services-manage", args=[self.shop.id]))

        self.assertEqual(response.status_code, 403)

        # 2. Employee should be able to access shop management for their shop
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.employee_token}")

        response = self.client.get(reverse("shop-services-manage", args=[self.shop.id]))

        self.assertEqual(response.status_code, 200)

        # 3. Admin should be able to access any shop management
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")

        response = self.client.get(reverse("shop-services-manage", args=[self.shop.id]))

        self.assertEqual(response.status_code, 200)

    def test_cross_shop_access_prevention(self):
        """Test that employees can't access data from other shops."""
        # Create a second shop and service
        shop2 = Shop.objects.create(
            company=self.company,
            name="Test Shop 2",
            phone_number="6789012345",
            username="testshop2",
            location=self.location,
        )

        service2 = Service.objects.create(
            shop=shop2,
            category=self.category,
            name="Test Service 2",
            price=150.00,
            duration=90,
            slot_granularity=30,
            buffer_before=5,
            buffer_after=5,
            service_location="in_shop",
        )

        # Employee tries to access service from another shop
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.employee_token}")

        response = self.client.get(reverse("shop-services-manage", args=[shop2.id]))

        self.assertEqual(response.status_code, 403)

    def test_resource_owner_validation(self):
        """Test that users can only modify their own resources."""
        # Create a second customer
        customer2 = User.objects.create(
            phone_number="7890123456",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        # Get token for second customer
        from apps.authapp.services.token_service import TokenService

        customer2_token = TokenService.get_tokens_for_user(customer2)["access"]

        # Create a booking for the first customer
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        start_time = time.min.replace(hour=10, minute=0, second=0, microsecond=0)
        start_datetime = datetime.combine(tomorrow, start_time)
        end_datetime = start_datetime + timedelta(minutes=60)

        booking = Appointment.objects.create(
            customer=self.customer,
            service=self.service,
            specialist=None,
            shop=self.shop,
            start_time=start_datetime,
            end_time=end_datetime,
            status="scheduled",
        )

        # Second customer tries to cancel first customer's booking
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {customer2_token}")

        response = self.client.post(
            reverse("bookings-cancel", args=[booking.id]),
            {"reason": "Testing"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)  # Should not even find the booking


class InputValidationTest(TestCase):
    """Test input validation security measures."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create(
            phone_number="1234567890",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        # Get token
        from apps.authapp.services.token_service import TokenService

        self.token = TokenService.get_tokens_for_user(self.user)["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_invalid_phone_number_rejected(self):
        """Test that invalid phone numbers are rejected."""
        response = self.client.post(
            reverse("auth-request-otp"),
            {"phone_number": "abc123"},  # Invalid phone number
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_xss_attempt_sanitized(self):
        """Test that XSS attempts are sanitized."""
        # Create basic data needed
        location = Location.objects.create(
            address="123 Test Street",
            city="Riyadh",
            country="Saudi Arabia",
            latitude=24.7136,
            longitude=46.6753,
        )

        company = Company.objects.create(
            name="Test Company",
            contact_phone="4567890123",
            owner=self.user,
            location=location,
        )

        # Try to create a shop with XSS in the name
        response = self.client.post(
            reverse("shops-list"),
            {
                "company_id": str(company.id),
                "name": '<script>alert("XSS")</script>Malicious Shop',
                "phone_number": "9876543210",
                "username": "maliciousshop",
                "location": {
                    "address": "123 Evil St",
                    "city": "Riyadh",
                    "country": "Saudi Arabia",
                    "latitude": 24.7136,
                    "longitude": 46.6753,
                },
            },
            format="json",
        )

        # Should either reject or sanitize
        if response.status_code == 201:
            shop_data = response.json()
            self.assertNotIn("<script>", shop_data["name"])
        else:
            self.assertEqual(response.status_code, 400)

    def test_sql_injection_prevention(self):
        """Test that SQL injection attempts are prevented."""
        # Try a basic SQL injection attack in a query parameter
        response = self.client.get(reverse("shops-list") + "?name=Test' OR '1'='1")

        # Should still return a valid response, not a 500 error
        self.assertNotEqual(response.status_code, 500)

        # Alternatively, can verify that no unexpected data is returned
        shops_data = response.json()
        self.assertLessEqual(len(shops_data["results"]), 0)


class DataPrivacyTest(TestCase):
    """Test data privacy and information leakage prevention."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create users
        self.customer1 = User.objects.create(
            phone_number="1234567890",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        self.customer2 = User.objects.create(
            phone_number="2345678901",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        # Create location
        self.location = Location.objects.create(
            address="123 Test Street",
            city="Riyadh",
            country="Saudi Arabia",
            latitude=24.7136,
            longitude=46.6753,
        )

        # Create company and shop
        self.company = Company.objects.create(
            name="Test Company",
            contact_phone="4567890123",
            owner=self.customer1,
            location=self.location,
        )

        self.shop = Shop.objects.create(
            company=self.company,
            name="Test Shop",
            phone_number="5678901234",
            username="testshop",
            location=self.location,
        )

        # Create service
        self.category = Category.objects.create(name="Test Category")
        self.service = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Test Service",
            price=100.00,
            duration=60,
            slot_granularity=30,
            buffer_before=5,
            buffer_after=5,
            service_location="in_shop",
        )

        # Create bookings for both customers
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        start_time = time.min.replace(hour=10, minute=0, second=0, microsecond=0)
        start_datetime = datetime.combine(tomorrow, start_time)
        end_datetime = start_datetime + timedelta(minutes=60)

        self.booking1 = Appointment.objects.create(
            customer=self.customer1,
            service=self.service,
            specialist=None,
            shop=self.shop,
            start_time=start_datetime,
            end_time=end_datetime,
            status="scheduled",
        )

        start_time2 = time.min.replace(hour=14, minute=0, second=0, microsecond=0)
        start_datetime2 = datetime.combine(tomorrow, start_time2)
        end_datetime2 = start_datetime2 + timedelta(minutes=60)

        self.booking2 = Appointment.objects.create(
            customer=self.customer2,
            service=self.service,
            specialist=None,
            shop=self.shop,
            start_time=start_datetime2,
            end_time=end_datetime2,
            status="scheduled",
        )

        # Get tokens
        from apps.authapp.services.token_service import TokenService

        self.token1 = TokenService.get_tokens_for_user(self.customer1)["access"]
        self.token2 = TokenService.get_tokens_for_user(self.customer2)["access"]

    def test_user_data_isolation(self):
        """Test that users can't access other users' data."""
        # Customer1 logs in and tries to access Customer2's booking
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token1}")

        response = self.client.get(reverse("bookings-detail", args=[self.booking2.id]))

        # Should not find the booking
        self.assertEqual(response.status_code, 404)

        # Customer2 logs in and tries to access Customer1's booking
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token2}")

        response = self.client.get(reverse("bookings-detail", args=[self.booking1.id]))

        # Should not find the booking
        self.assertEqual(response.status_code, 404)

    def test_sensitive_data_exposure_prevention(self):
        """Test that sensitive data is not exposed in responses."""
        # Log in as customer1
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token1}")

        # Get user profile
        response = self.client.get(reverse("user-profile"))

        # Check that sensitive fields are not exposed
        self.assertEqual(response.status_code, 200)
        user_data = response.json()

        # Should not include password hash or security details
        self.assertNotIn("password", user_data)
        self.assertNotIn("jwt_secret", user_data)

        # Check bookings endpoint
        response = self.client.get(reverse("bookings-list"))

        self.assertEqual(response.status_code, 200)
        bookings_data = response.json()

        # Ensure no other customer data is leaked
        for booking in bookings_data["results"]:
            if "customer" in booking:
                # Should only contain minimal customer info
                self.assertNotIn("phone_number", booking["customer"])


# tests/security/test_security.py (continued)
class APISecurityHeadersTest(TestCase):
    """Test security headers in API responses."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

    def test_security_headers_present(self):
        """Test that important security headers are present in responses."""
        response = self.client.get(reverse("api-root"))

        # Check for security headers
        self.assertIn("X-Content-Type-Options", response)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

        self.assertIn("X-Frame-Options", response)
        self.assertEqual(response["X-Frame-Options"], "DENY")

        self.assertIn("X-XSS-Protection", response)
        self.assertEqual(response["X-XSS-Protection"], "1; mode=block")

        self.assertIn("Content-Security-Policy", response)
        # CSP should be restrictive
        csp = response["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)

        self.assertIn("Strict-Transport-Security", response)
        # HSTS with at least 1 year max-age
        hsts = response["Strict-Transport-Security"]
        self.assertIn("max-age=", hsts)
        self.assertIn("includeSubDomains", hsts)


class PermissionsIntegrityTest(TestCase):
    """Test integrity of the permission system."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create shop manager user
        self.manager_user = User.objects.create(
            phone_number="1234567890",
            user_type="employee",
            is_verified=True,
            profile_completed=True,
        )

        # Create customer user
        self.customer = User.objects.create(
            phone_number="2345678901",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

        # Create location
        self.location = Location.objects.create(
            address="123 Test Street",
            city="Riyadh",
            country="Saudi Arabia",
            latitude=24.7136,
            longitude=46.6753,
        )

        # Create company
        self.company = Company.objects.create(
            name="Test Company",
            contact_phone="3456789012",
            owner=self.customer,
            location=self.location,
        )

        # Create shop
        self.shop = Shop.objects.create(
            company=self.company,
            name="Test Shop",
            phone_number="4567890123",
            username="testshop",
            location=self.location,
        )

        # Create employee record for manager
        self.employee = Employee.objects.create(
            user=self.manager_user,
            shop=self.shop,
            first_name="Manager",
            last_name="Test",
            position="manager",
        )

        # Create required permissions
        self.employee_view_perm, _ = Permission.objects.get_or_create(
            resource="employee", action="view"
        )
        self.employee_add_perm, _ = Permission.objects.get_or_create(
            resource="employee", action="add"
        )
        self.employee_edit_perm, _ = Permission.objects.get_or_create(
            resource="employee", action="edit"
        )
        self.employee_delete_perm, _ = Permission.objects.get_or_create(
            resource="employee", action="delete"
        )

        # Create a role with view-only permissions
        self.view_role = Role.objects.create(
            name="Employee Viewer", role_type="shop_employee", shop=self.shop
        )
        self.view_role.permissions.add(self.employee_view_perm)

        # Assign role to manager
        UserRole.objects.create(user=self.manager_user, role=self.view_role)

        # Get token for manager
        from apps.authapp.services.token_service import TokenService

        self.token = TokenService.get_tokens_for_user(self.manager_user)["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_permission_boundaries_respected(self):
        """Test that users can only perform actions they have permission for."""
        # Should be able to view employees
        view_response = self.client.get(reverse("shop-employees-list", args=[self.shop.id]))
        self.assertEqual(view_response.status_code, 200)

        # Should not be able to create employees
        create_data = {
            "user": {"phone_number": "5678901234", "user_type": "employee"},
            "first_name": "New",
            "last_name": "Employee",
            "position": "specialist",
        }

        create_response = self.client.post(
            reverse("shop-employees-create", args=[self.shop.id]),
            create_data,
            format="json",
        )
        self.assertEqual(create_response.status_code, 403)

        # Should not be able to edit employees
        edit_response = self.client.patch(
            reverse("shop-employees-detail", args=[self.shop.id, self.employee.id]),
            {"first_name": "Updated"},
            format="json",
        )
        self.assertEqual(edit_response.status_code, 403)

        # Should not be able to delete employees
        delete_response = self.client.delete(
            reverse("shop-employees-detail", args=[self.shop.id, self.employee.id])
        )
        self.assertEqual(delete_response.status_code, 403)

        # Now add edit permission to role
        self.view_role.permissions.add(self.employee_edit_perm)

        # Should now be able to edit employees
        edit_response_after = self.client.patch(
            reverse("shop-employees-detail", args=[self.shop.id, self.employee.id]),
            {"first_name": "Updated"},
            format="json",
        )
        self.assertEqual(edit_response_after.status_code, 200)


class SecurePasswordResetTest(TestCase):
    """Test security of password reset functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create(
            phone_number="1234567890",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )

    def test_password_reset_requires_verification(self):
        """Test that password reset requires proper verification."""
        # Request password reset
        request_response = self.client.post(
            reverse("auth-request-password-reset"),
            {"phone_number": "1234567890"},
            format="json",
        )

        self.assertEqual(request_response.status_code, 200)

        # Try to reset password without providing OTP
        reset_response = self.client.post(
            reverse("auth-reset-password"),
            {"phone_number": "1234567890", "new_password": "NewSecurePassword123"},
            format="json",
        )

        self.assertEqual(reset_response.status_code, 400)

        # Try to reset with invalid OTP
        reset_response_invalid = self.client.post(
            reverse("auth-reset-password"),
            {
                "phone_number": "1234567890",
                "code": "invalid",
                "new_password": "NewSecurePassword123",
            },
            format="json",
        )

        self.assertEqual(reset_response_invalid.status_code, 400)
