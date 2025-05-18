from datetime import datetime, time, timedelta

import pytz
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.serviceapp.models import Service, ServiceAvailability, ServiceException
from apps.shopapp.models import ShopHours
from apps.specialistsapp.models import SpecialistService, SpecialistWorkingHours


class AvailabilityService:
    @staticmethod
    def get_service_availability(service_id, date):
        """
        Get available time slots for a service on a specific date

        This sophisticated algorithm checks multiple constraints:
        1. Shop operating hours
        2. Service custom availability (if defined)
        3. Specialist availability
        4. Existing bookings
        5. Service exceptions (holidays, special days)

        Returns a list of available time slots
        """
        service = Service.objects.get(id=service_id)
        shop = service.shop

        # Check if current date is valid (not past, within max advance booking days)
        today = timezone.now().date()
        if date < today:
            return []  # Past date

        max_advance_date = today + timedelta(days=service.max_advance_booking_days)
        if date > max_advance_date:
            return []  # Too far in future

        # Check for service exception (holiday, special day)
        try:
            exception = ServiceException.objects.get(service=service, date=date)
            if exception.is_closed:
                return []  # Service is closed on this day

            # Use exception hours if not closed
            shop_open = exception.from_hour
            shop_close = exception.to_hour

            # Skip regular hour checks
        except ServiceException.DoesNotExist:
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

            # Check service custom availability (if enabled)
            if service.has_custom_availability:
                try:
                    service_availability = ServiceAvailability.objects.get(
                        service=service, weekday=weekday
                    )
                    if service_availability.is_closed:
                        return []  # Service not available on this day

                    # Intersection of shop hours and service hours
                    service_open = service_availability.from_hour
                    service_close = service_availability.to_hour

                    # Determine the most restrictive hours (latest open, earliest close)
                    if service_open > shop_open:
                        shop_open = service_open

                    if service_close < shop_close:
                        shop_close = service_close

                    # If the result is invalid (open time after close time), no availability
                    if shop_open >= shop_close:
                        return []  # No valid intersection of hours
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
        # Date object commented out as unused
        service_open_dt = datetime.combine(date, shop_open)
        service_close_dt = datetime.combine(date, shop_close)

        # Account for buffer time and duration
        slot_duration = service.duration
        total_slot_time = slot_duration + service.buffer_before + service.buffer_after

        # Start time is service open time plus buffer before
        current_dt = service_open_dt + timedelta(minutes=service.buffer_before)

        # Calculate current time for minimum booking notice
        now = timezone.now()
        min_notice_dt = now + timedelta(minutes=service.min_booking_notice)

        # Generate slots until we reach closing time
        while (
            current_dt + timedelta(minutes=slot_duration + service.buffer_after) <= service_close_dt
        ):
            slot_start = current_dt
            slot_end = slot_start + timedelta(minutes=slot_duration)

            # Skip slots that don't meet minimum booking notice
            if datetime.combine(date, slot_start.time()).replace(tzinfo=pytz.UTC) < min_notice_dt:
                current_dt += timedelta(minutes=service.slot_granularity)
                continue

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
                    # Slot is available if at least one specialist is available
                    available_slots.append(
                        {
                            "start": slot_start.strftime("%H:%M"),
                            "end": slot_end.strftime("%H:%M"),
                            "duration": slot_duration,
                            "buffer_before": service.buffer_before,
                            "buffer_after": service.buffer_after,
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

        This checks:
        1. Specialist working hours
        2. Existing appointments (including buffer times)

        Returns True if specialist is available, False otherwise
        """
        # Get day of week
        weekday = date.weekday()

        # Adjust for Python's weekday vs our schema
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
        # Date object commented out as unused

        # Slot start with buffer before
        slot_start_with_buffer = datetime.combine(date, start_time) - timedelta(
            minutes=buffer_before
        )

        # Slot end with buffer after
        slot_end_with_buffer = datetime.combine(date, end_time) + timedelta(minutes=buffer_after)

        # Make timezone aware
        timezone_obj = pytz.timezone("Asia/Riyadh")  # Saudi Arabia timezone
        slot_start_with_buffer = timezone_obj.localize(slot_start_with_buffer)
        slot_end_with_buffer = timezone_obj.localize(slot_end_with_buffer)

        # Check for overlapping appointments
        overlapping_appointments = Appointment.objects.filter(
            specialist=specialist,
            start_time__lt=slot_end_with_buffer,
            end_time__gt=slot_start_with_buffer,
            status__in=["scheduled", "confirmed", "in_progress"],
        )

        return not overlapping_appointments.exists()

    @staticmethod
    def get_available_specialists(service_id, date, start_time, end_time):
        """
        Get all available specialists for a service at a specific time

        This is used for booking to find which specialists can perform
        the service at the selected time.

        Returns a list of available specialist IDs
        """
        service = Service.objects.get(id=service_id)

        # Get time objects from string if needed
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, "%H:%M").time()

        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, "%H:%M").time()

        # Get specialists for this service
        specialist_services = SpecialistService.objects.filter(service=service)
        specialists = [ss.specialist for ss in specialist_services]

        # Filter for available specialists
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

    @staticmethod
    def get_service_available_days(service_id, start_date, end_date):
        """
        Get a list of days where a service has at least one available slot

        This is a performance-optimized version for showing a calendar UI,
        where we just need to know which days have any availability.

        Returns a list of dates that have at least one available slot
        """
        service = Service.objects.get(id=service_id)

        # Initialize empty available days list
        available_days = []

        # Check each day in the range
        current_date = start_date
        while current_date <= end_date:
            # Skip quickly if service/shop is closed on this day
            weekday = current_date.weekday()
            if weekday == 6:  # If Python's Sunday (6)
                weekday = 0  # Set to our Sunday (0)
            else:
                weekday += 1  # Otherwise add 1

            # Check for service exception
            exception_exists = ServiceException.objects.filter(
                service=service, date=current_date, is_closed=True
            ).exists()

            if exception_exists:
                current_date += timedelta(days=1)
                continue

            # Quick check for shop hours
            shop_closed = ShopHours.objects.filter(
                shop=service.shop, weekday=weekday, is_closed=True
            ).exists()

            if shop_closed:
                current_date += timedelta(days=1)
                continue

            # Quick check for service availability if enabled
            if service.has_custom_availability:
                service_closed = ServiceAvailability.objects.filter(
                    service=service, weekday=weekday, is_closed=True
                ).exists()

                if service_closed:
                    current_date += timedelta(days=1)
                    continue

            # If we reach here, do a full availability check
            slots = AvailabilityService.get_service_availability(service_id, current_date)

            if slots:
                available_days.append(current_date)

            current_date += timedelta(days=1)

        return available_days
