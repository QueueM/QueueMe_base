"""
Notification Models

This module defines the database models for the notification system.
"""

import math
import uuid
from datetime import time, timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
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
    body_en = models.TextField(
        help_text="Template content in English with variable placeholders"
    )
    body_ar = models.TextField(
        help_text="Template content in Arabic with variable placeholders"
    )
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
    idempotency_key = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )
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
        return (
            f"{self.notification} to {self.user_id} via {self.channel}: {self.status}"
        )


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
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

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


class Campaign(models.Model):
    """
    Communication campaign for sending messages to users via multiple channels
    """

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("canceled", "Canceled"),
    )

    TYPE_CHOICES = (
        ("marketing", "Marketing"),
        ("announcement", "Announcement"),
        ("notification", "Notification"),
        ("update", "System Update"),
        ("promotion", "Promotion"),
        ("newsletter", "Newsletter"),
        ("system", "System Message"),
    )

    RECIPIENT_CHOICES = (
        ("customers", "Customers"),
        ("shops", "Shop Owners"),
        ("both", "Both"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    campaign_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_CHOICES)

    # Target audience and filtering
    filter_type = models.CharField(max_length=20, default="all")
    filter_data = models.JSONField(default=dict, blank=True)
    audience_count = models.IntegerField(default=0)

    # Scheduling
    is_scheduled = models.BooleanField(default=False)
    scheduled_for = models.DateTimeField(null=True, blank=True)

    # Channels to use
    channels = models.JSONField(default=list)

    # Tracking timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Content for each channel type
    content = models.JSONField(default=dict)

    # Campaign metrics
    metrics = models.JSONField(default=dict, blank=True)
    error_info = models.TextField(blank=True, null=True)

    # Created by
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_campaigns",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["campaign_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["scheduled_for"]),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "admin_communications_campaign_detail", kwargs={"campaign_id": self.id}
        )

    def get_content_for_channel(self, channel):
        """Get content for a specific channel"""
        return self.content.get(channel, {})

    def get_recipients_count(self):
        """Get the number of recipients"""
        return self.audience_count

    def get_sent_count(self):
        """Get the number of messages sent"""
        return self.metrics.get("sent", 0)

    def get_delivered_count(self):
        """Get the number of messages delivered"""
        return self.metrics.get("delivered", 0)

    def get_opened_count(self):
        """Get the number of messages opened"""
        return self.metrics.get("opened", 0)

    def get_clicked_count(self):
        """Get the number of messages clicked"""
        return self.metrics.get("clicked", 0)

    def get_open_rate(self):
        """Get the open rate percentage"""
        delivered = self.get_delivered_count()
        if delivered == 0:
            return 0
        return round((self.get_opened_count() / delivered) * 100, 1)

    def get_click_rate(self):
        """Get the click rate percentage"""
        opened = self.get_opened_count()
        if opened == 0:
            return 0
        return round((self.get_clicked_count() / opened) * 100, 1)

    def is_editable(self):
        """Check if the campaign can be edited"""
        return self.status in ["draft", "scheduled"]

    def is_sendable(self):
        """Check if the campaign can be sent immediately"""
        return self.status in ["draft", "scheduled"]

    def is_cancelable(self):
        """Check if the campaign can be canceled"""
        return self.status in ["scheduled", "sending"]

    def can_view_report(self):
        """Check if the campaign has a viewable report"""
        return self.status in ["sent", "sending", "failed", "canceled"]

    @property
    def channels(self):
        """Return a list of channels used in this campaign"""
        channels = []
        if getattr(self.content, "email", None):
            channels.append("email")
        if getattr(self.content, "sms", None):
            channels.append("sms")
        if getattr(self.content, "push", None):
            channels.append("push")
        if getattr(self.content, "in_app", None):
            channels.append("in_app")
        return channels


class CampaignRecipient(models.Model):
    """
    Tracks individual recipients for a campaign and their interaction
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="recipients"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # Delivery status for each channel
    email_status = models.CharField(max_length=20, null=True, blank=True)
    sms_status = models.CharField(max_length=20, null=True, blank=True)
    push_status = models.CharField(max_length=20, null=True, blank=True)
    inapp_status = models.CharField(max_length=20, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    # Interaction data
    opened_count = models.IntegerField(default=0)
    clicked_count = models.IntegerField(default=0)
    conversion = models.BooleanField(default=False)
    click_data = models.JSONField(default=dict, blank=True)
    device_info = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("campaign", "user")
        indexes = [
            models.Index(fields=["campaign", "user"]),
            models.Index(fields=["email_status"]),
            models.Index(fields=["sms_status"]),
            models.Index(fields=["push_status"]),
            models.Index(fields=["inapp_status"]),
            models.Index(fields=["opened_at"]),
            models.Index(fields=["clicked_at"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.campaign}"

    def mark_opened(self, channel="email", device_info=None):
        """Mark message as opened"""
        self.opened_at = timezone.now() if not self.opened_at else self.opened_at
        self.opened_count += 1

        if device_info:
            self.device_info = device_info

        self.save()

    def mark_clicked(self, link_id=None, link_url=None):
        """Mark message as clicked"""
        self.clicked_at = timezone.now() if not self.clicked_at else self.clicked_at
        self.clicked_count += 1

        if link_id and link_url:
            if "links" not in self.click_data:
                self.click_data["links"] = {}

            if link_id not in self.click_data["links"]:
                self.click_data["links"][link_id] = {
                    "url": link_url,
                    "clicks": 0,
                    "first_click": timezone.now().isoformat(),
                }

            self.click_data["links"][link_id]["clicks"] += 1
            self.click_data["links"][link_id]["last_click"] = timezone.now().isoformat()

        self.save()

    def mark_converted(self):
        """Mark recipient as converted"""
        self.conversion = True
        self.save()


class EmailTemplate(models.Model):
    """Model for storing reusable email templates"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    subject = models.CharField(max_length=255)
    content = models.TextField()
    content_html = models.TextField()

    # Template category for organization
    CATEGORY_CHOICES = (
        ("marketing", "Marketing"),
        ("notification", "Notification"),
        ("system", "System"),
        ("booking", "Booking"),
        ("payment", "Payment"),
        ("other", "Other"),
    )
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="other"
    )

    # Variables that can be used in this template
    variables = models.JSONField(default=dict, blank=True)

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_templates",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    # Usage tracking
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    # Sample data for previewing
    sample_data = models.JSONField(default=dict, blank=True)

    # Analytics
    analytics = models.OneToOneField(
        "TemplateAnalytics",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_template",
    )

    def __str__(self):
        return self.name

    def increment_usage(self):
        """Increment the usage count and update last_used timestamp"""
        self.usage_count += 1
        self.last_used = timezone.now()
        self.save(update_fields=["usage_count", "last_used"])

    def get_preview(self, data=None):
        """
        Generate a preview of the template with sample data
        If data is provided, use it, otherwise use sample_data
        """
        content = self.content
        preview_data = data or self.sample_data

        # Simple template variable replacement
        if preview_data:
            for key, value in preview_data.items():
                placeholder = "{{" + key + "}}"
                content = content.replace(placeholder, str(value))

        return content

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"


