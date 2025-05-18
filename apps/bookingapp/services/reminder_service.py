# apps/bookingapp/services/reminder_service.py
from datetime import timedelta

from django.utils import timezone

from apps.bookingapp.models import AppointmentReminder
from apps.notificationsapp.services.notification_service import NotificationService


class ReminderService:
    """Service for managing appointment reminders with scheduling and delivery"""

    @staticmethod
    def create_appointment_reminders(appointment):
        """
        Create standard reminder schedule for an appointment

        Args:
            appointment: Appointment object

        Returns:
            List of created AppointmentReminder objects
        """
        reminders = []

        # Create day-before reminder
        one_day_before = appointment.start_time - timedelta(days=1)

        day_reminder = AppointmentReminder.objects.create(
            appointment=appointment,
            reminder_type="sms",
            scheduled_time=one_day_before,
            content=f"Reminder: Your appointment for {appointment.service.name} is tomorrow at {appointment.start_time.strftime('%I:%M %p')} with {appointment.specialist.employee.first_name}.",
        )
        reminders.append(day_reminder)

        # Create hour-before reminder
        one_hour_before = appointment.start_time - timedelta(hours=1)

        hour_reminder = AppointmentReminder.objects.create(
            appointment=appointment,
            reminder_type="push",
            scheduled_time=one_hour_before,
            content=f"Your appointment for {appointment.service.name} is in 1 hour at {appointment.start_time.strftime('%I:%M %p')}.",
        )
        reminders.append(hour_reminder)

        return reminders

    @staticmethod
    def create_custom_reminder(appointment, reminder_type, time_before, content=None):
        """
        Create a custom reminder for an appointment

        Args:
            appointment: Appointment object
            reminder_type: Type of reminder (sms, push, email)
            time_before: timedelta before appointment for the reminder
            content: Optional custom message

        Returns:
            Created AppointmentReminder object
        """
        scheduled_time = appointment.start_time - time_before

        # Generate default content if not provided
        if content is None:
            time_str = appointment.start_time.strftime("%I:%M %p")

            if time_before.days > 0:
                days = time_before.days
                content = f"Reminder: Your appointment for {appointment.service.name} is in {days} days at {time_str}."
            elif time_before.seconds // 3600 > 0:
                hours = time_before.seconds // 3600
                content = f"Reminder: Your appointment for {appointment.service.name} is in {hours} hours at {time_str}."
            else:
                minutes = time_before.seconds // 60
                content = f"Reminder: Your appointment for {appointment.service.name} is in {minutes} minutes at {time_str}."

        reminder = AppointmentReminder.objects.create(
            appointment=appointment,
            reminder_type=reminder_type,
            scheduled_time=scheduled_time,
            content=content,
        )

        return reminder

    @staticmethod
    def process_due_reminders():
        """
        Process all reminders that are due to be sent

        Returns:
            Count of reminders processed
        """
        now = timezone.now()

        # Get all unsent reminders that are due
        due_reminders = AppointmentReminder.objects.filter(
            is_sent=False,
            scheduled_time__lte=now,
            appointment__status__in=["scheduled", "confirmed"],
        )

        count = 0

        for reminder in due_reminders:
            # Only send if appointment is still active
            if reminder.appointment.status in ["scheduled", "confirmed"]:

                # Send notification based on reminder type
                if reminder.reminder_type == "sms":
                    NotificationService.send_sms_reminder(reminder)
                elif reminder.reminder_type == "push":
                    NotificationService.send_push_reminder(reminder)
                elif reminder.reminder_type == "email":
                    NotificationService.send_email_reminder(reminder)

                # Mark reminder as sent
                reminder.mark_sent()
                count += 1

        return count

    @staticmethod
    def reschedule_reminders(appointment):
        """
        Reschedule all unsent reminders for an appointment after changes

        Args:
            appointment: Updated Appointment object

        Returns:
            List of rescheduled reminders
        """
        # Delete existing unsent reminders
        appointment.reminders.filter(is_sent=False).delete()

        # Create new reminders
        return ReminderService.create_appointment_reminders(appointment)
