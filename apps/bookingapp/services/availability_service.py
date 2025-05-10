# apps/bookingapp/services/availability_service.py
from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.serviceapp.models import Service, ServiceAvailability
from apps.shopapp.models import ShopHours
from apps.specialistsapp.models import (
    Specialist,
    SpecialistService,
    SpecialistWorkingHours,
)


class AvailabilityService:
    """
    Advanced service for calculating available time slots based on multiple constraints:
    - Shop opening hours
    - Service availability windows
    - Specialist working hours
    - Existing appointments
    - Buffer times
    """

    @staticmethod
    def get_service_availability(service_id, date):
        """
        Get available time slots for a service on a specific date

        Args:
            service_id: UUID of the service
            date: Date object for which to get availability

        Returns:
            List of available time slots with start/end times
        """
        service = Service.objects.get(id=service_id)
        shop = service.shop

        # Get day of week (0 = Sunday, 6 = Saturday)
        weekday = date.weekday()

        # Adjust for Python's weekday (0 = Monday) vs our schema (0 = Sunday)
        if weekday == 6:  # If Python's Sunday (6)
            weekday = 0  # Set to our Sunday (0)
        else:
            weekday += 1  # Otherwise add 1

        # Check shop hours
        try:
            shop_hours = ShopHours.objects.get(shop=shop, weekday=weekday)
            if shop_hours.is_closed:
                return []  # Shop is closed on this day

            shop_open = shop_hours.from_hour
            shop_close = shop_hours.to_hour
        except ShopHours.DoesNotExist:
            return []  # No hours defined for this day

        # Check service availability (if custom defined)
        service_open = shop_open
        service_close = shop_close

        try:
            service_availability = ServiceAvailability.objects.get(
                service=service, weekday=weekday
            )
            if service_availability.is_closed:
                return []  # Service not available on this day

            service_open = max(service_availability.from_hour, shop_open)
            service_close = min(service_availability.to_hour, shop_close)
        except ServiceAvailability.DoesNotExist:
            # Use shop hours if no custom service hours
            pass

        # Get specialists for this service
        specialist_services = SpecialistService.objects.filter(service=service)
        if not specialist_services.exists():
            return []  # No specialists for this service

        specialists = [ss.specialist for ss in specialist_services]

        # Generate possible time slots based on service duration and granularity
        possible_slots = []

        # Convert time objects to datetime for easier arithmetic
        unused_unused_date_obj = datetime.combine(date, time.min)
        service_open_dt = datetime.combine(date, service_open)
        service_close_dt = datetime.combine(date, service_close)

        # Account for buffer time and duration
        slot_duration = service.duration
        unused_unused_total_slot_time = (
            slot_duration + service.buffer_before + service.buffer_after
        )

        # Start time is service open time plus buffer before
        current_dt = service_open_dt + timedelta(minutes=service.buffer_before)

        # Generate slots until we reach closing time
        while (
            current_dt + timedelta(minutes=slot_duration + service.buffer_after)
            <= service_close_dt
        ):
            slot_start = current_dt
            slot_end = slot_start + timedelta(minutes=slot_duration)

            # Add to possible slots
            possible_slots.append((slot_start.time(), slot_end.time()))

            # Move to next slot based on granularity
            current_dt += timedelta(minutes=service.slot_granularity)

        # Filter out slots where no specialist is available
        available_slots = []

        for slot_start, slot_end in possible_slots:
            # For each slot, check if at least one specialist is available
            for specialist in specialists:
                if AvailabilityService.is_specialist_available(
                    specialist,
                    date,
                    slot_start,
                    slot_end,
                    service.buffer_before,
                    service.buffer_after,
                ):
                    # If any specialist is available, slot is available
                    available_slots.append(
                        {
                            "start": slot_start.strftime("%H:%M"),
                            "end": slot_end.strftime("%H:%M"),
                            "duration": slot_duration,
                            "buffer_before": service.buffer_before,
                            "buffer_after": service.buffer_after,
                            "specialist_id": str(
                                specialist.id
                            ),  # Include available specialist
                        }
                    )
                    break  # Found an available specialist, no need to check others

        return available_slots

    @staticmethod
    def is_specialist_available(
        specialist, date, start_time, end_time, buffer_before, buffer_after
    ):
        """
        Check if a specialist is available for a specific time slot

        Args:
            specialist: Specialist object
            date: Date object
            start_time: Start time
            end_time: End time
            buffer_before: Buffer time before appointment (minutes)
            buffer_after: Buffer time after appointment (minutes)

        Returns:
            Boolean indicating if specialist is available
        """
        # Get day of week
        weekday = date.weekday()

        # Adjust for Python's weekday (0 = Monday) vs our schema (0 = Sunday)
        if weekday == 6:  # If Python's Sunday (6)
            weekday = 0  # Set to our Sunday (0)
        else:
            weekday += 1  # Otherwise add 1

        # Check specialist working hours
        try:
            working_hours = SpecialistWorkingHours.objects.get(
                specialist=specialist, weekday=weekday
            )
            if working_hours.is_off:
                return False  # Specialist is off on this day

            specialist_start = working_hours.from_hour
            specialist_end = working_hours.to_hour

            # Check if slot is within specialist working hours
            if start_time < specialist_start or end_time > specialist_end:
                return False
        except SpecialistWorkingHours.DoesNotExist:
            return False  # No working hours defined

        # Check existing appointments
        # Calculate total slot time with buffers
        unused_unused_date_obj = datetime.combine(date, time.min)

        # Create timezone-aware datetime objects
        unused_unused_tz = timezone.get_default_timezone()

        # Slot start with buffer before
        slot_start_with_buffer = timezone.make_aware(
            datetime.combine(date, start_time)
        ) - timedelta(minutes=buffer_before)

        # Slot end with buffer after
        slot_end_with_buffer = timezone.make_aware(
            datetime.combine(date, end_time)
        ) + timedelta(minutes=buffer_after)

        # Check for overlapping appointments
        overlapping_appointments = Appointment.objects.filter(
            specialist=specialist,
            start_time__lt=slot_end_with_buffer,
            end_time__gt=slot_start_with_buffer,
            status__in=["scheduled", "confirmed", "in_progress"],
        )

        return not overlapping_appointments.exists()

    @staticmethod
    def check_time_slot_available(
        service_id, specialist_id, start_time, end_time, exclude_appointment_id=None
    ):
        """
        Check if a specific time slot is available for booking

        Args:
            service_id: UUID of the service
            specialist_id: UUID of the specialist
            start_time: Aware datetime for start
            end_time: Aware datetime for end
            exclude_appointment_id: Optional appointment ID to exclude (for reschedule)

        Returns:
            Boolean indicating if the slot is available
        """
        service = Service.objects.get(id=service_id)
        specialist = Specialist.objects.get(id=specialist_id)

        # Get date components
        date = start_time.date()
        start_time_obj = start_time.time()
        unused_unused_end_time_obj = end_time.time()

        # Check if specialist provides this service
        specialist_service = SpecialistService.objects.filter(
            specialist=specialist, service=service
        ).exists()

        if not specialist_service:
            return False

        # Check if slot is within service availability for this date
        available_slots = AvailabilityService.get_service_availability(service_id, date)

        # Format times for comparison
        start_str = start_time_obj.strftime("%H:%M")

        # Check if this specific start time is in available slots
        slot_available = False
        for slot in available_slots:
            if slot["start"] == start_str:
                slot_available = True
                break

        if not slot_available:
            return False

        # Check for conflicts with existing appointments
        buffer_before = service.buffer_before
        buffer_after = service.buffer_after

        # Create buffer-adjusted times
        slot_start_with_buffer = start_time - timedelta(minutes=buffer_before)
        slot_end_with_buffer = end_time + timedelta(minutes=buffer_after)

        # Build query for overlapping appointments
        query = Q(
            specialist=specialist,
            start_time__lt=slot_end_with_buffer,
            end_time__gt=slot_start_with_buffer,
            status__in=["scheduled", "confirmed", "in_progress"],
        )

        # Exclude the appointment if provided (for reschedule)
        if exclude_appointment_id:
            query &= ~Q(id=exclude_appointment_id)

        # Check for conflicts
        conflicts = Appointment.objects.filter(query).exists()

        return not conflicts

    @staticmethod
    def get_available_specialists(service_id, date, start_time, end_time):
        """
        Find all specialists who can provide a service at the given time

        Args:
            service_id: UUID of the service
            date: Date object
            start_time: Time object for start
            end_time: Time object for end

        Returns:
            List of available specialist IDs
        """
        service = Service.objects.get(id=service_id)

        # Get specialists who provide this service
        specialist_services = SpecialistService.objects.filter(service=service)
        specialists = [ss.specialist for ss in specialist_services]

        available_specialists = []

        for specialist in specialists:
            if AvailabilityService.is_specialist_available(
                specialist,
                date,
                start_time,
                end_time,
                service.buffer_before,
                service.buffer_after,
            ):
                available_specialists.append(specialist.id)

        return available_specialists
