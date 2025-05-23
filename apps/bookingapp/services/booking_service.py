"""
Booking Service Module for QueueMe Backend

This module provides comprehensive booking functionality for managing appointments,
scheduling, and queue management. It handles the entire booking lifecycle from
creation to completion, with proper transaction management and concurrency control.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from apps.bookingapp.models import (
    Appointment,
    AppointmentStatus,
)
from apps.customersapp.models import Customer
from apps.notificationsapp.services.notification_service import NotificationService
from apps.payment.services.payment_service import PaymentService
from apps.queueapp.services.queue_service import QueueService
from apps.serviceapp.models import Service
from apps.specialistsapp.models import Specialist
from utils.distributed_locks import with_distributed_lock

# Configure logging
logger = logging.getLogger(__name__)


class BookingService:
    """
    Service for managing the booking process with transaction management and concurrency control.

    This service handles:
    - Appointment creation, modification, and cancellation
    - Availability checking and conflict detection
    - Queue management integration
    - Notification triggering
    - Payment processing for bookings
    - Multi-service booking coordination

    All methods use database transactions and distributed locks to ensure
    data consistency and prevent double-bookings.
    """

    @staticmethod
    @with_distributed_lock("specialist:{specialist_id}:date:{date_str}")
    @transaction.atomic
    def create_appointment(
        customer_id: str,
        service_id: str,
        specialist_id: str,
        start_time_str: str,
        date_str: str,
        notes: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        promo_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new appointment booking with all necessary setup.

        This method:
        1. Validates customer, service, and specialist
        2. Checks availability for the requested time slot
        3. Creates the appointment record
        4. Sets up reminders and notifications
        5. Processes payment if payment_method_id is provided
        6. Creates a queue ticket if the appointment is for today

        Args:
            customer_id: UUID of the customer
            service_id: UUID of the service
            specialist_id: UUID of the specialist
            start_time_str: Time string in format HH:MM
            date_str: Date string in format YYYY-MM-DD
            notes: Optional notes for the appointment
            payment_method_id: Optional payment method ID for immediate payment
            promo_code: Optional promotion code for discounts

        Returns:
            Dict containing appointment details and status

        Raises:
            ValueError: If the requested time slot is not available
            ValueError: If any of the required entities don't exist
            ValueError: If payment processing fails
        """
        # Parse date and time
        booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        start_time = datetime.strptime(start_time_str, "%H:%M").time()

        # Get required objects
        try:
            customer = Customer.objects.get(id=customer_id)
            service = Service.objects.get(id=service_id)
            specialist = Specialist.objects.get(id=service_id)
            shop = specialist.shop
        except (
            Customer.DoesNotExist,
            Service.DoesNotExist,
            Specialist.DoesNotExist,
        ) as e:
            logger.error(f"Entity not found when creating appointment: {str(e)}")
            raise ValueError(f"Required entity not found: {str(e)}")

        # Check if specialist offers this service
        if not specialist.services.filter(id=service_id).exists():
            logger.warning(
                f"Specialist {specialist_id} does not offer service {service_id}"
            )
            raise ValueError("The selected specialist does not offer this service")

        # Check availability
        from .availability_service import AvailabilityService

        is_available = AvailabilityService.check_specialist_availability(
            specialist_id=specialist_id,
            service_id=service_id,
            date_str=date_str,
            start_time_str=start_time_str,
        )

        if not is_available:
            logger.warning(
                f"Time slot not available for specialist {specialist_id} at {date_str} {start_time_str}"
            )
            raise ValueError("The requested time slot is not available")

        # Calculate end time based on service duration
        start_datetime = datetime.combine(booking_date, start_time)
        end_datetime = start_datetime + timedelta(minutes=service.duration_minutes)

        # Create appointment
        appointment = Appointment.objects.create(
            customer=customer,
            service=service,
            specialist=specialist,
            shop=shop,
            start_time=start_datetime,
            end_time=end_datetime,
            status=AppointmentStatus.BOOKED,
            notes=notes,
            promo_code=promo_code,
        )

        # Set up reminders
        BookingService._create_appointment_reminders(appointment)

        # Process payment if payment method provided
        payment_status = None
        if payment_method_id:
            try:
                payment_result = PaymentService.process_appointment_payment(
                    appointment_id=str(appointment.id),
                    payment_method_id=payment_method_id,
                    customer_id=customer_id,
                )
                payment_status = payment_result.get("status")
            except Exception as e:
                logger.error(f"Payment processing failed: {str(e)}")
                # Rollback will happen automatically due to @transaction.atomic
                raise ValueError(f"Payment processing failed: {str(e)}")

        # Create queue ticket if appointment is for today
        queue_ticket = None
        if booking_date == timezone.now().date():
            queue_ticket = QueueService.create_ticket_for_appointment(appointment)

        # Send notifications
        NotificationService.send_appointment_confirmation(
            appointment_id=str(appointment.id), customer_id=customer_id
        )

        # Log successful booking
        logger.info(
            f"Appointment created: ID={appointment.id}, "
            f"Customer={customer_id}, Service={service_id}, "
            f"Specialist={specialist_id}, Time={date_str} {start_time_str}"
        )

        # Return appointment details
        return {
            "appointment_id": str(appointment.id),
            "start_time": appointment.start_time.isoformat(),
            "end_time": appointment.end_time.isoformat(),
            "status": appointment.status,
            "payment_status": payment_status,
            "queue_ticket_id": str(queue_ticket.id) if queue_ticket else None,
        }
