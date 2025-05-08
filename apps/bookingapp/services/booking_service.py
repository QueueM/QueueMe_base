# apps/bookingapp/services/booking_service.py
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.authapp.models import User
from apps.bookingapp.models import Appointment, AppointmentReminder, MultiServiceBooking
from apps.notificationsapp.services.notification_service import NotificationService
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


class BookingService:
    """Service for managing the booking process with transaction management"""

    @staticmethod
    @transaction.atomic
    def create_appointment(
        customer_id, service_id, specialist_id, start_time_str, date_str, notes=None
    ):
        """
        Create a new appointment booking with all necessary setup

        Args:
            customer_id: UUID of the customer
            service_id: UUID of the service
            specialist_id: UUID of the specialist
            start_time_str: Time string (HH:MM)
            date_str: Date string (YYYY-MM-DD)
            notes: Optional notes for the appointment

        Returns:
            Created Appointment object
        """
        # Get required objects
        customer = User.objects.get(id=customer_id)
        service = Service.objects.get(id=service_id)
        specialist = Specialist.objects.get(id=specialist_id)
        shop = service.shop

        # Parse date and time
        booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        start_time = datetime.strptime(start_time_str, "%H:%M").time()

        # Combine date and time
        start_datetime = datetime.combine(booking_date, start_time)

        # Make timezone-aware
        tz = timezone.get_default_timezone()
        start_datetime = timezone.make_aware(start_datetime, tz)

        # Calculate end time based on service duration
        end_datetime = start_datetime + timedelta(minutes=service.duration)

        # Check if specialist is available
        from apps.bookingapp.services.availability_service import AvailabilityService

        if not AvailabilityService.check_time_slot_available(
            service.id, specialist.id, start_datetime, end_datetime
        ):
            raise ValueError("Specialist is not available for this time slot")

        # Create appointment
        appointment = Appointment.objects.create(
            customer=customer,
            service=service,
            specialist=specialist,
            shop=shop,
            start_time=start_datetime,
            end_time=end_datetime,
            status="scheduled",
            notes=notes or "",
            total_price=service.price,
            buffer_before=service.buffer_before,
            buffer_after=service.buffer_after,
            duration=service.duration,
        )

        # Schedule reminders (1 day before and 1 hour before)
        one_day_before = start_datetime - timedelta(days=1)
        one_hour_before = start_datetime - timedelta(hours=1)

        AppointmentReminder.objects.create(
            appointment=appointment,
            reminder_type="sms",
            scheduled_time=one_day_before,
            content=f"Reminder: You have an appointment for {service.name} tomorrow at {start_time_str}.",
        )

        AppointmentReminder.objects.create(
            appointment=appointment,
            reminder_type="push",
            scheduled_time=one_hour_before,
            content=f"Your appointment for {service.name} is in 1 hour at {start_time_str}.",
        )

        # Send confirmation notification
        NotificationService.send_appointment_confirmation(appointment)

        return appointment

    @staticmethod
    @transaction.atomic
    def cancel_appointment(appointment_id, cancelled_by_id, reason=""):
        """
        Cancel an appointment with proper notifications and updates

        Args:
            appointment_id: UUID of the appointment
            cancelled_by_id: UUID of the user who cancelled
            reason: Optional cancellation reason

        Returns:
            Updated Appointment object
        """
        appointment = Appointment.objects.get(id=appointment_id)
        cancelled_by = User.objects.get(id=cancelled_by_id)

        # Check if cancellation is allowed
        now = timezone.now()
        if now > appointment.start_time:
            raise ValueError("Cannot cancel an appointment that has already started")

        # Update appointment status
        appointment.status = "cancelled"
        appointment.cancelled_by = cancelled_by
        appointment.cancellation_reason = reason
        appointment.save()

        # Cancel scheduled reminders
        appointment.reminders.filter(is_sent=False).delete()

        # Send cancellation notification
        NotificationService.send_appointment_cancellation(appointment)

        return appointment

    @staticmethod
    @transaction.atomic
    def reschedule_appointment(
        appointment_id, new_date_str, new_start_time_str, new_specialist_id=None
    ):
        """
        Reschedule an appointment with availability checking

        Args:
            appointment_id: UUID of the appointment
            new_date_str: New date string (YYYY-MM-DD)
            new_start_time_str: New time string (HH:MM)
            new_specialist_id: Optional UUID of new specialist

        Returns:
            Updated Appointment object
        """
        appointment = Appointment.objects.get(id=appointment_id)

        # Parse new date and time
        new_date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
        new_start_time = datetime.strptime(new_start_time_str, "%H:%M").time()

        # Combine date and time
        new_start_datetime = datetime.combine(new_date, new_start_time)

        # Make timezone-aware
        tz = timezone.get_default_timezone()
        new_start_datetime = timezone.make_aware(new_start_datetime, tz)

        # Calculate new end time
        service_duration = appointment.service.duration
        new_end_datetime = new_start_datetime + timedelta(minutes=service_duration)

        # Get specialist
        specialist = appointment.specialist
        if new_specialist_id:
            specialist = Specialist.objects.get(id=new_specialist_id)

        # Check availability
        from apps.bookingapp.services.availability_service import AvailabilityService

        if not AvailabilityService.check_time_slot_available(
            appointment.service.id,
            specialist.id,
            new_start_datetime,
            new_end_datetime,
            exclude_appointment_id=appointment.id,
        ):
            raise ValueError("Selected time slot is not available")

        # Update appointment
        appointment.start_time = new_start_datetime
        appointment.end_time = new_end_datetime
        appointment.specialist = specialist
        appointment.save()

        # Reschedule reminders
        appointment.reminders.filter(is_sent=False).delete()

        one_day_before = new_start_datetime - timedelta(days=1)
        one_hour_before = new_start_datetime - timedelta(hours=1)

        AppointmentReminder.objects.create(
            appointment=appointment,
            reminder_type="sms",
            scheduled_time=one_day_before,
            content=f"Reminder: Your rescheduled appointment for {appointment.service.name} is tomorrow at {new_start_time_str}.",
        )

        AppointmentReminder.objects.create(
            appointment=appointment,
            reminder_type="push",
            scheduled_time=one_hour_before,
            content=f"Your rescheduled appointment for {appointment.service.name} is in 1 hour at {new_start_time_str}.",
        )

        # Send rescheduling notification
        NotificationService.send_appointment_reschedule(appointment)

        return appointment

    @staticmethod
    @transaction.atomic
    def create_multi_service_booking(customer_id, bookings_data, shop_id):
        """
        Create multiple appointments as part of a single booking session

        Args:
            customer_id: UUID of the customer
            bookings_data: List of booking data dictionaries
            shop_id: UUID of the shop

        Returns:
            Created MultiServiceBooking object
        """
        customer = User.objects.get(id=customer_id)
        shop = Shop.objects.get(id=shop_id)

        # Create multi-service booking
        multi_booking = MultiServiceBooking.objects.create(customer=customer, shop=shop)

        # Create individual appointments
        appointments = []
        total_price = 0

        for booking_data in bookings_data:
            service = Service.objects.get(id=booking_data["service_id"])
            specialist = Specialist.objects.get(id=booking_data["specialist_id"])

            # Create appointment
            appointment = Appointment.objects.create(
                customer=customer,
                service=service,
                specialist=specialist,
                shop=shop,
                start_time=booking_data["start_datetime"],
                end_time=booking_data["end_datetime"],
                status="scheduled",
                notes=booking_data.get("notes", ""),
                total_price=service.price,
                buffer_before=service.buffer_before,
                buffer_after=service.buffer_after,
                duration=service.duration,
            )

            # Add to multi-booking
            multi_booking.appointments.add(appointment)
            appointments.append(appointment)
            total_price += service.price

            # Schedule reminders
            one_day_before = booking_data["start_datetime"] - timedelta(days=1)
            one_hour_before = booking_data["start_datetime"] - timedelta(hours=1)

            AppointmentReminder.objects.create(
                appointment=appointment,
                reminder_type="sms",
                scheduled_time=one_day_before,
                content=f"Reminder: You have an appointment for {service.name} tomorrow at {booking_data['start_datetime'].strftime('%H:%M')}.",
            )

            AppointmentReminder.objects.create(
                appointment=appointment,
                reminder_type="push",
                scheduled_time=one_hour_before,
                content=f"Your appointment for {service.name} is in 1 hour at {booking_data['start_datetime'].strftime('%H:%M')}.",
            )

        # Update total price
        multi_booking.total_price = total_price
        multi_booking.save()

        # Send confirmation notification for the whole booking
        NotificationService.send_multi_service_booking_confirmation(
            multi_booking, appointments
        )

        return multi_booking
