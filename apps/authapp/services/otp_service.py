import datetime
import logging

from django.db import transaction
from django.utils import timezone

from apps.authapp.constants import OTP_EXPIRY_MINUTES, OTP_LENGTH
from apps.authapp.models import OTP, User
from apps.authapp.validators import normalize_phone_number

logger = logging.getLogger(__name__)


class OTPService:
    """
    Service for OTP generation, verification, and management.
    """

    @staticmethod
    @transaction.atomic
    def send_otp(phone_number):
        """
        Generate and send OTP to the provided phone number.

        Args:
            phone_number: The phone number to send OTP to

        Returns:
            bool: True if OTP was generated and sent successfully

        Raises:
            ValueError: If rate limit is exceeded
        """
        # Normalize phone number
        phone_number = normalize_phone_number(phone_number)

        # Check if rate limited
        from apps.authapp.services.security_service import SecurityService

        if SecurityService.is_rate_limited(phone_number, "otp"):
            logger.warning(f"Rate limit exceeded for OTP generation: {phone_number}")
            raise ValueError("Too many OTP requests. Please try again later.")

        # Generate OTP
        code = OTP.generate_otp(length=OTP_LENGTH)

        # Set expiry (configurable minutes from now)
        expires_at = timezone.now() + datetime.timedelta(minutes=OTP_EXPIRY_MINUTES)

        # Get user if exists
        user = User.objects.filter(phone_number=phone_number).first()

        # Deactivate any existing active OTPs for this phone number
        OTP.objects.filter(
            phone_number=phone_number, is_used=False, expires_at__gt=timezone.now()
        ).update(is_used=True)

        # Create OTP record
        OTP.objects.create(
            user=user, phone_number=phone_number, code=code, expires_at=expires_at
        )

        # OTP will be sent via signals.py
        logger.info(f"OTP generated for {phone_number}: {code}")

        return True

    @staticmethod
    @transaction.atomic
    def verify_otp(phone_number, code):
        """
        Verify OTP code for phone number.

        Args:
            phone_number: The phone number to verify
            code: The OTP code to verify

        Returns:
            User object if verification successful, None otherwise
        """
        # Normalize phone number
        phone_number = normalize_phone_number(phone_number)

        # Find the latest valid OTP for this phone number
        otp = (
            OTP.objects.filter(
                phone_number=phone_number, is_used=False, expires_at__gt=timezone.now()
            )
            .order_by("-created_at")
            .first()
        )

        if not otp:
            logger.warning(f"No valid OTP found for {phone_number}")
            return None

        # Increment verification attempts
        otp.verification_attempts += 1
        otp.save(update_fields=["verification_attempts"])

        # Verify code
        if otp.code != code:
            logger.warning(f"Invalid OTP attempt for {phone_number}")
            return None

        # Mark OTP as used
        otp.is_used = True
        otp.save(update_fields=["is_used"])

        # Get or create user
        user, created = User.objects.get_or_create(
            phone_number=phone_number, defaults={"is_verified": True}
        )

        # If user exists, mark as verified
        if not created and not user.is_verified:
            user.is_verified = True
            user.save(update_fields=["is_verified"])

        # Update last login time
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        logger.info(f"OTP verification successful for {phone_number}")
        return user

    @staticmethod
    def check_otp_status(phone_number):
        """
        Check if an unused OTP exists for this phone number and is still valid.
        Useful for determining if we should create a new OTP or reuse existing.

        Args:
            phone_number: The phone number to check

        Returns:
            dict: Status information about existing OTPs
        """
        # Normalize phone number
        phone_number = normalize_phone_number(phone_number)

        # Find the latest OTP for this phone number
        latest_otp = (
            OTP.objects.filter(phone_number=phone_number)
            .order_by("-created_at")
            .first()
        )

        if not latest_otp:
            return {"exists": False, "valid": False, "time_to_expiry": None}

        now = timezone.now()
        is_valid = not latest_otp.is_used and latest_otp.expires_at > now

        # Calculate time to expiry if valid
        time_to_expiry = None
        if is_valid:
            time_to_expiry = (latest_otp.expires_at - now).total_seconds()

        return {
            "exists": True,
            "valid": is_valid,
            "time_to_expiry": time_to_expiry,
            "attempts": latest_otp.verification_attempts,
        }
