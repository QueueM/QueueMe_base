import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.notificationsapp.models import Notification
from apps.notificationsapp.tasks import process_notification, send_scheduled_notification

logger = logging.getLogger("notifications")
channel_layer = get_channel_layer()


@receiver(post_save, sender=Notification)
def handle_notification_created(sender, instance, created, **kwargs):
    """Handle notification creation"""
    if created:
        # If scheduled for future, create a Celery task
        if instance.scheduled_for and instance.status == "pending":
            send_scheduled_notification.apply_async(
                args=[str(instance.id)], eta=instance.scheduled_for
            )
        # If pending but not scheduled, send immediately via background task
        elif instance.status == "pending" and not instance.scheduled_for:
            process_notification.delay(str(instance.id))

        # For in-app notifications that were just marked as sent,
        # send unread count update to WebSocket
        if instance.channel == "in_app" and instance.status == "sent":
            from apps.notificationsapp.services.notification_service import NotificationService

            unread_count = NotificationService.get_unread_count(instance.user_id)

            try:
                async_to_sync(channel_layer.group_send)(
                    f"notifications_{instance.user_id}",
                    {"type": "unread_count_update", "count": unread_count},
                )
            except Exception as e:
                # WebSocket channel may not exist yet, log this for debugging
                logger.debug(
                    f"Failed to send notification update to WebSocket for user {instance.user_id}: {str(e)}"
                )


@receiver(pre_save, sender=Notification)
def handle_notification_status_change(sender, instance, **kwargs):
    """Handle notification status changes"""
    # Check if this is an existing notification (not new)
    if instance.pk:
        try:
            old_instance = Notification.objects.get(pk=instance.pk)

            # If status changed to 'read'
            if old_instance.status != "read" and instance.status == "read":
                # Send unread count update to WebSocket
                from apps.notificationsapp.services.notification_service import NotificationService

                unread_count = NotificationService.get_unread_count(instance.user_id)

                try:
                    async_to_sync(channel_layer.group_send)(
                        f"notifications_{instance.user_id}",
                        {"type": "unread_count_update", "count": unread_count},
                    )
                except Exception as e:
                    # WebSocket channel may not exist, log this for debugging
                    logger.debug(
                        f"Failed to send notification status update to WebSocket for user {instance.user_id}: {str(e)}"
                    )

        except Notification.DoesNotExist:
            # This is a new notification or it was deleted, log this unusual case
            logger.warning(
                f"Attempted to update non-existent notification with ID {instance.pk}. This could indicate a race condition."
            )
