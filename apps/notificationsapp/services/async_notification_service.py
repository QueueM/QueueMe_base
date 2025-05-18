"""
Asynchronous Notification Service

This module provides high-performance notification delivery
using asynchronous task processing with prioritization and batching.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from celery import chain, chord, group, shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.notificationsapp.enums import (  # type: ignore
    DeliveryChannel,
    NotificationDeliveryStatus,
    NotificationType,
)
from apps.notificationsapp.models import Notification, NotificationDelivery
from core.cache.advanced_cache import AdvancedCache, cached

logger = logging.getLogger(__name__)

# Initialize cache for notifications
notification_cache = AdvancedCache("notification")

# Default batch sizes
PUSH_BATCH_SIZE = getattr(settings, "PUSH_NOTIFICATION_BATCH_SIZE", 100)
EMAIL_BATCH_SIZE = getattr(settings, "EMAIL_NOTIFICATION_BATCH_SIZE", 50)
SMS_BATCH_SIZE = getattr(settings, "SMS_NOTIFICATION_BATCH_SIZE", 25)


class AsyncNotificationService:
    """
    Service for sending notifications asynchronously with
    prioritization, batching, and delivery tracking
    """

    @staticmethod
    def send_notification(
        user_ids: List[str],
        notification_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        channels: Optional[List[str]] = None,
        priority: str = "normal",
        scheduled_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Queue a notification for asynchronous delivery

        Args:
            user_ids: List of user IDs to send notification to
            notification_type: Type of notification (from NotificationType)
            title: Notification title
            message: Notification message
            data: Additional data for the notification
            channels: Delivery channels (push, email, sms) or None for all
            priority: Priority level (high, normal, low)
            scheduled_time: Optional time to schedule delivery

        Returns:
            Dictionary with notification IDs and status
        """
        # Validate channels
        valid_channels = {c.value for c in DeliveryChannel}
        if channels:
            channels = [c for c in channels if c in valid_channels]
        else:
            # Default to all channels if not specified
            channels = list(valid_channels)

        if not channels:
            return {"error": "No valid delivery channels specified"}

        # Create notification
        with transaction.atomic():
            # Save base notification
            notification = Notification.objects.create(
                notification_type=notification_type,
                title=title,
                message=message,
                data=data or {},
                priority=priority,
            )

            # Create delivery tasks for each user/channel
            deliveries = []
            for user_id in user_ids:
                for channel in channels:
                    delivery = NotificationDelivery.objects.create(
                        notification=notification,
                        user_id=user_id,
                        channel=channel,
                        status=NotificationDeliveryStatus.PENDING.value,
                        scheduled_time=scheduled_time or timezone.now(),
                    )
                    deliveries.append(delivery)

        # Queue for processing based on priority and scheduled time
        if scheduled_time and scheduled_time > timezone.now():
            # Schedule for later delivery
            process_notifications_task.apply_async(args=[notification.id], eta=scheduled_time)
        else:
            # Process immediately based on priority
            if priority == "high":
                process_notifications_task.apply_async(
                    args=[notification.id],
                    priority=0,  # Higher Celery priority (lower number)
                )
            elif priority == "low":
                process_notifications_task.apply_async(
                    args=[notification.id],
                    priority=9,  # Lower Celery priority (higher number)
                )
            else:  # normal
                process_notifications_task.apply_async(
                    args=[notification.id], priority=5  # Default Celery priority
                )

        return {
            "notification_id": str(notification.id),
            "status": "queued",
            "delivery_count": len(deliveries),
        }

    @staticmethod
    def bulk_send_notification(
        notification_configs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Queue multiple notifications in bulk

        Args:
            notification_configs: List of notification configurations

        Returns:
            List of notification IDs and status
        """
        results = []
        for config in notification_configs:
            result = AsyncNotificationService.send_notification(
                user_ids=config.get("user_ids", []),
                notification_type=config.get("notification_type", ""),
                title=config.get("title", ""),
                message=config.get("message", ""),
                data=config.get("data"),
                channels=config.get("channels"),
                priority=config.get("priority", "normal"),
                scheduled_time=config.get("scheduled_time"),
            )
            results.append(result)

        return results

    @staticmethod
    def cancel_notification(notification_id: str) -> bool:
        """
        Cancel a pending notification

        Args:
            notification_id: ID of notification to cancel

        Returns:
            True if successful, False otherwise
        """
        try:
            with transaction.atomic():
                # Update all pending deliveries
                updated = NotificationDelivery.objects.filter(
                    notification_id=notification_id,
                    status=NotificationDeliveryStatus.PENDING.value,
                ).update(
                    status=NotificationDeliveryStatus.CANCELLED.value,
                    updated_at=timezone.now(),
                )

                # Update notification (if there are no in-progress deliveries)
                if not NotificationDelivery.objects.filter(
                    notification_id=notification_id,
                    status=NotificationDeliveryStatus.PROCESSING.value,
                ).exists():
                    Notification.objects.filter(id=notification_id).update(
                        cancelled=True, updated_at=timezone.now()
                    )

                return updated > 0
        except Exception as e:
            logger.error(f"Error cancelling notification {notification_id}: {e}")
            return False

    @staticmethod
    def get_notification_status(notification_id: str) -> Dict[str, Any]:
        """
        Get detailed status of a notification

        Args:
            notification_id: ID of notification

        Returns:
            Status details dictionary
        """
        try:
            # Get notification
            notification = Notification.objects.get(id=notification_id)

            # Get delivery statistics
            deliveries = NotificationDelivery.objects.filter(notification=notification)
            delivery_stats = {}

            for status in NotificationDeliveryStatus:
                delivery_stats[status.value] = deliveries.filter(status=status.value).count()

            channel_stats = {}
            for channel in DeliveryChannel:
                channel_stats[channel.value] = {
                    "total": deliveries.filter(channel=channel.value).count(),
                    "success": deliveries.filter(
                        channel=channel.value,
                        status=NotificationDeliveryStatus.DELIVERED.value,
                    ).count(),
                    "failed": deliveries.filter(
                        channel=channel.value,
                        status=NotificationDeliveryStatus.FAILED.value,
                    ).count(),
                }

            return {
                "notification_id": str(notification.id),
                "notification_type": notification.notification_type,
                "title": notification.title,
                "created_at": notification.created_at.isoformat(),
                "cancelled": notification.cancelled,
                "delivery_stats": delivery_stats,
                "channel_stats": channel_stats,
                "total_deliveries": deliveries.count(),
                "completed": (
                    delivery_stats.get(NotificationDeliveryStatus.DELIVERED.value, 0)
                    + delivery_stats.get(NotificationDeliveryStatus.FAILED.value, 0)
                    + delivery_stats.get(NotificationDeliveryStatus.CANCELLED.value, 0)
                )
                == deliveries.count(),
            }
        except Notification.DoesNotExist:
            return {"error": "Notification not found"}
        except Exception as e:
            logger.error(f"Error getting notification status {notification_id}: {e}")
            return {"error": str(e)}

    @staticmethod
    def retry_failed_deliveries(
        notification_id: Optional[str] = None,
        channel: Optional[str] = None,
        max_age_hours: int = 24,
    ) -> Dict[str, int]:
        """
        Retry failed notification deliveries

        Args:
            notification_id: Optional specific notification ID
            channel: Optional specific channel
            max_age_hours: Maximum age in hours for retrying

        Returns:
            Dictionary with retry counts
        """
        try:
            # Build query for failed deliveries
            min_time = timezone.now() - timedelta(hours=max_age_hours)
            query = Q(status=NotificationDeliveryStatus.FAILED.value, updated_at__gte=min_time)

            if notification_id:
                query &= Q(notification_id=notification_id)

            if channel:
                query &= Q(channel=channel)

            # Get failed deliveries
            failed_deliveries = NotificationDelivery.objects.filter(query)

            # Group by notification for efficiency
            notification_ids = set(failed_deliveries.values_list("notification_id", flat=True))

            # Queue each notification for retry
            for n_id in notification_ids:
                process_notifications_task.apply_async(args=[n_id], priority=8)

            return {
                "notifications_queued": len(notification_ids),
                "deliveries_affected": failed_deliveries.count(),
            }
        except Exception as e:
            logger.error(f"Error retrying failed deliveries: {e}")
            return {"error": str(e), "deliveries_affected": 0}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_notifications_task(self, notification_id: str) -> Dict[str, Any]:
    """
    Process notifications in the background

    Args:
        notification_id: ID of notification to process

    Returns:
        Status information
    """
    try:
        # Get notification
        notification = Notification.objects.get(id=notification_id)

        # Skip if cancelled
        if notification.cancelled:
            return {"status": "cancelled", "notification_id": str(notification_id)}

        # Get pending deliveries grouped by channel for batching
        deliveries_by_channel = {}

        for channel in DeliveryChannel:
            channel_deliveries = NotificationDelivery.objects.filter(
                notification=notification,
                channel=channel.value,
                status=NotificationDeliveryStatus.PENDING.value,
            )
            deliveries_by_channel[channel.value] = list(channel_deliveries)

        # Process each channel with appropriate batching
        tasks = []

        # Push notifications
        push_deliveries = deliveries_by_channel.get(DeliveryChannel.PUSH.value, [])
        if push_deliveries:
            for i in range(0, len(push_deliveries), PUSH_BATCH_SIZE):
                batch = push_deliveries[i : i + PUSH_BATCH_SIZE]
                delivery_ids = [str(d.id) for d in batch]
                tasks.append(send_push_notifications_task.s(delivery_ids, notification.data))

        # Email notifications
        email_deliveries = deliveries_by_channel.get(DeliveryChannel.EMAIL.value, [])
        if email_deliveries:
            for i in range(0, len(email_deliveries), EMAIL_BATCH_SIZE):
                batch = email_deliveries[i : i + EMAIL_BATCH_SIZE]
                delivery_ids = [str(d.id) for d in batch]
                tasks.append(send_email_notifications_task.s(delivery_ids, notification.data))

        # SMS notifications
        sms_deliveries = deliveries_by_channel.get(DeliveryChannel.SMS.value, [])
        if sms_deliveries:
            for i in range(0, len(sms_deliveries), SMS_BATCH_SIZE):
                batch = sms_deliveries[i : i + SMS_BATCH_SIZE]
                delivery_ids = [str(d.id) for d in batch]
                tasks.append(send_sms_notifications_task.s(delivery_ids, notification.data))

        # Execute all tasks in parallel if any
        if tasks:
            chord(tasks)(update_notification_status_task.s(str(notification_id)))
            return {"status": "processing", "batch_count": len(tasks)}
        else:
            # No deliveries to process
            return {"status": "complete", "notification_id": str(notification_id)}

    except Notification.DoesNotExist:
        return {"status": "error", "error": "Notification not found"}
    except Exception as e:
        logger.error(f"Error processing notification {notification_id}: {e}")
        # Retry task
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {"status": "error", "error": str(e), "retries_exceeded": True}


@shared_task(bind=True, max_retries=2)
def send_push_notifications_task(
    self, delivery_ids: List[str], data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Send push notifications in batches

    Args:
        delivery_ids: List of delivery IDs
        data: Additional data for the notification

    Returns:
        Status information
    """
    try:
        from apps.notificationsapp.services.push_service import PushService

        # Mark deliveries as processing
        with transaction.atomic():
            NotificationDelivery.objects.filter(id__in=delivery_ids).update(
                status=NotificationDeliveryStatus.PROCESSING.value,
                updated_at=timezone.now(),
            )

        # Collect user devices by user ID
        deliveries = NotificationDelivery.objects.filter(id__in=delivery_ids).select_related(
            "notification"
        )
        user_ids = set(deliveries.values_list("user_id", flat=True))

        results = {}

        # Process in smaller batches for better reliability
        for delivery in deliveries:
            try:
                user_id = delivery.user_id
                notification = delivery.notification

                # Send the push notification using the device service
                success = PushService.send_push_notification(
                    user_id=user_id,
                    title=notification.title,
                    message=notification.message,
                    data=notification.data,
                )

                # Update delivery status
                delivery.status = (
                    NotificationDeliveryStatus.DELIVERED.value
                    if success
                    else NotificationDeliveryStatus.FAILED.value
                )
                delivery.attempts += 1
                delivery.updated_at = timezone.now()
                delivery.save()

                results[str(delivery.id)] = success
            except Exception as e:
                logger.error(f"Error sending push notification to user {delivery.user_id}: {e}")
                delivery.status = NotificationDeliveryStatus.FAILED.value
                delivery.error_message = str(e)
                delivery.attempts += 1
                delivery.updated_at = timezone.now()
                delivery.save()
                results[str(delivery.id)] = False

        return {
            "channel": DeliveryChannel.PUSH.value,
            "success_count": sum(1 for success in results.values() if success),
            "failure_count": sum(1 for success in results.values() if not success),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error sending push notifications: {e}")
        # Mark all as failed
        with transaction.atomic():
            NotificationDelivery.objects.filter(id__in=delivery_ids).update(
                status=NotificationDeliveryStatus.FAILED.value,
                error_message=str(e),
                attempts=F("attempts") + 1,
                updated_at=timezone.now(),
            )

        # Retry task
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "channel": DeliveryChannel.PUSH.value,
                "success_count": 0,
                "failure_count": len(delivery_ids),
                "error": str(e),
            }


@shared_task(bind=True, max_retries=2)
def send_email_notifications_task(
    self, delivery_ids: List[str], data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Send email notifications in batches

    Args:
        delivery_ids: List of delivery IDs
        data: Additional data for the notification

    Returns:
        Status information
    """
    try:
        from apps.notificationsapp.services.email_service import EmailService

        # Mark deliveries as processing
        with transaction.atomic():
            NotificationDelivery.objects.filter(id__in=delivery_ids).update(
                status=NotificationDeliveryStatus.PROCESSING.value,
                updated_at=timezone.now(),
            )

        # Get all deliveries
        deliveries = NotificationDelivery.objects.filter(id__in=delivery_ids).select_related(
            "notification"
        )

        results = {}

        # Process one by one
        for delivery in deliveries:
            try:
                user_id = delivery.user_id
                notification = delivery.notification

                # Send the email notification
                success = EmailService.send_notification_email(
                    user_id=user_id,
                    subject=notification.title,
                    message=notification.message,
                    template_data=notification.data,
                )

                # Update delivery status
                delivery.status = (
                    NotificationDeliveryStatus.DELIVERED.value
                    if success
                    else NotificationDeliveryStatus.FAILED.value
                )
                delivery.attempts += 1
                delivery.updated_at = timezone.now()
                delivery.save()

                results[str(delivery.id)] = success
            except Exception as e:
                logger.error(f"Error sending email notification to user {delivery.user_id}: {e}")
                delivery.status = NotificationDeliveryStatus.FAILED.value
                delivery.error_message = str(e)
                delivery.attempts += 1
                delivery.updated_at = timezone.now()
                delivery.save()
                results[str(delivery.id)] = False

        return {
            "channel": DeliveryChannel.EMAIL.value,
            "success_count": sum(1 for success in results.values() if success),
            "failure_count": sum(1 for success in results.values() if not success),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error sending email notifications: {e}")
        # Mark all as failed
        with transaction.atomic():
            NotificationDelivery.objects.filter(id__in=delivery_ids).update(
                status=NotificationDeliveryStatus.FAILED.value,
                error_message=str(e),
                attempts=F("attempts") + 1,
                updated_at=timezone.now(),
            )

        # Retry task
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "channel": DeliveryChannel.EMAIL.value,
                "success_count": 0,
                "failure_count": len(delivery_ids),
                "error": str(e),
            }


@shared_task(bind=True, max_retries=2)
def send_sms_notifications_task(
    self, delivery_ids: List[str], data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Send SMS notifications in batches

    Args:
        delivery_ids: List of delivery IDs
        data: Additional data for the notification

    Returns:
        Status information
    """
    try:
        from apps.notificationsapp.services.sms_service import SMSService

        # Mark deliveries as processing
        with transaction.atomic():
            NotificationDelivery.objects.filter(id__in=delivery_ids).update(
                status=NotificationDeliveryStatus.PROCESSING.value,
                updated_at=timezone.now(),
            )

        # Get all deliveries
        deliveries = NotificationDelivery.objects.filter(id__in=delivery_ids).select_related(
            "notification"
        )

        results = {}

        # Process one by one
        for delivery in deliveries:
            try:
                user_id = delivery.user_id
                notification = delivery.notification

                # Send the SMS notification
                success = SMSService.send_notification_sms(
                    user_id=user_id, message=notification.message
                )

                # Update delivery status
                delivery.status = (
                    NotificationDeliveryStatus.DELIVERED.value
                    if success
                    else NotificationDeliveryStatus.FAILED.value
                )
                delivery.attempts += 1
                delivery.updated_at = timezone.now()
                delivery.save()

                results[str(delivery.id)] = success
            except Exception as e:
                logger.error(f"Error sending SMS notification to user {delivery.user_id}: {e}")
                delivery.status = NotificationDeliveryStatus.FAILED.value
                delivery.error_message = str(e)
                delivery.attempts += 1
                delivery.updated_at = timezone.now()
                delivery.save()
                results[str(delivery.id)] = False

        return {
            "channel": DeliveryChannel.SMS.value,
            "success_count": sum(1 for success in results.values() if success),
            "failure_count": sum(1 for success in results.values() if not success),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error sending SMS notifications: {e}")
        # Mark all as failed
        with transaction.atomic():
            NotificationDelivery.objects.filter(id__in=delivery_ids).update(
                status=NotificationDeliveryStatus.FAILED.value,
                error_message=str(e),
                attempts=F("attempts") + 1,
                updated_at=timezone.now(),
            )

        # Retry task
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "channel": DeliveryChannel.SMS.value,
                "success_count": 0,
                "failure_count": len(delivery_ids),
                "error": str(e),
            }


@shared_task
def update_notification_status_task(
    results: List[Dict[str, Any]], notification_id: str
) -> Dict[str, Any]:
    """
    Update overall notification status after all channel tasks complete

    Args:
        results: List of results from channel tasks
        notification_id: Notification ID

    Returns:
        Status information
    """
    try:
        # Combine results
        success_count = sum(r.get("success_count", 0) for r in results)
        failure_count = sum(r.get("failure_count", 0) for r in results)

        # Check if all deliveries are complete
        all_complete = True
        notification = Notification.objects.get(id=notification_id)
        pending_count = NotificationDelivery.objects.filter(
            notification=notification, status=NotificationDeliveryStatus.PENDING.value
        ).count()

        processing_count = NotificationDelivery.objects.filter(
            notification=notification,
            status=NotificationDeliveryStatus.PROCESSING.value,
        ).count()

        all_complete = pending_count == 0 and processing_count == 0

        return {
            "notification_id": str(notification_id),
            "success_count": success_count,
            "failure_count": failure_count,
            "channel_results": results,
            "completed": all_complete,
        }
    except Exception as e:
        logger.error(f"Error updating notification status {notification_id}: {e}")
        return {"error": str(e), "notification_id": str(notification_id)}
