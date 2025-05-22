import logging
from typing import Any, Dict

import requests
from django.conf import settings
from django.template.loader import render_to_string
from twilio.rest import Client

logger = logging.getLogger(__name__)


# SMS Provider Enum
class SMSProvider:
    TWILIO = "twilio"
    FIREBASE = "firebase"
    MOCK = "mock"  # For testing


class SMSService:
    """
    Service for sending SMS messages with templates.
    Implements character-efficient text formatting, template rendering,
    and integration with SMS provider.
    """

    @classmethod
    def send_sms(
        cls,
        phone_number: str,
        message: str,
        sender_id: str = None,
        template: str = None,
        context: Dict[str, Any] = None,
        priority: str = "normal",
        log_to_db: bool = True,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Send SMS message to a phone number.

        Args:
            phone_number: Recipient phone number (E.164 format)
            message: SMS content
            sender_id: Sender ID or phone number
            template: Optional template name
            context: Context data for template
            priority: Message priority (normal, high)
            log_to_db: Whether to log this SMS in the database
            metadata: Additional metadata

        Returns:
            Dictionary with the result of the operation
        """
        # Render template if provided
        if template and context:
            try:
                message = render_to_string(template, context)
            except Exception as e:
                logger.error(f"Error rendering SMS template {template}: {str(e)}")
                return {
                    "success": False,
                    "error": f"Error rendering template: {str(e)}",
                }

        # Get SMS provider from settings
        provider = getattr(settings, "SMS_PROVIDER", SMSProvider.TWILIO)

        # Clean the phone number
        cleaned_phone = cls._clean_phone_number(phone_number)

        # Choose the appropriate provider
        if provider == SMSProvider.TWILIO:
            return cls._send_via_twilio(cleaned_phone, message, sender_id)
        elif provider == SMSProvider.FIREBASE:
            return cls._send_via_firebase(cleaned_phone, message, sender_id)
        elif provider == SMSProvider.MOCK:
            return cls._send_via_mock(cleaned_phone, message, sender_id)
        else:
            logger.error(f"Unknown SMS provider: {provider}")
            return {"success": False, "error": f"Unknown SMS provider: {provider}"}

    @classmethod
    def _send_via_twilio(
        cls, phone_number: str, message: str, sender_id: str = None
    ) -> Dict[str, Any]:
        """
        Send SMS using Twilio.

        Args:
            phone_number: Recipient phone number
            message: SMS content
            sender_id: Sender ID or phone number

        Returns:
            Dictionary with the result of the operation
        """
        try:
            # Get Twilio credentials from settings
            account_sid = settings.TWILIO_ACCOUNT_SID
            auth_token = settings.TWILIO_AUTH_TOKEN
            from_number = sender_id or settings.TWILIO_PHONE_NUMBER

            # Initialize Twilio client
            client = Client(account_sid, auth_token)

            # Send message
            twilio_message = client.messages.create(
                body=message, from_=from_number, to=phone_number
            )

            # Return success response
            return {
                "success": True,
                "provider": "twilio",
                "message_id": twilio_message.sid,
                "status": twilio_message.status,
            }

        except Exception as e:
            logger.error(f"Error sending SMS via Twilio: {str(e)}")
            return {"success": False, "provider": "twilio", "error": str(e)}

    @classmethod
    def _send_via_firebase(
        cls, phone_number: str, message: str, sender_id: str = None
    ) -> Dict[str, Any]:
        """
        Send SMS using Firebase.

        Args:
            phone_number: Recipient phone number
            message: SMS content
            sender_id: Sender ID or phone number

        Returns:
            Dictionary with the result of the operation
        """
        try:
            # Get Firebase credentials from settings
            firebase_api_url = settings.FIREBASE_SMS_API_URL
            server_key = settings.FIREBASE_SERVER_KEY

            # Prepare request headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"key={server_key}",
            }

            # Prepare request data
            data = {
                "phone": phone_number,
                "message": message,
                "sender": sender_id or "QueueMe",
            }

            # Send the request
            response = requests.post(firebase_api_url, json=data, headers=headers)
            response.raise_for_status()  # Raise exception for non-2xx responses

            # Parse the response
            result = response.json()

            # Return success response
            return {
                "success": True,
                "provider": "firebase",
                "message_id": result.get("message_id", "unknown"),
                "status": "sent",
            }

        except Exception as e:
            logger.error(f"Error sending SMS via Firebase: {str(e)}")
            return {"success": False, "provider": "firebase", "error": str(e)}

    @classmethod
    def _send_via_mock(
        cls, phone_number: str, message: str, sender_id: str = None
    ) -> Dict[str, Any]:
        """
        Mock SMS sending for testing.

        Args:
            phone_number: Recipient phone number
            message: SMS content
            sender_id: Sender ID or phone number

        Returns:
            Dictionary with the result of the operation
        """
        logger.info(
            f"MOCK SMS to {phone_number} from {sender_id or 'QueueMe'}: {message}"
        )
        return {
            "success": True,
            "provider": "mock",
            "message_id": "mock-message-id",
            "status": "sent",
        }

    @classmethod
    def _clean_phone_number(cls, phone_number: str) -> str:
        """
        Clean and format a phone number to E.164 format.

        Args:
            phone_number: Phone number to clean

        Returns:
            Cleaned phone number
        """
        # Remove spaces, dashes, parentheses, etc.
        cleaned = "".join(filter(str.isdigit, phone_number))

        # If the phone number already has a +, we need to preserve it
        if phone_number.strip().startswith("+"):
            return "+" + cleaned

        # Assume it's a local number if it doesn't start with country code
        if len(cleaned) <= 10:  # US number without country code
            cleaned = "1" + cleaned  # Add US country code

        # Add + prefix
        return "+" + cleaned

    @staticmethod
    def send_with_template(phone_number, template_name, context, language="en"):
        """
        Send SMS using a template.

        Args:
            phone_number: Recipient phone number
            template_name: Template name (without extension)
            context: Dictionary of context data for template rendering
            language: Language code (en or ar)

        Returns:
            Boolean indicating success
        """
        try:
            # Try to render the template
            template_path = f"notificationsapp/sms/{template_name}.txt"
            message = render_to_string(template_path, context)

            # Strip excess whitespace
            message = " ".join(message.split())

            # Send the message
            result = SMSService.send_sms(phone_number, message)
            return result.get("success", False)

        except Exception:
            logger.error(
                f"Error sending SMS with template {template_name}: {template_path}"
            )
            return False

    @staticmethod
    def send_verification_code(phone_number, code, language="en"):
        """
        Send verification code SMS.

        Args:
            phone_number: Recipient phone number
            code: Verification code
            language: Language code (en or ar)

        Returns:
            Boolean indicating success
        """
        # Generate message based on language
        if language == "ar":
            message = f"رمز التحقق الخاص بك هو: {code}. صالح لمدة 10 دقائق."
        else:
            message = (
                f"Your Queue Me verification code is: {code}. Valid for 10 minutes."
            )

        return SMSService.send_sms(phone_number, message)

    @staticmethod
    def send_appointment_reminder(phone_number, appointment, language="en"):
        """
        Send appointment reminder SMS.

        Args:
            phone_number: Recipient phone number
            appointment: Appointment object
            language: Language code (en or ar)

        Returns:
            Boolean indicating success
        """
        # Format date and time
        date_str = appointment.start_time.strftime("%d %b, %Y")
        time_str = appointment.start_time.strftime("%I:%M %p")

        # Generate message based on language
        if language == "ar":
            message = (
                f"تذكير: لديك موعد في {appointment.shop.name} في {date_str} "
                f"الساعة {time_str}. للخدمة: {appointment.service.name}."
            )
        else:
            message = (
                f"Reminder: Your appointment at {appointment.shop.name} is on {date_str} "
                f"at {time_str}. Service: {appointment.service.name}."
            )

        return SMSService.send_sms(phone_number, message)

    @staticmethod
    def send_queue_called(phone_number, ticket, language="en"):
        """
        Send queue called SMS.

        Args:
            phone_number: Recipient phone number
            ticket: Queue ticket object
            language: Language code (en or ar)

        Returns:
            Boolean indicating success
        """
        # Generate message based on language
        if language == "ar":
            message = (
                f"حان دورك الآن! يرجى التوجه إلى {ticket.queue.shop.name}. "
                f"رقم التذكرة الخاص بك: {ticket.ticket_number}."
            )
        else:
            message = (
                f"It's your turn now! Please proceed to {ticket.queue.shop.name}. "
                f"Your ticket: {ticket.ticket_number}."
            )

        return SMSService.send_sms(phone_number, message)
