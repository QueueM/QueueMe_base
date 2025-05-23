"""
Enhanced authentication and security tests for QueueMe backend

This module provides comprehensive test coverage for authentication flows,
security features, and edge cases in the authentication system.
"""

import json
from datetime import timedelta
from unittest import mock

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authapp.models import OTP, User


class EnhancedAuthenticationTest(TestCase):
    """
    Enhanced test cases for authentication flows and security features.

    This test suite provides comprehensive coverage for:
    - User registration with phone number validation
    - OTP generation, verification, and expiration
    - Login with various credentials
    - Token refresh and validation
    - Password reset flows
    - Account lockout after failed attempts
    - Session management and security
    """

    def setUp(self):
        """Set up test environment"""
        self.client = Client()

        # Create verified user
        self.verified_user = User.objects.create(
            phone_number="966501234567",
            email="verified@example.com",
            first_name="Verified",
            last_name="User",
            user_type="customer",
            is_verified=True,
            profile_completed=True,
        )
        self.verified_user.set_password("correctpassword")
        self.verified_user.save()

        # Create unverified user
        self.unverified_user = User.objects.create(
            phone_number="966502222222",
            email="unverified@example.com",
            first_name="Unverified",
            last_name="User",
            user_type="customer",
            is_verified=False,
            profile_completed=False,
        )
        self.unverified_user.set_password("testpassword")
        self.unverified_user.save()

    def test_registration_with_valid_saudi_phone(self):
        """Test user registration with valid Saudi phone number formats"""
        valid_phone_formats = [
            "966501234567",  # Standard format
            "+966501234567",  # With plus
            "0501234567",  # Local format
            "501234567",  # Short format
        ]

        for phone in valid_phone_formats:
            registration_data = {
                "phone_number": phone,
                "email": f"test_{phone}@example.com",
                "first_name": "Test",
                "last_name": "User",
                "password": "SecurePassword123",
                "user_type": "customer",
            }

            response = self.client.post(
                reverse("api:auth:register"),
                data=json.dumps(registration_data),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            # Verify user was created
            user = User.objects.filter(email=f"test_{phone}@example.com").first()
            self.assertIsNotNone(user)
            self.assertFalse(user.is_verified)  # Should require OTP verification

    def test_registration_with_invalid_phone(self):
        """Test user registration with invalid phone number formats"""
        invalid_phone_formats = [
            "123",  # Too short
            "abcdefghijk",  # Non-numeric
            "9665012345678901234",  # Too long
            "123456789",  # Non-Saudi format
            "+1234567890",  # Non-Saudi country code
        ]

        for phone in invalid_phone_formats:
            registration_data = {
                "phone_number": phone,
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "password": "SecurePassword123",
                "user_type": "customer",
            }

            response = self.client.post(
                reverse("api:auth:register"),
                data=json.dumps(registration_data),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("phone_number", response.json())

    def test_registration_with_existing_phone(self):
        """Test user registration with already registered phone number"""
        registration_data = {
            "phone_number": "966501234567",  # Already used by verified_user
            "email": "new_email@example.com",
            "first_name": "Test",
            "last_name": "User",
            "password": "SecurePassword123",
            "user_type": "customer",
        }

        response = self.client.post(
            reverse("api:auth:register"),
            data=json.dumps(registration_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone_number", response.json())

    def test_registration_with_weak_password(self):
        """Test user registration with weak passwords"""
        weak_passwords = [
            "12345",  # Too short
            "password",  # Common password
            "qwerty",  # Common password
            "123456789",  # Only numbers
        ]

        for password in weak_passwords:
            registration_data = {
                "phone_number": "966509999999",
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "password": password,
                "user_type": "customer",
            }

            response = self.client.post(
                reverse("api:auth:register"),
                data=json.dumps(registration_data),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("password", response.json())

    def test_otp_generation_and_verification(self):
        """Test OTP generation, verification, and expiration"""
        # Request OTP
        otp_request_data = {"phone_number": "966502222222"}  # Unverified user

        response = self.client.post(
            reverse("api:auth:request_otp"),
            data=json.dumps(otp_request_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get the OTP from the database
        otp = (
            OTP.objects.filter(phone_number="966502222222", is_used=False)
            .order_by("-created_at")
            .first()
        )

        self.assertIsNotNone(otp)

        # Test with incorrect OTP
        verify_data = {
            "phone_number": "966502222222",
            "code": "000000",  # Incorrect code
        }

        response = self.client.post(
            reverse("api:auth:verify_otp"),
            data=json.dumps(verify_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Verify OTP verification attempts are tracked
        otp.refresh_from_db()
        self.assertEqual(otp.verification_attempts, 1)

        # Test with correct OTP
        verify_data["code"] = otp.code

        response = self.client.post(
            reverse("api:auth:verify_otp"),
            data=json.dumps(verify_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.json().get("access")
        self.assertIsNotNone(token)

        # Verify user is now verified
        self.unverified_user.refresh_from_db()
        self.assertTrue(self.unverified_user.is_verified)

        # Verify OTP is marked as used
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

        # Try to use the same OTP again
        response = self.client.post(
            reverse("api:auth:verify_otp"),
            data=json.dumps(verify_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_otp_expiration(self):
        """Test OTP expiration"""
        # Create an expired OTP
        expired_otp = OTP.objects.create(
            user=self.unverified_user,
            phone_number=self.unverified_user.phone_number,
            code="123456",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        # Try to verify with expired OTP
        verify_data = {
            "phone_number": self.unverified_user.phone_number,
            "code": expired_otp.code,
        }

        response = self.client.post(
            reverse("api:auth:verify_otp"),
            data=json.dumps(verify_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", response.json())

    def test_otp_max_verification_attempts(self):
        """Test OTP maximum verification attempts"""
        # Create a new OTP
        otp = OTP.objects.create(
            user=self.unverified_user,
            phone_number=self.unverified_user.phone_number,
            code="123456",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        # Try incorrect verification multiple times
        verify_data = {
            "phone_number": self.unverified_user.phone_number,
            "code": "000000",  # Incorrect code
        }

        # Assuming max attempts is 3
        for i in range(3):
            response = self.client.post(
                reverse("api:auth:verify_otp"),
                data=json.dumps(verify_data),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            otp.refresh_from_db()
            self.assertEqual(otp.verification_attempts, i + 1)

        # Try one more time (should be blocked)
        response = self.client.post(
            reverse("api:auth:verify_otp"),
            data=json.dumps(verify_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", response.json())
        self.assertIn("maximum", response.json().get("code", [""])[0].lower())

    def test_login_with_phone_and_password(self):
        """Test login with phone number and password"""
        # Test with correct credentials
        login_data = {"phone_number": "966501234567", "password": "correctpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())

        # Test with incorrect password
        login_data["password"] = "wrongpassword"

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Test with non-existent phone
        login_data["phone_number"] = "966509999999"

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_with_unverified_user(self):
        """Test login with unverified user"""
        login_data = {"phone_number": "966502222222", "password": "testpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        # Should return 401 with specific error about verification
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("verification", response.json().get("detail", "").lower())

    def test_token_refresh(self):
        """Test JWT token refresh"""
        # Login to get tokens
        login_data = {"phone_number": "966501234567", "password": "correctpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        refresh_token = response.json().get("refresh")

        # Use refresh token to get new access token
        refresh_data = {"refresh": refresh_token}

        response = self.client.post(
            reverse("api:auth:token_refresh"),
            data=json.dumps(refresh_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())

        # Test with invalid refresh token
        refresh_data["refresh"] = "invalid_token"

        response = self.client.post(
            reverse("api:auth:token_refresh"),
            data=json.dumps(refresh_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_reset_flow(self):
        """Test password reset flow"""
        # Request password reset
        reset_request_data = {"phone_number": "966501234567"}

        response = self.client.post(
            reverse("api:auth:request_password_reset"),
            data=json.dumps(reset_request_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get the OTP from the database
        otp = (
            OTP.objects.filter(phone_number="966501234567", is_used=False)
            .order_by("-created_at")
            .first()
        )

        self.assertIsNotNone(otp)

        # Reset password with OTP
        reset_data = {
            "phone_number": "966501234567",
            "code": otp.code,
            "new_password": "NewSecurePassword123",
        }

        response = self.client.post(
            reverse("api:auth:reset_password"),
            data=json.dumps(reset_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify OTP is marked as used
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

        # Try to login with new password
        login_data = {
            "phone_number": "966501234567",
            "password": "NewSecurePassword123",
        }

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())

    def test_account_lockout_after_failed_attempts(self):
        """Test account lockout after multiple failed login attempts"""
        # Patch the settings for failed login attempts
        with mock.patch("apps.authapp.views.MAX_FAILED_LOGIN_ATTEMPTS", 3):
            with mock.patch(
                "apps.authapp.views.ACCOUNT_LOCKOUT_DURATION", 10
            ):  # 10 minutes
                # Try incorrect login multiple times
                login_data = {
                    "phone_number": "966501234567",
                    "password": "wrongpassword",
                }

                # Make 3 failed attempts
                for _ in range(3):
                    response = self.client.post(
                        reverse("api:auth:login"),
                        data=json.dumps(login_data),
                        content_type="application/json",
                    )

                    self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

                # Try with correct password (should be locked)
                login_data["password"] = "correctpassword"

                response = self.client.post(
                    reverse("api:auth:login"),
                    data=json.dumps(login_data),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
                self.assertIn("locked", response.json().get("detail", "").lower())

                # Verify user is locked
                self.verified_user.refresh_from_db()
                self.assertIsNotNone(self.verified_user.locked_until)
                self.assertTrue(self.verified_user.locked_until > timezone.now())

    def test_token_validation_and_user_access(self):
        """Test token validation and protected endpoint access"""
        # Login to get token
        login_data = {"phone_number": "966501234567", "password": "correctpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        token = response.json().get("access")

        # Access protected endpoint with token
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        response = self.client.get(reverse("api:auth:user_profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get("phone_number"), "966501234567")

        # Access with invalid token
        self.client.defaults["HTTP_AUTHORIZATION"] = "Bearer invalid_token"

        response = self.client.get(reverse("api:auth:user_profile"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Access without token
        self.client.defaults.pop("HTTP_AUTHORIZATION", None)

        response = self.client.get(reverse("api:auth:user_profile"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_type_permissions(self):
        """Test permissions based on user type"""
        # Create admin user
        admin_user = User.objects.create(
            phone_number="966503333333",
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            user_type="admin",
            is_verified=True,
            is_staff=True,
        )
        admin_user.set_password("adminpassword")
        admin_user.save()

        # Create company user
        company_user = User.objects.create(
            phone_number="966504444444",
            email="company@example.com",
            first_name="Company",
            last_name="User",
            user_type="company",
            is_verified=True,
        )
        company_user.set_password("companypassword")
        company_user.save()

        # Login as admin
        login_data = {"phone_number": "966503333333", "password": "adminpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        admin_token = response.json().get("access")

        # Login as company user
        login_data = {"phone_number": "966504444444", "password": "companypassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        company_token = response.json().get("access")

        # Login as customer
        login_data = {"phone_number": "966501234567", "password": "correctpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        customer_token = response.json().get("access")

        # Test admin-only endpoint
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {admin_token}"
        response = self.client.get(reverse("api:admin:users_list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test with company user (should be forbidden)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {company_token}"
        response = self.client.get(reverse("api:admin:users_list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test with customer (should be forbidden)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {customer_token}"
        response = self.client.get(reverse("api:admin:users_list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test company-only endpoint
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {company_token}"
        response = self.client.get(reverse("api:companies:my_company"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test with customer (should be forbidden)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {customer_token}"
        response = self.client.get(reverse("api:companies:my_company"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_token_expiration(self):
        """Test token expiration"""
        # Get token for user
        refresh = RefreshToken.for_user(self.verified_user)
        access_token = str(refresh.access_token)

        # Access protected endpoint with valid token
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"
        response = self.client.get(reverse("api:auth:user_profile"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Patch the token to be expired
        with mock.patch(
            "rest_framework_simplejwt.tokens.AccessToken.current_time",
            return_value=timezone.now().timestamp() + 86400,
        ):  # Add 1 day
            # Access with expired token
            response = self.client.get(reverse("api:auth:user_profile"))
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertIn("token", response.json().get("detail", "").lower())
            self.assertIn("expired", response.json().get("detail", "").lower())

    def test_concurrent_sessions(self):
        """Test handling of concurrent sessions"""
        # Login from first device
        login_data = {"phone_number": "966501234567", "password": "correctpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        first_token = response.json().get("access")

        # Login from second device
        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        second_token = response.json().get("access")

        # Both tokens should be valid
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {first_token}"
        response = self.client.get(reverse("api:auth:user_profile"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {second_token}"
        response = self.client.get(reverse("api:auth:user_profile"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test logout from first device
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {first_token}"
        response = self.client.post(reverse("api:auth:logout"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # First token should now be invalid
        response = self.client.get(reverse("api:auth:user_profile"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Second token should still be valid
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {second_token}"
        response = self.client.get(reverse("api:auth:user_profile"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_profile_update(self):
        """Test user profile update"""
        # Login
        login_data = {"phone_number": "966501234567", "password": "correctpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        token = response.json().get("access")
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        # Update profile
        profile_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "email": "updated@example.com",
        }

        response = self.client.patch(
            reverse("api:auth:update_profile"),
            data=json.dumps(profile_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify profile was updated
        self.verified_user.refresh_from_db()
        self.assertEqual(self.verified_user.first_name, "Updated")
        self.assertEqual(self.verified_user.last_name, "Name")
        self.assertEqual(self.verified_user.email, "updated@example.com")

        # Try to update with invalid data
        invalid_profile_data = {"email": "not_an_email"}

        response = self.client.patch(
            reverse("api:auth:update_profile"),
            data=json.dumps(invalid_profile_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.json())

    def test_change_password(self):
        """Test password change"""
        # Login
        login_data = {"phone_number": "966501234567", "password": "correctpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        token = response.json().get("access")
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        # Change password
        password_data = {
            "current_password": "correctpassword",
            "new_password": "NewSecurePassword123",
        }

        response = self.client.post(
            reverse("api:auth:change_password"),
            data=json.dumps(password_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Try to login with old password
        self.client.defaults.pop("HTTP_AUTHORIZATION", None)
        login_data["password"] = "correctpassword"

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Login with new password
        login_data["password"] = "NewSecurePassword123"

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())

    def test_csrf_protection(self):
        """Test CSRF protection for sensitive operations"""
        # Login
        login_data = {"phone_number": "966501234567", "password": "correctpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        token = response.json().get("access")

        # Get CSRF token
        self.client.get(reverse("api:auth:csrf_token"))
        csrf_token = self.client.cookies.get("csrftoken").value

        # Try to change password without CSRF token
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        password_data = {
            "current_password": "correctpassword",
            "new_password": "NewSecurePassword123",
        }

        # Disable CSRF protection for this test
        self.client.handler.enforce_csrf_checks = True

        response = self.client.post(
            reverse("api:auth:change_password"),
            data=json.dumps(password_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Try with CSRF token
        self.client.defaults["HTTP_X_CSRFTOKEN"] = csrf_token

        response = self.client.post(
            reverse("api:auth:change_password"),
            data=json.dumps(password_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Reset for other tests
        self.client.handler.enforce_csrf_checks = False


class SecurityHeadersTest(TestCase):
    """Test security headers and protections"""

    def test_security_headers(self):
        """Test security headers are properly set"""
        response = self.client.get(reverse("api:auth:csrf_token"))

        # Check security headers
        self.assertEqual(response.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.get("X-XSS-Protection"), "1; mode=block")
        self.assertTrue(response.get("Strict-Transport-Security"))
        self.assertEqual(
            response.get("Referrer-Policy"), "strict-origin-when-cross-origin"
        )

        # Check Content Security Policy
        csp = response.get("Content-Security-Policy")
        self.assertIsNotNone(csp)
        self.assertIn("default-src", csp)
        self.assertIn("script-src", csp)
        self.assertIn("img-src", csp)
        self.assertIn("style-src", csp)
        self.assertIn("connect-src", csp)
        self.assertIn("frame-ancestors", csp)

        # Check CSRF cookie
        self.assertIsNotNone(response.cookies.get("csrftoken"))
        csrf_cookie = response.cookies.get("csrftoken")
        self.assertTrue(csrf_cookie["secure"])
        self.assertTrue(csrf_cookie["httponly"])
        self.assertEqual(csrf_cookie["samesite"], "Lax")


class APIRateLimitingTest(TestCase):
    """Test API rate limiting"""

    def setUp(self):
        """Set up test environment"""
        self.client = Client()

        # Create test user
        self.user = User.objects.create(
            phone_number="966501234567",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            user_type="customer",
            is_verified=True,
        )
        self.user.set_password("testpassword")
        self.user.save()

    def test_login_rate_limiting(self):
        """Test rate limiting for login endpoint"""
        # Patch the rate limit settings
        with mock.patch("apps.authapp.views.LOGIN_RATE_LIMIT", "3/minute"):
            # Make multiple login attempts
            login_data = {"phone_number": "966501234567", "password": "wrongpassword"}

            # Make 3 requests (should be allowed)
            for _ in range(3):
                response = self.client.post(
                    reverse("api:auth:login"),
                    data=json.dumps(login_data),
                    content_type="application/json",
                )

                self.assertNotEqual(
                    response.status_code, status.HTTP_429_TOO_MANY_REQUESTS
                )

            # Make one more request (should be rate limited)
            response = self.client.post(
                reverse("api:auth:login"),
                data=json.dumps(login_data),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_otp_request_rate_limiting(self):
        """Test rate limiting for OTP request endpoint"""
        # Patch the rate limit settings
        with mock.patch("apps.authapp.views.OTP_REQUEST_RATE_LIMIT", "2/minute"):
            # Make multiple OTP requests
            otp_request_data = {"phone_number": "966501234567"}

            # Make 2 requests (should be allowed)
            for _ in range(2):
                response = self.client.post(
                    reverse("api:auth:request_otp"),
                    data=json.dumps(otp_request_data),
                    content_type="application/json",
                )

                self.assertNotEqual(
                    response.status_code, status.HTTP_429_TOO_MANY_REQUESTS
                )

            # Make one more request (should be rate limited)
            response = self.client.post(
                reverse("api:auth:request_otp"),
                data=json.dumps(otp_request_data),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_api_endpoint_rate_limiting(self):
        """Test rate limiting for general API endpoints"""
        # Login to get token
        login_data = {"phone_number": "966501234567", "password": "testpassword"}

        response = self.client.post(
            reverse("api:auth:login"),
            data=json.dumps(login_data),
            content_type="application/json",
        )

        token = response.json().get("access")
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        # Patch the rate limit settings
        with mock.patch("apps.core.throttling.UserRateThrottle.rate", "5/minute"):
            # Make multiple requests to a protected endpoint
            # Make 5 requests (should be allowed)
            for _ in range(5):
                response = self.client.get(reverse("api:auth:user_profile"))
                self.assertNotEqual(
                    response.status_code, status.HTTP_429_TOO_MANY_REQUESTS
                )

            # Make one more request (should be rate limited)
            response = self.client.get(reverse("api:auth:user_profile"))
            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
