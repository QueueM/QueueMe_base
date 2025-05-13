# apps/bookingapp/services/booking_service.py
import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q
from django.utils import timezone

from apps.authapp.models import User
from apps.bookingapp.models import (
    Appointment,
    AppointmentReminder,
    AppointmentStatus,
    MultiServiceBooking,
)
from apps.customersapp.models import Customer
from apps.notificationsapp.services.notification_service import NotificationService
from apps.queueapp.models import QueueTicket
from apps.queueapp.services.queue_service import QueueService
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist
from utils.distributed_locks import DistributedLock, with_distributed_lock

from .availability_service import AvailabilityService

logger = logging.getLogger(__name__)


class BookingService:
    """Service for managing the booking process with transaction management"""

    @staticmethod
    @with_distributed_lock("specialist:{specialist_id}:date:{date_str}")
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
    @with_distributed_lock("appointment:{appointment_id}")
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
    @with_distributed_lock(
        "appointment:{appointment_id}:specialist:{new_specialist_id or 'current'}"
    )
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
    @with_distributed_lock("multi_service_booking:shop:{shop_id}:customer:{customer_id}")
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
        NotificationService.send_multi_service_booking_confirmation(multi_booking, appointments)

        return multi_booking

    @classmethod
    @transaction.atomic
    def create_appointment(
        cls,
        customer_id: str,
        shop_id: str,
        service_id: str,
        specialist_id: Optional[str] = None,
        date_time: datetime = None,
        duration_minutes: Optional[int] = None,
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new appointment with pessimistic locking to prevent double-booking.

        Args:
            customer_id: ID of the customer
            shop_id: ID of the shop
            service_id: ID of the service
            specialist_id: Optional ID of the specialist (if None, any available will be assigned)
            date_time: Date and time of the appointment
            duration_minutes: Optional duration override (if None, uses service default)
            notes: Optional notes for the appointment
            metadata: Additional data for the appointment

        Returns:
            Dictionary with appointment details and status
        """
        try:
            # Validate basic inputs
            if not customer_id or not shop_id or not service_id:
                return {
                    "success": False,
                    "message": "Customer, shop and service are required",
                }

            if not date_time:
                return {
                    "success": False,
                    "message": "Appointment date and time are required",
                }

            # Get necessary models with select_for_update to prevent race conditions
            try:
                customer = Customer.objects.select_for_update().get(id=customer_id)
                shop = Shop.objects.select_for_update().get(id=shop_id)
                service = Service.objects.select_for_update().get(id=service_id)
            except (
                Customer.DoesNotExist,
                Shop.DoesNotExist,
                Service.DoesNotExist,
            ) as e:
                return {"success": False, "message": f"Object not found: {str(e)}"}

            # Verify shop is open on the appointment date/time
            appointment_date = date_time.date()
            appointment_start_time = date_time.time()

            # Get appointment end time based on duration
            if not duration_minutes:
                duration_minutes = service.duration_minutes

            appointment_end_time = (
                datetime.combine(date.min, appointment_start_time)
                + timedelta(minutes=duration_minutes)
            ).time()

            # Check if shop is open
            if not AvailabilityService.is_shop_open(
                shop, appointment_date, appointment_start_time, appointment_end_time
            ):
                return {
                    "success": False,
                    "message": "Shop is not open at the requested time",
                }

            # Find or assign specialist
            if specialist_id:
                try:
                    specialist = Specialist.objects.select_for_update().get(
                        id=specialist_id,
                        shop=shop,
                        services__id=service_id,
                        is_active=True,
                    )
                except Specialist.DoesNotExist:
                    return {
                        "success": False,
                        "message": "Specialist not found or doesn't provide the requested service",
                    }
            else:
                # Find available specialist who provides this service
                available_specialists = AvailabilityService.get_available_specialists(
                    shop_id=shop_id,
                    service_id=service_id,
                    date=appointment_date,
                    start_time=appointment_start_time,
                    end_time=appointment_end_time,
                )

                if not available_specialists:
                    return {
                        "success": False,
                        "message": "No specialists available at the requested time",
                    }

                # Get the first available specialist with fewest appointments that day
                # to balance workload
                specialist_appointments = {
                    s.id: Appointment.objects.filter(
                        specialist=s,
                        date=appointment_date,
                        status__in=[
                            AppointmentStatus.CONFIRMED,
                            AppointmentStatus.PENDING,
                        ],
                    ).count()
                    for s in available_specialists
                }

                # Sort by appointment count and get the specialist with fewest appointments
                specialist = min(available_specialists, key=lambda s: specialist_appointments[s.id])

            # Check for overlapping appointments (both for specialist and customer)
            # We're using select_for_update to lock the related rows during this transaction
            overlapping_specialist_appointments = Appointment.objects.select_for_update().filter(
                specialist=specialist,
                date=appointment_date,
                status__in=[AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING],
                start_time__lt=appointment_end_time,
                end_time__gt=appointment_start_time,
            )

            if overlapping_specialist_appointments.exists():
                return {
                    "success": False,
                    "message": "Specialist already has an appointment at this time",
                }

            overlapping_customer_appointments = Appointment.objects.select_for_update().filter(
                customer=customer,
                date=appointment_date,
                status__in=[AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING],
                start_time__lt=appointment_end_time,
                end_time__gt=appointment_start_time,
            )

            if overlapping_customer_appointments.exists():
                return {
                    "success": False,
                    "message": "You already have an appointment at this time",
                }

            # Calculate price
            specialist_service = specialist.specialist_services.filter(service=service).first()
            if specialist_service:
                price = specialist_service.price
            else:
                price = service.base_price

            # Create appointment
            appointment = Appointment.objects.create(
                customer=customer,
                shop=shop,
                service=service,
                specialist=specialist,
                date=appointment_date,
                start_time=appointment_start_time,
                end_time=appointment_end_time,
                duration_minutes=duration_minutes,
                price=price,
                status=AppointmentStatus.PENDING,
                notes=notes or "",
                metadata=metadata or {},
            )

            # Send notification to customer
            NotificationService.send_appointment_created(appointment)

            # Send notification to specialist
            NotificationService.send_specialist_new_appointment(appointment)

            return {
                "success": True,
                "appointment_id": str(appointment.id),
                "customer_id": str(customer.id),
                "shop_id": str(shop.id),
                "service_id": str(service.id),
                "specialist_id": str(specialist.id),
                "date": appointment_date.isoformat(),
                "start_time": appointment_start_time.isoformat(),
                "end_time": appointment_end_time.isoformat(),
                "duration_minutes": duration_minutes,
                "price": float(price),
                "status": appointment.status,
            }

        except Exception as e:
            logger.error(f"Error creating appointment: {str(e)}")
            return {
                "success": False,
                "message": f"Error creating appointment: {str(e)}",
            }

    @classmethod
    @transaction.atomic
    def update_appointment_status(
        cls,
        appointment_id: str,
        new_status: str,
        notes: Optional[str] = None,
        notify: bool = True,
    ) -> Dict[str, Any]:
        """
        Update the status of an appointment with validation of allowed transitions.

        Args:
            appointment_id: ID of the appointment
            new_status: New status value
            notes: Optional notes for the status change
            notify: Whether to send notifications

        Returns:
            Dictionary with update status
        """
        try:
            try:
                appointment = Appointment.objects.select_for_update().get(id=appointment_id)
            except Appointment.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Appointment not found with ID: {appointment_id}",
                }

            current_status = appointment.status

            # Define allowed status transitions
            allowed_transitions = {
                AppointmentStatus.PENDING: [
                    AppointmentStatus.CONFIRMED,
                    AppointmentStatus.CANCELLED,
                ],
                AppointmentStatus.CONFIRMED: [
                    AppointmentStatus.CHECKED_IN,
                    AppointmentStatus.NO_SHOW,
                    AppointmentStatus.CANCELLED,
                    AppointmentStatus.RESCHEDULED,
                ],
                AppointmentStatus.CHECKED_IN: [
                    AppointmentStatus.IN_PROGRESS,
                    AppointmentStatus.CANCELLED,
                ],
                AppointmentStatus.IN_PROGRESS: [
                    AppointmentStatus.COMPLETED,
                    AppointmentStatus.CANCELLED,
                ],
                AppointmentStatus.COMPLETED: [],
                AppointmentStatus.CANCELLED: [],
                AppointmentStatus.NO_SHOW: [],
                AppointmentStatus.RESCHEDULED: [],
            }

            # Validate the status transition
            if new_status not in allowed_transitions.get(current_status, []):
                return {
                    "success": False,
                    "message": f"Invalid status transition from {current_status} to {new_status}",
                }

            # Special case for CHECKED_IN status - check if too early
            if new_status == AppointmentStatus.CHECKED_IN:
                now = timezone.now()
                appointment_datetime = datetime.combine(appointment.date, appointment.start_time)
                check_in_window = timedelta(minutes=30)  # Allow check-in 30 minutes before

                if now < (appointment_datetime - check_in_window):
                    return {
                        "success": False,
                        "message": "Cannot check in more than 30 minutes before appointment time",
                    }

            # Record old status for notification
            old_status = appointment.status

            # Update the appointment
            appointment.status = new_status
            if notes:
                appointment.notes = f"{appointment.notes}\n{notes}" if appointment.notes else notes

            # Record status change time
            status_timestamp_field = f"{new_status.lower()}_at"
            if hasattr(appointment, status_timestamp_field):
                setattr(appointment, status_timestamp_field, timezone.now())

            appointment.save()

            # Create a QueueTicket if appointment is checked in
            if new_status == AppointmentStatus.CHECKED_IN:
                # Check if a queue ticket already exists
                existing_ticket = QueueTicket.objects.filter(
                    appointment=appointment, status__in=["waiting", "serving"]
                ).first()

                if not existing_ticket:
                    # Create a new queue ticket
                    queue_result = QueueService.add_customer_to_queue(
                        shop_id=str(appointment.shop.id),
                        customer_id=str(appointment.customer.id),
                        specialist_id=str(appointment.specialist.id),
                        service_id=str(appointment.service.id),
                        appointment_id=str(appointment.id),
                    )

                    if not queue_result.get("success", False):
                        logger.error(
                            f"Failed to create queue ticket: {queue_result.get('message')}"
                        )

            # Send notifications if requested
            if notify:
                if new_status == AppointmentStatus.CONFIRMED:
                    NotificationService.send_appointment_confirmed(appointment)
                elif new_status == AppointmentStatus.CANCELLED:
                    NotificationService.send_appointment_cancelled(appointment, old_status)
                elif new_status == AppointmentStatus.COMPLETED:
                    NotificationService.send_appointment_completed(appointment)
                elif new_status == AppointmentStatus.NO_SHOW:
                    NotificationService.send_appointment_no_show(appointment)

            return {
                "success": True,
                "appointment_id": str(appointment.id),
                "new_status": new_status,
                "old_status": old_status,
            }

        except Exception as e:
            logger.error(f"Error updating appointment status: {str(e)}")
            return {
                "success": False,
                "message": f"Error updating appointment status: {str(e)}",
            }

    @classmethod
    @transaction.atomic
    def reschedule_appointment(
        cls,
        appointment_id: str,
        new_date: date,
        new_start_time: time,
        new_specialist_id: Optional[str] = None,
        notes: Optional[str] = None,
        notify: bool = True,
    ) -> Dict[str, Any]:
        """
        Reschedule an appointment with validation of time slots.

        Args:
            appointment_id: ID of the appointment to reschedule
            new_date: New date for the appointment
            new_start_time: New start time for the appointment
            new_specialist_id: Optional ID of a new specialist
            notes: Optional notes for the reschedule
            notify: Whether to send notifications

        Returns:
            Dictionary with reschedule status
        """
        try:
            try:
                appointment = Appointment.objects.select_for_update().get(id=appointment_id)
            except Appointment.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Appointment not found with ID: {appointment_id}",
                }

            # Check if appointment can be rescheduled
            if appointment.status not in [
                AppointmentStatus.PENDING,
                AppointmentStatus.CONFIRMED,
            ]:
                return {
                    "success": False,
                    "message": f"Cannot reschedule appointment with status: {appointment.status}",
                }

            # Calculate new end time
            new_end_time = (
                datetime.combine(date.min, new_start_time)
                + timedelta(minutes=appointment.duration_minutes)
            ).time()

            # Determine which specialist we're using
            specialist = appointment.specialist
            if new_specialist_id:
                try:
                    specialist = Specialist.objects.select_for_update().get(
                        id=new_specialist_id,
                        shop=appointment.shop,
                        services__id=str(appointment.service.id),
                        is_active=True,
                    )
                except Specialist.DoesNotExist:
                    return {
                        "success": False,
                        "message": "New specialist not found or doesn't provide the requested service",
                    }

            # Verify shop is open on the new appointment date/time
            if not AvailabilityService.is_shop_open(
                appointment.shop, new_date, new_start_time, new_end_time
            ):
                return {
                    "success": False,
                    "message": "Shop is not open at the requested time",
                }

            # Check if specialist is available
            if not AvailabilityService.is_specialist_available(
                specialist, new_date, new_start_time, new_end_time
            ):
                return {
                    "success": False,
                    "message": "Specialist is not available at the requested time",
                }

            # Check for overlapping appointments (excluding this appointment)
            overlapping_specialist_appointments = Appointment.objects.select_for_update().filter(
                ~Q(id=appointment.id),
                specialist=specialist,
                date=new_date,
                status__in=[AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING],
                start_time__lt=new_end_time,
                end_time__gt=new_start_time,
            )

            if overlapping_specialist_appointments.exists():
                return {
                    "success": False,
                    "message": "Specialist already has an appointment at this time",
                }

            overlapping_customer_appointments = Appointment.objects.select_for_update().filter(
                ~Q(id=appointment.id),
                customer=appointment.customer,
                date=new_date,
                status__in=[AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING],
                start_time__lt=new_end_time,
                end_time__gt=new_start_time,
            )

            if overlapping_customer_appointments.exists():
                return {
                    "success": False,
                    "message": "Customer already has an appointment at this time",
                }

            # Store old values for notification
            old_date = appointment.date
            old_start_time = appointment.start_time
            old_specialist = appointment.specialist

            # Update the appointment
            appointment.date = new_date
            appointment.start_time = new_start_time
            appointment.end_time = new_end_time
            appointment.specialist = specialist
            appointment.status = AppointmentStatus.CONFIRMED
            appointment.rescheduled_at = timezone.now()

            if notes:
                appointment.notes = (
                    f"{appointment.notes}\nRescheduled: {notes}"
                    if appointment.notes
                    else f"Rescheduled: {notes}"
                )

            appointment.save()

            # Send notifications if requested
            if notify:
                NotificationService.send_appointment_rescheduled(
                    appointment, old_date, old_start_time, old_specialist
                )

            return {
                "success": True,
                "appointment_id": str(appointment.id),
                "new_date": new_date.isoformat(),
                "new_start_time": new_start_time.isoformat(),
                "new_end_time": new_end_time.isoformat(),
                "specialist_id": str(specialist.id),
                "status": appointment.status,
            }

        except Exception as e:
            logger.error(f"Error rescheduling appointment: {str(e)}")
            return {
                "success": False,
                "message": f"Error rescheduling appointment: {str(e)}",
            }

    @classmethod
    def get_appointment_details(cls, appointment_id: str) -> Dict[str, Any]:
        """
        Get detailed information about an appointment.

        Args:
            appointment_id: ID of the appointment

        Returns:
            Dictionary with appointment details
        """
        try:
            try:
                appointment = Appointment.objects.get(id=appointment_id)
            except Appointment.DoesNotExist:
                return {
                    "success": False,
                    "message": f"Appointment not found with ID: {appointment_id}",
                }

            # Get queue position if checked in
            queue_position = None
            estimated_wait_time = None

            if appointment.status == AppointmentStatus.CHECKED_IN:
                queue_ticket = QueueTicket.objects.filter(
                    appointment=appointment, status="waiting"
                ).first()

                if queue_ticket:
                    queue_info = QueueService.get_customer_position(str(queue_ticket.id))
                    if queue_info.get("success", False):
                        queue_position = queue_info.get("position")
                        estimated_wait_time = queue_info.get("estimated_wait_minutes")

            return {
                "success": True,
                "appointment": {
                    "id": str(appointment.id),
                    "customer": {
                        "id": str(appointment.customer.id),
                        "name": appointment.customer.name,
                        "phone": appointment.customer.phone,
                    },
                    "shop": {
                        "id": str(appointment.shop.id),
                        "name": appointment.shop.name,
                        "address": appointment.shop.address,
                    },
                    "service": {
                        "id": str(appointment.service.id),
                        "name": appointment.service.name,
                        "category": (
                            appointment.service.category.name
                            if appointment.service.category
                            else None
                        ),
                    },
                    "specialist": {
                        "id": str(appointment.specialist.id),
                        "name": appointment.specialist.name,
                        "title": appointment.specialist.title,
                    },
                    "date": appointment.date.isoformat(),
                    "start_time": appointment.start_time.isoformat(),
                    "end_time": appointment.end_time.isoformat(),
                    "duration_minutes": appointment.duration_minutes,
                    "price": float(appointment.price),
                    "status": appointment.status,
                    "notes": appointment.notes,
                    "created_at": appointment.created_at.isoformat(),
                    "confirmed_at": (
                        appointment.confirmed_at.isoformat() if appointment.confirmed_at else None
                    ),
                    "cancelled_at": (
                        appointment.cancelled_at.isoformat() if appointment.cancelled_at else None
                    ),
                    "completed_at": (
                        appointment.completed_at.isoformat() if appointment.completed_at else None
                    ),
                    "checked_in_at": (
                        appointment.checked_in_at.isoformat() if appointment.checked_in_at else None
                    ),
                    "queue_position": queue_position,
                    "estimated_wait_minutes": estimated_wait_time,
                },
            }

        except Exception as e:
            logger.error(f"Error getting appointment details: {str(e)}")
            return {
                "success": False,
                "message": f"Error getting appointment details: {str(e)}",
            }
