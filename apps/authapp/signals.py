from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import OTP, User
from apps.notificationsapp.services.notification_service import (  # Import from notificationsapp
    NotificationService,
)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal handler to perform additional actions when a User is created.
    """
    if created:
        # You could initialize related profiles or perform other setup here
        pass


@receiver(post_save, sender=OTP)
def send_otp_notification(sender, instance, created, **kwargs):
    """
    Send OTP notification when a new OTP is created.
    """
    if created and not instance.is_used:
        try:
            # Send OTP via notification service
            if instance.user:
                # User already exists, send notification
                NotificationService.send_notification(
                    user_id=instance.user.id,
                    notification_type="otp_verification",
                    data={"otp_code": instance.code},
                    channels=["sms"],  # Send only via SMS
                )
            else:
                # No user associated yet, use direct SMS
                from utils.sms.sender import send_sms

                # Get message based on language (default to English)
                message = _(
                    f"Your Queue Me verification code is: {instance.code}. It expires in 10 minutes."
                )

                # Send the SMS
                send_sms(instance.phone_number, message)

        except Exception as e:
            # Log the error but don't fail the operation
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send OTP notification: {str(e)}")
