# apps/bookingapp/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from apps.bookingapp.models import Appointment, MultiServiceBooking
from apps.bookingapp.services.reminder_service import ReminderService


@receiver(post_save, sender=Appointment)
def create_appointment_reminders(sender, instance, created, **kwargs):
    """Create reminders when a new appointment is created"""
    if created:
        # Create standard reminders
        ReminderService.create_appointment_reminders(instance)


@receiver(post_save, sender=Appointment)
def notify_on_status_change(sender, instance, **kwargs):
    """Send notifications on appointment status changes"""
    if kwargs.get("update_fields") and "status" in kwargs["update_fields"]:
        # Status has changed, send appropriate notifications
        from apps.notificationsapp.services.notification_service import (
            NotificationService,
        )

        if instance.status == "confirmed":
            # Send confirmation notification
            NotificationService.send_appointment_status_update(
                instance, _("Your appointment has been confirmed")
            )
        elif instance.status == "cancelled":
            # Send cancellation notification if not already handled
            if not instance.cancelled_by:
                NotificationService.send_appointment_status_update(
                    instance, _("Your appointment has been cancelled")
                )
        elif instance.status == "completed":
            # Send thank you and review request
            NotificationService.send_appointment_status_update(
                instance, _("Thank you for your visit! Please leave a review.")
            )


@receiver(pre_save, sender=Appointment)
def handle_appointment_reschedule(sender, instance, **kwargs):
    """Handle appointment reschedule by recreating reminders"""
    if instance.pk:  # Only for existing appointments
        try:
            old_instance = Appointment.objects.get(pk=instance.pk)

            # Check if start_time changed
            if old_instance.start_time != instance.start_time:
                # This is a reschedule - delete old unsent reminders
                old_instance.reminders.filter(is_sent=False).delete()

                # New reminders will be created by the reminder service
                # after save via transaction
        except Appointment.DoesNotExist:
            pass  # New appointment


@receiver(post_save, sender=MultiServiceBooking)
def update_appointments_payment(sender, instance, **kwargs):
    """Sync payment status to all appointments in a multi-service booking"""
    if kwargs.get("update_fields") and "payment_status" in kwargs["update_fields"]:
        # Payment status changed, update all appointments
        for appointment in instance.appointments.all():
            if appointment.payment_status != instance.payment_status:
                appointment.payment_status = instance.payment_status
                appointment.transaction_id = instance.transaction_id
                appointment.save(update_fields=["payment_status", "transaction_id"])
