# apps/bookingapp/signals.py
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from algorithms.availability.slot_generator import SlotGenerator
from apps.bookingapp.models import Appointment, MultiServiceBooking
from apps.bookingapp.services.reminder_service import ReminderService
from apps.notificationsapp.services.notification_service import NotificationService


@receiver(post_save, sender=Appointment)
def appointment_post_save(sender, instance, created, **kwargs):
    """
    Handle post-save signal for Appointments.
    Sends notifications and invalidates cache.
    """
    if created:
        # Create standard reminders
        ReminderService.create_appointment_reminders(instance)

        # Send notification to customer
        NotificationService.send_appointment_confirmation(instance)

        # Send notification to specialist
        NotificationService.send_new_appointment_to_specialist(instance)

        # Invalidate availability cache for this date
        slot_generator = SlotGenerator()
        slot_generator.invalidate_cache_for_date(
            instance.start_time.date(),
            shop_id=str(instance.shop.id),
            specialist_id=str(instance.specialist.id),
        )

    elif instance.tracker.has_changed("status") and instance.status == "cancelled":
        # Send cancellation notification
        NotificationService.send_appointment_cancellation(instance)

        # Invalidate availability cache for this date
        slot_generator = SlotGenerator()
        slot_generator.invalidate_cache_for_date(
            instance.start_time.date(),
            shop_id=str(instance.shop.id),
            specialist_id=str(instance.specialist.id),
        )

    # Check if start_time or specialist changed (reschedule)
    elif not created and (
        instance.tracker.has_changed("start_time") or instance.tracker.has_changed("specialist_id")
    ):
        # Invalidate availability cache for old and new dates
        slot_generator = SlotGenerator()

        # Get old date from tracker if start_time changed
        if instance.tracker.has_changed("start_time"):
            old_date = instance.tracker.previous("start_time").date()
            slot_generator.invalidate_cache_for_date(old_date)

        # Invalidate cache for current date
        slot_generator.invalidate_cache_for_date(
            instance.start_time.date(),
            shop_id=str(instance.shop.id),
            specialist_id=str(instance.specialist.id),
        )

        # Get old specialist from tracker if changed
        if instance.tracker.has_changed("specialist_id"):
            old_specialist_id = instance.tracker.previous("specialist_id")
            if old_specialist_id:
                slot_generator.invalidate_cache_for_date(
                    instance.start_time.date(), specialist_id=str(old_specialist_id)
                )


@receiver(post_delete, sender=Appointment)
def appointment_post_delete(sender, instance, **kwargs):
    """
    Handle post-delete signal for Appointments.
    Invalidates cache when an appointment is deleted.
    """
    # Invalidate availability cache for this date
    slot_generator = SlotGenerator()
    slot_generator.invalidate_cache_for_date(
        instance.start_time.date(),
        shop_id=str(instance.shop.id),
        specialist_id=str(instance.specialist.id),
    )


@receiver(post_save, sender=MultiServiceBooking)
def multi_service_booking_post_save(sender, instance, created, **kwargs):
    """
    Handle post-save signal for MultiServiceBookings.
    Sends payment confirmation notifications.
    """
    if created:
        # This is handled by the individual appointment signals
        pass
    elif instance.tracker.has_changed("payment_status") and instance.payment_status == "paid":
        # Send payment confirmation
        NotificationService.send_payment_confirmation(instance)


@receiver(post_save, sender=Appointment)
def notify_on_status_change(sender, instance, **kwargs):
    """Send notifications on appointment status changes"""
    if instance.tracker.has_changed("status"):
        # Status has changed, send appropriate notifications
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
    if instance.pk and instance.tracker.has_changed("start_time"):
        # This is a reschedule - delete old unsent reminders
        old_instance = Appointment.objects.get(pk=instance.pk)
        old_instance.reminders.filter(is_sent=False).delete()

        # New reminders will be created by the reminder service
        # after save via separate signal handler


@receiver(post_save, sender=MultiServiceBooking)
def update_appointments_payment(sender, instance, **kwargs):
    """Sync payment status to all appointments in a multi-service booking"""
    if instance.tracker.has_changed("payment_status"):
        # Payment status changed, update all appointments
        for appointment in instance.appointments.all():
            if appointment.payment_status != instance.payment_status:
                appointment.payment_status = instance.payment_status
                appointment.transaction_id = instance.transaction_id
                appointment.save(update_fields=["payment_status", "transaction_id"])
