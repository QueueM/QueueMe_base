# apps/bookingapp/models.py
import uuid
from enum import Enum

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import FieldTracker

from apps.authapp.models import User
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


class AppointmentStatus(str, Enum):
    """Enum for appointment status values"""

    PENDING = "scheduled"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class Appointment(models.Model):
    """Appointment booking record with complete tracking of status and metadata"""

    STATUS_CHOICES = (
        ("scheduled", _("Scheduled")),
        ("confirmed", _("Confirmed")),
        ("in_progress", _("In Progress")),
        ("completed", _("Completed")),
        ("cancelled", _("Cancelled")),
        ("no_show", _("No Show")),
    )

    PAYMENT_STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("paid", _("Paid")),
        ("failed", _("Failed")),
        ("refunded", _("Refunded")),
        ("partially_refunded", _("Partially Refunded")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name=_("Customer"),
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name=_("Service"),
    )
    specialist = models.ForeignKey(
        Specialist,
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name=_("Specialist"),
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name=_("Shop"),
    )
    start_time = models.DateTimeField(_("Start Time"), db_index=True)
    end_time = models.DateTimeField(_("End Time"), db_index=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
        db_index=True,
    )
    notes = models.TextField(_("Notes"), blank=True)
    transaction_id = models.CharField(
        _("Transaction ID"), max_length=100, null=True, blank=True
    )
    payment_status = models.CharField(
        _("Payment Status"),
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    is_reminder_sent = models.BooleanField(_("Reminder Sent"), default=False)
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="cancelled_appointments",
        verbose_name=_("Cancelled By"),
        null=True,
        blank=True,
    )
    cancellation_reason = models.TextField(_("Cancellation Reason"), blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    total_price = models.DecimalField(
        _("Total Price"), max_digits=10, decimal_places=2, default=0
    )
    buffer_before = models.PositiveIntegerField(_("Buffer Before (minutes)"), default=0)
    buffer_after = models.PositiveIntegerField(_("Buffer After (minutes)"), default=0)
    duration = models.PositiveIntegerField(_("Duration (minutes)"), default=0)
    is_reviewed = models.BooleanField(_("Reviewed"), default=False)

    # Track field changes for signals
    tracker = FieldTracker(
        fields=["status", "payment_status", "start_time", "end_time", "specialist_id"]
    )

    class Meta:
        verbose_name = _("Appointment")
        verbose_name_plural = _("Appointments")
        ordering = ["-start_time"]
        indexes = [
            models.Index(fields=["start_time", "end_time"]),
            models.Index(fields=["status"]),
            models.Index(fields=["customer"]),
            models.Index(fields=["specialist"]),
            models.Index(fields=["shop"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["payment_status"]),
            # Add more powerful composite indexes for common queries
            models.Index(fields=["shop", "start_time", "status"]),
            models.Index(fields=["specialist", "start_time", "status"]),
            models.Index(fields=["customer", "start_time", "status"]),
            models.Index(fields=["shop", "payment_status"]),
            models.Index(fields=["service", "start_time"]),
        ]

    def __str__(self):
        return f"{self.customer.phone_number} - {self.service.name} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    def clean(self):
        """Validate appointment time constraints and business rules"""
        # Ensure end time is after start time
        if self.end_time <= self.start_time:
            raise ValidationError(_("End time must be after start time"))

        # Ensure specialist can provide this service
        from apps.specialistsapp.models import SpecialistService

        specialist_service = SpecialistService.objects.filter(
            specialist=self.specialist, service=self.service
        ).exists()

        if not specialist_service:
            raise ValidationError(_("Specialist does not provide this service"))

        # Ensure service belongs to the shop
        if self.service.shop != self.shop:
            raise ValidationError(_("Service does not belong to the selected shop"))

        # Ensure specialist belongs to the shop
        if self.specialist.employee.shop != self.shop:
            raise ValidationError(_("Specialist does not belong to the selected shop"))

    def save(self, *args, **kwargs):
        """Override save to handle automatic fields and validation"""
        # Set duration from service if not explicitly set
        if not self.duration and hasattr(self, "service") and self.service:
            self.duration = self.service.duration

        # Set buffer times from service if not explicitly set
        if self.service:
            if not self.buffer_before:
                self.buffer_before = self.service.buffer_before
            if not self.buffer_after:
                self.buffer_after = self.service.buffer_after

        # Ensure total price is set
        if self.service and not self.total_price:
            self.total_price = self.service.price

        # Call the clean method to validate
        self.clean()

        super().save(*args, **kwargs)

    def mark_confirmed(self):
        """Mark appointment as confirmed"""
        self.status = "confirmed"
        self.save(update_fields=["status", "updated_at"])

    def mark_in_progress(self):
        """Mark appointment as in progress"""
        self.status = "in_progress"
        self.save(update_fields=["status", "updated_at"])

    def mark_completed(self):
        """Mark appointment as completed"""
        self.status = "completed"
        self.save(update_fields=["status", "updated_at"])

    def mark_cancelled(self, cancelled_by, reason=""):
        """Mark appointment as cancelled with user who cancelled and reason"""
        self.status = "cancelled"
        self.cancelled_by = cancelled_by
        self.cancellation_reason = reason
        self.save(
            update_fields=[
                "status",
                "cancelled_by",
                "cancellation_reason",
                "updated_at",
            ]
        )

    def mark_no_show(self):
        """Mark appointment as no-show"""
        self.status = "no_show"
        self.save(update_fields=["status", "updated_at"])

    def mark_paid(self, transaction_id=None):
        """Mark appointment as paid"""
        self.payment_status = "paid"
        if transaction_id:
            self.transaction_id = transaction_id
        self.save(update_fields=["payment_status", "transaction_id", "updated_at"])

    def mark_reminder_sent(self):
        """Mark that a reminder has been sent"""
        self.is_reminder_sent = True
        self.save(update_fields=["is_reminder_sent", "updated_at"])


class AppointmentReminder(models.Model):
    """Appointment reminder record with tracking of delivery status"""

    REMINDER_TYPE_CHOICES = (
        ("sms", _("SMS")),
        ("push", _("Push Notification")),
        ("email", _("Email")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="reminders",
        verbose_name=_("Appointment"),
    )
    reminder_type = models.CharField(
        _("Reminder Type"), max_length=10, choices=REMINDER_TYPE_CHOICES
    )
    scheduled_time = models.DateTimeField(_("Scheduled Time"))
    sent_at = models.DateTimeField(_("Sent At"), null=True, blank=True)
    is_sent = models.BooleanField(_("Is Sent"), default=False)
    content = models.TextField(_("Content"), blank=True)

    class Meta:
        verbose_name = _("Appointment Reminder")
        verbose_name_plural = _("Appointment Reminders")
        ordering = ["scheduled_time"]
        indexes = [
            models.Index(fields=["scheduled_time"]),
            models.Index(fields=["is_sent"]),
        ]

    def __str__(self):
        return f"{self.appointment} - {self.get_reminder_type_display()} - {self.scheduled_time.strftime('%Y-%m-%d %H:%M')}"

    def mark_sent(self):
        """Mark reminder as sent"""
        self.is_sent = True
        self.sent_at = timezone.now()
        self.save()

        # Also update the appointment
        self.appointment.mark_reminder_sent()


class BookingStatus(models.Model):
    """Status options for bookings"""

    name = models.CharField(_("Status Name"), max_length=50)
    color = models.CharField(
        _("Color"), max_length=20, help_text=_("Hex color code (e.g. #FF0000)")
    )
    is_active = models.BooleanField(_("Active"), default=True)
    description = models.TextField(_("Description"), blank=True)

    class Meta:
        verbose_name = _("Booking Status")
        verbose_name_plural = _("Booking Statuses")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Booking(models.Model):
    """Booking model for customer appointments"""

    # Customer information
    customer_name = models.CharField(_("Customer Name"), max_length=255)
    customer_email = models.EmailField(_("Email"), blank=True)
    customer_phone = models.CharField(_("Phone"), max_length=20, blank=True)

    # Booking details
    booking_date = models.DateField(_("Date"), default=timezone.now)
    booking_time = models.TimeField(_("Time"), default=timezone.now)
    duration = models.IntegerField(_("Duration (minutes)"), default=60)

    # Service information
    service = models.CharField(_("Service"), max_length=255)
    specialist = models.CharField(_("Specialist"), max_length=255, blank=True)
    price = models.DecimalField(_("Price"), max_digits=10, decimal_places=2, default=0)

    # Status
    status = models.ForeignKey(
        BookingStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Status"),
    )

    # Additional information
    notes = models.TextField(_("Notes"), blank=True)

    # Metadata
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Booking")
        verbose_name_plural = _("Bookings")
        ordering = ["-booking_date", "-booking_time"]

    def __str__(self):
        return f"{self.customer_name} - {self.service} ({self.booking_date})"


class MultiServiceBooking(models.Model):
    """Booking that includes multiple services"""

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="multi_services",
        null=True,  # Allow null for existing records
        verbose_name=_("Booking"),
    )
    service_name = models.CharField(
        _("Service Name"), max_length=255, default="Unknown Service"
    )
    duration = models.IntegerField(_("Duration (minutes)"), default=30)
    price = models.DecimalField(_("Price"), max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = _("Multi-Service Booking")
        verbose_name_plural = _("Multi-Service Bookings")

    def __str__(self):
        if self.booking:
            return f"{self.booking.customer_name} - {self.service_name}"
        return f"Unassigned - {self.service_name}"


class AppointmentNote(models.Model):
    """Additional notes for appointments, can be added by staff or customer"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="notes_history",
        verbose_name=_("Appointment"),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="appointment_notes",
        verbose_name=_("User"),
    )
    note = models.TextField(_("Note"))
    is_private = models.BooleanField(
        _("Private"),
        default=False,
        help_text=_("Private notes are only visible to staff"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Appointment Note")
        verbose_name_plural = _("Appointment Notes")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.appointment} - Note by {self.user.phone_number}"
