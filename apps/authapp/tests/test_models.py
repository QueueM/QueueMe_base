import datetime

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import OTP, User
from apps.authapp.validators import validate_phone_number


class UserModelTest(TestCase):
    """
    Test case for the User model.
    """

    def setUp(self):
        # Create a basic user for testing
        self.user = User.objects.create(
            phone_number="966501234567",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

    def test_create_user(self):
        """Test creating a regular user."""
        self.assertEqual(self.user.phone_number, "966501234567")
        self.assertEqual(self.user.email, "test@example.com")
        self.assertEqual(self.user.first_name, "Test")
        self.assertEqual(self.user.last_name, "User")
        self.assertEqual(self.user.user_type, "customer")  # Default
        self.assertFalse(self.user.is_staff)
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.user.is_verified)
        self.assertFalse(self.user.profile_completed)

    def test_create_superuser(self):
        """Test creating a superuser."""
        admin = User.objects.create_superuser(phone_number="966507654321", password="testpassword")

        self.assertEqual(admin.phone_number, "966507654321")
        self.assertEqual(admin.user_type, "admin")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.is_verified)
        self.assertTrue(admin.profile_completed)
        self.assertTrue(admin.is_superuser)

    def test_get_full_name(self):
        """Test get_full_name method."""
        self.assertEqual(self.user.get_full_name(), "Test User")

    def test_get_short_name(self):
        """Test get_short_name method."""
        self.assertEqual(self.user.get_short_name(), "Test")

    def test_phone_number_validation(self):
        """Test phone number validation."""
        # Valid formats
        self.assertIsNotNone(validate_phone_number("966501234567"))
        self.assertIsNotNone(validate_phone_number("+966501234567"))
        self.assertIsNotNone(validate_phone_number("0501234567"))
        self.assertIsNotNone(validate_phone_number("501234567"))

        # Invalid formats
        with self.assertRaises(ValidationError):
            validate_phone_number("123")

        with self.assertRaises(ValidationError):
            validate_phone_number("abcdefghijk")

        with self.assertRaises(ValidationError):
            validate_phone_number("9665012345678901234")  # Too long


class OTPModelTest(TestCase):
    """
    Test case for the OTP model.
    """

    def setUp(self):
        # Create a user
        self.user = User.objects.create(phone_number="966501234567", email="test@example.com")

        # Create an OTP
        self.otp = OTP.objects.create(
            user=self.user,
            phone_number=self.user.phone_number,
            code="123456",
            expires_at=timezone.now() + datetime.timedelta(minutes=10),
        )

    def test_create_otp(self):
        """Test OTP creation."""
        self.assertEqual(self.otp.phone_number, "966501234567")
        self.assertEqual(self.otp.code, "123456")
        self.assertFalse(self.otp.is_used)
        self.assertEqual(self.otp.verification_attempts, 0)

        # Related to correct user
        self.assertEqual(self.otp.user, self.user)

    def test_generate_otp(self):
        """Test OTP generation."""
        # Generate a 6-digit OTP
        otp_code = OTP.generate_otp(length=6)
        self.assertEqual(len(otp_code), 6)
        self.assertTrue(otp_code.isdigit())

        # Generate a custom length OTP
        otp_code = OTP.generate_otp(length=8)
        self.assertEqual(len(otp_code), 8)
        self.assertTrue(otp_code.isdigit())

    def test_is_valid(self):
        """Test OTP validation."""
        # Valid OTP
        self.assertTrue(self.otp.is_valid())

        # Used OTP
        self.otp.is_used = True
        self.otp.save()
        self.assertFalse(self.otp.is_valid())

        # Reset for next test
        self.otp.is_used = False
        self.otp.save()

        # Expired OTP
        self.otp.expires_at = timezone.now() - datetime.timedelta(minutes=1)
        self.otp.save()
        self.assertFalse(self.otp.is_valid())

        # Reset for next test
        self.otp.expires_at = timezone.now() + datetime.timedelta(minutes=10)
        self.otp.save()

        # Too many attempts
        self.otp.verification_attempts = 5  # Assuming max is less than this
        self.otp.save()
        self.assertFalse(self.otp.is_valid())
