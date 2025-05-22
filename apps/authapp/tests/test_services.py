import datetime
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import OTP, User
from apps.authapp.services.otp_service import OTPService
from apps.authapp.services.phone_verification import PhoneVerificationService
from apps.authapp.services.security_service import SecurityService
from apps.authapp.services.token_service import TokenService


class OTPServiceTest(TestCase):
    """
    Test case for the OTP service.
    """

    def setUp(self):
        # Create a user
        self.user = User.objects.create(
            phone_number="966501234567", email="test@example.com"
        )

        # Clear cache to avoid rate limiting issues
        cache.clear()

    @patch("apps.authapp.signals.send_otp_notification")
    def test_send_otp(self, mock_send):
        """Test sending OTP."""
        # Send OTP
        result = OTPService.send_otp(self.user.phone_number)

        # Check results
        self.assertTrue(result)

        # Verify OTP was created in database
        otp = OTP.objects.filter(
            phone_number=self.user.phone_number, is_used=False
        ).latest("created_at")

        self.assertIsNotNone(otp)
        self.assertEqual(len(otp.code), 6)  # Default length

        # Expiration time should be in the future
        self.assertTrue(otp.expires_at > timezone.now())

    @patch("apps.authapp.services.security_service.SecurityService.is_rate_limited")
    def test_rate_limit(self, mock_rate_limit):
        """Test rate limiting for OTP."""
        # Mock rate limit reached
        mock_rate_limit.return_value = True

        # Attempt to send OTP
        with self.assertRaises(ValueError):
            OTPService.send_otp(self.user.phone_number)

    def test_verify_otp_success(self):
        """Test successful OTP verification."""
        # Create an OTP
        otp = OTP.objects.create(
            user=self.user,
            phone_number=self.user.phone_number,
            code="123456",
            expires_at=timezone.now() + datetime.timedelta(minutes=10),
        )

        # Verify OTP
        result_user = OTPService.verify_otp(self.user.phone_number, "123456")

        # Check results
        self.assertIsNotNone(result_user)
        self.assertEqual(result_user, self.user)

        # Check OTP is marked as used
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_verify_otp_failure(self):
        """Test failed OTP verification."""
        # Create an OTP
        OTP.objects.create(
            user=self.user,
            phone_number=self.user.phone_number,
            code="123456",
            expires_at=timezone.now() + datetime.timedelta(minutes=10),
        )

        # Verify with wrong code
        result_user = OTPService.verify_otp(self.user.phone_number, "wrong")

        # Check results
        self.assertIsNone(result_user)

    def test_verify_expired_otp(self):
        """Test verification with expired OTP."""
        # Create an expired OTP
        OTP.objects.create(
            user=self.user,
            phone_number=self.user.phone_number,
            code="123456",
            expires_at=timezone.now() - datetime.timedelta(minutes=1),
        )

        # Verify with expired OTP
        result_user = OTPService.verify_otp(self.user.phone_number, "123456")

        # Check results
        self.assertIsNone(result_user)


class TokenServiceTest(TestCase):
    """
    Test case for the Token service.
    """

    def setUp(self):
        # Create a user
        self.user = User.objects.create(
            phone_number="966501234567", email="test@example.com", user_type="customer"
        )

    def test_get_tokens_for_user(self):
        """Test token generation."""
        # Generate tokens
        tokens = TokenService.get_tokens_for_user(self.user)

        # Check results
        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)
        self.assertIn("access_expires", tokens)
        self.assertIn("refresh_expires", tokens)

        # Access token should be a string
        self.assertIsInstance(tokens["access"], str)
        self.assertIsInstance(tokens["refresh"], str)

    @patch("rest_framework_simplejwt.tokens.AccessToken")
    def test_get_user_from_token(self, mock_token):
        """Test extracting user from token."""
        # Setup mock
        mock_instance = MagicMock()
        mock_token.return_value = mock_instance
        mock_instance.__getitem__.return_value = str(self.user.id)

        # Get user from token
        result_user = TokenService.get_user_from_token("dummy_token")

        # Check results
        self.assertEqual(result_user, self.user)

    @patch("rest_framework_simplejwt.tokens.AccessToken")
    def test_get_user_from_invalid_token(self, mock_token):
        """Test extracting user from invalid token."""
        # Setup mock to raise exception
        mock_token.side_effect = Exception("Invalid token")

        # Get user from invalid token
        result_user = TokenService.get_user_from_token("invalid_token")

        # Check results
        self.assertIsNone(result_user)


