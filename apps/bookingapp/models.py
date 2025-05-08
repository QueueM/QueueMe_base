# apps/bookingapp/models.py
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


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
    start_time = models.DateTimeField(_("Start Time"))
    end_time = models.DateTimeField(_("End Time"))
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default="scheduled"
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
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    total_price = models.DecimalField(
        _("Total Price"), max_digits=10, decimal_places=2, default=0
    )
    buffer_before = models.PositiveIntegerField(_("Buffer Before (minutes)"), default=0)
    buffer_after = models.PositiveIntegerField(_("Buffer After (minutes)"), default=0)
    duration = models.PositiveIntegerField(_("Duration (minutes)"), default=0)
    is_reviewed = models.BooleanField(_("Reviewed"), default=False)

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
        self.save()

    def mark_in_progress(self):
        """Mark appointment as in progress"""
        self.status = "in_progress"
        self.save()

    def mark_completed(self):
        """Mark appointment as completed"""
        self.status = "completed"
        self.save()

    def mark_cancelled(self, cancelled_by, reason=""):
        """Mark appointment as cancelled with user who cancelled and reason"""
        self.status = "cancelled"
        self.cancelled_by = cancelled_by
        self.cancellation_reason = reason
        self.save()

    def mark_no_show(self):
        """Mark appointment as no-show"""
        self.status = "no_show"
        self.save()

    def mark_paid(self, transaction_id=None):
        """Mark appointment as paid"""
        self.payment_status = "paid"
        if transaction_id:
            self.transaction_id = transaction_id
        self.save()

    def mark_reminder_sent(self):
        """Mark that a reminder has been sent"""
        self.is_reminder_sent = True
        self.save()


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


class MultiServiceBooking(models.Model):
    """Group multiple appointments into a single booking session"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="multi_service_bookings",
        verbose_name=_("Customer"),
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="multi_service_bookings",
        verbose_name=_("Shop"),
    )
    appointments = models.ManyToManyField(
        Appointment, related_name="booking_group", verbose_name=_("Appointments")
    )
    total_price = models.DecimalField(
        _("Total Price"), max_digits=10, decimal_places=2, default=0
    )
    transaction_id = models.CharField(
        _("Transaction ID"), max_length=100, null=True, blank=True
    )
    payment_status = models.CharField(
        _("Payment Status"),
        max_length=20,
        choices=Appointment.PAYMENT_STATUS_CHOICES,
        default="pending",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Multi-Service Booking")
        verbose_name_plural = _("Multi-Service Bookings")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer.phone_number} - {self.shop.name} - {self.created_at.strftime('%Y-%m-%d')}"

    def update_total_price(self):
        """Calculate and update total price based on all appointments"""
        self.total_price = sum(
            appointment.total_price for appointment in self.appointments.all()
        )
        self.save()

    def mark_paid(self, transaction_id=None):
        """Mark booking and all appointments as paid"""
        self.payment_status = "paid"
        if transaction_id:
            self.transaction_id = transaction_id
        self.save()

        # Also mark all appointments as paid
        for appointment in self.appointments.all():
            appointment.mark_paid(transaction_id)


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
