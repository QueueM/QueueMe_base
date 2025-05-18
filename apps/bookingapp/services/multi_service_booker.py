# apps/bookingapp/services/multi_service_booker.py
from django.utils import timezone

from apps.serviceapp.models import Service


class MultiServiceBooker:
    """Advanced service for handling multiple service bookings with conflict resolution"""

    @staticmethod
    def check_multi_service_conflicts(booking_requests):
        """
        Check for conflicts between multiple service booking requests

        Args:
            booking_requests: List of dicts with booking info (specialist_id, start_time, end_time)

        Returns:
            String with conflict description or None if no conflicts
        """
        # Check each pair of bookings for time conflicts
        for i, booking1 in enumerate(booking_requests):
            for j, booking2 in enumerate(booking_requests[i + 1 :], i + 1):

                # Check if same customer is trying to book overlapping services
                if (
                    booking1["start_time"] < booking2["end_time"]
                    and booking1["end_time"] > booking2["start_time"]
                ):

                    # If different specialists, no problem - customer can have concurrent services
                    if booking1["specialist_id"] != booking2["specialist_id"]:
                        continue

                    # Same specialist - definite conflict
                    return "Conflict between services: overlapping times with same specialist"

        # Check specialist availability for each booking
        from apps.bookingapp.services.conflict_service import ConflictService

        for booking in booking_requests:
            # Check for existing appointments
            conflict = ConflictService.check_appointment_conflict(
                booking["specialist_id"], booking["start_time"], booking["end_time"]
            )

            if conflict:
                return "Specialist already has an appointment during the requested time"

        return None  # No conflicts found

    @staticmethod
    def suggest_optimal_sequence(service_ids, date, shop_id, customer_id=None):
        """
        Suggest optimal sequence and times for multiple services

        Args:
            service_ids: List of service UUIDs
            date: Date for the booking
            shop_id: UUID of the shop
            customer_id: Optional customer UUID

        Returns:
            List of dicts with optimal booking sequence
        """
        services = [Service.objects.get(id=service_id) for service_id in service_ids]

        # Sort services by duration (longest first for better packing)
        services.sort(key=lambda s: s.duration, reverse=True)

        # Get available time slots for each service
        from apps.bookingapp.services.availability_service import AvailabilityService

        service_slots = {}
        for service in services:
            service_slots[service.id] = AvailabilityService.get_service_availability(
                service.id, date
            )

        # Find the earliest slot where all services can be booked sequentially
        # Start with the earliest slot of the first service
        if not all(service_slots.values()):
            return []  # Not all services have available slots

        # Get the earliest available start time
        earliest_start = None
        for slots in service_slots.values():
            if slots:
                first_slot_time = timezone.datetime.strptime(slots[0]["start"], "%H:%M").time()
                if earliest_start is None or first_slot_time < earliest_start:
                    earliest_start = first_slot_time

        if earliest_start is None:
            return []  # No available slots

        # Convert to datetime for easier arithmetic
        earliest_start_dt = timezone.datetime.combine(date, earliest_start)
        earliest_start_dt = timezone.make_aware(earliest_start_dt)

        # Try to fit all services sequentially
        current_time = earliest_start_dt
        bookings = []

        for service in services:
            # Find available slot that starts after current_time
            found_slot = False

            for slot in service_slots[service.id]:
                slot_start = timezone.datetime.strptime(slot["start"], "%H:%M").time()
                slot_start_dt = timezone.datetime.combine(date, slot_start)
                slot_start_dt = timezone.make_aware(slot_start_dt)

                if slot_start_dt >= current_time:
                    # Find best specialist for this service and time
                    from apps.bookingapp.services.specialist_matcher import SpecialistMatcher

                    slot_end = timezone.datetime.strptime(slot["end"], "%H:%M").time()
                    slot_end_dt = timezone.datetime.combine(date, slot_end)
                    slot_end_dt = timezone.make_aware(slot_end_dt)

                    specialist = SpecialistMatcher.find_best_specialist(
                        service.id, customer_id, (slot_start_dt, slot_end_dt)
                    )

                    if specialist:
                        bookings.append(
                            {
                                "service_id": service.id,
                                "service_name": service.name,
                                "specialist_id": specialist.id,
                                "specialist_name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
                                "start_time": slot_start_dt,
                                "end_time": slot_end_dt,
                                "duration": service.duration,
                                "price": service.price,
                            }
                        )

                        # Update current_time for next service
                        current_time = slot_end_dt + timezone.timedelta(
                            minutes=15
                        )  # 15-min break between services
                        found_slot = True
                        break

            if not found_slot:
                # Try again another day
                return []

        return bookings
