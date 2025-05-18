from datetime import datetime, time, timedelta

from django.core.cache import cache
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.serviceapp.models import Service
from apps.specialistsapp.constants import SPECIALIST_AVAILABILITY_CACHE_KEY
from apps.specialistsapp.models import Specialist, SpecialistWorkingHours


class AvailabilityService:
    """Service for calculating specialist availability"""

    def get_specialist_availability(self, specialist_id, date):
        """
        Get available time slots for a specialist on a specific date.

        Args:
            specialist_id: UUID of the specialist
            date: Date object for the requested day

        Returns:
            List of available time slots with start/end times
        """
        # Try to get from cache first
        cache_key = SPECIALIST_AVAILABILITY_CACHE_KEY.format(
            id=specialist_id, date=date.isoformat()
        )
        cached_availability = cache.get(cache_key)

        if cached_availability is not None:
            return cached_availability

        # Get specialist and check if they work on this day
        specialist = Specialist.objects.select_related("employee", "employee__shop").get(
            id=specialist_id
        )

        shop = specialist.employee.shop

        # Convert to weekday (0=Sunday, 6=Saturday)
        weekday = date.weekday()
        if weekday == 6:  # Python's Sunday (6)
            weekday = 0  # Our Sunday (0)
        else:
            weekday += 1  # Otherwise add 1

        # Check specialist working hours for this day
        try:
            working_hours = SpecialistWorkingHours.objects.get(
                specialist=specialist, weekday=weekday
            )

            if working_hours.is_off:
                # Specialist is off this day
                return []

            specialist_start = working_hours.from_hour
            specialist_end = working_hours.to_hour
        except SpecialistWorkingHours.DoesNotExist:
            # No working hours defined for this day
            return []

        # Check shop hours for this day
        shop_hours = shop.hours.filter(weekday=weekday).first()
        if not shop_hours or shop_hours.is_closed:
            # Shop is closed on this day
            return []

        shop_start = shop_hours.from_hour
        shop_end = shop_hours.to_hour

        # Calculate effective working hours (intersection of shop and specialist hours)
        effective_start = max(specialist_start, shop_start)
        effective_end = min(specialist_end, shop_end)

        if effective_start >= effective_end:
            # No overlap in working hours
            return []

        # Get services this specialist provides
        specialist_services = specialist.specialist_services.select_related("service").all()

        if not specialist_services.exists():
            # Specialist doesn't provide any services
            return []

        # Find the minimum slot length across all services
        min_slot_duration = min(ss.get_effective_duration() for ss in specialist_services)
        min_granularity = min(ss.service.slot_granularity for ss in specialist_services)

        # Generate all possible time slots based on shortest service and granularity
        slots = self._generate_time_slots(
            date, effective_start, effective_end, min_slot_duration, min_granularity
        )

        # Filter slots based on existing appointments
        available_slots = self._filter_available_slots(specialist, date, slots)

        # Format results
        formatted_slots = []

        for start, end in available_slots:
            # Check which services can be provided in this slot
            available_services = []

            for ss in specialist_services:
                service = ss.service
                duration = ss.get_effective_duration()

                # Calculate end time for this service
                service_end_time = (
                    datetime.combine(date, start) + timedelta(minutes=duration)
                ).time()

                # Check if service fits in this slot
                if service_end_time <= end:
                    available_services.append(
                        {
                            "id": str(service.id),
                            "name": service.name,
                            "duration": duration,
                            "price": float(service.price),
                        }
                    )

            # Only include slot if at least one service fits
            if available_services:
                formatted_slots.append(
                    {
                        "start": start.strftime("%H:%M"),
                        "end": end.strftime("%H:%M"),
                        "available_services": available_services,
                    }
                )

        # Cache the result for 5 minutes (balance between performance and accuracy)
        cache.set(cache_key, formatted_slots, 60 * 5)

        return formatted_slots

    def check_availability_for_service(self, specialist_id, service_id, date, start_time):
        """
        Check if a specialist is available for a specific service, date and time.

        Args:
            specialist_id: UUID of the specialist
            service_id: UUID of the service
            date: Date object for the requested day
            start_time: Time object for the start time

        Returns:
            Boolean indicating if the specialist is available
        """
        # Get specialist and service
        specialist = Specialist.objects.get(id=specialist_id)

        # Check if specialist provides this service
        specialist_service = specialist.specialist_services.filter(service_id=service_id).first()

        if not specialist_service:
            return False

        # Get service duration
        duration = specialist_service.get_effective_duration()

        # Calculate end time
        end_time = (datetime.combine(date, start_time) + timedelta(minutes=duration)).time()

        # Get available slots
        availability = self.get_specialist_availability(specialist_id, date)

        # Format start_time to match availability format
        start_str = start_time.strftime("%H:%M")
        end_str = end_time.strftime("%H:%M")

        # Check if the requested time slot is in the available slots
        for slot in availability:
            if slot["start"] <= start_str and end_str <= slot["end"]:
                # Check if service is available in this slot
                for service in slot["available_services"]:
                    if service["id"] == str(service_id):
                        return True

        return False

    def get_shop_specialists_availability(self, shop_id, service_id, date):
        """
        Get availability for all specialists in a shop for a specific service and date.

        Args:
            shop_id: UUID of the shop
            service_id: UUID of the service
            date: Date object for the requested day

        Returns:
            Dictionary mapping specialist IDs to their available time slots
        """
        from apps.shopapp.models import Shop

        # Get shop and service
        shop = Shop.objects.get(id=shop_id)
        service = Service.objects.get(id=service_id)

        # Get all specialists who provide this service
        specialists = Specialist.objects.filter(
            employee__shop=shop,
            employee__is_active=True,
            specialist_services__service=service,
        ).distinct()

        # Get availability for each specialist
        result = {}

        for specialist in specialists:
            availability = self.get_specialist_availability(specialist.id, date)

            # Filter slots for the specific service
            service_slots = []

            for slot in availability:
                for available_service in slot["available_services"]:
                    if available_service["id"] == str(service_id):
                        service_slots.append(slot)
                        break

            if service_slots:
                result[str(specialist.id)] = {
                    "name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
                    "slots": service_slots,
                }

        return result

    def is_specialist_available(self, specialist_id, date, start_time, end_time, service_id=None):
        """
        Check if a specialist is available during a specific time window.

        Args:
            specialist_id: UUID of the specialist
            date: Date object for the requested day
            start_time: Time object for the start time
            end_time: Time object for the end time
            service_id: Optional UUID of the service (for specific service checks)

        Returns:
            Boolean indicating if the specialist is available
        """
        # Get specialist
        specialist = Specialist.objects.get(id=specialist_id)

        # Convert date to weekday
        weekday = date.weekday()
        if weekday == 6:  # Python's Sunday (6)
            weekday = 0  # Our Sunday (0)
        else:
            weekday += 1  # Otherwise add 1

        # Check specialist working hours
        try:
            working_hours = SpecialistWorkingHours.objects.get(
                specialist=specialist, weekday=weekday
            )

            if working_hours.is_off:
                return False

            if start_time < working_hours.from_hour or end_time > working_hours.to_hour:
                return False
        except SpecialistWorkingHours.DoesNotExist:
            return False

        # Check shop hours
        shop = specialist.employee.shop
        shop_hours = shop.hours.filter(weekday=weekday).first()

        if not shop_hours or shop_hours.is_closed:
            return False

        if start_time < shop_hours.from_hour or end_time > shop_hours.to_hour:
            return False

        # Check existing appointments
        start_datetime = datetime.combine(date, start_time)
        end_datetime = datetime.combine(date, end_time)

        # Adjust for timezone if needed
        tz = timezone.get_current_timezone()
        start_datetime = timezone.make_aware(start_datetime, tz)
        end_datetime = timezone.make_aware(end_datetime, tz)

        # Check for overlapping appointments
        overlapping_appointments = Appointment.objects.filter(
            specialist=specialist,
            start_time__lt=end_datetime,
            end_time__gt=start_datetime,
            status__in=["scheduled", "confirmed", "in_progress"],
        )

        return not overlapping_appointments.exists()

    def _generate_time_slots(self, date_obj, start_time, end_time, min_duration, granularity):
        """
        Generate all possible time slots for the given time range.

        Args:
            date_obj: Date object
            start_time: Start time of availability
            end_time: End time of availability
            min_duration: Minimum duration of a slot in minutes
            granularity: Slot granularity in minutes

        Returns:
            List of (start_time, end_time) tuples
        """
        slots = []

        # Convert to datetime for easier arithmetic
        start_dt = datetime.combine(date_obj, start_time)
        end_dt = datetime.combine(date_obj, end_time)

        # Generate slots at each granularity increment
        current_start = start_dt

        while current_start + timedelta(minutes=min_duration) <= end_dt:
            slot_end = current_start + timedelta(minutes=min_duration)
            slots.append((current_start.time(), slot_end.time()))

            # Move to next slot based on granularity
            current_start += timedelta(minutes=granularity)

        return slots

    def _filter_available_slots(self, specialist, date_obj, slots):
        """
        Filter out slots that overlap with existing appointments.

        Args:
            specialist: Specialist object
            date_obj: Date object
            slots: List of (start_time, end_time) tuples

        Returns:
            List of available (start_time, end_time) tuples
        """
        # Get all appointments for this specialist on this date
        start_of_day = datetime.combine(date_obj, time.min)
        end_of_day = datetime.combine(date_obj, time.max)

        # Make timezone aware
        tz = timezone.get_current_timezone()
        start_of_day = timezone.make_aware(start_of_day, tz)
        end_of_day = timezone.make_aware(end_of_day, tz)

        # Get appointments with buffer times
        appointments = Appointment.objects.filter(
            specialist=specialist,
            start_time__date=date_obj,
            status__in=["scheduled", "confirmed", "in_progress"],
        ).order_by("start_time")

        # Create an optimized data structure to quickly check for overlaps
        busy_ranges = []

        for appt in appointments:
            # Include buffer times in the busy range
            service = appt.service

            # Calculate buffer start and end
            buffer_start = appt.start_time - timedelta(minutes=service.buffer_before)
            buffer_end = appt.end_time + timedelta(minutes=service.buffer_after)

            busy_ranges.append((buffer_start, buffer_end))

        # Filter slots that don't overlap with busy ranges
        available_slots = []

        for start_time, end_time in slots:
            # Convert to datetime for comparison
            slot_start = timezone.make_aware(datetime.combine(date_obj, start_time), tz)
            slot_end = timezone.make_aware(datetime.combine(date_obj, end_time), tz)

            # Check if slot overlaps with any busy range
            overlap = False

            for busy_start, busy_end in busy_ranges:
                if slot_start < busy_end and busy_start < slot_end:
                    overlap = True
                    break

            if not overlap:
                available_slots.append((start_time, end_time))

        return available_slots
