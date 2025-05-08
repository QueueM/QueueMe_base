import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User


class NotificationTemplate(models.Model):
    """Template for notifications"""

    TYPE_CHOICES = (
        ("appointment_confirmation", _("Appointment Confirmation")),
        ("appointment_reminder", _("Appointment Reminder")),
        ("appointment_cancellation", _("Appointment Cancellation")),
        ("appointment_reschedule", _("Appointment Reschedule")),
        ("queue_join_confirmation", _("Queue Join Confirmation")),
        ("queue_status_update", _("Queue Status Update")),
        ("queue_called", _("Queue Called")),
        ("queue_cancelled", _("Queue Cancelled")),
        ("new_message", _("New Message")),
        ("payment_confirmation", _("Payment Confirmation")),
        ("service_feedback", _("Service Feedback")),
        ("verification_code", _("Verification Code")),
        ("welcome", _("Welcome")),
        ("password_reset", _("Password Reset")),
    )

    CHANNEL_CHOICES = (
        ("sms", _("SMS")),
        ("push", _("Push Notification")),
        ("email", _("Email")),
        ("in_app", _("In-App Notification")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(_("Type"), max_length=50, choices=TYPE_CHOICES)
    channel = models.CharField(_("Channel"), max_length=10, choices=CHANNEL_CHOICES)
    subject = models.CharField(_("Subject"), max_length=255, blank=True)
    body_en = models.TextField(_("Body (English)"))
    body_ar = models.TextField(_("Body (Arabic)"))
    variables = models.JSONField(_("Variables"), default=list)
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Notification Template")
        verbose_name_plural = _("Notification Templates")
        unique_together = ("type", "channel")

    def __str__(self):
        return f"{self.get_type_display()} - {self.get_channel_display()}"


class Notification(models.Model):
    """Notification record"""

    STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("sent", _("Sent")),
        ("delivered", _("Delivered")),
        ("failed", _("Failed")),
        ("read", _("Read")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("User"),
    )
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        related_name="notifications",
        verbose_name=_("Template"),
        null=True,
    )
    type = models.CharField(_("Type"), max_length=50)
    channel = models.CharField(_("Channel"), max_length=10)
    subject = models.CharField(_("Subject"), max_length=255, blank=True)
    body = models.TextField(_("Body"))
    status = models.CharField(
        _("Status"), max_length=10, choices=STATUS_CHOICES, default="pending"
    )
    data = models.JSONField(_("Data"), default=dict)
    scheduled_for = models.DateTimeField(_("Scheduled For"), null=True, blank=True)
    sent_at = models.DateTimeField(_("Sent At"), null=True, blank=True)
    delivered_at = models.DateTimeField(_("Delivered At"), null=True, blank=True)
    read_at = models.DateTimeField(_("Read At"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["scheduled_for"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return f"{self.user.phone_number} - {self.type} - {self.status}"


class DeviceToken(models.Model):
    """Device token for push notifications"""

    PLATFORM_CHOICES = (
        ("ios", _("iOS")),
        ("android", _("Android")),
        ("web", _("Web")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="device_tokens",
        verbose_name=_("User"),
    )
    token = models.TextField(_("Token"))
    platform = models.CharField(_("Platform"), max_length=10, choices=PLATFORM_CHOICES)
    device_id = models.CharField(_("Device ID"), max_length=255)
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    last_used_at = models.DateTimeField(_("Last Used At"), auto_now=True)

    class Meta:
        verbose_name = _("Device Token")
        verbose_name_plural = _("Device Tokens")
        unique_together = ("user", "token")
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["device_id"]),
        ]

    def __str__(self):
        return f"{self.user.phone_number} - {self.get_platform_display()}"
