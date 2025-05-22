import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from apps.authapp.models import User
from apps.notificationsapp.models import DeviceToken, Notification
from apps.notificationsapp.services.push_service import FirebasePushService
from apps.notificationsapp.services.sms_service import SMSService

logger = logging.getLogger(__name__)


@shared_task
def send_scheduled_notification(notification_id):
    """
    Send a scheduled notification.

    Args:
        notification_id: UUID of the notification to send
    """
    try:
        # Import inside the function to avoid circular import
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        notification = Notification.objects.get(id=notification_id)

        # Check if notification is still scheduled (not cancelled)
        if notification.status != "scheduled":
            logger.info(
                f"Notification {notification_id} is no longer scheduled (status: {notification.status})"
            )
            # Log status change in notification history
            NotificationService.update_notification_status(
                notification_id,
                "all",
                "skipped",
                f"Notification no longer scheduled: {notification.status}",
            )
            return {
                "success": False,
                "message": f"Notification {notification_id} is no longer scheduled",
            }

        # Check if notification is expired
        if notification.expires_at and notification.expires_at < timezone.now():
            # Update status to expired
            NotificationService.update_notification_status(
                notification_id, "all", "expired", "Notification has expired"
            )
            notification.status = "expired"
            notification.save(update_fields=["status"])
            logger.info(f"Notification {notification_id} has expired")
            return {
                "success": False,
                "message": f"Notification {notification_id} has expired",
            }

        # Update status to processing
        notification.status = "processing"
        notification.processed_at = timezone.now()
        notification.save(update_fields=["status", "processed_at"])

        # Process the notification according to its channels
        channels = notification.channels or []
        for channel in channels:
            if channel == "email":
                send_email_notification_task.delay(
                    notification_id=str(notification.id),
                    recipient_id=str(notification.recipient_id),
                )
            elif channel == "sms":
                send_sms_notification_task.delay(
                    notification_id=str(notification.id),
                    recipient_id=str(notification.recipient_id),
                )
            elif channel == "push":
                send_push_notification_task.delay(
                    notification_id=str(notification.id),
                    recipient_id=str(notification.recipient_id),
                )
            elif channel == "in_app":
                # In-app notifications are already created in the database
                # Just mark them as delivered
                NotificationService.update_notification_status(
                    notification_id, "in_app", "delivered"
                )
                channel_status = notification.channel_status or {}
                channel_status["in_app"] = {
                    "status": "delivered",
                    "delivered_at": timezone.now().isoformat(),
                }
                notification.channel_status = channel_status
                notification.save(update_fields=["channel_status"])

        return {
            "success": True,
            "notification_id": str(notification.id),
            "channels": channels,
        }

    except Notification.DoesNotExist:
        logger.error(f"Scheduled notification {notification_id} not found")
        return {
            "success": False,
            "message": f"Notification {notification_id} not found",
        }
    except Exception as e:
        logger.exception(
            f"Error processing scheduled notification {notification_id}: {str(e)}"
        )
        return {"success": False, "message": f"Error processing notification: {str(e)}"}


