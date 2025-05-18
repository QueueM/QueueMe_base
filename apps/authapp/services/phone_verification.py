import logging

from apps.authapp.models import User
from apps.authapp.services.otp_service import OTPService
from apps.authapp.validators import normalize_phone_number

logger = logging.getLogger(__name__)


class PhoneVerificationService:
    """
    Service for phone number verification.
    """

    @staticmethod
    def start_verification(phone_number):
        """
        Start the phone verification process by sending an OTP.

        Args:
            phone_number: Phone number to verify

        Returns:
            dict: Status of verification request
        """
        # Normalize phone number
        phone_number = normalize_phone_number(phone_number)

        # Check if phone is already verified for a user
        existing_user = User.objects.filter(phone_number=phone_number, is_verified=True).first()

        if existing_user:
            return {
                "status": "already_verified",
                "message": "This phone number is already verified.",
            }

        # Send OTP for verification
        try:
            OTPService.send_otp(phone_number)

            return {
                "status": "otp_sent",
                "message": "Verification code sent successfully.",
            }
        except ValueError as e:
            return {"status": "rate_limited", "message": str(e)}
        except Exception as e:
            logger.error(f"Error sending OTP: {str(e)}")
            return {
                "status": "error",
                "message": "Failed to send verification code. Please try again later.",
            }

    @staticmethod
    def complete_verification(phone_number, code):
        """
        Complete phone verification by validating the OTP.

        Args:
            phone_number: Phone number being verified
            code: OTP code to verify

        Returns:
            dict: Verification result with user if successful
        """
        # Normalize phone number
        phone_number = normalize_phone_number(phone_number)

        # Verify OTP
        user = OTPService.verify_otp(phone_number, code)

        if not user:
            return {"status": "invalid_code", "message": "Invalid verification code."}

        # Update user as verified
        user.is_verified = True
        user.save(update_fields=["is_verified"])

        return {
            "status": "verified",
            "message": "Phone number verified successfully.",
            "user": user,
        }

    @staticmethod
    def verify_phone_change(user, new_phone_number, code):
        """
        Verify a phone number change by validating OTP for new number.

        Args:
            user: User requesting the phone change
            new_phone_number: New phone number
            code: OTP code for verification

        Returns:
            dict: Phone change result
        """
        # Normalize phone number
        new_phone_number = normalize_phone_number(new_phone_number)

        # Check if new phone is already in use
        if User.objects.filter(phone_number=new_phone_number).exclude(id=user.id).exists():
            return {
                "status": "already_in_use",
                "message": "This phone number is already in use by another account.",
            }

        # Verify OTP
        verified = OTPService.verify_otp(new_phone_number, code)

        if not verified:
            return {"status": "invalid_code", "message": "Invalid verification code."}

        # Update user's phone number
        old_phone = user.phone_number
        user.phone_number = new_phone_number
        user.save(update_fields=["phone_number"])

        logger.info(
            f"Phone number changed for user {user.id} from {old_phone} to {new_phone_number}"
        )

        return {
            "status": "changed",
            "message": "Phone number changed successfully.",
        }