class SMSTemplate(models.Model):
    """Model for storing reusable SMS templates"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    content = models.TextField(
        help_text="SMS content with variable placeholders (max 160 chars)"
    )

    # Template category for organization (same categories as EmailTemplate)
    CATEGORY_CHOICES = (
        ("marketing", "Marketing"),
        ("notification", "Notification"),
        ("system", "System"),
        ("booking", "Booking"),
        ("payment", "Payment"),
        ("other", "Other"),
    )
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="other"
    )

    # Language support
    content_ar = models.TextField(
        blank=True, null=True, help_text="Arabic version of SMS content"
    )

    # Variables that can be used in this template
    variables = models.JSONField(default=dict, blank=True)

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_sms_templates",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    # Character count tracking
    character_count = models.PositiveIntegerField(
        default=0, help_text="Number of characters in the template"
    )

    # Usage tracking
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    # Sample data for previewing
    sample_data = models.JSONField(default=dict, blank=True)

    # Analytics
    analytics = models.OneToOneField(
        "TemplateAnalytics",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_template",
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Update character count before saving
        self.character_count = len(self.content)
        super().save(*args, **kwargs)

    def increment_usage(self):
        """Increment the usage count and update last_used timestamp"""
        self.usage_count += 1
        self.last_used = timezone.now()
        self.save(update_fields=["usage_count", "last_used"])

    def get_preview(self, data=None, language="en"):
        """
        Generate a preview of the template with sample data
        If data is provided, use it, otherwise use sample_data

        Args:
            data: Optional dict of template data
            language: 'en' for English, 'ar' for Arabic
        """
        if language == "ar" and self.content_ar:
            content = self.content_ar
        else:
            content = self.content

        preview_data = data or self.sample_data

        # Simple template variable replacement
        if preview_data:
            for key, value in preview_data.items():
                placeholder = "{{" + key + "}}"
                content = content.replace(placeholder, str(value))

        return content

    def get_segments_count(self):
        """Calculate the number of SMS segments based on character count"""
        # Standard GSM encoding: 160 chars per segment, or 153 for multipart messages
        char_count = self.character_count

        if char_count <= 160:
            return 1
        else:
            return math.ceil(char_count / 153)

    def get_estimated_cost(self, recipient_count=1, cost_per_segment=0.05):
        """
        Calculate the estimated cost to send this template

        Args:
            recipient_count: Number of recipients
            cost_per_segment: Cost per SMS segment in dollars
        """
        segments = self.get_segments_count()
        return round(segments * recipient_count * cost_per_segment, 2)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "SMS Template"
        verbose_name_plural = "SMS Templates"


class PushNotificationTemplate(models.Model):
    """Model for storing reusable push notification templates"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    # Push notification components
    title = models.CharField(
        max_length=100, help_text="Title of the push notification (max 100 chars)"
    )
    body = models.TextField(help_text="Body text of the notification (max 240 chars)")

    # Optional fields
    image_url = models.URLField(
        blank=True,
        null=True,
        help_text="Optional image URL to display with the notification",
    )
    action_url = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Deep link or URL to open when notification is tapped",
    )
    action_button_text = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text="Optional text for action button",
    )

    # Template category for organization (same categories as other templates)
    CATEGORY_CHOICES = (
        ("marketing", "Marketing"),
        ("notification", "Notification"),
        ("system", "System"),
        ("booking", "Booking"),
        ("payment", "Payment"),
        ("other", "Other"),
    )
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="other"
    )

    # Platform specific settings
    PLATFORM_CHOICES = (
        ("all", "All Platforms"),
        ("ios", "iOS Only"),
        ("android", "Android Only"),
        ("web", "Web Only"),
    )
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default="all")

    # Additional notification data (key-value pairs to send with notification)
    additional_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional data to send with the notification",
    )

    # Language support
    title_ar = models.CharField(
        max_length=100, blank=True, null=True, help_text="Arabic version of title"
    )
    body_ar = models.TextField(
        blank=True, null=True, help_text="Arabic version of body text"
    )
    action_button_text_ar = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text="Arabic version of action button text",
    )

    # Variables that can be used in this template
    variables = models.JSONField(default=dict, blank=True)

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_push_templates",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    # Usage tracking
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    # Sample data for previewing
    sample_data = models.JSONField(default=dict, blank=True)

    # Analytics
    analytics = models.OneToOneField(
        "TemplateAnalytics",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="push_template",
    )

    def __str__(self):
        return self.name

    def increment_usage(self):
        """Increment the usage count and update last_used timestamp"""
        self.usage_count += 1
        self.last_used = timezone.now()
        self.save(update_fields=["usage_count", "last_used"])

    def get_preview(self, data=None, language="en"):
        """
        Generate a preview of the template with sample data

        Args:
            data: Optional dict of template data
            language: 'en' for English, 'ar' for Arabic
        """
        if language == "ar" and self.title_ar and self.body_ar:
            title = self.title_ar
            body = self.body_ar
            action_button_text = self.action_button_text_ar or self.action_button_text
        else:
            title = self.title
            body = self.body
            action_button_text = self.action_button_text

        preview_data = data or self.sample_data

        # Simple template variable replacement
        if preview_data:
            for key, value in preview_data.items():
                placeholder = "{{" + key + "}}"
                title = title.replace(placeholder, str(value)) if title else title
                body = body.replace(placeholder, str(value)) if body else body
                action_button_text = (
                    action_button_text.replace(placeholder, str(value))
                    if action_button_text
                    else action_button_text
                )

        return {
            "title": title,
            "body": body,
            "action_button_text": action_button_text,
            "image_url": self.image_url,
            "action_url": self.action_url,
        }

    def character_counts(self):
        """Return character counts for title and body"""
        return {
            "title": len(self.title) if self.title else 0,
            "body": len(self.body) if self.body else 0,
        }

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Push Notification Template"
        verbose_name_plural = "Push Notification Templates"