@shared_task
def process_notification(notification_id):
    """
    Process a notification in the background.

    Args:
        notification_id: UUID of the notification to process
    """
    try:
        # Import inside the function to avoid circular import
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        notification = Notification.objects.get(id=notification_id, status="pending")

        # Send the notification
        result = NotificationService._send_notification(notification)

        if result:
            return f"Processed notification {notification_id}"
        else:
            return f"Failed to process notification {notification_id}"

    except Notification.DoesNotExist:
        logger.warning(f"Notification {notification_id} not found or already processed")
        return f"Notification {notification_id} not found or already processed"
    except Exception as e:
        logger.error(f"Error processing notification {notification_id}: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def cleanup_old_notifications():
    """
    Clean up old read notifications to prevent database bloat.
    Keeps the last 100 read notifications per user and deletes the rest.
    """
    try:
        pass

        # Use Django ORM instead of raw SQL for this operation for better security
        # First, find notifications to keep (latest 100 read notifications)
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # Find all read notifications older than 30 days
        old_read_notifications = Notification.objects.filter(
            status="read", read_at__lt=thirty_days_ago
        )

        # For each user, keep only the latest 100 notifications
        users_with_notifications = User.objects.filter(
            notifications__in=old_read_notifications
        ).distinct()

        deleted_count = 0

        for user in users_with_notifications:
            # Get IDs of notifications to keep for this user
            keep_ids = (
                Notification.objects.filter(
                    recipient=user, status="read", read_at__lt=thirty_days_ago
                )
                .order_by("-read_at")[:100]
                .values_list("id", flat=True)
            )

            # Delete old notifications for this user (excluding the kept ones)
            to_delete = Notification.objects.filter(
                recipient=user, status="read", read_at__lt=thirty_days_ago
            ).exclude(id__in=keep_ids)

            count = to_delete.count()
            to_delete.delete()
            deleted_count += count

        logger.info(f"Cleaned up {deleted_count} old notifications")
        return f"Cleaned up {deleted_count} old notifications"

    except Exception as e:
        logger.error(f"Error cleaning up old notifications: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def send_pending_notifications():
    """
    Send all pending notifications that are ready to be sent.
    Used as a backup in case scheduled tasks failed.
    """
    try:
        # Import inside the function to avoid circular import
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        # Get pending notifications that should have been sent already
        pending_notifications = Notification.objects.filter(
            Q(status="pending"),
            Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=timezone.now()),
        )

        if not pending_notifications.exists():
            return "No pending notifications to send"

        count = 0
        for notification in pending_notifications:
            result = NotificationService._send_notification(notification)
            if result:
                count += 1

        return f"Sent {count} of {pending_notifications.count()} pending notifications"

    except Exception as e:
        logger.error(f"Error sending pending notifications: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def send_email_notification_task(notification_id, recipient_id=None, **kwargs):
    """
    Send an email notification.

    Args:
        notification_id: ID of the notification
        recipient_id: Recipient user ID (optional if in notification)
        **kwargs: Additional parameters
    """
    try:
        # Import inside the function to avoid circular import
        from django.conf import settings
        from django.core.mail import send_mail

        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        # Get user's email
        try:
            user = User.objects.get(id=recipient_id)
            email = user.email
        except User.DoesNotExist:
            logger.error(f"User {recipient_id} not found for email notification")
            NotificationService.update_notification_status(
                notification_id, "email", "error", f"User {recipient_id} not found"
            )
            return False

        if not email:
            logger.error(f"User {recipient_id} has no email address")
            NotificationService.update_notification_status(
                notification_id, "email", "error", "User has no email address"
            )
            return False

        # Get notification details
        notification = Notification.objects.get(id=notification_id)

        # Update status to sending
        NotificationService.update_notification_status(
            notification_id, "email", "sending"
        )

        # Send email
        try:
            send_mail(
                subject=notification.title,
                message=notification.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            # Update status to delivered
            NotificationService.update_notification_status(
                notification_id, "email", "delivered"
            )
            return True

        except Exception as e:
            logger.error(f"Error sending email to {email}: {str(e)}")
            NotificationService.update_notification_status(
                notification_id, "email", "error", str(e)
            )
            return False

    except Exception as e:
        logger.exception(f"Error in email notification task: {str(e)}")
        return False


@shared_task
def send_sms_notification_task(notification_id, recipient_id=None, **kwargs):
    """
    Send an SMS notification.

    Args:
        notification_id: ID of the notification
        recipient_id: Recipient user ID (optional if in notification)
        **kwargs: Additional parameters
    """
    try:
        # Import inside the function to avoid circular import
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        # Get user's phone number
        try:
            user = User.objects.get(id=recipient_id)
            phone = user.phone_number
        except User.DoesNotExist:
            logger.error(f"User {recipient_id} not found for SMS notification")
            NotificationService.update_notification_status(
                notification_id, "sms", "error", f"User {recipient_id} not found"
            )
            return False

        if not phone:
            logger.error(f"User {recipient_id} has no phone number")
            NotificationService.update_notification_status(
                notification_id, "sms", "error", "User has no phone number"
            )
            return False

        # Get notification details
        notification = Notification.objects.get(id=notification_id)

        # Update status to sending
        NotificationService.update_notification_status(
            notification_id, "sms", "sending"
        )

        # Send SMS
        result = SMSService.send_sms(phone_number=phone, message=notification.message)

        if result.get("success"):
            # Update status to delivered
            NotificationService.update_notification_status(
                notification_id, "sms", "delivered"
            )
            return True
        else:
            # Update status to error
            NotificationService.update_notification_status(
                notification_id, "sms", "error", result.get("error", "Unknown error")
            )
            return False

    except Exception as e:
        logger.exception(f"Error in SMS notification task: {str(e)}")
        return False


@shared_task
def send_push_notification_task(notification_id, recipient_id=None, **kwargs):
    """
    Send a push notification.

    Args:
        notification_id: ID of the notification
        recipient_id: Recipient user ID (optional if in notification)
        **kwargs: Additional parameters
    """
    try:
        # Import inside the function to avoid circular import
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        # Get user's device tokens
        device_tokens = DeviceToken.objects.filter(user_id=recipient_id, is_active=True)

        if not device_tokens.exists():
            logger.warning(f"User {recipient_id} has no active device tokens")
            NotificationService.update_notification_status(
                notification_id, "push", "skipped", "User has no active device tokens"
            )
            return False

        # Get notification details
        notification = Notification.objects.get(id=notification_id)

        # Update status to sending
        NotificationService.update_notification_status(
            notification_id, "push", "sending"
        )

        # Extract FCM tokens
        token_strings = [token.token for token in device_tokens]

        # Send push notification
        result = FirebasePushService.send_notification(
            tokens=token_strings,
            title=notification.title,
            body=notification.message,
            data=notification.data,
        )

        if result.get("success"):
            # Update status to delivered
            NotificationService.update_notification_status(
                notification_id, "push", "delivered"
            )
            return True
        else:
            # Update status to error
            NotificationService.update_notification_status(
                notification_id, "push", "error", result.get("error", "Unknown error")
            )
            return False

    except Exception as e:
        logger.exception(f"Error in push notification task: {str(e)}")
        return False


@shared_task
def retry_failed_notification_task(notification_id, channel):
    """
    Retry a failed notification.

    Args:
        notification_id: ID of the notification
        channel: Channel to retry (email, sms, push)
    """
    try:
        # Import inside the function to avoid circular import
        pass

        # Get notification
        notification = Notification.objects.get(id=notification_id)

        # Retry based on channel
        if channel == "email":
            send_email_notification_task.delay(
                notification_id=str(notification.id),
                recipient_id=str(notification.recipient_id),
            )
        elif channel == "sms":
            send_sms_notification_task.delay(
                notification_id=str(notification.id),
                recipient_id=str(notification.recipient_id),
            )
        elif channel == "push":
            send_push_notification_task.delay(
                notification_id=str(notification.id),
                recipient_id=str(notification.recipient_id),
            )

        return True

    except Exception as e:
        logger.exception(
            f"Error retrying notification {notification_id} on {channel}: {str(e)}"
        )
        return False


@shared_task
def clean_old_notifications():
    """
    Clean up old notifications to prevent database bloat.
    Keeps the most recent notifications per user according to settings.
    """
    try:
        # Import inside function to avoid circular imports
        from django.conf import settings
        from django.db.models import Count

        # Get retention configuration
        max_notifications_per_user = getattr(
            settings, "MAX_NOTIFICATIONS_PER_USER", 100
        )
        retention_days = getattr(settings, "NOTIFICATION_RETENTION_DAYS", 90)

        # Delete notifications older than retention period
        retention_date = timezone.now() - timedelta(days=retention_days)
        old_notifications = Notification.objects.filter(created_at__lt=retention_date)

        deleted_count = old_notifications.count()
        old_notifications.delete()

        # For each user, keep only the most recent max_notifications_per_user
        users_with_many_notifications = (
            User.objects.filter(notifications__isnull=False)
            .annotate(notification_count=Count("notifications"))
            .filter(notification_count__gt=max_notifications_per_user)
        )

        for user in users_with_many_notifications:
            # Get IDs of notifications to keep
            keep_ids = (
                Notification.objects.filter(recipient_id=user.id)
                .order_by("-created_at")[:max_notifications_per_user]
                .values_list("id", flat=True)
            )

            # Delete excess notifications
            excess_count = (
                Notification.objects.filter(recipient_id=user.id)
                .exclude(id__in=keep_ids)
                .count()
            )

            Notification.objects.filter(recipient_id=user.id).exclude(
                id__in=keep_ids
            ).delete()

            deleted_count += excess_count

        logger.info(f"Cleaned up {deleted_count} old notifications")
        return {"success": True, "deleted_count": deleted_count}

    except Exception as e:
        logger.exception(f"Error cleaning old notifications: {str(e)}")
        return {
            "success": False,
            "message": f"Error cleaning old notifications: {str(e)}",
        }
