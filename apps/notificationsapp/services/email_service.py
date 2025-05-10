import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending emails with templates.
    Handles template rendering, HTML/text alternatives, and tracking.
    """

    @staticmethod
    def send_email(
        to_email, subject, template_name, context, from_email=None, attachments=None
    ):
        """
        Send an email using a template.

        Args:
            to_email: Recipient email address
            subject: Email subject
            template_name: Path to the template (without extension)
            context: Dictionary of context data for template rendering
            from_email: Sender email (uses DEFAULT_FROM_EMAIL if not provided)
            attachments: List of (filename, content, mimetype) tuples

        Returns:
            Boolean indicating success
        """
        try:
            # Get sender email from settings if not provided
            if not from_email:
                from_email = settings.DEFAULT_FROM_EMAIL

            # Try to render the template
            html_content = None
            try:
                template_path = f"notificationsapp/email/{template_name}.html"
                html_content = render_to_string(template_path, context)
            except Exception as e:
                logger.warning(
                    f"Error rendering HTML template {template_name}: {str(e)}"
                )

            # Try to render text template, or fall back to stripping HTML
            text_content = None
            try:
                text_template_path = f"notificationsapp/email/{template_name}.txt"
                text_content = render_to_string(text_template_path, context)
            except Exception:
                # Fall back to stripping HTML
                if html_content:
                    text_content = strip_tags(html_content)
                else:
                    # No template found, use basic text
                    logger.error(f"No template found for {template_name}")
                    return False

            # Create email message
            email = EmailMultiAlternatives(
                subject=subject, body=text_content, from_email=from_email, to=[to_email]
            )

            # Add HTML alternative if available
            if html_content:
                email.attach_alternative(html_content, "text/html")

            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    email.attach(*attachment)

            # Send email
            email.send()
            return True

        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False

    @staticmethod
    def send_appointment_confirmation(user, appointment):
        """
        Send appointment confirmation email.

        Args:
            user: User receiving the email
            appointment: Appointment object

        Returns:
            Boolean indicating success
        """
        context = {
            "user": user,
            "appointment": appointment,
            "shop": appointment.shop,
            "service": appointment.service,
            "specialist": appointment.specialist,
            "date": appointment.start_time.strftime("%d %b, %Y"),
            "time": appointment.start_time.strftime("%I:%M %p"),
        }

        return EmailService.send_email(
            to_email=user.email,
            subject=f"Your appointment at {appointment.shop.name} is confirmed",
            template_name="appointment_confirmation",
            context=context,
        )

    @staticmethod
    def send_appointment_reminder(user, appointment):
        """
        Send appointment reminder email.

        Args:
            user: User receiving the email
            appointment: Appointment object

        Returns:
            Boolean indicating success
        """
        context = {
            "user": user,
            "appointment": appointment,
            "shop": appointment.shop,
            "service": appointment.service,
            "specialist": appointment.specialist,
            "date": appointment.start_time.strftime("%d %b, %Y"),
            "time": appointment.start_time.strftime("%I:%M %p"),
        }

        return EmailService.send_email(
            to_email=user.email,
            subject=f"Reminder: Your appointment at {appointment.shop.name}",
            template_name="appointment_reminder",
            context=context,
        )

    @staticmethod
    def send_queue_update(user, ticket):
        """
        Send queue status update email.

        Args:
            user: User receiving the email
            ticket: Queue ticket object

        Returns:
            Boolean indicating success
        """
        context = {
            "user": user,
            "ticket": ticket,
            "shop": ticket.queue.shop,
            "queue": ticket.queue,
            "position": ticket.position,
            "wait_time": ticket.estimated_wait_time,
        }

        return EmailService.send_email(
            to_email=user.email,
            subject=f"Queue update for {ticket.queue.shop.name}",
            template_name="queue_update",
            context=context,
        )
