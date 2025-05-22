import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.notificationsapp.models import (
    DeadLetterNotification,
    Notification,
)
from apps.notificationsapp.tasks import (
    retry_failed_notification_task,
    send_email_notification_task,
    send_push_notification_task,
    send_sms_notification_task,
)

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

# Rate limiting constants
SMS_RATE_LIMIT = getattr(
    settings,
    "SMS_RATE_LIMIT",
    {
        "user": 5,  # Max 5 SMS per user per hour
        "global": 100,  # Max 100 SMS per hour globally
    },
)

EMAIL_RATE_LIMIT = getattr(
    settings,
    "EMAIL_RATE_LIMIT",
    {
        "user": 10,  # Max 10 emails per user per hour
        "global": 500,  # Max 500 emails per hour globally
    },
)

# Retry configuration
MAX_RETRY_ATTEMPTS = getattr(settings, "NOTIFICATION_MAX_RETRY_ATTEMPTS", 5)
RETRY_DELAY_BASE = getattr(
    settings, "NOTIFICATION_RETRY_DELAY_BASE", 60
)  # 1 minute base delay


class NotificationService:
    @classmethod
    def send_notification(
        cls,
        recipient_id: str,
        notification_type: str,
        title: str,
        message: str,
        channels: List[str] = None,
        data: Dict[str, Any] = None,
        scheduled_for: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        priority: str = "normal",
        idempotency_key: Optional[str] = None,
        rate_limit_bypass: bool = False,
    ) -> Dict[str, Any]:
        """
        Send a notification to a recipient using the specified channels.

        Args:
            recipient_id: ID of the recipient
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            channels: List of channels (email, sms, push, in_app)
            data: Additional data for the notification
            scheduled_for: Optional future time to send the notification
            metadata: Additional metadata
            priority: Notification priority (high, normal, low)
            idempotency_key: Key to prevent duplicate notifications
            rate_limit_bypass: Whether to bypass rate limiting

        Returns:
            Dictionary with notification result
        """
        try:
            # Validate inputs
            if not recipient_id or not notification_type or not message:
                return {
                    "success": False,
                    "message": "Recipient ID, notification type, and message are required",
                }

            # Set default channels if not provided
            if not channels:
                channels = ["in_app"]

            # Check for duplicate notification if idempotency key provided
            if idempotency_key:
                existing = Notification.objects.filter(
                    idempotency_key=idempotency_key,
                    created_at__gte=timezone.now() - timedelta(hours=24),
                ).first()

                if existing:
                    return {
                        "success": True,
                        "notification_id": str(existing.id),
                        "message": "Duplicate notification prevented by idempotency key",
                    }

            # Apply rate limiting for SMS and email if not bypassed
            if not rate_limit_bypass:
                for channel in channels:
                    if channel == "sms" and not cls._check_sms_rate_limit(recipient_id):
                        channels.remove("sms")
                        logger.warning(
                            f"SMS rate limit exceeded for recipient {recipient_id}"
                        )

                    if channel == "email" and not cls._check_email_rate_limit(
                        recipient_id
                    ):
                        channels.remove("email")
                        logger.warning(
                            f"Email rate limit exceeded for recipient {recipient_id}"
                        )

            # If all channels were removed due to rate limiting
            if not channels:
                return {
                    "success": False,
                    "message": "All notification channels exceeded rate limits",
                }

            # Process notification immediately
            notification_data = {
                "notification_id": str(notification.id),
                "recipient_id": recipient_id,
                "title": title,
                "message": message,
                "data": data,
                "channels": channels,
                "metadata": metadata,
            }

            # Track channel status for reporting
            channel_results = {}
            all_channels_success = True

            # Process each channel
            for channel in channels:
                try:
                    if channel == "email":
                        send_email_notification_task.delay(**notification_data)
                        channel_results["email"] = {"status": "queued"}

                    elif channel == "sms":
                        send_sms_notification_task.delay(**notification_data)
                        channel_results["sms"] = {"status": "queued"}

                    elif channel == "push":
                        send_push_notification_task.delay(**notification_data)
                        channel_results["push"] = {"status": "queued"}

                    elif channel == "in_app":
                        # In-app notifications are stored in the database
                        notification.in_app_seen = False
                        channel_results["in_app"] = {"status": "delivered"}

                except Exception as e:
                    logger.error(f"Error queueing {channel} notification: {str(e)}")
                    channel_results[channel] = {"status": "error", "message": str(e)}
                    all_channels_success = False

            # Update notification with channel status
            notification.channel_status = channel_results
            notification.status = "processing"
            notification.save()

            return {
                "success": True,
                "notification_id": str(notification.id),
                "channels_status": channel_results,
                "all_channels_success": all_channels_success,
            }

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return {
                "success": False,
                "message": f"Error sending notification: {str(e)}",
            }

    @classmethod
    def update_notification_status(
        cls,
        notification_id: str,
        channel: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update the status of a notification channel. If failed, schedule retry if attempts remain.

        Args:
            notification_id: ID of the notification
            channel: Name of the channel to update
            status: New status value
            error_message: Optional error message in case of failure

        Returns:
            Boolean indicating success
        """
        try:
            # Use select_for_update with nowait to prevent concurrent updates
            # The nowait option will raise an error if the row is locked
            try:
                with transaction.atomic():
                    try:
                        notification = Notification.objects.select_for_update(
                            nowait=True
                        ).get(id=notification_id)
                    except Notification.DoesNotExist:
                        logger.error(
                            f"Notification not found with ID: {notification_id}"
                        )
                        return False

                    # Add a small delay before proceeding if we're retrying
                    # This helps spread out retries and reduce contention
                    retry_count = notification.retry_count.get(channel, 0)
                    if retry_count > 0 and status == "retrying":
                        time.sleep(0.1 * min(retry_count, 5))  # Max 0.5 seconds

                    # Update channel status
                    channel_status = notification.channel_status or {}
                    channel_status[channel] = {
                        "status": status,
                        "updated_at": timezone.now().isoformat(),
                    }

                    if error_message:
                        channel_status[channel]["error"] = error_message

                    notification.channel_status = channel_status

                    # Check if all channels are processed
                    all_processed = True
                    all_success = True

                    for ch in notification.channels:
                        if ch not in channel_status:
                            all_processed = False
                            break

                        ch_status = channel_status[ch].get("status")
                        if ch_status not in ["delivered", "seen", "error"]:
                            all_processed = False
                            break

                        if ch_status == "error":
                            all_success = False

                    # Schedule retry if the channel failed but still has retry attempts left
                    if status == "error":
                        retry_count = notification.retry_count.get(channel, 0)

                        if retry_count < MAX_RETRY_ATTEMPTS:
                            # Calculate exponential backoff delay (1min, 2min, 4min, 8min, etc.)
                            # Add a small random jitter to prevent thundering herd
                            import random

                            jitter = random.uniform(0.8, 1.2)
                            delay_seconds = int(
                                RETRY_DELAY_BASE * (2**retry_count) * jitter
                            )

                            # Update retry count
                            retry_data = notification.retry_count or {}
                            retry_data[channel] = retry_count + 1
                            notification.retry_count = retry_data

                            # Schedule retry with the calculated delay
                            retry_failed_notification_task.apply_async(
                                args=[notification_id, channel], countdown=delay_seconds
                            )

                            logger.info(
                                f"Scheduled retry #{retry_count+1} for notification {notification_id} "
                                f"channel {channel} in {delay_seconds} seconds"
                            )
                        else:
                            # Move to dead letter queue
                            cls._move_to_dead_letter_queue(
                                notification,
                                channel,
                                error_message or "Max retry attempts exceeded",
                            )

                    # Update overall status
                    if all_processed:
                        notification.status = "completed" if all_success else "partial"
                        notification.completed_at = timezone.now()

                    notification.save()
                    return True

            except DatabaseError as e:
                # This catches lock wait timeout and deadlocks
                logger.warning(
                    f"Database error updating notification {notification_id}: {str(e)}"
                )
                # Add a small delay and retry once
                time.sleep(0.5)
                with transaction.atomic():
                    notification = Notification.objects.select_for_update().get(
                        id=notification_id
                    )
                    # Perform minimal update to avoid race conditions
                    if status == "error":
                        # Just increment retry count if we're handling an error
                        retry_data = notification.retry_count or {}
                        retry_count = retry_data.get(channel, 0) + 1
                        retry_data[channel] = retry_count
                        notification.retry_count = retry_data
                        notification.save(update_fields=["retry_count"])

                        # Schedule retry outside transaction
                        delay_seconds = RETRY_DELAY_BASE * (2**retry_count)
                        retry_failed_notification_task.apply_async(
                            args=[notification_id, channel], countdown=delay_seconds
                        )

                    return True

        except Exception as e:
            logger.error(f"Error updating notification status: {str(e)}", exc_info=True)
            return False

    @classmethod
    def retry_notification(cls, notification_id: str, channel: str) -> bool:
        """
        Retry sending a notification through a specific channel.

        Args:
            notification_id: ID of the notification
            channel: Channel to retry

        Returns:
            Boolean indicating success
        """
        try:
            try:
                notification = Notification.objects.get(id=notification_id)
            except Notification.DoesNotExist:
                logger.error(f"Notification not found with ID: {notification_id}")
                return False

            # Only retry if channel is in the notification's channels
            if channel not in notification.channels:
                logger.error(
                    f"Channel {channel} not found in notification {notification_id}"
                )
                return False

            # Prepare notification data
            notification_data = {
                "notification_id": str(notification.id),
                "recipient_id": notification.recipient_id,
                "title": notification.title,
                "message": notification.message,
                "data": notification.data,
                "metadata": notification.metadata,
            }

            # Update status to indicate retry
            channel_status = notification.channel_status or {}
            channel_status[channel] = {
                "status": "retrying",
                "updated_at": timezone.now().isoformat(),
            }
            notification.channel_status = channel_status
            notification.save()

            # Send to appropriate channel
            if channel == "email":
                send_email_notification_task.delay(**notification_data)
            elif channel == "sms":
                send_sms_notification_task.delay(**notification_data)
            elif channel == "push":
                send_push_notification_task.delay(**notification_data)

            return True

        except Exception as e:
            logger.error(f"Error retrying notification: {str(e)}")
            return False

    @classmethod
    def get_notifications(
        cls,
        recipient_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        notification_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        include_seen: bool = False,
    ) -> Dict[str, Any]:
        """
        Get notifications for a recipient.

        Args:
            recipient_id: ID of the recipient
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            notification_type: Optional type filter
            status: Optional status filter
            limit: Maximum number of notifications to return
            include_seen: Whether to include notifications marked as seen

        Returns:
            Dictionary with notifications
        """
        try:
            # Set default date range if not provided
            if not end_date:
                end_date = timezone.now()
            if not start_date:
                start_date = end_date - timedelta(days=30)  # 30 days by default

            # Validate date range
            if end_date < start_date:
                return {
                    "success": False,
                    "message": "End date must be after start date",
                }

            # Base query
            query = Notification.objects.filter(
                recipient_id=recipient_id,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )

            # Apply filters
            if notification_type:
                query = query.filter(notification_type=notification_type)

            if status:
                query = query.filter(status=status)

            if not include_seen:
                query = query.filter(in_app_seen=False)

            # Add channel filter for in-app notifications
            query = query.filter(channels__contains=["in_app"])

            # Get count and paginated results
            total_count = query.count()
            notifications = query.order_by("-created_at")[:limit]

            # Format results
            formatted_notifications = []
            for n in notifications:
                formatted_notifications.append(
                    {
                        "id": str(n.id),
                        "type": n.notification_type,
                        "title": n.title,
                        "message": n.message,
                        "data": n.data,
                        "created_at": n.created_at.isoformat(),
                        "status": n.status,
                        "seen": n.in_app_seen,
                        "priority": n.priority,
                    }
                )

            return {
                "success": True,
                "recipient_id": recipient_id,
                "total_count": total_count,
                "returned_count": len(formatted_notifications),
                "notifications": formatted_notifications,
            }

        except Exception as e:
            logger.error(f"Error getting notifications: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting notifications: {str(e)}",
            }

    @classmethod
    def mark_notification_seen(cls, notification_id: str) -> Dict[str, Any]:
        """
        Mark a notification as seen.

        Args:
            notification_id: ID of the notification

        Returns:
            Dictionary with update status
        """
        try:
            try:
                notification = Notification.objects.get(id=notification_id)
            except Notification.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Notification not found with ID: {notification_id}",
                }

            # Mark as seen
            notification.in_app_seen = True
            notification.seen_at = timezone.now()
            notification.save()

            # Update channel status if in_app is a channel
            if "in_app" in notification.channels:
                channel_status = notification.channel_status or {}
                channel_status["in_app"] = {
                    "status": "seen",
                    "updated_at": timezone.now().isoformat(),
                }
                notification.channel_status = channel_status
                notification.save()

            return {"success": True, "notification_id": str(notification.id)}

        except Exception as e:
            logger.error(f"Error marking notification as seen: {str(e)}")
            return {
                "success": False,
                "message": f"Error marking notification as seen: {str(e)}",
            }

    # Helper methods for rate limiting

    @classmethod
    def _check_sms_rate_limit(cls, recipient_id: str) -> bool:
        """
        Check if SMS rate limit has been exceeded.

        Args:
            recipient_id: ID of the recipient

        Returns:
            Boolean indicating if rate limit is not exceeded
        """
        # Check user-specific rate limit
        user_key = f"sms_rate_limit:{recipient_id}"
        user_count = cache.get(user_key, 0)

        if user_count >= SMS_RATE_LIMIT["user"]:
            return False

        # Check global rate limit
        global_key = "sms_rate_limit:global"
        global_count = cache.get(global_key, 0)

        if global_count >= SMS_RATE_LIMIT["global"]:
            return False

        # Increment counters
        cache.set(user_key, user_count + 1, 3600)  # 1 hour expiry
        cache.set(global_key, global_count + 1, 3600)  # 1 hour expiry

        return True

    @classmethod
    def _check_email_rate_limit(cls, recipient_id: str) -> bool:
        """
        Check if email rate limit has been exceeded.

        Args:
            recipient_id: ID of the recipient

        Returns:
            Boolean indicating if rate limit is not exceeded
        """
        # Check user-specific rate limit
        user_key = f"email_rate_limit:{recipient_id}"
        user_count = cache.get(user_key, 0)

        if user_count >= EMAIL_RATE_LIMIT["user"]:
            return False

        # Check global rate limit
        global_key = "email_rate_limit:global"
        global_count = cache.get(global_key, 0)

        if global_count >= EMAIL_RATE_LIMIT["global"]:
            return False

        # Increment counters
        cache.set(user_key, user_count + 1, 3600)  # 1 hour expiry
        cache.set(global_key, global_count + 1, 3600)  # 1 hour expiry

        return True

    @classmethod
    def _move_to_dead_letter_queue(
        cls, notification: Notification, channel: str, error_message: str
    ) -> None:
        """
        Move a failed notification to the dead letter queue.

        Args:
            notification: The notification object
            channel: Channel that failed
            error_message: Error message
        """
        try:
            # Create a record in the dead letter queue
            DeadLetterNotification.objects.create(
                original_notification_id=notification.id,
                recipient_id=notification.recipient_id,
                notification_type=notification.notification_type,
                channel=channel,
                title=notification.title,
                message=notification.message,
                data=notification.data,
                metadata=notification.metadata,
                error_message=error_message,
                retry_count=notification.retry_count.get(channel, 0),
            )

            logger.warning(
                f"Notification {notification.id} channel {channel} moved to dead letter queue "
                f"after {notification.retry_count.get(channel, 0)} retries. Error: {error_message}"
            )

        except Exception as e:
            logger.error(f"Error moving notification to dead letter queue: {str(e)}")

    # Application-specific notification methods

    @classmethod
    def send_appointment_created(cls, appointment):
        """Send notification when an appointment is created"""
        return cls.send_notification(
            recipient_id=str(appointment.customer.id),
            notification_type="appointment_created",
            title="Appointment Confirmation",
            message=f"Your appointment with {appointment.specialist.name} has been created.",
            channels=["in_app", "email"],
            data={
                "appointment_id": str(appointment.id),
                "date": appointment.date.isoformat(),
                "time": appointment.start_time.isoformat(),
                "specialist_name": appointment.specialist.name,
                "service_name": appointment.service.name,
                "shop_name": appointment.shop.name,
            },
        )

    @classmethod
    def send_specialist_new_appointment(cls, appointment):
        """Send notification to specialist about new appointment"""
        return cls.send_notification(
            recipient_id=str(appointment.specialist.id),
            notification_type="specialist_new_appointment",
            title="New Appointment",
            message=f"You have a new appointment with {appointment.customer.name}.",
            channels=["in_app", "email"],
            data={
                "appointment_id": str(appointment.id),
                "date": appointment.date.isoformat(),
                "time": appointment.start_time.isoformat(),
                "customer_name": appointment.customer.name,
                "service_name": appointment.service.name,
            },
        )

    @classmethod
    def send_appointment_confirmed(cls, appointment):
        """Send notification when an appointment is confirmed"""
        return cls.send_notification(
            recipient_id=str(appointment.customer.id),
            notification_type="appointment_confirmed",
            title="Appointment Confirmed",
            message=f"Your appointment with {appointment.specialist.name} has been confirmed.",
            channels=["in_app", "email", "sms"],
            data={
                "appointment_id": str(appointment.id),
                "date": appointment.date.isoformat(),
                "time": appointment.start_time.isoformat(),
                "specialist_name": appointment.specialist.name,
                "service_name": appointment.service.name,
                "shop_name": appointment.shop.name,
            },
        )

    @classmethod
    def send_appointment_cancelled(cls, appointment, previous_status):
        """Send notification when an appointment is cancelled"""
        # Notify customer
        customer_result = cls.send_notification(
            recipient_id=str(appointment.customer.id),
            notification_type="appointment_cancelled",
            title="Appointment Cancelled",
            message=f"Your appointment with {appointment.specialist.name} has been cancelled.",
            channels=["in_app", "email", "sms"],
            data={
                "appointment_id": str(appointment.id),
                "date": appointment.date.isoformat(),
                "time": appointment.start_time.isoformat(),
                "specialist_name": appointment.specialist.name,
                "service_name": appointment.service.name,
                "shop_name": appointment.shop.name,
                "previous_status": previous_status,
            },
        )

        # Notify specialist
        specialist_result = cls.send_notification(
            recipient_id=str(appointment.specialist.id),
            notification_type="appointment_cancelled",
            title="Appointment Cancelled",
            message=f"The appointment with {appointment.customer.name} has been cancelled.",
            channels=["in_app", "email"],
            data={
                "appointment_id": str(appointment.id),
                "date": appointment.date.isoformat(),
                "time": appointment.start_time.isoformat(),
                "customer_name": appointment.customer.name,
                "service_name": appointment.service.name,
                "previous_status": previous_status,
            },
        )

        return {
            "customer_notification": customer_result,
            "specialist_notification": specialist_result,
        }

    @classmethod
    def send_appointment_rescheduled(
        cls, appointment, old_date, old_time, old_specialist
    ):
        """Send notification when an appointment is rescheduled"""
        # Notify customer
        customer_result = cls.send_notification(
            recipient_id=str(appointment.customer.id),
            notification_type="appointment_rescheduled",
            title="Appointment Rescheduled",
            message=f"Your appointment has been rescheduled to {appointment.date.isoformat()} at {appointment.start_time.isoformat()}.",
            channels=["in_app", "email", "sms"],
            data={
                "appointment_id": str(appointment.id),
                "new_date": appointment.date.isoformat(),
                "new_time": appointment.start_time.isoformat(),
                "old_date": old_date.isoformat(),
                "old_time": old_time.isoformat(),
                "specialist_name": appointment.specialist.name,
                "service_name": appointment.service.name,
                "shop_name": appointment.shop.name,
                "specialist_changed": str(old_specialist.id)
                != str(appointment.specialist.id),
            },
        )

        # Notify new specialist if different
        if str(old_specialist.id) != str(appointment.specialist.id):
            new_specialist_result = cls.send_notification(
                recipient_id=str(appointment.specialist.id),
                notification_type="specialist_new_appointment",
                title="New Appointment (Rescheduled)",
                message=f"You have a new appointment with {appointment.customer.name}.",
                channels=["in_app", "email"],
                data={
                    "appointment_id": str(appointment.id),
                    "date": appointment.date.isoformat(),
                    "time": appointment.start_time.isoformat(),
                    "customer_name": appointment.customer.name,
                    "service_name": appointment.service.name,
                },
            )
        else:
            new_specialist_result = None

        # Notify old specialist if different
        if str(old_specialist.id) != str(appointment.specialist.id):
            old_specialist_result = cls.send_notification(
                recipient_id=str(old_specialist.id),
                notification_type="appointment_reassigned",
                title="Appointment Reassigned",
                message=f"The appointment with {appointment.customer.name} has been reassigned.",
                channels=["in_app", "email"],
                data={
                    "appointment_id": str(appointment.id),
                    "old_date": old_date.isoformat(),
                    "old_time": old_time.isoformat(),
                    "customer_name": appointment.customer.name,
                    "service_name": appointment.service.name,
                    "new_specialist_name": appointment.specialist.name,
                },
            )
        else:
            old_specialist_result = cls.send_notification(
                recipient_id=str(appointment.specialist.id),
                notification_type="appointment_rescheduled",
                title="Appointment Rescheduled",
                message=f"The appointment with {appointment.customer.name} has been rescheduled.",
                channels=["in_app", "email"],
                data={
                    "appointment_id": str(appointment.id),
                    "new_date": appointment.date.isoformat(),
                    "new_time": appointment.start_time.isoformat(),
                    "old_date": old_date.isoformat(),
                    "old_time": old_time.isoformat(),
                    "customer_name": appointment.customer.name,
                    "service_name": appointment.service.name,
                },
            )

        return {
            "customer_notification": customer_result,
            "new_specialist_notification": new_specialist_result,
            "old_specialist_notification": old_specialist_result,
        }

    @classmethod
    def send_appointment_reminder(cls, appointment, hours_before=24):
        """Send reminder notification for upcoming appointment"""
        return cls.send_notification(
            recipient_id=str(appointment.customer.id),
            notification_type="appointment_reminder",
            title="Appointment Reminder",
            message=f"Reminder: Your appointment with {appointment.specialist.name} is in {hours_before} hours.",
            channels=(
                ["in_app", "email", "sms"] if hours_before <= 3 else ["in_app", "email"]
            ),
            data={
                "appointment_id": str(appointment.id),
                "date": appointment.date.isoformat(),
                "time": appointment.start_time.isoformat(),
                "specialist_name": appointment.specialist.name,
                "service_name": appointment.service.name,
                "shop_name": appointment.shop.name,
                "hours_before": hours_before,
            },
        )

    @classmethod
    def send_appointment_completed(cls, appointment):
        """Send notification when an appointment is completed"""
        return cls.send_notification(
            recipient_id=str(appointment.customer.id),
            notification_type="appointment_completed",
            title="Appointment Completed",
            message=f"Thank you for visiting {appointment.shop.name}. We hope you enjoyed your service.",
            channels=["in_app", "email"],
            data={
                "appointment_id": str(appointment.id),
                "date": appointment.date.isoformat(),
                "specialist_name": appointment.specialist.name,
                "service_name": appointment.service.name,
                "shop_name": appointment.shop.name,
            },
        )

    @classmethod
    def send_appointment_no_show(cls, appointment):
        """Send notification when customer doesn't show up for appointment"""
        return cls.send_notification(
            recipient_id=str(appointment.customer.id),
            notification_type="appointment_no_show",
            title="Missed Appointment",
            message=f"You missed your appointment with {appointment.specialist.name} at {appointment.shop.name}.",
            channels=["in_app", "email"],
            data={
                "appointment_id": str(appointment.id),
                "date": appointment.date.isoformat(),
                "time": appointment.start_time.isoformat(),
                "specialist_name": appointment.specialist.name,
                "service_name": appointment.service.name,
                "shop_name": appointment.shop.name,
            },
        )