class TemplateAnalytics(models.Model):
    """Analytics data for template performance tracking"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template_id = models.UUIDField(
        help_text="ID of the template this analytics data belongs to"
    )
    template_type = models.CharField(
        max_length=20,
        choices=[
            ("email", "Email Template"),
            ("sms", "SMS Template"),
            ("push", "Push Notification Template"),
        ],
    )

    # Delivery metrics
    sent_count = models.IntegerField(default=0)
    delivered_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    # Engagement metrics
    open_count = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)

    # Performance metrics
    bounce_rate = models.FloatField(default=0.0)
    open_rate = models.FloatField(default=0.0)
    click_rate = models.FloatField(default=0.0)

    # Demographic data
    recipient_data = models.JSONField(
        default=dict, blank=True, help_text="Aggregated data about recipients"
    )

    # Time-based analysis
    hourly_stats = models.JSONField(
        default=dict, blank=True, help_text="Engagement by hour of day"
    )
    daily_stats = models.JSONField(
        default=dict, blank=True, help_text="Engagement by day of week"
    )

    # A/B testing data
    a_b_test_results = models.JSONField(
        default=dict, blank=True, help_text="Results of A/B tests"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Template Analytics"
        verbose_name_plural = "Template Analytics"
        unique_together = [["template_id", "template_type"]]
        indexes = [
            models.Index(fields=["template_id"]),
            models.Index(fields=["template_type"]),
        ]

    def __str__(self):
        return f"Analytics for {self.template_type} template: {self.template_id}"

    def calculate_rates(self):
        """Calculate performance rates based on current counts"""
        # Calculate delivery rate
        if self.sent_count > 0:
            self.delivery_rate = (self.delivered_count / self.sent_count) * 100

        # Calculate open rate
        if self.delivered_count > 0:
            self.open_rate = (self.open_count / self.delivered_count) * 100

        # Calculate click rate
        if self.open_count > 0:
            self.click_rate = (self.click_count / self.open_count) * 100

        self.save(update_fields=["delivery_rate", "open_rate", "click_rate"])

    def record_send(self, success=True):
        """Record a send event"""
        self.sent_count += 1
        if success:
            self.delivered_count += 1
        else:
            self.failed_count += 1
        self.calculate_rates()

    def record_open(self):
        """Record an open event"""
        self.open_count += 1
        self.calculate_rates()

    def record_click(self):
        """Record a click event"""
        self.click_count += 1
        self.calculate_rates()

    def update_hourly_stats(self, hour):
        """Update engagement statistics by hour"""
        if "by_hour" not in self.hourly_stats:
            self.hourly_stats["by_hour"] = {str(h): 0 for h in range(24)}

        hour_str = str(hour)
        self.hourly_stats["by_hour"][hour_str] = (
            self.hourly_stats["by_hour"].get(hour_str, 0) + 1
        )
        self.save(update_fields=["hourly_stats"])

    def update_daily_stats(self, day):
        """Update engagement statistics by day of week (0=Monday, 6=Sunday)"""
        if "by_day" not in self.daily_stats:
            self.daily_stats["by_day"] = {str(d): 0 for d in range(7)}

        day_str = str(day)
        self.daily_stats["by_day"][day_str] = (
            self.daily_stats["by_day"].get(day_str, 0) + 1
        )
        self.save(update_fields=["daily_stats"])


# Add relationships to existing template models
EmailTemplate.analytics = models.OneToOneField(
    TemplateAnalytics,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="email_template",
)

SMSTemplate.analytics = models.OneToOneField(
    TemplateAnalytics,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="sms_template",
)

PushNotificationTemplate.analytics = models.OneToOneField(
    TemplateAnalytics,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="push_template",
)


class ABTest(models.Model):
    """A/B Test for template optimization"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    # Test type (which template type is being tested)
    TEST_TYPE_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
        ("push", "Push Notification"),
    ]
    test_type = models.CharField(max_length=20, choices=TEST_TYPE_CHOICES)

    # Control template references - based on test type, only one will be used
    email_template_a = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        related_name="ab_tests_as_a",
        null=True,
        blank=True,
    )
    email_template_b = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        related_name="ab_tests_as_b",
        null=True,
        blank=True,
    )

    sms_template_a = models.ForeignKey(
        SMSTemplate,
        on_delete=models.SET_NULL,
        related_name="ab_tests_as_a",
        null=True,
        blank=True,
    )
    sms_template_b = models.ForeignKey(
        SMSTemplate,
        on_delete=models.SET_NULL,
        related_name="ab_tests_as_b",
        null=True,
        blank=True,
    )

    push_template_a = models.ForeignKey(
        PushNotificationTemplate,
        on_delete=models.SET_NULL,
        related_name="ab_tests_as_a",
        null=True,
        blank=True,
    )
    push_template_b = models.ForeignKey(
        PushNotificationTemplate,
        on_delete=models.SET_NULL,
        related_name="ab_tests_as_b",
        null=True,
        blank=True,
    )

    # Audience and traffic split
    audience_size = models.IntegerField(default=0)
    traffic_split = models.IntegerField(
        default=50, help_text="Percentage of traffic to send to variant B (0-100)"
    )

    # Test configuration
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("running", "Running"),
            ("paused", "Paused"),
            ("completed", "Completed"),
            ("canceled", "Canceled"),
        ],
        default="draft",
    )

    # Success metrics to track
    success_metric = models.CharField(
        max_length=20,
        choices=[
            ("open_rate", "Open Rate"),
            ("click_rate", "Click Rate"),
            ("conversion_rate", "Conversion Rate"),
            ("revenue", "Revenue"),
        ],
        default="open_rate",
    )

    # Auto-selection if enabled
    auto_select_winner = models.BooleanField(
        default=False,
        help_text="Automatically select the winner at the end of the test",
    )
    minimum_confidence = models.FloatField(
        default=95.0,
        help_text="Minimum statistical confidence for auto-selection (0-100)",
    )

    # Test results
    results = models.JSONField(default=dict, blank=True)
    winning_variant = models.CharField(
        max_length=1,
        choices=[("A", "Variant A"), ("B", "Variant B")],
        null=True,
        blank=True,
    )
    confidence_level = models.FloatField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_ab_tests",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "A/B Test"
        verbose_name_plural = "A/B Tests"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def is_active(self):
        return self.status == "running"

    @property
    def variant_a_template(self):
        """Get the variant A template based on test type"""
        if self.test_type == "email":
            return self.email_template_a
        elif self.test_type == "sms":
            return self.sms_template_a
        elif self.test_type == "push":
            return self.push_template_a
        return None

    @property
    def variant_b_template(self):
        """Get the variant B template based on test type"""
        if self.test_type == "email":
            return self.email_template_b
        elif self.test_type == "sms":
            return self.sms_template_b
        elif self.test_type == "push":
            return self.push_template_b
        return None

    def get_test_status(self):
        """Get the current status of the test with analytics"""
        status_data = {
            "status": self.status,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "duration_days": (self.end_date - self.start_date).days,
            "days_remaining": (
                (self.end_date - timezone.now()).days
                if self.end_date > timezone.now()
                else 0
            ),
            "progress_percent": 0,
            "results": self.results,
        }

        # Calculate progress percentage
        if self.status == "completed":
            status_data["progress_percent"] = 100
        elif self.status == "running":
            total_duration = (self.end_date - self.start_date).total_seconds()
            elapsed = (timezone.now() - self.start_date).total_seconds()
            if total_duration > 0:
                status_data["progress_percent"] = min(
                    round((elapsed / total_duration) * 100), 99
                )

        return status_data

    def calculate_results(self):
        """Calculate test results and determine winner if possible"""
        # Initialize results structure if empty
        if not self.results:
            self.results = {
                "variant_a": {
                    "sent": 0,
                    "delivered": 0,
                    "opened": 0,
                    "clicked": 0,
                    "conversions": 0,
                    "revenue": 0.0,
                },
                "variant_b": {
                    "sent": 0,
                    "delivered": 0,
                    "opened": 0,
                    "clicked": 0,
                    "conversions": 0,
                    "revenue": 0.0,
                },
                "rates": {
                    "variant_a": {
                        "delivery_rate": 0.0,
                        "open_rate": 0.0,
                        "click_rate": 0.0,
                        "conversion_rate": 0.0,
                    },
                    "variant_b": {
                        "delivery_rate": 0.0,
                        "open_rate": 0.0,
                        "click_rate": 0.0,
                        "conversion_rate": 0.0,
                    },
                },
                "improvement": {
                    "delivery_rate": 0.0,
                    "open_rate": 0.0,
                    "click_rate": 0.0,
                    "conversion_rate": 0.0,
                    "revenue": 0.0,
                },
                "statistical_significance": {
                    "confidence": 0.0,
                    "sample_size_adequate": False,
                    "is_significant": False,
                },
            }

        # In a real implementation, we would pull actual metrics from our analytics system
        # For now, we'll use placeholder logic to calculate rates

        # Calculate rates for variant A
        a_results = self.results["variant_a"]
        if a_results["sent"] > 0:
            self.results["rates"]["variant_a"]["delivery_rate"] = (
                a_results["delivered"] / a_results["sent"]
            ) * 100

        if a_results["delivered"] > 0:
            self.results["rates"]["variant_a"]["open_rate"] = (
                a_results["opened"] / a_results["delivered"]
            ) * 100

        if a_results["opened"] > 0:
            self.results["rates"]["variant_a"]["click_rate"] = (
                a_results["clicked"] / a_results["opened"]
            ) * 100

        if a_results["delivered"] > 0:
            self.results["rates"]["variant_a"]["conversion_rate"] = (
                a_results["conversions"] / a_results["delivered"]
            ) * 100

        # Calculate rates for variant B
        b_results = self.results["variant_b"]
        if b_results["sent"] > 0:
            self.results["rates"]["variant_b"]["delivery_rate"] = (
                b_results["delivered"] / b_results["sent"]
            ) * 100

        if b_results["delivered"] > 0:
            self.results["rates"]["variant_b"]["open_rate"] = (
                b_results["opened"] / b_results["delivered"]
            ) * 100

        if b_results["opened"] > 0:
            self.results["rates"]["variant_b"]["click_rate"] = (
                b_results["clicked"] / b_results["opened"]
            ) * 100

        if b_results["delivered"] > 0:
            self.results["rates"]["variant_b"]["conversion_rate"] = (
                b_results["conversions"] / b_results["delivered"]
            ) * 100

        # Calculate improvements
        self.results["improvement"]["delivery_rate"] = (
            self.results["rates"]["variant_b"]["delivery_rate"]
            - self.results["rates"]["variant_a"]["delivery_rate"]
        )

        self.results["improvement"]["open_rate"] = (
            self.results["rates"]["variant_b"]["open_rate"]
            - self.results["rates"]["variant_a"]["open_rate"]
        )

        self.results["improvement"]["click_rate"] = (
            self.results["rates"]["variant_b"]["click_rate"]
            - self.results["rates"]["variant_a"]["click_rate"]
        )

        self.results["improvement"]["conversion_rate"] = (
            self.results["rates"]["variant_b"]["conversion_rate"]
            - self.results["rates"]["variant_a"]["conversion_rate"]
        )

        if a_results["sent"] > 0 and b_results["sent"] > 0:
            self.results["improvement"]["revenue"] = (
                b_results["revenue"] / b_results["sent"]
            ) - (a_results["revenue"] / a_results["sent"])

        # In a real implementation, we would calculate statistical significance
        # For now, we'll use a placeholder with random confidence level
        import random

        self.confidence_level = round(random.uniform(80.0, 99.9), 1)

        self.results["statistical_significance"]["confidence"] = self.confidence_level
        self.results["statistical_significance"]["sample_size_adequate"] = (
            a_results["sent"] >= 500 and b_results["sent"] >= 500
        )
        self.results["statistical_significance"]["is_significant"] = (
            self.confidence_level >= self.minimum_confidence
        )

        # Determine winner based on success metric
        a_metric_value = 0
        b_metric_value = 0

        if self.success_metric == "open_rate":
            a_metric_value = self.results["rates"]["variant_a"]["open_rate"]
            b_metric_value = self.results["rates"]["variant_b"]["open_rate"]
        elif self.success_metric == "click_rate":
            a_metric_value = self.results["rates"]["variant_a"]["click_rate"]
            b_metric_value = self.results["rates"]["variant_b"]["click_rate"]
        elif self.success_metric == "conversion_rate":
            a_metric_value = self.results["rates"]["variant_a"]["conversion_rate"]
            b_metric_value = self.results["rates"]["variant_b"]["conversion_rate"]
        elif self.success_metric == "revenue":
            a_metric_value = (
                a_results["revenue"] / a_results["sent"] if a_results["sent"] > 0 else 0
            )
            b_metric_value = (
                b_results["revenue"] / b_results["sent"] if b_results["sent"] > 0 else 0
            )

        # Set winner if there's a clear winner and confidence is high enough
        if (
            self.results["statistical_significance"]["is_significant"]
            and self.results["statistical_significance"]["sample_size_adequate"]
        ):
            if b_metric_value > a_metric_value:
                self.winning_variant = "B"
            else:
                self.winning_variant = "A"

        # Auto-select winner if enabled and test is complete
        if (
            self.auto_select_winner
            and self.status == "completed"
            and self.winning_variant is not None
        ):
            # In a real implementation, this would update the default template
            pass

        self.save()
        return self.results

    def record_event(self, variant, event_type, amount=None):
        """Record an event for a specific variant

        Args:
            variant: 'A' or 'B'
            event_type: 'sent', 'delivered', 'opened', 'clicked', 'conversion'
            amount: Optional amount for revenue tracking
        """
        variant_key = "variant_a" if variant == "A" else "variant_b"

        # Initialize results if needed
        if not self.results:
            self.calculate_results()

        # Update the count for the event type
        if event_type in ["sent", "delivered", "opened", "clicked", "conversions"]:
            self.results[variant_key][event_type] += 1

        # Update revenue if provided
        if event_type == "conversion" and amount is not None:
            self.results[variant_key]["revenue"] += float(amount)

        # Recalculate results
        self.calculate_results()

    def start_test(self):
        """Start the A/B test"""
        if self.status == "scheduled" or self.status == "paused":
            self.status = "running"
            self.save()
            return True
        return False

    def pause_test(self):
        """Pause the A/B test"""
        if self.status == "running":
            self.status = "paused"
            self.save()
            return True
        return False

    def complete_test(self):
        """Complete the A/B test and select winner if auto-select is enabled"""
        if self.status in ["running", "paused"]:
            self.status = "completed"

            # Calculate final results
            self.calculate_results()

            # Auto-select winner if enabled
            if self.auto_select_winner and self.winning_variant is not None:
                # In a real implementation, this would update the default template
                pass

            self.save()
            return True
        return False

    def cancel_test(self):
        """Cancel the A/B test"""
        if self.status in ["draft", "scheduled", "running", "paused"]:
            self.status = "canceled"
            self.save()
            return True
        return False


