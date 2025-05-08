import logging

from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class SMSService:
    """
    Service for sending SMS messages with templates.
    Implements character-efficient text formatting, template rendering,
    and integration with SMS provider.
    """

    @staticmethod
    def send_sms(phone_number, message):
        """
        Send SMS to a phone number.

        Args:
            phone_number: Recipient phone number
            message: SMS content

        Returns:
            Boolean indicating success
        """
        try:
            # Import the sender function from your SMS utility
            from utils.sms.sender import send_sms

            # Ensure phone number is formatted correctly
            if not phone_number.startswith("+"):
                phone_number = f"+{phone_number}"

            # Truncate message if too long (standard SMS is 160 chars)
            if len(message) > 160:
                message = message[:157] + "..."

            # Send the message
            result = send_sms(phone_number, message)

            if not result:
                logger.warning(f"Failed to send SMS to {phone_number}")

            return result

        except Exception as e:
            logger.error(f"Error sending SMS to {phone_number}: {str(e)}")
            return False

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
            return SMSService.send_sms(phone_number, message)

        except Exception as e:
            logger.error(f"Error sending SMS with template {template_name}: {str(e)}")
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
            message = f"تذكير: لديك موعد في {appointment.shop.name} في {date_str} الساعة {time_str}. للخدمة: {appointment.service.name}."
        else:
            message = f"Reminder: Your appointment at {appointment.shop.name} is on {date_str} at {time_str}. Service: {appointment.service.name}."

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
            message = f"حان دورك الآن! يرجى التوجه إلى {ticket.queue.shop.name}. رقم التذكرة الخاص بك: {ticket.ticket_number}."
        else:
            message = f"It's your turn now! Please proceed to {ticket.queue.shop.name}. Your ticket: {ticket.ticket_number}."

        return SMSService.send_sms(phone_number, message)
