import logging

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from apps.notificationsapp.models import Notification

logger = logging.getLogger(__name__)


@shared_task
def send_scheduled_notification(notification_id):
    """
    Send a scheduled notification.

    Args:
        notification_id: UUID of the notification to send
    """
    try:
        notification = Notification.objects.get(id=notification_id, status="pending")

        # Only send if it's time (or past time)
        if notification.scheduled_for and notification.scheduled_for > timezone.now():
            # Not time yet, reschedule
            send_scheduled_notification.apply_async(
                args=[notification_id], eta=notification.scheduled_for
            )
            return f"Rescheduled notification {notification_id} for {notification.scheduled_for}"

        # Send the notification
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        result = NotificationService._send_notification(notification)

        if result:
            return f"Sent scheduled notification {notification_id}"
        else:
            return f"Failed to send scheduled notification {notification_id}"

    except Notification.DoesNotExist:
        logger.warning(
            f"Scheduled notification {notification_id} not found or already sent"
        )
        return f"Notification {notification_id} not found or already sent"
    except Exception as e:
        logger.error(
            f"Error sending scheduled notification {notification_id}: {str(e)}"
        )
        return f"Error: {str(e)}"


@shared_task
def process_notification(notification_id):
    """
    Process a notification in the background.

    Args:
        notification_id: UUID of the notification to process
    """
    try:
        notification = Notification.objects.get(id=notification_id, status="pending")

        # Send the notification
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

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
        from django.db import connection

        # Using raw SQL for efficiency with large datasets
        with connection.cursor() as cursor:
            # For each user, get IDs of read notifications to keep (most recent 100)
            cursor.execute(
                """
                DELETE FROM notificationsapp_notification
                WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id FROM notificationsapp_notification
                        WHERE status = 'read' AND read_at < NOW() - INTERVAL '30 days'
                        ORDER BY read_at DESC
                        LIMIT 100
                    ) AS to_keep
                )
                AND status = 'read'
                AND read_at < NOW() - INTERVAL '30 days'
            """
            )

            deleted_count = cursor.rowcount

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
        # Get pending notifications that should have been sent already
        pending_notifications = Notification.objects.filter(
            Q(status="pending"),
            Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=timezone.now()),
        )

        if not pending_notifications.exists():
            return "No pending notifications to send"

        count = 0
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        for notification in pending_notifications:
            result = NotificationService._send_notification(notification)
            if result:
                count += 1

        return f"Sent {count} of {pending_notifications.count()} pending notifications"

    except Exception as e:
        logger.error(f"Error sending pending notifications: {str(e)}")
        return f"Error: {str(e)}"
