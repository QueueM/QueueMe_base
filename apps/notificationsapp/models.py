"""
Notification Models

This module defines the database models for the notification system.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationType:
    """Constants for notification types"""

    GENERAL = "general"
    APPOINTMENT_CREATED = "appointment_created"
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
    APPOINTMENT_REMINDER = "appointment_reminder"
    APPOINTMENT_COMPLETED = "appointment_completed"
    APPOINTMENT_NO_SHOW = "appointment_no_show"

    QUEUE_JOINED = "queue_joined"
    QUEUE_POSITION_UPDATED = "queue_position_updated"
    QUEUE_CALLED = "queue_called"
    QUEUE_COMPLETED = "queue_completed"

    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    PASSWORD_RESET_COMPLETE = "password_reset_complete"
    ACCOUNT_LOCKED = "account_locked"

    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_REFUNDED = "payment_refunded"

    REVIEW_RECEIVED = "review_received"
    REVIEW_REPLIED = "review_replied"

    SPECIALIST_NEW_APPOINTMENT = "specialist_new_appointment"
    SPECIALIST_CANCELLED_APPOINTMENT = "specialist_cancelled_appointment"

    MARKETING_CAMPAIGN = "marketing_campaign"
    SHOP_PROMOTION = "shop_promotion"


class NotificationChannel:
    """Constants for notification channels"""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"

    @classmethod
    def choices(cls):
        return [
            (cls.EMAIL, "Email"),
            (cls.SMS, "SMS"),
            (cls.PUSH, "Push Notification"),
            (cls.IN_APP, "In-App Notification"),
        ]


class NotificationTemplate(models.Model):
    """
    Template for notifications to ensure consistency across channels
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(
        max_length=50, unique=True, help_text="Unique identifier for this template type"
    )
    channel = models.CharField(
        max_length=20,
        choices=[
            ("email", "Email"),
            ("push", "Push Notification"),
            ("sms", "SMS"),
            ("in_app", "In-App Notification"),
        ],
    )
    subject = models.CharField(
        max_length=255,
        blank=True,
        help_text="Subject line for emails, or title for other notifications",
    )
    body_en = models.TextField(help_text="Template content in English with variable placeholders")
    body_ar = models.TextField(help_text="Template content in Arabic with variable placeholders")
    variables = models.JSONField(
        default=list,
        blank=True,
        help_text="List of available variables for this template",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["type", "channel"]]
        indexes = [models.Index(fields=["type"]), models.Index(fields=["channel"])]

    def __str__(self):
        return f"{self.type} ({self.channel})"


class Notification(models.Model):
    """
    Primary notification record that stores the content and metadata
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient_id = models.UUIDField(default=uuid.uuid4)
    notification_type = models.CharField(max_length=50, default="general")
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    title = models.CharField(max_length=255, default="Notification")
    message = models.TextField(default="")
    data = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    channels = models.JSONField(default=list)
    status = models.CharField(max_length=20, default="pending")
    channel_status = models.JSONField(default=dict, blank=True)
    retry_count = models.JSONField(default=dict, blank=True)
    priority = models.CharField(max_length=20, default="normal")
    scheduled_for = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    seen_at = models.DateTimeField(null=True, blank=True)
    cancelled = models.BooleanField(default=False)
    in_app_seen = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient_id"]),
            models.Index(fields=["notification_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["scheduled_for"]),
            models.Index(fields=["priority"]),
        ]

    def __str__(self):
        return f"{self.notification_type}: {self.title}"


class NotificationDelivery(models.Model):
    """
    Tracks delivery attempts for each notification to each user via each channel
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="deliveries"
    )
    user_id = models.UUIDField()
    channel = models.CharField(max_length=20)
    status = models.CharField(max_length=20)
    error_message = models.TextField(blank=True, null=True)
    attempts = models.PositiveIntegerField(default=0)
    scheduled_time = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_time"]
        indexes = [
            models.Index(fields=["user_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["channel"]),
            models.Index(fields=["scheduled_time"]),
        ]
        # Ensure we don't try to deliver the same notification via the same channel twice
        unique_together = [["notification", "user_id", "channel"]]

    def __str__(self):
        return f"{self.notification} to {self.user_id} via {self.channel}: {self.status}"


class DeviceToken(models.Model):
    """
    Store device tokens for push notifications
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="device_tokens"
    )
    token = models.CharField(max_length=255, unique=True)
    device_id = models.CharField(max_length=255, blank=True)
    platform = models.CharField(
        max_length=20,
        choices=[
            ("ios", "iOS"),
            ("android", "Android"),
            ("web", "Web"),
        ],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["platform"]),
            models.Index(fields=["is_active"]),
        ]
        unique_together = [["user", "device_id", "platform"]]

    def __str__(self):
        return f"{self.user} - {self.platform} device"


class UserNotificationSettings(models.Model):
    """
    User preferences for notifications
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(unique=True)
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    # Specific notification type preferences stored as JSON
    preferences = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["user_id"])]

    def __str__(self):
        return f"Notification settings for {self.user_id}"


class DeadLetterNotification(models.Model):
    """
    Stores notifications that failed to deliver after all retry attempts
    Used for auditing and manual resolution
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_notification_id = models.UUIDField(null=True, blank=True)
    recipient_id = models.UUIDField()
    notification_type = models.CharField(max_length=50)
    channel = models.CharField(max_length=20)
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField()
    retry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.UUIDField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient_id"]),
            models.Index(fields=["notification_type"]),
            models.Index(fields=["channel"]),
            models.Index(fields=["resolved"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Failed {self.channel} notification: {self.notification_type} ({self.created_at})"

    def retry_manually(self):
        """
        Manually retry sending this notification
        """
        from apps.notificationsapp.services.notification_service import NotificationService

        # Create a new notification based on this dead letter
        result = NotificationService.send_notification(
            recipient_id=str(self.recipient_id),
            notification_type=self.notification_type,
            title=self.title,
            message=self.message,
            channels=[self.channel],
            data=self.data,
            metadata=self.metadata,
            priority="high",
            rate_limit_bypass=True,  # Bypass rate limiting for manual retries
        )

        if result.get("success"):
            self.resolved = True
            self.resolved_at = timezone.now()
            self.resolution_notes = f"Manually retried and succeeded. New notification ID: {result.get('notification_id')}"
            self.save()

        return result