class ABTestRecipient(models.Model):
    """Tracks individual recipients in an A/B test"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test = models.ForeignKey(
        ABTest, on_delete=models.CASCADE, related_name="recipients"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    variant = models.CharField(
        max_length=1, choices=[("A", "Variant A"), ("B", "Variant B")]
    )

    # Delivery and engagement tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)

    # For revenue tracking if applicable
    conversion_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["test", "user"]]
        verbose_name = "A/B Test Recipient"
        verbose_name_plural = "A/B Test Recipients"

    def __str__(self):
        return f"{self.user} - {self.test} - Variant {self.variant}"

    def record_event(self, event_type, amount=None):
        """Record an event for this recipient

        Args:
            event_type: 'delivered', 'opened', 'clicked', 'converted'
            amount: Optional amount for conversion tracking
        """
        now = timezone.now()

        if event_type == "delivered" and not self.delivered_at:
            self.delivered_at = now
            self.test.record_event(self.variant, "delivered")

        elif event_type == "opened" and not self.opened_at:
            self.opened_at = now
            self.test.record_event(self.variant, "opened")

        elif event_type == "clicked" and not self.clicked_at:
            self.clicked_at = now
            self.test.record_event(self.variant, "clicked")

        elif event_type == "converted" and not self.converted_at:
            self.converted_at = now
            self.conversion_value = amount
            self.test.record_event(self.variant, "conversions", amount)

        self.save()


class Language(models.Model):
    """Supported languages for templates"""

    code = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=100)
    native_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    direction = models.CharField(
        max_length=3,
        choices=[("ltr", "Left to Right"), ("rtl", "Right to Left")],
        default="ltr",
    )
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class TemplateTranslation(models.Model):
    """
    Translation for templates in different languages
    Allows for unlimited language support beyond just English and Arabic
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)

    # Support for translation across different template types
    TEMPLATE_TYPE_CHOICES = [
        ("email", "Email Template"),
        ("sms", "SMS Template"),
        ("push", "Push Notification Template"),
    ]
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)

    # References to each template type - only one will be used
    email_template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="translations",
    )
    sms_template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="translations",
    )
    push_template = models.ForeignKey(
        PushNotificationTemplate,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="translations",
    )

    # Email template fields
    subject = models.CharField(max_length=255, blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    content_html = models.TextField(blank=True, null=True)

    # SMS template fields
    sms_content = models.TextField(blank=True, null=True)

    # Push notification fields
    push_title = models.CharField(max_length=100, blank=True, null=True)
    push_body = models.TextField(blank=True, null=True)
    push_action_button_text = models.CharField(max_length=30, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ["language", "email_template"],
            ["language", "sms_template"],
            ["language", "push_template"],
        ]
        verbose_name = "Template Translation"
        verbose_name_plural = "Template Translations"

    def __str__(self):
        template_name = ""
        if self.email_template:
            template_name = self.email_template.name
        elif self.sms_template:
            template_name = self.sms_template.name
        elif self.push_template:
            template_name = self.push_template.name

        return f"{template_name} ({self.language.code})"

    def get_translated_content(self):
        """Get the translated content based on template type"""
        if self.template_type == "email":
            return {
                "subject": self.subject,
                "content": self.content,
                "content_html": self.content_html,
            }
        elif self.template_type == "sms":
            return {"content": self.sms_content}
        elif self.template_type == "push":
            return {
                "title": self.push_title,
                "body": self.push_body,
                "action_button_text": self.push_action_button_text,
            }
        return {}


class AIContentSuggestion(models.Model):
    """AI-generated suggestions for content optimization"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Template references
    TEMPLATE_TYPE_CHOICES = [
        ("email", "Email Template"),
        ("sms", "SMS Template"),
        ("push", "Push Notification Template"),
    ]
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)

    email_template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_suggestions",
    )
    sms_template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_suggestions",
    )
    push_template = models.ForeignKey(
        PushNotificationTemplate,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_suggestions",
    )

    # Request parameters
    OPTIMIZATION_TYPE_CHOICES = [
        ("engagement", "Increase Engagement"),
        ("clarity", "Improve Clarity"),
        ("brevity", "Increase Brevity"),
        ("persuasive", "Make More Persuasive"),
        ("inclusive", "Make More Inclusive"),
        ("tone", "Adjust Tone"),
        ("grammar", "Fix Grammar Issues"),
        ("localize", "Culturally Localize"),
    ]
    optimization_type = models.CharField(
        max_length=20, choices=OPTIMIZATION_TYPE_CHOICES
    )
    language = models.CharField(max_length=10, default="en")
    target_audience = models.CharField(max_length=100, blank=True, null=True)
    additional_instructions = models.TextField(blank=True, null=True)

    # Original content (from template)
    original_subject = models.CharField(max_length=255, blank=True, null=True)
    original_content = models.TextField(blank=True, null=True)

    # AI-generated suggestions
    suggested_subject = models.CharField(max_length=255, blank=True, null=True)
    suggested_content = models.TextField(blank=True, null=True)

    # Suggestion metadata
    explanation = models.TextField(
        blank=True, null=True, help_text="AI's explanation of changes"
    )
    improvements = models.JSONField(
        default=dict, blank=True, help_text="Specific improvements made"
    )
    ai_model_used = models.CharField(max_length=100, blank=True, null=True)

    # Status tracking
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True, null=True)

    # Template feedback
    was_applied = models.BooleanField(default=False)
    user_feedback = models.CharField(
        max_length=20,
        choices=[
            ("positive", "Positive"),
            ("negative", "Negative"),
            ("neutral", "Neutral"),
        ],
        null=True,
        blank=True,
    )
    user_feedback_text = models.TextField(blank=True, null=True)

    # Tracking
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ai_content_requests",
    )
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "AI Content Suggestion"
        verbose_name_plural = "AI Content Suggestions"
        ordering = ["-created_at"]

    def __str__(self):
        template_name = ""
        if self.email_template:
            template_name = self.email_template.name
        elif self.sms_template:
            template_name = self.sms_template.name
        elif self.push_template:
            template_name = self.push_template.name

        return f"{self.get_optimization_type_display()} for {template_name}"

    @property
    def template(self):
        """Get the associated template"""
        if self.template_type == "email":
            return self.email_template
        elif self.template_type == "sms":
            return self.sms_template
        elif self.template_type == "push":
            return self.push_template
        return None

    @property
    def processing_time(self):
        """Calculate the processing time in seconds"""
        if self.completed_at and self.created_at:
            return (self.completed_at - self.created_at).total_seconds()
        return None

    def apply_suggestion(self):
        """Apply the AI suggestion to the template"""
        if self.status != "completed" or self.was_applied:
            return False

        template = self.template
        if not template:
            return False

        if self.template_type == "email":
            if self.suggested_subject:
                template.subject = self.suggested_subject
            if self.suggested_content:
                template.content_html = self.suggested_content
                # Also update plain text content
                from html2text import html2text

                template.content = html2text(self.suggested_content)

        elif self.template_type == "sms":
            if self.suggested_content:
                template.content = self.suggested_content

        elif self.template_type == "push":
            if self.suggested_subject:
                template.title = self.suggested_subject
            if self.suggested_content:
                template.body = self.suggested_content

        template.save()
        self.was_applied = True
        self.save()
        return True

    def get_prompt_for_ai(self):
        """Generate a prompt for the AI model based on the request parameters"""
        template = self.template
        if not template:
            return None

        prompt_parts = [
            f"Please optimize the following {self.get_template_type_display()} content for {self.get_optimization_type_display()}.",
            f"The target audience is: {self.target_audience or 'general users'}.",
            f"Language: {self.language}.",
        ]

        if self.additional_instructions:
            prompt_parts.append(
                f"Additional instructions: {self.additional_instructions}"
            )

        prompt_parts.append("\nOriginal content:")

        if self.template_type == "email":
            prompt_parts.append(f"Subject: {template.subject}")
            prompt_parts.append(f"Body:\n{template.content_html or template.content}")

        elif self.template_type == "sms":
            prompt_parts.append(f"SMS Content:\n{template.content}")

        elif self.template_type == "push":
            prompt_parts.append(f"Title: {template.title}")
            prompt_parts.append(f"Body: {template.body}")

        prompt_parts.append("\nPlease provide:")

        if self.template_type in ["email", "push"]:
            prompt_parts.append("1. An optimized subject/title")
            prompt_parts.append("2. Optimized body content")
        else:
            prompt_parts.append("1. Optimized SMS content")

        prompt_parts.append(
            "3. A brief explanation of the changes and improvements made"
        )

        return "\n".join(prompt_parts)

    def process_ai_response(self, response_text):
        """Process and extract content from the AI response"""
        import re

        # Extract subject/title if applicable
        subject_pattern = r"(?:Subject|Title):\s*(.*?)(?:\n|$)"
        subject_match = re.search(subject_pattern, response_text)
        if subject_match:
            self.suggested_subject = subject_match.group(1).strip()

        # Extract body/content
        if self.template_type == "email":
            # Look for email body, might be in HTML
            content_pattern = (
                r"(?:Body|Content):\s*([\s\S]*?)(?:\n\d\.|\n\nExplanation|\Z)"
            )
            content_match = re.search(content_pattern, response_text)
            if content_match:
                self.suggested_content = content_match.group(1).strip()

        elif self.template_type == "sms":
            # Look for SMS content
            content_pattern = r"(?:SMS Content|Content|Optimized content):\s*([\s\S]*?)(?:\n\d\.|\n\nExplanation|\Z)"
            content_match = re.search(content_pattern, response_text)
            if content_match:
                self.suggested_content = content_match.group(1).strip()

        elif self.template_type == "push":
            # Look for push body
            content_pattern = (
                r"(?:Body|Content):\s*([\s\S]*?)(?:\n\d\.|\n\nExplanation|\Z)"
            )
            content_match = re.search(content_pattern, response_text)
            if content_match:
                self.suggested_content = content_match.group(1).strip()

        # Extract explanation
        explanation_pattern = r"(?:Explanation|Changes made):\s*([\s\S]*?)(?:\n\d\.|\Z)"
        explanation_match = re.search(explanation_pattern, response_text)
        if explanation_match:
            self.explanation = explanation_match.group(1).strip()

        # If basic patterns didn't work, use the full response
        if not self.suggested_content and not self.suggested_subject:
            # Try to parse sections by looking for common patterns
            sections = re.split(r"\n\d+\.\s+|\n\n", response_text)
            if len(sections) >= 2:
                if (
                    self.template_type in ["email", "push"]
                    and not self.suggested_subject
                ):
                    self.suggested_subject = sections[0].strip()

                if not self.suggested_content:
                    self.suggested_content = sections[1].strip()

                if len(sections) >= 3 and not self.explanation:
                    self.explanation = sections[2].strip()
            else:
                # If all else fails, use the whole response as content
                self.suggested_content = response_text.strip()

        # Update status
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save()

        return True


class ScheduledTemplate(models.Model):
    """Schedule templates for automated sending"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Template references
    TEMPLATE_TYPE_CHOICES = [
        ("email", "Email Template"),
        ("sms", "SMS Template"),
        ("push", "Push Notification Template"),
    ]
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)

    email_template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="schedules",
    )
    sms_template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="schedules",
    )
    push_template = models.ForeignKey(
        PushNotificationTemplate,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="schedules",
    )

    # Schedule configuration
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    # Audience selection
    audience_type = models.CharField(
        max_length=20,
        choices=[
            ("all", "All Users"),
            ("segment", "User Segment"),
            ("list", "Custom List"),
            ("filtered", "Filtered Users"),
        ],
        default="all",
    )
    audience_filter = models.JSONField(
        default=dict, blank=True, help_text="Filters for audience selection"
    )
    estimated_audience_size = models.IntegerField(default=0)

    # Send time configuration
    SCHEDULE_TYPE_CHOICES = [
        ("one_time", "One-Time Send"),
        ("recurring", "Recurring Send"),
        ("triggered", "Event Triggered"),
    ]
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES)

    # For one-time sends
    scheduled_time = models.DateTimeField(null=True, blank=True)
    time_zone = models.CharField(max_length=50, default="UTC")

    # For recurring sends
    recurrence_pattern = models.CharField(
        max_length=20,
        choices=[
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("custom", "Custom"),
        ],
        null=True,
        blank=True,
    )
    recurrence_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Configuration for recurring schedules (days, times, etc.)",
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    # For event-triggered sends
    trigger_event = models.CharField(
        max_length=50, null=True, blank=True, help_text="Event that triggers this send"
    )
    trigger_config = models.JSONField(
        default=dict, blank=True, help_text="Configuration for the trigger conditions"
    )

    # Tracking
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("canceled", "Canceled"),
        ("error", "Error"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    last_sent_at = models.DateTimeField(null=True, blank=True)
    next_send_at = models.DateTimeField(null=True, blank=True)
    total_sends = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)

    # Schedule metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_schedules",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Scheduled Template"
        verbose_name_plural = "Scheduled Templates"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def template(self):
        """Get the associated template"""
        if self.template_type == "email":
            return self.email_template
        elif self.template_type == "sms":
            return self.sms_template
        elif self.template_type == "push":
            return self.push_template
        return None

    def get_schedule_status(self):
        """Get the current status of the schedule with next run info"""
        status_data = {
            "status": self.status,
            "last_sent_at": self.last_sent_at,
            "next_send_at": self.next_send_at,
            "total_sends": self.total_sends,
        }

        # Add schedule-type specific info
        if self.schedule_type == "one_time":
            if self.scheduled_time:
                now = timezone.now()
                if self.scheduled_time > now:
                    time_diff = self.scheduled_time - now
                    status_data["time_until_send"] = {
                        "days": time_diff.days,
                        "hours": time_diff.seconds // 3600,
                        "minutes": (time_diff.seconds % 3600) // 60,
                    }

        elif self.schedule_type == "recurring":
            if self.start_date and self.end_date:
                now = timezone.now()
                if now < self.start_date:
                    status_data["starts_in"] = (self.start_date - now).days

                if now < self.end_date:
                    status_data["ends_in"] = (self.end_date - now).days

                status_data["total_scheduled_days"] = (
                    self.end_date - self.start_date
                ).days

                # Add recurrence info
                status_data["recurrence"] = {
                    "pattern": self.get_recurrence_pattern_display(),
                    "config": self.recurrence_config,
                }

        # Add audience info
        status_data["audience"] = {
            "type": self.get_audience_type_display(),
            "estimated_size": self.estimated_audience_size,
        }

        return status_data

    def calculate_next_send_time(self):
        """Calculate the next time this template should be sent"""
        now = timezone.now()

        if self.schedule_type == "one_time":
            # For one-time schedules, set to the scheduled time if it's in the future
            if self.scheduled_time and self.scheduled_time > now:
                self.next_send_at = self.scheduled_time
            else:
                # One-time schedules in the past don't have a next send time
                self.next_send_at = None

        elif self.schedule_type == "recurring":
            if not self.start_date or not self.recurrence_pattern:
                # Can't calculate without required fields
                self.next_send_at = None
                return

            # Check if we're past the end date
            if self.end_date and now > self.end_date:
                self.next_send_at = None
                return

            # Check if we haven't started yet
            if now < self.start_date:
                self.next_send_at = self.start_date
                return

            # For active recurring schedules, calculate next occurrence
            if self.recurrence_pattern == "daily":
                # If we've already sent today, schedule for tomorrow
                if self.last_sent_at and self.last_sent_at.date() == now.date():
                    next_date = now.date() + timedelta(days=1)
                else:
                    next_date = now.date()

                # Get time from config, default to same time as start_date
                send_hour = self.recurrence_config.get("hour", self.start_date.hour)
                send_minute = self.recurrence_config.get(
                    "minute", self.start_date.minute
                )

                # Combine date and time
                from datetime import datetime

                next_datetime = datetime.combine(
                    next_date,
                    time(hour=send_hour, minute=send_minute),
                    tzinfo=now.tzinfo,
                )

                # If the time today is already past, schedule for tomorrow
                if next_datetime <= now:
                    next_datetime += timedelta(days=1)

                self.next_send_at = next_datetime

            elif self.recurrence_pattern == "weekly":
                # Get days of week to send (0=Monday, 6=Sunday)
                days_of_week = self.recurrence_config.get(
                    "days_of_week", [self.start_date.weekday()]
                )

                # Convert to integers if needed
                days_of_week = [
                    int(d) if isinstance(d, str) else d for d in days_of_week
                ]

                # Get time from config
                send_hour = self.recurrence_config.get("hour", self.start_date.hour)
                send_minute = self.recurrence_config.get(
                    "minute", self.start_date.minute
                )

                # Find next occurrence
                current_weekday = now.weekday()
                days_ahead = None

                # Check if we can send later today
                if current_weekday in days_of_week:
                    current_time = now.time()
                    send_time = time(hour=send_hour, minute=send_minute)

                    if current_time < send_time:
                        # We can send later today
                        days_ahead = 0

                # If we can't send today, find the next day in our schedule
                if days_ahead is None:
                    # Sort days for easier calculation
                    sorted_days = sorted(days_of_week)

                    # Find days later in the week
                    future_days = [d for d in sorted_days if d > current_weekday]

                    if future_days:
                        # There's a scheduled day later this week
                        days_ahead = future_days[0] - current_weekday
                    else:
                        # Wrap around to next week
                        days_ahead = 7 - current_weekday + sorted_days[0]

                # Calculate the next date
                next_date = now.date() + timedelta(days=days_ahead)

                # Combine with the send time
                from datetime import datetime

                self.next_send_at = datetime.combine(
                    next_date,
                    time(hour=send_hour, minute=send_minute),
                    tzinfo=now.tzinfo,
                )

            elif self.recurrence_pattern == "monthly":
                # Get days of month to send
                days_of_month = self.recurrence_config.get(
                    "days_of_month", [self.start_date.day]
                )

                # Convert to integers if needed
                days_of_month = [
                    int(d) if isinstance(d, str) else d for d in days_of_month
                ]

                # Get time from config
                send_hour = self.recurrence_config.get("hour", self.start_date.hour)
                send_minute = self.recurrence_config.get(
                    "minute", self.start_date.minute
                )

                # Start with current month
                current_month = now.replace(day=1)

                # Find the next valid day in the current month
                valid_days = [
                    d
                    for d in days_of_month
                    if d >= now.day and d <= self._days_in_month(now)
                ]

                if valid_days:
                    # We have valid days this month
                    next_day = valid_days[0]
                    next_date = now.replace(day=next_day)
                else:
                    # Move to next month
                    if now.month == 12:
                        next_month = now.replace(year=now.year + 1, month=1, day=1)
                    else:
                        next_month = now.replace(month=now.month + 1, day=1)

                    # Find the first valid day next month
                    valid_days = [
                        d for d in days_of_month if d <= self._days_in_month(next_month)
                    ]
                    if not valid_days:
                        # If no valid days (e.g. trying to send on day 31 in February),
                        # use the last day of the month
                        valid_days = [self._days_in_month(next_month)]

                    next_day = valid_days[0]
                    next_date = next_month.replace(day=next_day)

                # Combine with the send time
                from datetime import datetime

                next_datetime = datetime.combine(
                    next_date.date(),
                    time(hour=send_hour, minute=send_minute),
                    tzinfo=now.tzinfo,
                )

                # If the calculated time is in the past, recalculate
                if next_datetime <= now:
                    # This can happen if it's the right day but we're past the time
                    if now.day == next_day:
                        # Try next month
                        if now.month == 12:
                            next_month = now.replace(year=now.year + 1, month=1, day=1)
                        else:
                            next_month = now.replace(month=now.month + 1, day=1)

                        valid_days = [
                            d
                            for d in days_of_month
                            if d <= self._days_in_month(next_month)
                        ]
                        if not valid_days:
                            valid_days = [self._days_in_month(next_month)]

                        next_day = valid_days[0]
                        next_date = next_month.replace(day=next_day)

                        next_datetime = datetime.combine(
                            next_date.date(),
                            time(hour=send_hour, minute=send_minute),
                            tzinfo=now.tzinfo,
                        )

                self.next_send_at = next_datetime

        # For event triggered, the next_send_at is not applicable
        elif self.schedule_type == "triggered":
            self.next_send_at = None

        self.save(update_fields=["next_send_at"])
        return self.next_send_at

    def _days_in_month(self, date_obj):
        """Helper method to get the number of days in a month"""
        if date_obj.month == 12:
            return 31
        return (
            date_obj.replace(month=date_obj.month + 1, day=1) - timedelta(days=1)
        ).day

    def process_send(self):
        """Process the scheduled send if it's time"""
        now = timezone.now()

        # Check if it's ready to send
        if self.status != "active" and self.status != "scheduled":
            return False

        if self.schedule_type == "one_time":
            if not self.scheduled_time or self.scheduled_time > now:
                return False

        elif self.schedule_type == "recurring":
            if not self.next_send_at or self.next_send_at > now:
                return False

            # Check if we're within the schedule bounds
            if self.start_date and now < self.start_date:
                return False

            if self.end_date and now > self.end_date:
                self.status = "completed"
                self.save(update_fields=["status"])
                return False

        # Ready to send - in a real implementation, this would queue the sending task

        # Update tracking info
        self.last_sent_at = now
        self.total_sends += 1

        # For one-time sends, mark as completed
        if self.schedule_type == "one_time":
            self.status = "completed"
            self.next_send_at = None
        else:
            # For recurring, calculate the next send time
            self.calculate_next_send_time()

        self.save(
            update_fields=["last_sent_at", "total_sends", "status", "next_send_at"]
        )
        return True

    def pause(self):
        """Pause the schedule"""
        if self.status in ["active", "scheduled"]:
            self.status = "paused"
            self.save(update_fields=["status"])
            return True
        return False

    def resume(self):
        """Resume the schedule"""
        if self.status == "paused":
            if self.schedule_type == "one_time":
                # For one-time, check if the scheduled time is still in the future
                if self.scheduled_time and self.scheduled_time > timezone.now():
                    self.status = "scheduled"
                else:
                    return False
            else:
                # For recurring, recalculate next send time
                self.status = "active"
                self.calculate_next_send_time()

            self.save(update_fields=["status", "next_send_at"])
            return True
        return False

    def cancel(self):
        """Cancel the schedule"""
        if self.status in ["active", "scheduled", "paused"]:
            self.status = "canceled"
            self.next_send_at = None
            self.save(update_fields=["status", "next_send_at"])
            return True
        return False
