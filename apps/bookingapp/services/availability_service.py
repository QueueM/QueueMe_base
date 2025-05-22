# apps/bookingapp/services/availability_service.py
import logging
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from django.core.cache import cache

from apps.bookingapp.models import Appointment
from apps.serviceapp.models import Service, ServiceAvailability
from apps.shopapp.models import Shop, ShopHours
from apps.specialistsapp.models import (
    Specialist,
    SpecialistWorkingHours,
)

logger = logging.getLogger(__name__)

# Type definitions for time slots
TimeSlot = Tuple[datetime, datetime]  # (start_time, end_time)
TimeRange = Tuple[time, time]  # (start_time, end_time)
DayOfWeek = int  # 0-6: Monday-Sunday


class AvailabilityService:
    """
    Service for calculating dynamic availability based on multiple constraints.

    This implements sophisticated algorithms to determine available time slots
    by intersecting various time-based constraints.
    """

    # Cache settings
    AVAILABILITY_CACHE_TTL = 60 * 15  # 15 minutes

    @classmethod
    def get_available_slots(
        cls,
        shop_id: str,
        service_id: str,
        target_date: date,
        specialist_id: Optional[str] = None,
        duration_override: Optional[int] = None,
        slot_interval: Optional[int] = None,
    ) -> List[TimeSlot]:
        """
        Calculate available time slots for booking a service on a specific date.

        Args:
            shop_id: ID of the shop
            service_id: ID of the service
            target_date: Date to check availability for
            specialist_id: Optional ID of specific specialist (if None, finds any available specialist)
            duration_override: Optional custom duration (overrides service duration)
            slot_interval: Optional custom slot granularity (overrides service slot_granularity)

        Returns:
            List of available time slots as (start_time, end_time) tuples
        """
        # Check cache first
        cache_key = f"availability:{shop_id}:{service_id}:{target_date}:{specialist_id}:{duration_override}:{slot_interval}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        try:
            # Get required data
            service = Service.objects.select_related("shop").get(id=service_id)
            shop = Shop.objects.get(id=shop_id)

            # Get service details
            duration = duration_override or service.duration
            buffer_before = service.buffer_before or 0
            buffer_after = service.buffer_after or 0
            granularity = (
                slot_interval or service.slot_granularity or 15
            )  # Default 15-min slots

            # 1. Get shop operating hours for the day
            day_of_week = target_date.weekday()
            shop_hours = cls._get_shop_hours(shop, day_of_week)
            if not shop_hours:
                logger.info(f"Shop {shop.name} is closed on {target_date}")
                return []

            # 2. Get service availability time ranges
            service_ranges = cls._get_service_availability(service, day_of_week)
            if not service_ranges:
                logger.info(f"Service {service.name} is not available on {target_date}")
                return []

            # 3. Intersect shop hours and service availability
            base_availability = cls._intersect_time_ranges(shop_hours, service_ranges)
            if not base_availability:
                logger.info(
                    f"No overlap between shop hours and service availability on {target_date}"
                )
                return []

            # 4. If specialist is specified, consider their availability
            if specialist_id:
                specialist = Specialist.objects.get(id=specialist_id)
                specialist_ranges = cls._get_specialist_hours(specialist, day_of_week)
                if not specialist_ranges:
                    logger.info(
                        f"Specialist {specialist.employee.name} is not working on {target_date}"
                    )
                    return []

                # Intersect with specialist availability
                base_availability = cls._intersect_time_ranges(
                    base_availability, specialist_ranges
                )
                if not base_availability:
                    logger.info(
                        f"No overlap between service availability and specialist hours on {target_date}"
                    )
                    return []

                # Get specialist's existing appointments
                existing_bookings = cls._get_specialist_bookings(
                    specialist_id, target_date
                )

                # Generate discrete time slots, avoiding existing bookings
                available_slots = cls._generate_available_slots(
                    base_availability,
                    target_date,
                    duration,
                    buffer_before,
                    buffer_after,
                    granularity,
                    existing_bookings,
                )
            else:
                # Find any available specialist
                specialists = cls._get_specialists_for_service(service_id)
                if not specialists:
                    logger.warning(f"No specialists assigned to service {service.name}")
                    return []

                # Combine availability across all specialists
                available_slots = []
                for sp in specialists:
                    # Get this specialist's working hours
                    specialist_ranges = cls._get_specialist_hours(sp, day_of_week)
                    if not specialist_ranges:
                        continue

                    # Intersect base availability with this specialist's hours
                    specialist_availability = cls._intersect_time_ranges(
                        base_availability, specialist_ranges
                    )
                    if not specialist_availability:
                        continue

                    # Get this specialist's existing appointments
                    existing_bookings = cls._get_specialist_bookings(sp.id, target_date)

                    # Generate slots for this specialist
                    specialist_slots = cls._generate_available_slots(
                        specialist_availability,
                        target_date,
                        duration,
                        buffer_before,
                        buffer_after,
                        granularity,
                        existing_bookings,
                    )

                    # Merge into overall availability
                    available_slots = cls._merge_time_slots(
                        available_slots, specialist_slots
                    )

            # Sort slots by start time
            available_slots.sort(key=lambda x: x[0])

            # Cache the result
            cache.set(cache_key, available_slots, cls.AVAILABILITY_CACHE_TTL)

            return available_slots

        except Exception as e:
            logger.error(f"Error calculating availability: {str(e)}")
            return []

    @classmethod
    def get_earliest_available_slot(
        cls,
        shop_id: str,
        service_id: str,
        start_date: date,
        days_to_check: int = 7,
        specialist_id: Optional[str] = None,
    ) -> Optional[TimeSlot]:
        """
        Find the earliest available slot for a service within a date range.

        Args:
            shop_id: ID of the shop
            service_id: ID of the service
            start_date: Starting date to check
            days_to_check: Number of days to look ahead
            specialist_id: Optional specialist ID

        Returns:
            The earliest available time slot, or None if none available
        """
        current_date = start_date

        for _ in range(days_to_check):
            # Get available slots for this day
            slots = cls.get_available_slots(
                shop_id, service_id, current_date, specialist_id
            )

            # Return the earliest slot if any available
            if slots:
                return slots[0]

            # Move to next day
            current_date += timedelta(days=1)

        # No slots found in the date range
        return None

    @classmethod
    def get_next_available_specialist(
        cls, shop_id: str, service_id: str, target_date: date, target_time: time
    ) -> Optional[str]:
        """
        Find the next available specialist for a service at a specific time.

        Args:
            shop_id: ID of the shop
            service_id: ID of the service
            target_date: Date for the appointment
            target_time: Time for the appointment

        Returns:
            ID of an available specialist, or None if none available
        """
        try:
            service = Service.objects.get(id=service_id)
            specialists = cls._get_specialists_for_service(service_id)

            target_datetime = datetime.combine(target_date, target_time)
            duration = service.duration
            buffer_before = service.buffer_before or 0
            buffer_after = service.buffer_after or 0

            # Required time block including buffers
            start_with_buffer = target_datetime - timedelta(minutes=buffer_before)
            end_with_buffer = target_datetime + timedelta(
                minutes=duration + buffer_after
            )

            for specialist in specialists:
                # Check if specialist is working during this time
                if not cls._is_specialist_available(
                    specialist,
                    target_date,
                    start_with_buffer.time(),
                    end_with_buffer.time(),
                ):
                    continue

                # Check for conflicts with existing bookings
                existing_bookings = cls._get_specialist_bookings(
                    specialist.id, target_date
                )
                has_conflict = False

                for booking_start, booking_end in existing_bookings:
                    # Check for overlap
                    if (
                        start_with_buffer < booking_end
                        and end_with_buffer > booking_start
                    ):
                        has_conflict = True
                        break

                if not has_conflict:
                    return specialist.id

            # No available specialist found
            return None

        except Exception as e:
            logger.error(f"Error finding available specialist: {str(e)}")
            return None

    @classmethod
    def is_slot_available(
        cls,
        shop_id: str,
        service_id: str,
        target_datetime: datetime,
        specialist_id: Optional[str] = None,
    ) -> bool:
        """
        Check if a specific time slot is available for booking.

        Args:
            shop_id: ID of the shop
            service_id: ID of the service
            target_datetime: The datetime to check availability for
            specialist_id: Optional specialist ID

        Returns:
            Boolean indicating if the slot is available
        """
        try:
            target_date = target_datetime.date()
            target_datetime.time()
            service = Service.objects.get(id=service_id)

            # Get all available slots for that day
            available_slots = cls.get_available_slots(
                shop_id, service_id, target_date, specialist_id
            )

            # Check if the target time is in any of the available slots
            target_datetime_end = target_datetime + timedelta(minutes=service.duration)

            for slot_start, slot_end in available_slots:
                # Using a slight buffer for time comparison to account for second differences
                if (
                    abs((slot_start - target_datetime).total_seconds()) < 60
                    and abs((slot_end - target_datetime_end).total_seconds()) < 60
                ):
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking slot availability: {str(e)}")
            return False

    # ------------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------------

    @staticmethod
    def _get_shop_hours(shop: Shop, day_of_week: int) -> List[TimeRange]:
        """Get operating hours for a shop on a specific day of the week."""
        try:
            shop_hours = ShopHours.objects.filter(
                shop=shop, weekday=day_of_week, is_closed=False
            )

            if not shop_hours:
                return []

            return [(hours.from_hour, hours.to_hour) for hours in shop_hours]

        except Exception as e:
            logger.error(f"Error getting shop hours: {str(e)}")
            return []

    @staticmethod
    def _get_service_availability(
        service: Service, day_of_week: int
    ) -> List[TimeRange]:
        """Get availability time ranges for a service on a specific day."""
        try:
            availability = ServiceAvailability.objects.filter(
                service=service, day_of_week=day_of_week, is_available=True
            )

            if not availability:
                # If no specific availability set, use shop hours
                return AvailabilityService._get_shop_hours(service.shop, day_of_week)

            return [(a.start_time, a.end_time) for a in availability]

        except Exception as e:
            logger.error(f"Error getting service availability: {str(e)}")
            return []

    @staticmethod
    def _get_specialist_hours(
        specialist: Specialist, day_of_week: int
    ) -> List[TimeRange]:
        """Get working hours for a specialist on a specific day."""
        try:
            working_hours = SpecialistWorkingHours.objects.filter(
                specialist=specialist, weekday=day_of_week, is_off=False
            )

            if not working_hours:
                return []

            return [(wh.from_hour, wh.to_hour) for wh in working_hours]

        except Exception as e:
            logger.error(f"Error getting specialist hours: {str(e)}")
            return []

    @staticmethod
    def _get_specialists_for_service(service_id: str) -> List[Specialist]:
        """Get all specialists who can perform a specific service."""
        try:
            return Specialist.objects.filter(
                specialist_services__service_id=service_id, is_active=True
            ).select_related("employee")

        except Exception as e:
            logger.error(f"Error getting specialists for service: {str(e)}")
            return []

    @staticmethod
    def _get_specialist_bookings(
        specialist_id: str, target_date: date
    ) -> List[TimeSlot]:
        """Get existing bookings for a specialist on a specific date."""
        try:
            # Get start and end of the target date
            day_start = datetime.combine(target_date, time.min)
            day_end = datetime.combine(target_date, time.max)

            # Find all appointments for this specialist on this day
            appointments = Appointment.objects.filter(
                specialist_id=specialist_id,
                start_time__gte=day_start,
                start_time__lte=day_end,
                status__in=[
                    "scheduled",
                    "confirmed",
                    "in_progress",
                ],  # Only active appointments
            )

            return [(appt.start_time, appt.end_time) for appt in appointments]

        except Exception as e:
            logger.error(f"Error getting specialist bookings: {str(e)}")
            return []

    @staticmethod
    def _is_specialist_available(
        specialist: Specialist, target_date: date, start_time: time, end_time: time
    ) -> bool:
        """Check if a specialist is available during a specific time range."""
        try:
            day_of_week = target_date.weekday()
            working_hours = AvailabilityService._get_specialist_hours(
                specialist, day_of_week
            )

            # If no working hours defined, specialist is not working
            if not working_hours:
                return False

            # Check if the requested time falls within any working period
            for work_start, work_end in working_hours:
                if start_time >= work_start and end_time <= work_end:
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking specialist availability: {str(e)}")
            return False

    @staticmethod
    def _intersect_time_ranges(
        ranges1: List[TimeRange], ranges2: List[TimeRange]
    ) -> List[TimeRange]:
        """
        Find the intersection of two sets of time ranges.

        This is a key algorithm for availability calculation, finding overlapping time periods
        between different constraints. This optimized version uses sorting for better performance
        with large datasets.
        """
        if not ranges1 or not ranges2:
            return []

        # Sort ranges by start time for optimization
        ranges1 = sorted(ranges1, key=lambda x: x[0])
        ranges2 = sorted(ranges2, key=lambda x: x[0])

        result = []
        i, j = 0, 0

        # Use a two-pointer approach to find intersections efficiently
        while i < len(ranges1) and j < len(ranges2):
            # Get current ranges
            start1, end1 = ranges1[i]
            start2, end2 = ranges2[j]

            # Find intersection
            intersect_start = max(start1, start2)
            intersect_end = min(end1, end2)

            # If there's a valid intersection, add it
            if intersect_start < intersect_end:
                result.append((intersect_start, intersect_end))

            # Move the pointer for the range that ends earlier
            if end1 < end2:
                i += 1
            else:
                j += 1

        return result

    @staticmethod
    def _generate_available_slots(
        availability_ranges: List[TimeRange],
        target_date: date,
        duration: int,
        buffer_before: int,
        buffer_after: int,
        granularity: int,
        existing_bookings: List[TimeSlot],
    ) -> List[TimeSlot]:
        """
        Generate discrete time slots from availability ranges, considering constraints.

        This algorithm creates potential booking slots and filters out any that conflict
        with existing bookings or don't have enough time for the service + buffers.
        """
        available_slots = []
        total_duration = buffer_before + duration + buffer_after

        for start_time, end_time in availability_ranges:
            # Get datetime objects for start and end
            range_start = datetime.combine(target_date, start_time)
            range_end = datetime.combine(target_date, end_time)

            # Generate slots at granularity intervals
            current = range_start
            while current + timedelta(minutes=total_duration) <= range_end:
                # Potential slot with buffers
                slot_start_with_buffer = current
                slot_end_with_buffer = current + timedelta(minutes=total_duration)

                # The actual appointment time (excluding buffers)
                appointment_start = current + timedelta(minutes=buffer_before)
                appointment_end = appointment_start + timedelta(minutes=duration)

                # Check for conflicts with existing bookings
                has_conflict = False
                for booking_start, booking_end in existing_bookings:
                    # Check if there's any overlap between the slots with buffers
                    if (
                        slot_start_with_buffer < booking_end
                        and slot_end_with_buffer > booking_start
                    ):
                        has_conflict = True
                        break

                if not has_conflict:
                    # Add the appointment time (without buffers) to available slots
                    available_slots.append((appointment_start, appointment_end))

                # Move to next possible start time
                current += timedelta(minutes=granularity)

        return available_slots

    @staticmethod
    def _merge_time_slots(
        slots1: List[TimeSlot], slots2: List[TimeSlot]
    ) -> List[TimeSlot]:
        """
        Merge two lists of time slots, removing any duplicates.

        This is used when combining availability across multiple specialists.
        """
        # Create a set to eliminate duplicates (convert to string for hashability)
        merged_set = set(
            f"{slot[0].isoformat()}|{slot[1].isoformat()}" for slot in slots1 + slots2
        )

        # Convert back to datetime tuples
        merged_slots = []
        for slot_str in merged_set:
            start_str, end_str = slot_str.split("|")
            merged_slots.append(
                (datetime.fromisoformat(start_str), datetime.fromisoformat(end_str))
            )

        return merged_slots
