import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.template import Context, Template
from django.utils import timezone

from apps.authapp.models import User
from apps.notificationsapp.models import DeviceToken, Notification, NotificationTemplate
from apps.notificationsapp.services.channel_selector import ChannelSelector
from apps.notificationsapp.services.timing_optimizer import TimingOptimizer

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


class NotificationService:
    @staticmethod
    def send_notification(
        user_id, notification_type, data=None, scheduled_for=None, channels=None
    ):
        """
        Send notification to user via specified channels with advanced channel selection.

        Args:
            user_id: UUID of the user to notify
            notification_type: Type of notification (must match a template type)
            data: Dictionary of data to populate the template
            scheduled_for: Optional future datetime to send the notification
            channels: Optional list of channels to use, if None uses intelligent selection

        Returns:
            List of created notification objects
        """
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"Cannot send notification: User {user_id} does not exist")
            return []

        if data is None:
            data = {}

        # If no channels specified, use intelligent channel selection
        if channels is None:
            channels = ChannelSelector.select_optimal_channels(
                user_id=user_id, notification_type=notification_type, data=data
            )

        # If still no channels, use all
        if not channels:
            channels = ["push", "sms", "email", "in_app"]

        # If not scheduled, optimize timing if appropriate
        if not scheduled_for and notification_type not in [
            "verification_code",
            "queue_called",
        ]:
            # Only optimize timing for non-urgent notifications
            scheduled_for = TimingOptimizer.determine_optimal_send_time(
                user_id=user_id, notification_type=notification_type
            )

        notifications = []

        for channel in channels:
            try:
                # Get template
                template = NotificationTemplate.objects.get(
                    type=notification_type, channel=channel, is_active=True
                )

                # Get correct body based on user language preference
                # Default to English if preference not set
                language = getattr(user, "language_preference", "en")
                body_field = f"body_{language}"
                body_template = getattr(template, body_field, template.body_en)

                # Render template with data
                context = Context(data)
                rendered_body = Template(body_template).render(context)
                rendered_subject = (
                    Template(template.subject).render(context)
                    if template.subject
                    else ""
                )

                # Create notification
                notification = Notification.objects.create(
                    user=user,
                    template=template,
                    type=notification_type,
                    channel=channel,
                    subject=rendered_subject,
                    body=rendered_body,
                    data=data,
                    scheduled_for=scheduled_for,
                    status="pending",
                )

                # Send immediately if not scheduled
                if not scheduled_for:
                    NotificationService._send_notification(notification)

                notifications.append(notification)

            except NotificationTemplate.DoesNotExist:
                logger.warning(
                    f"No template found for {notification_type} via {channel}"
                )
                continue
            except Exception as e:
                logger.error(f"Error creating notification: {str(e)}")
                continue

        return notifications

    @staticmethod
    def _send_notification(notification):
        """Send a single notification based on its channel"""
        channel_methods = {
            "sms": NotificationService._send_sms,
            "push": NotificationService._send_push,
            "email": NotificationService._send_email,
            "in_app": NotificationService._send_in_app,
        }

        send_method = channel_methods.get(notification.channel)

        if not send_method:
            logger.error(f"Unknown notification channel: {notification.channel}")
            notification.status = "failed"
            notification.save()
            return False

        try:
            result = send_method(notification)

            if result:
                notification.status = "sent"
                notification.sent_at = timezone.now()
            else:
                # Try to use fallback channels if primary channel fails
                fallback_result = NotificationService._try_fallback_channels(
                    notification
                )
                if fallback_result:
                    notification.status = "sent"
                    notification.sent_at = timezone.now()
                    notification.channel = (
                        fallback_result  # Update to successful channel
                    )
                else:
                    notification.status = "failed"
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            notification.status = "failed"

        notification.save()
        return notification.status == "sent"

    @staticmethod
    def _try_fallback_channels(notification):
        """Try to send notification using fallback channels"""
        # Determine fallback channels based on current channel
        fallback_map = {
            "push": ["in_app", "sms"],
            "sms": ["push", "in_app"],
            "email": ["push", "in_app", "sms"],
            "in_app": ["push", "sms"],
        }

        current_channel = notification.channel
        fallbacks = fallback_map.get(current_channel, [])

        for fallback in fallbacks:
            try:
                # Check if we have a template for this fallback channel
                template = NotificationTemplate.objects.get(
                    type=notification.type, channel=fallback, is_active=True
                )

                # Create a new notification object for the fallback
                fallback_notification = Notification.objects.create(
                    user=notification.user,
                    template=template,
                    type=notification.type,
                    channel=fallback,
                    subject=notification.subject,
                    body=notification.body,
                    data=notification.data,
                    status="pending",
                )

                # Try to send with the fallback channel
                send_method = getattr(NotificationService, f"_send_{fallback}")
                if send_method(fallback_notification):
                    # If successful, mark the fallback as sent but don't save it
                    # (we'll update the original notification instead)
                    return fallback

            except (NotificationTemplate.DoesNotExist, Exception) as e:
                logger.warning(f"Fallback to {fallback} failed: {str(e)}")
                continue

        return None

    @staticmethod
    def _send_sms(notification):
        """Send SMS notification"""
        from utils.sms.sender import send_sms

        user = notification.user
        phone_number = user.phone_number
        message = notification.body

        if not phone_number:
            logger.error(f"Cannot send SMS: No phone number for user {user.id}")
            return False

        return send_sms(phone_number, message)

    @staticmethod
    def _send_push(notification):
        """Send push notification"""
        user = notification.user

        # Get active device tokens
        device_tokens = DeviceToken.objects.filter(user=user, is_active=True)

        if not device_tokens.exists():
            logger.info(f"No active device tokens for user {user.id}")
            return False

        # Group tokens by platform
        ios_tokens = []
        android_tokens = []
        web_tokens = []

        for device in device_tokens:
            if device.platform == "ios":
                ios_tokens.append(device.token)
            elif device.platform == "android":
                android_tokens.append(device.token)
            elif device.platform == "web":
                web_tokens.append(device.token)

        # Send to each platform
        success = False

        if ios_tokens:
            success = (
                NotificationService._send_apns(notification, ios_tokens) or success
            )

        if android_tokens:
            success = (
                NotificationService._send_fcm(notification, android_tokens) or success
            )

        if web_tokens:
            success = (
                NotificationService._send_web_push(notification, web_tokens) or success
            )

        return success

    @staticmethod
    def _send_apns(notification, tokens):
        """Send Apple Push Notification Service (APNS) messages"""
        try:
            # Here you would integrate with your APNS provider
            # This is a placeholder implementation
            logger.info(
                f"Would send APNS to {len(tokens)} devices: {notification.subject}"
            )

            # In a real implementation, you'd use a library like aioapns or apns2
            # Example with apns2:
            # from apns2.client import APNsClient
            # from apns2.payload import Payload
            # client = APNsClient(settings.APNS_CERT_PATH, use_sandbox=settings.APNS_USE_SANDBOX)
            # payload = Payload(alert=notification.subject, sound="default", badge=1, custom=notification.data)
            # for token in tokens:
            #     client.send_notification(token, payload, topic=settings.APNS_TOPIC)

            return True
        except Exception as e:
            logger.error(f"Error sending APNS: {str(e)}")
            return False

    @staticmethod
    def _send_fcm(notification, tokens):
        """Send Firebase Cloud Messaging (FCM) messages"""
        try:
            # Here you would integrate with FCM
            # This is a placeholder implementation
            logger.info(
                f"Would send FCM to {len(tokens)} devices: {notification.subject}"
            )

            # In a real implementation, you'd use the firebase-admin library
            # Example:
            # from firebase_admin import messaging
            # message = messaging.MulticastMessage(
            #     notification=messaging.Notification(
            #         title=notification.subject,
            #         body=notification.body
            #     ),
            #     data=notification.data,
            #     tokens=tokens
            # )
            # response = messaging.send_multicast(message)

            return True
        except Exception as e:
            logger.error(f"Error sending FCM: {str(e)}")
            return False

    @staticmethod
    def _send_web_push(notification, tokens):
        """Send Web Push notifications"""
        try:
            # Here you would integrate with a web push service
            # This is a placeholder implementation
            logger.info(
                f"Would send Web Push to {len(tokens)} devices: {notification.subject}"
            )

            # In a real implementation, you'd use the pywebpush library
            # Example:
            # from pywebpush import webpush
            # for token_json in tokens:
            #     token_data = json.loads(token_json)
            #     webpush(
            #         subscription_info=token_data,
            #         data=json.dumps({
            #             'title': notification.subject,
            #             'body': notification.body,
            #             'data': notification.data
            #         }),
            #         vapid_private_key=settings.VAPID_PRIVATE_KEY,
            #         vapid_claims={
            #             'sub': f'mailto:{settings.VAPID_CLAIM_EMAIL}'
            #         }
            #     )

            return True
        except Exception as e:
            logger.error(f"Error sending Web Push: {str(e)}")
            return False

    @staticmethod
    def _send_email(notification):
        """Send email notification"""
        from django.core.mail import send_mail
        from django.template.loader import render_to_string

        user = notification.user

        if not user.email:
            logger.info(f"Cannot send email: No email for user {user.id}")
            return False

        try:
            # Get template path based on notification type
            template_name = f"notificationsapp/email/{notification.type}.html"

            # Try to render the template with notification data
            try:
                email_body = render_to_string(
                    template_name,
                    {
                        "user": user,
                        "notification": notification,
                        "data": notification.data,
                    },
                )
            except Exception:
                # Fallback to using the notification body directly
                email_body = notification.body

            # Send the email
            send_mail(
                subject=notification.subject or "Queue Me Notification",
                message=notification.body,  # Plain text fallback
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=email_body,
            )

            return True

        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False

    @staticmethod
    def _send_in_app(notification):
        """Create in-app notification (no actual sending needed)"""
        # In-app notifications are already created in the database
        # But we need to send a real-time update via WebSockets

        try:
            pass

            from apps.notificationsapp.serializers import NotificationSerializer

            # Send real-time notification to WebSocket if user is connected
            serializer = NotificationSerializer(notification)
            notification_data = serializer.data

            async_to_sync(channel_layer.group_send)(
                f"notifications_{notification.user.id}",
                {"type": "notification", "notification": notification_data},
            )

            # Also send updated unread count
            unread_count = Notification.objects.filter(
                user=notification.user, status__in=["sent", "delivered"]
            ).count()

            async_to_sync(channel_layer.group_send)(
                f"notifications_{notification.user.id}",
                {"type": "unread_count_update", "count": unread_count},
            )

            return True

        except Exception as e:
            logger.error(f"Error sending WebSocket notification: {str(e)}")
            # Still return True as the notification is created in DB even if WebSocket fails
            return True

    @staticmethod
    def mark_as_delivered(notification_id):
        """Mark a notification as delivered"""
        try:
            notification = Notification.objects.get(id=notification_id)

            if notification.status == "sent":
                notification.status = "delivered"
                notification.delivered_at = timezone.now()
                notification.save()

                return True
        except Notification.DoesNotExist:
            logger.warning(
                f"Cannot mark as delivered: Notification {notification_id} not found"
            )

        return False

    @staticmethod
    def mark_as_read(notification_id):
        """Mark a notification as read"""
        try:
            notification = Notification.objects.get(id=notification_id)

            if notification.status in ["sent", "delivered"]:
                notification.status = "read"
                notification.read_at = timezone.now()
                notification.save()

                return True
        except Notification.DoesNotExist:
            logger.warning(
                f"Cannot mark as read: Notification {notification_id} not found"
            )

        return False

    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread notifications for a user"""
        return Notification.objects.filter(
            user_id=user_id, status__in=["sent", "delivered"]
        ).count()

    # Domain-specific notification methods

    @staticmethod
    def send_appointment_confirmation(appointment):
        """Send appointment confirmation notification"""
        data = {
            "appointment_id": str(appointment.id),
            "service_name": appointment.service.name,
            "shop_name": appointment.shop.name,
            "date": appointment.start_time.strftime("%d %b, %Y"),
            "time": appointment.start_time.strftime("%I:%M %p"),
            "specialist_name": f"{appointment.specialist.employee.first_name} {appointment.specialist.employee.last_name}",
        }

        return NotificationService.send_notification(
            user_id=appointment.customer.id,
            notification_type="appointment_confirmation",
            data=data,
        )

    @staticmethod
    def send_appointment_reminder(appointment):
        """Send appointment reminder notification"""
        data = {
            "appointment_id": str(appointment.id),
            "service_name": appointment.service.name,
            "shop_name": appointment.shop.name,
            "date": appointment.start_time.strftime("%d %b, %Y"),
            "time": appointment.start_time.strftime("%I:%M %p"),
            "specialist_name": f"{appointment.specialist.employee.first_name} {appointment.specialist.employee.last_name}",
        }

        # For reminders, prioritize channels for immediate attention
        return NotificationService.send_notification(
            user_id=appointment.customer.id,
            notification_type="appointment_reminder",
            data=data,
            channels=["push", "sms"],  # Prioritize immediate channels
        )

    @staticmethod
    def send_queue_join_confirmation(ticket):
        """Send queue join confirmation notification"""
        data = {
            "ticket_id": str(ticket.id),
            "ticket_number": ticket.ticket_number,
            "shop_name": ticket.queue.shop.name,
            "position": ticket.position,
            "estimated_wait": ticket.estimated_wait_time,
            "service_name": ticket.service.name if ticket.service else "",
        }

        return NotificationService.send_notification(
            user_id=ticket.customer.id,
            notification_type="queue_join_confirmation",
            data=data,
        )

    @staticmethod
    def send_queue_called_notification(ticket):
        """Send notification when customer is called from queue"""
        data = {
            "ticket_id": str(ticket.id),
            "ticket_number": ticket.ticket_number,
            "shop_name": ticket.queue.shop.name,
            "specialist_name": (
                f"{ticket.specialist.employee.first_name} {ticket.specialist.employee.last_name}"
                if ticket.specialist
                else ""
            ),
        }

        # This is time-sensitive, use all channels
        return NotificationService.send_notification(
            user_id=ticket.customer.id,
            notification_type="queue_called",
            data=data,
            channels=["push", "sms", "in_app"],  # All immediate channels
        )

    @staticmethod
    def send_service_feedback_request(ticket_or_appointment):
        """Send feedback request notification after service"""
        # Determine if this is a ticket or appointment
        if hasattr(ticket_or_appointment, "queue"):
            # It's a queue ticket
            data = {
                "id": str(ticket_or_appointment.id),
                "type": "queue",
                "shop_name": ticket_or_appointment.queue.shop.name,
                "service_name": (
                    ticket_or_appointment.service.name
                    if ticket_or_appointment.service
                    else ""
                ),
                "specialist_name": (
                    f"{ticket_or_appointment.specialist.employee.first_name} {ticket_or_appointment.specialist.employee.last_name}"
                    if ticket_or_appointment.specialist
                    else ""
                ),
            }
            user_id = ticket_or_appointment.customer.id
        else:
            # It's an appointment
            data = {
                "id": str(ticket_or_appointment.id),
                "type": "appointment",
                "shop_name": ticket_or_appointment.shop.name,
                "service_name": ticket_or_appointment.service.name,
                "specialist_name": (
                    f"{ticket_or_appointment.specialist.employee.first_name} {ticket_or_appointment.specialist.employee.last_name}"
                    if ticket_or_appointment.specialist
                    else ""
                ),
            }
            user_id = ticket_or_appointment.customer.id

        # Not urgent, can use optimal timing and channels
        return NotificationService.send_notification(
            user_id=user_id, notification_type="service_feedback", data=data
        )