class SecurityServiceTest(TestCase):
    """
    Test case for the Security service.
    """

    def setUp(self):
        # Clear cache
        cache.clear()

    def test_is_rate_limited(self):
        """Test rate limiting."""
        identifier = "test_phone"
        action = "otp"

        # Should not be rate limited initially
        self.assertFalse(SecurityService.is_rate_limited(identifier, action))

        # Make multiple requests
        for _ in range(5):  # Assuming limit is more than this
            SecurityService.is_rate_limited(identifier, action)

        # Should still not be rate limited
        self.assertFalse(SecurityService.is_rate_limited(identifier, action))

        # Clear the rate limit
        SecurityService.clear_rate_limit(identifier, action)

        # Should no longer be rate limited
        self.assertFalse(SecurityService.is_rate_limited(identifier, action))


class PhoneVerificationServiceTest(TestCase):
    """
    Test case for the Phone Verification service.
    """

    def setUp(self):
        # Create a user
        self.user = User.objects.create(
            phone_number="966501234567", email="test@example.com"
        )

        # Create another user for phone change tests
        self.user2 = User.objects.create(
            phone_number="966507654321", email="test2@example.com"
        )

        # Clear cache
        cache.clear()

    @patch("apps.authapp.services.otp_service.OTPService.send_otp")
    def test_start_verification(self, mock_send_otp):
        """Test starting verification process."""
        # Setup mock
        mock_send_otp.return_value = True

        # Start verification for a new number
        result = PhoneVerificationService.start_verification("966500000000")

        # Check results
        self.assertEqual(result["status"], "otp_sent")
        mock_send_otp.assert_called_once_with("966500000000")

    @patch("apps.authapp.services.otp_service.OTPService.send_otp")
    def test_start_verification_existing_verified(self, mock_send_otp):
        """Test starting verification for an already verified number."""
        # Make the user verified
        self.user.is_verified = True
        self.user.save()

        # Start verification for an already verified number
        result = PhoneVerificationService.start_verification(self.user.phone_number)

        # Check results
        self.assertEqual(result["status"], "already_verified")
        mock_send_otp.assert_not_called()

    @patch("apps.authapp.services.otp_service.OTPService.verify_otp")
    def test_complete_verification(self, mock_verify_otp):
        """Test completing verification process."""
        # Setup mock
        mock_verify_otp.return_value = self.user

        # Complete verification
        result = PhoneVerificationService.complete_verification(
            self.user.phone_number, "123456"
        )

        # Check results
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["user"], self.user)

        # User should now be verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)

    @patch("apps.authapp.services.otp_service.OTPService.verify_otp")
    def test_complete_verification_invalid(self, mock_verify_otp):
        """Test completing verification with invalid code."""
        # Setup mock
        mock_verify_otp.return_value = None

        # Complete verification with invalid code
        result = PhoneVerificationService.complete_verification(
            self.user.phone_number, "invalid"
        )

        # Check results
        self.assertEqual(result["status"], "invalid_code")

    @patch("apps.authapp.services.otp_service.OTPService.verify_otp")
    def test_verify_phone_change(self, mock_verify_otp):
        """Test verifying phone number change."""
        # Setup mock
        mock_verify_otp.return_value = True

        # Verify phone change
        new_phone = "966500000000"
        result = PhoneVerificationService.verify_phone_change(
            self.user, new_phone, "123456"
        )

        # Check results
        self.assertEqual(result["status"], "changed")

        # Phone number should be updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, new_phone)

    @patch("apps.authapp.services.otp_service.OTPService.verify_otp")
    def test_verify_phone_change_already_in_use(self, mock_verify_otp):
        """Test verifying phone change to a number already in use."""
        # Try to change to a number already in use
        result = PhoneVerificationService.verify_phone_change(
            self.user, self.user2.phone_number, "123456"
        )

        # Check results
        self.assertEqual(result["status"], "already_in_use")
        mock_verify_otp.assert_not_called()

        # Phone number should not change
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, "966501234567")
