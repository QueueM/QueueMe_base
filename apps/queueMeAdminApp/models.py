import random
import string
import uuid

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User
from apps.shopapp.models import Shop

from .constants import (
    AUDIT_ACTION_CHOICES,
    COMPONENT_CHOICES,
    MAINTENANCE_SCHEDULED,
    MAINTENANCE_STATUS_CHOICES,
    NOTIFICATION_LEVEL_CHOICES,
    NOTIFICATION_LEVEL_INFO,
    PLATFORM_STATUS_CHOICES,
    PLATFORM_STATUS_OPERATIONAL,
    SETTING_CATEGORY_CHOICES,
    SETTING_CATEGORY_GENERAL,
    TICKET_CATEGORY_CHOICES,
    TICKET_PRIORITY_CHOICES,
    TICKET_PRIORITY_MEDIUM,
    TICKET_STATUS_CHOICES,
    TICKET_STATUS_OPEN,
    VERIFICATION_STATUS_CHOICES,
    VERIFICATION_STATUS_PENDING,
)


class SystemSetting(models.Model):
    """System-wide settings configurable by Queue Me admins"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(_("Key"), max_length=100, unique=True)
    value = models.TextField(_("Value"))
    description = models.TextField(_("Description"), blank=True)
    category = models.CharField(
        _("Category"),
        max_length=20,
        choices=SETTING_CATEGORY_CHOICES,
        default=SETTING_CATEGORY_GENERAL,
    )
    is_public = models.BooleanField(
        _("Public Setting"),
        default=False,
        help_text=_("If enabled, this setting will be visible to all users"),
    )
    last_updated = models.DateTimeField(_("Last Updated"), auto_now=True)

    class Meta:
        verbose_name = _("System Setting")
        verbose_name_plural = _("System Settings")
        ordering = ["category", "key"]

    def __str__(self):
        return f"{self.key}: {self.value}"


class AdminNotification(models.Model):
    """System notifications for Queue Me admins"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_("Title"), max_length=255)
    message = models.TextField(_("Message"))
    level = models.CharField(
        _("Level"),
        max_length=10,
        choices=NOTIFICATION_LEVEL_CHOICES,
        default=NOTIFICATION_LEVEL_INFO,
    )
    is_read = models.BooleanField(_("Read"), default=False)
    data = models.JSONField(_("Additional Data"), default=dict, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Admin Notification")
        verbose_name_plural = _("Admin Notifications")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class VerificationRequest(models.Model):
    """Shop verification request record"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="verification_requests",
        verbose_name=_("Shop"),
    )
    status = models.CharField(
        _("Status"),
        max_length=10,
        choices=VERIFICATION_STATUS_CHOICES,
        default=VERIFICATION_STATUS_PENDING,
    )
    documents = models.JSONField(_("Verification Documents"), default=list, blank=True)
    notes = models.TextField(_("Admin Notes"), blank=True)
    rejection_reason = models.TextField(_("Rejection Reason"), blank=True)
    submitted_at = models.DateTimeField(_("Submitted At"), auto_now_add=True)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="verified_shops",
        verbose_name=_("Verified By"),
        null=True,
        blank=True,
    )
    verified_at = models.DateTimeField(_("Verified At"), null=True, blank=True)

    class Meta:
        verbose_name = _("Verification Request")
        verbose_name_plural = _("Verification Requests")
        ordering = ["-submitted_at"]
        # A shop can only have one pending verification request at a time
        constraints = [
            models.UniqueConstraint(
                fields=["shop"],
                condition=models.Q(status=VERIFICATION_STATUS_PENDING),
                name="unique_pending_verification",
            )
        ]

    def __str__(self):
        return f"{self.shop.name} - {self.get_status_display()}"


class SupportTicket(models.Model):
    """Support ticket for customer or shop issues"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(
        _("Reference Number"), max_length=20, unique=True, editable=False
    )
    subject = models.CharField(_("Subject"), max_length=255)
    description = models.TextField(_("Description"))
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=TICKET_STATUS_CHOICES,
        default=TICKET_STATUS_OPEN,
    )
    priority = models.CharField(
        _("Priority"),
        max_length=10,
        choices=TICKET_PRIORITY_CHOICES,
        default=TICKET_PRIORITY_MEDIUM,
    )
    category = models.CharField(_("Category"), max_length=20, choices=TICKET_CATEGORY_CHOICES)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_tickets",
        verbose_name=_("Created By"),
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
        verbose_name=_("Assigned To"),
        null=True,
        blank=True,
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.SET_NULL,
        related_name="support_tickets",
        verbose_name=_("Related Shop"),
        null=True,
        blank=True,
    )
    attachments = models.JSONField(_("Attachments"), default=list, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Support Ticket")
        verbose_name_plural = _("Support Tickets")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference_number} - {self.subject}"

    def save(self, *args, **kwargs):
        # Generate a reference number if one doesn't exist
        if not self.reference_number:
            self.reference_number = self._generate_reference_number()
        super().save(*args, **kwargs)

    def _generate_reference_number(self):
        """Generate a unique reference number for the ticket"""
        timestamp = timezone.now().strftime("%y%m%d")
        random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"TKT-{timestamp}-{random_part}"


