"""
OTP Service Module for QueueMe Backend

This module provides comprehensive OTP (One-Time Password) functionality for user authentication,
verification, and security. It handles OTP generation, verification, and management with
proper error handling, rate limiting, and security features.
"""

import datetime
import logging
import random
from typing import Dict, Optional, Union

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.authapp.constants import (
    MAX_OTP_VERIFICATION_ATTEMPTS,
    OTP_EXPIRY_MINUTES,
    OTP_LENGTH,
)
from apps.authapp.models import OTP, User
from apps.authapp.validators import normalize_phone_number, validate_saudi_phone_number

# Configure logging
logger = logging.getLogger(__name__)


class OTPService:
    """
    Service for OTP generation, verification, and management.

    This service handles:
    - OTP generation with configurable length and expiry
    - OTP verification with attempt tracking
    - Rate limiting for OTP requests
    - Phone number normalization and validation
    - User verification status management

    All methods use database transactions to ensure data consistency.
    """

    @staticmethod
    @transaction.atomic
    def send_otp(phone_number: str) -> bool:
        """
        Generate and send OTP to the provided phone number.

        This method:
        1. Normalizes the phone number to standard format
        2. Checks if the phone number is rate limited
        3. Generates a random OTP code
        4. Deactivates any existing active OTPs for this phone number
        5. Creates a new OTP record
        6. Triggers OTP sending via SMS (handled by signals)

        Args:
            phone_number: The phone number to send OTP to (Saudi format)

        Returns:
            bool: True if OTP was generated and sent successfully

        Raises:
            ValueError: If rate limit is exceeded or phone number is invalid
        """
        # Normalize and validate phone number
        phone_number = normalize_phone_number(phone_number)

        if not validate_saudi_phone_number(phone_number):
            logger.warning(f"Invalid Saudi phone number format: {phone_number}")
            raise ValueError(
                "Invalid phone number format. Please use a valid Saudi phone number."
            )

        # Check if rate limited
        from apps.authapp.services.security_service import SecurityService

        if SecurityService.is_rate_limited(phone_number, "otp"):
            logger.warning(f"Rate limit exceeded for OTP generation: {phone_number}")
            raise ValueError("Too many OTP requests. Please try again later.")

        # Generate OTP
        code = OTPService._generate_secure_otp(length=OTP_LENGTH)

        # Set expiry (configurable minutes from now)
        expires_at = timezone.now() + datetime.timedelta(minutes=OTP_EXPIRY_MINUTES)

        # Get user if exists
        user = User.objects.filter(phone_number=phone_number).first()

        # Deactivate any existing active OTPs for this phone number
        OTP.objects.filter(
            phone_number=phone_number, is_used=False, expires_at__gt=timezone.now()
        ).update(is_used=True)

        # Create OTP record
        otp = OTP.objects.create(
            user=user, phone_number=phone_number, code=code, expires_at=expires_at
        )

        # Log OTP generation (in development only)
        if settings.DEBUG:
            logger.info(f"OTP generated for {phone_number}: {code}")
        else:
            logger.info(f"OTP generated for {phone_number}")

        # OTP will be sent via signals.py
        return True

    @staticmethod
    @transaction.atomic
    def verify_otp(phone_number: str, code: str) -> Optional[User]:
        """
        Verify OTP code for phone number.

        This method:
        1. Normalizes the phone number
        2. Finds the latest valid OTP for this phone number
        3. Tracks verification attempts
        4. Verifies the provided code against the stored OTP
        5. Marks the OTP as used if verification is successful
        6. Updates user verification status if needed

        Args:
            phone_number: The phone number to verify (Saudi format)
            code: The OTP code to verify

        Returns:
            User object if verification successful, None otherwise

        Raises:
            ValueError: If maximum verification attempts exceeded
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

        # Check if maximum verification attempts exceeded
        if otp.verification_attempts >= MAX_OTP_VERIFICATION_ATTEMPTS:
            logger.warning(
                f"Maximum OTP verification attempts exceeded for {phone_number}"
            )
            raise ValueError(
                "Maximum verification attempts exceeded. Please request a new OTP."
            )

        # Increment verification attempts
        otp.verification_attempts += 1
        otp.save(update_fields=["verification_attempts"])

        # Verify code
        if otp.code != code:
            logger.warning(f"Invalid OTP attempt for {phone_number}")
            return None

        # Mark OTP as used
        otp.is_used = True
        otp.verified_at = timezone.now()
        otp.save(update_fields=["is_used", "verified_at"])

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

        # Track successful verification for security monitoring
        from apps.authapp.services.security_service import SecurityService

        SecurityService.track_successful_verification(phone_number)

        return user

    @staticmethod
    def check_otp_status(phone_number: str) -> Dict[str, Union[bool, int, float, None]]:
        """
        Check if an unused OTP exists for this phone number and is still valid.

        This method is useful for determining if we should create a new OTP or reuse existing,
        and for providing feedback to users about remaining time and attempts.

        Args:
            phone_number: The phone number to check (Saudi format)

        Returns:
            dict: Status information about existing OTPs with the following keys:
                - exists: Whether any OTP exists for this phone number
                - valid: Whether a valid (unused and not expired) OTP exists
                - time_to_expiry: Seconds until expiry if valid, None otherwise
                - attempts: Number of verification attempts made if valid
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
            return {
                "exists": False,
                "valid": False,
                "time_to_expiry": None,
                "attempts": 0,
            }

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
            "max_attempts": MAX_OTP_VERIFICATION_ATTEMPTS,
        }

    @staticmethod
    def invalidate_all_otps(phone_number: str) -> int:
        """
        Invalidate all active OTPs for a phone number.

        This is useful when:
        - User requests to cancel OTP verification
        - Account security is compromised
        - User changes phone number

        Args:
            phone_number: The phone number to invalidate OTPs for

        Returns:
            int: Number of OTPs invalidated
        """
        # Normalize phone number
        phone_number = normalize_phone_number(phone_number)

        # Mark all active OTPs as used
        count, _ = OTP.objects.filter(
            phone_number=phone_number, is_used=False, expires_at__gt=timezone.now()
        ).update(is_used=True)

        if count > 0:
            logger.info(f"Invalidated {count} active OTPs for {phone_number}")

        return count

    @staticmethod
    def _generate_secure_otp(length: int = OTP_LENGTH) -> str:
        """
        Generate a secure random OTP of specified length.

        This method uses Python's cryptographically secure random number generator
        to ensure OTP codes cannot be predicted.

        Args:
            length: Length of the OTP code to generate

        Returns:
            str: Generated OTP code
        """
        # Generate random digits
        digits = [str(random.SystemRandom().randint(0, 9)) for _ in range(length)]

        # Join digits into a string
        return "".join(digits)

    @staticmethod
    def get_otp_stats() -> Dict[str, int]:
        """
        Get statistics about OTP usage.

        This method is useful for monitoring and analytics.

        Returns:
            dict: Statistics about OTP usage with the following keys:
                - total_generated: Total number of OTPs generated
                - total_verified: Total number of OTPs successfully verified
                - total_expired: Total number of OTPs that expired without use
                - total_failed: Total number of OTPs that failed verification
        """
        now = timezone.now()

        # Get counts
        total_generated = OTP.objects.count()
        total_verified = OTP.objects.filter(
            is_used=True, verified_at__isnull=False
        ).count()
        total_expired = OTP.objects.filter(expires_at__lt=now, is_used=False).count()
        total_failed = OTP.objects.filter(
            is_used=True, verified_at__isnull=True
        ).count()

        return {
            "total_generated": total_generated,
            "total_verified": total_verified,
            "total_expired": total_expired,
            "total_failed": total_failed,
        }
