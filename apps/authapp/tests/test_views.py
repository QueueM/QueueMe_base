import datetime
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authapp.models import OTP, User


class AuthViewsTest(APITestCase):
    """
    Test case for authentication views.
    """

    def setUp(self):
        # Create a user
        self.user = User.objects.create(
            phone_number="966501234567", email="test@example.com", is_verified=True
        )
        self.user.set_password("testpassword")
        self.user.save()

        # Create an OTP
        self.otp = OTP.objects.create(
            user=self.user,
            phone_number=self.user.phone_number,
            code="123456",
            expires_at=timezone.now() + datetime.timedelta(minutes=10),
        )

    @patch("apps.authapp.services.security_service.SecurityService.is_rate_limited")
    @patch("apps.authapp.services.otp_service.OTPService.send_otp")
    def test_request_otp(self, mock_send_otp, mock_rate_limited):
        """Test requesting OTP."""
        # Setup mocks
        mock_rate_limited.return_value = False
        mock_send_otp.return_value = True

        # Request OTP
        url = reverse("request-otp")
        data = {"phone_number": "966500000000"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_otp.assert_called_once_with("966500000000")

    @patch("apps.authapp.services.security_service.SecurityService.is_rate_limited")
    def test_request_otp_rate_limited(self, mock_rate_limited):
        """Test requesting OTP when rate limited."""
        # Setup mock
        mock_rate_limited.return_value = True

        # Request OTP
        url = reverse("request-otp")
        data = {"phone_number": "966500000000"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch("apps.authapp.services.token_service.TokenService.get_tokens_for_user")
    @patch("apps.authapp.services.otp_service.OTPService.verify_otp")
    def test_verify_otp(self, mock_verify_otp, mock_get_tokens):
        """Test verifying OTP."""
        # Setup mocks
        mock_verify_otp.return_value = self.user
        mock_get_tokens.return_value = {
            "access": "dummy_access",
            "refresh": "dummy_refresh",
            "access_expires": timezone.now() + datetime.timedelta(hours=1),
            "refresh_expires": timezone.now() + datetime.timedelta(days=7),
        }

        # Verify OTP
        url = reverse("verify-otp")
        data = {"phone_number": self.user.phone_number, "code": "123456"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)
        self.assertIn("profile_completed", response.data)
        self.assertIn("user_type", response.data)

        # Verify mocks called
        mock_verify_otp.assert_called_once_with(self.user.phone_number, "123456")
        mock_get_tokens.assert_called_once_with(self.user)

    @patch("apps.authapp.services.otp_service.OTPService.verify_otp")
    def test_verify_otp_invalid(self, mock_verify_otp):
        """Test verifying with invalid OTP."""
        # Setup mock
        mock_verify_otp.return_value = None

        # Verify OTP
        url = reverse("verify-otp")
        data = {"phone_number": self.user.phone_number, "code": "invalid"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.authapp.services.token_service.TokenService.get_tokens_for_user")
    def test_login(self, mock_get_tokens):
        """Test login with credentials."""
        # Setup mock
        mock_get_tokens.return_value = {
            "access": "dummy_access",
            "refresh": "dummy_refresh",
            "access_expires": timezone.now() + datetime.timedelta(hours=1),
            "refresh_expires": timezone.now() + datetime.timedelta(days=7),
        }

        # Login
        url = reverse("login")
        data = {"phone_number": self.user.phone_number, "password": "testpassword"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)

    def test_login_invalid(self):
        """Test login with invalid credentials."""
        # Login with wrong password
        url = reverse("login")
        data = {"phone_number": self.user.phone_number, "password": "wrongpassword"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.authapp.services.token_service.TokenService.refresh_token")
    def test_refresh_token(self, mock_refresh):
        """Test refreshing token."""
        # Setup mock
        mock_refresh.return_value = {"access": "new_access", "refresh": "new_refresh"}

        # Refresh token
        url = reverse("refresh-token")
        data = {"refresh": "dummy_refresh"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    @patch("apps.authapp.services.token_service.TokenService.refresh_token")
    def test_refresh_token_invalid(self, mock_refresh):
        """Test refreshing with invalid token."""
        # Setup mock
        mock_refresh.side_effect = Exception("Invalid token")

        # Refresh token
        url = reverse("refresh-token")
        data = {"refresh": "invalid_refresh"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout(self):
        """Test logout."""
        # Login first
        self.client.force_authenticate(user=self.user)

        # Logout
        url = reverse("logout")
        response = self.client.post(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class UserProfileViewsTest(APITestCase):
    """
    Test case for user profile views.
    """

    def setUp(self):
        # Create a user
        self.user = User.objects.create(
            phone_number="966501234567", email="test@example.com", is_verified=True
        )

        # Authenticate
        self.client.force_authenticate(user=self.user)

    def test_retrieve_profile(self):
        """Test retrieving user profile."""
        url = reverse("profile")
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone_number"], self.user.phone_number)
        self.assertEqual(response.data["email"], self.user.email)

    def test_update_profile(self):
        """Test updating user profile."""
        url = reverse("profile")
        data = {
            "first_name": "Updated",
            "last_name": "User",
            "email": "updated@example.com",
            "language_preference": "ar",
        }
        response = self.client.put(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check user was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.last_name, "User")
        self.assertEqual(self.user.email, "updated@example.com")
        self.assertEqual(self.user.language_preference, "ar")
        self.assertTrue(self.user.profile_completed)

    def test_partial_update_profile(self):
        """Test partially updating user profile."""
        url = reverse("profile")
        data = {"first_name": "Partial"}
        response = self.client.patch(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check only specified field was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Partial")
        self.assertEqual(self.user.email, "test@example.com")  # Unchanged

    @patch("apps.authapp.services.phone_verification.PhoneVerificationService.start_verification")
    def test_change_phone_request(self, mock_start):
        """Test requesting phone number change."""
        # Setup mock
        mock_start.return_value = {
            "status": "otp_sent",
            "message": "Verification code sent successfully.",
        }

        # Request phone change
        url = reverse("user-profile-change-phone")
        data = {"phone_number": "966500000000"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_start.assert_called_once_with("966500000000")

    @patch("apps.authapp.services.phone_verification.PhoneVerificationService.verify_phone_change")
    def test_verify_new_phone(self, mock_verify):
        """Test verifying new phone number."""
        # Setup mock
        mock_verify.return_value = {
            "status": "changed",
            "message": "Phone number changed successfully.",
        }

        # Verify new phone
        url = reverse("user-profile-verify-new-phone")
        data = {"phone_number": "966500000000", "code": "123456"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_verify.assert_called_once_with(self.user, "966500000000", "123456")

    def test_change_language(self):
        """Test changing language preference."""
        url = reverse("change-language")
        data = {"language": "ar"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check language was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.language_preference, "ar")
