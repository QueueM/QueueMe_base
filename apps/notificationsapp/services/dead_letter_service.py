"""
Dead letter queue service for notification system.

This service provides functions to monitor and manage failed notifications
that have been moved to the dead letter queue after exceeding retry limits.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from django.utils import timezone

from apps.notificationsapp.models import DeadLetterNotification, Notification
from utils.error_handling import log_exception, transaction_with_retry

logger = logging.getLogger(__name__)


class DeadLetterQueueService:
    """
    Service for managing notifications in the dead letter queue.

    This service provides functions to:
    1. Retrieve dead letter notifications
    2. Retry dead letter notifications
    3. Generate reports on dead letter queue status
    4. Clean up old dead letter notifications
    """

    @classmethod
    @log_exception()
    def get_dead_letter_notifications(
        cls,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        channel: Optional[str] = None,
        error_contains: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict:
        """
        Get notifications in the dead letter queue with filtering options.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            channel: Optional channel filter
            error_contains: Optional error message contains filter
            limit: Maximum number of results to return
            offset: Offset for pagination

        Returns:
            Dictionary with dead letter notifications and count
        """
        # Set default date range if not provided
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=7)  # Default to last 7 days

        # Build query
        query = DeadLetterNotification.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Apply channel filter if provided
        if channel:
            query = query.filter(channel=channel)

        # Apply error message filter if provided
        if error_contains:
            query = query.filter(error_message__icontains=error_contains)

        # Get total count for pagination
        total_count = query.count()

        # Apply pagination
        dead_letter_notifications = query.order_by("-created_at")[
            offset : offset + limit
        ]

        # Format response
        results = []
        for dln in dead_letter_notifications:
            results.append(
                {
                    "id": str(dln.id),
                    "notification_id": str(dln.notification_id),
                    "recipient_id": str(dln.recipient_id),
                    "channel": dln.channel,
                    "error_message": dln.error_message,
                    "retry_count": dln.retry_count,
                    "created_at": dln.created_at.isoformat(),
                    "data": dln.data,
                }
            )

        return {
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "results": results,
        }

    @classmethod
    @transaction_with_retry(max_retries=3)
    def retry_dead_letter_notification(cls, dead_letter_id: str) -> Dict:
        """
        Retry sending a notification from the dead letter queue.

        Args:
            dead_letter_id: ID of the dead letter notification to retry

        Returns:
            Dictionary with retry result
        """
        try:
            # Get the dead letter notification
            dead_letter = DeadLetterNotification.objects.get(id=dead_letter_id)

            # Check if the original notification still exists
            try:
                notification = Notification.objects.get(id=dead_letter.notification_id)
            except Notification.DoesNotExist:
                return {
                    "success": False,
                    "message": "Original notification no longer exists",
                }

            # Import here to avoid circular imports
            from apps.notificationsapp.services.notification_service import (
                NotificationService,
            )

            # Retry the notification
            result = NotificationService.retry_notification(
                notification_id=str(dead_letter.notification_id),
                channel=dead_letter.channel,
            )

            if result:
                # Update dead letter notification status
                dead_letter.retried_at = timezone.now()
                dead_letter.save()

                return {
                    "success": True,
                    "message": f"Successfully retried notification via {dead_letter.channel}",
                    "notification_id": str(dead_letter.notification_id),
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to retry notification",
                }

        except DeadLetterNotification.DoesNotExist:
            return {
                "success": False,
                "message": f"Dead letter notification with ID {dead_letter_id} not found",
            }
        except Exception as e:
            logger.error(
                f"Error retrying dead letter notification: {str(e)}", exc_info=True
            )
            return {
                "success": False,
                "message": f"Error retrying dead letter notification: {str(e)}",
            }

    @classmethod
    def get_dead_letter_queue_stats(
        cls,
        days: int = 7,
        group_by: str = "channel",
    ) -> Dict:
        """
        Get statistics about the dead letter queue.

        Args:
            days: Number of days to include in stats
            group_by: Field to group stats by (channel, error_type, recipient_id)

        Returns:
            Dictionary with statistics
        """
        from django.db.models import Count

        # Set date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get base query
        query = DeadLetterNotification.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get total count
        total_count = query.count()

        # Get counts grouped by specified field
        if group_by == "channel":
            group_field = "channel"
        elif group_by == "error_type":
            # We don't have a specific error_type field, so use the first word of error_message
            # as a rough approximation
            from django.db.models.functions import Substr

            query = query.annotate(error_type=Substr("error_message", 1, 20))
            group_field = "error_type"
        elif group_by == "recipient_id":
            group_field = "recipient_id"
        else:
            group_field = "channel"  # Default

        grouped_counts = list(
            query.values(group_field).annotate(count=Count("id")).order_by("-count")
        )

        # Get counts by day for trend analysis
        from django.db.models.functions import TruncDay

        daily_counts = list(
            query.annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        # Format daily counts for easier plotting
        trend_data = [
            {"date": item["day"].strftime("%Y-%m-%d"), "count": item["count"]}
            for item in daily_counts
        ]

        return {
            "total_count": total_count,
            "period_days": days,
            "grouped_by": group_by,
            "groups": grouped_counts,
            "trend": trend_data,
        }

    @classmethod
    @log_exception()
    @transaction_with_retry(max_retries=3)
    def cleanup_old_notifications(cls, days_to_keep: int = 30) -> Dict:
        """
        Clean up old dead letter notifications.

        Args:
            days_to_keep: Number of days of notifications to keep

        Returns:
            Dictionary with cleanup result
        """
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        # Delete notifications older than cutoff date
        deleted_count, _ = DeadLetterNotification.objects.filter(
            created_at__lt=cutoff_date
        ).delete()

        logger.info(f"Deleted {deleted_count} old dead letter notifications")

        return {
            "success": True,
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
        }