class SupportMessage(models.Model):
    """Message within a support ticket thread"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("Ticket"),
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="support_messages",
        verbose_name=_("Sender"),
    )
    message = models.TextField(_("Message"))
    attachments = models.JSONField(_("Attachments"), default=list, blank=True)
    is_from_admin = models.BooleanField(_("From Admin"), default=False)
    is_internal_note = models.BooleanField(
        _("Internal Note"), default=False, help_text=_("Only visible to admins")
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Support Message")
        verbose_name_plural = _("Support Messages")
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.ticket.reference_number} - {self.sender} - {self.created_at}"


class PlatformStatus(models.Model):
    """Status tracking for platform components"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    component = models.CharField(
        _("Component"), max_length=50, choices=COMPONENT_CHOICES, unique=True
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=PLATFORM_STATUS_CHOICES,
        default=PLATFORM_STATUS_OPERATIONAL,
    )
    description = models.TextField(_("Description"), blank=True)
    last_checked = models.DateTimeField(_("Last Checked"), auto_now=True)
    metrics = models.JSONField(_("Performance Metrics"), default=dict, blank=True)

    class Meta:
        verbose_name = _("Platform Status")
        verbose_name_plural = _("Platform Statuses")
        ordering = ["component"]

    def __str__(self):
        return f"{self.get_component_display()} - {self.get_status_display()}"


class MaintenanceSchedule(models.Model):
    """Scheduled maintenance events"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_("Title"), max_length=255)
    description = models.TextField(_("Description"))
    affected_components = models.JSONField(_("Affected Components"), default=list)
    start_time = models.DateTimeField(_("Start Time"))
    end_time = models.DateTimeField(_("End Time"))
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=MAINTENANCE_STATUS_CHOICES,
        default=MAINTENANCE_SCHEDULED,
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="scheduled_maintenances",
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Maintenance Schedule")
        verbose_name_plural = _("Maintenance Schedules")
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.title} ({self.start_time.strftime('%Y-%m-%d %H:%M')})"


class AuditLog(models.Model):
    """System-wide audit logging for admin actions"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(_("Action"), max_length=20, choices=AUDIT_ACTION_CHOICES)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        verbose_name=_("Actor"),
        null=True,
    )
    entity_type = models.CharField(_("Entity Type"), max_length=100)
    entity_id = models.CharField(_("Entity ID"), max_length=100)
    details = models.JSONField(_("Details"), default=dict, blank=True)
    ip_address = models.GenericIPAddressField(_("IP Address"), null=True, blank=True)
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True)

    class Meta:
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["entity_type"]),
            models.Index(fields=["entity_id"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} {self.entity_type} {self.entity_id} by {self.actor}"
