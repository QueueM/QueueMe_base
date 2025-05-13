# apps/bookingapp/services/conflict_service.py

from django.db.models import Q

from apps.bookingapp.models import Appointment
from apps.shopapp.models import ShopHours
from apps.specialistsapp.models import SpecialistWorkingHours


class ConflictService:
    """Advanced service for detecting and resolving scheduling conflicts"""

    @staticmethod
    def check_appointment_conflict(
        specialist_id, start_time, end_time, exclude_appointment_id=None
    ):
        """
        Check if proposed appointment time conflicts with existing bookings

        Args:
            specialist_id: UUID of the specialist
            start_time: Datetime of appointment start
            end_time: Datetime of appointment end
            exclude_appointment_id: Optional appointment ID to exclude (for reschedule)

        Returns:
            Boolean indicating if a conflict exists
        """
        # Create the base query for overlapping appointments
        query = Q(
            specialist_id=specialist_id,
            start_time__lt=end_time,  # Starts before new appointment ends
            end_time__gt=start_time,  # Ends after new appointment starts
            status__in=["scheduled", "confirmed", "in_progress"],
        )

        # Exclude the specified appointment if needed
        if exclude_appointment_id:
            query &= ~Q(id=exclude_appointment_id)

        # Check for conflicts
        return Appointment.objects.filter(query).exists()

    @staticmethod
    def check_multi_appointment_conflicts(appointments_data):
        """
        Check for conflicts between multiple appointments

        Args:
            appointments_data: List of dicts with appointment info (start_time, end_time, specialist_id)

        Returns:
            List of conflict pairs (indices of conflicting appointments)
        """
        conflicts = []

        # Check each pair of appointments
        for i in range(len(appointments_data)):
            for j in range(i + 1, len(appointments_data)):
                appt1 = appointments_data[i]
                appt2 = appointments_data[j]

                # Skip if different specialists
                if appt1["specialist_id"] != appt2["specialist_id"]:
                    continue

                # Check for time overlap
                if (
                    appt1["start_time"] < appt2["end_time"]
                    and appt1["end_time"] > appt2["start_time"]
                ):
                    conflicts.append((i, j))

        return conflicts

    @staticmethod
    def check_service_specialist_compatibility(service_id, specialist_id):
        """
        Check if specialist is qualified to provide the service

        Args:
            service_id: UUID of the service
            specialist_id: UUID of the specialist

        Returns:
            Boolean indicating if specialist can provide the service
        """
        from apps.specialistsapp.models import SpecialistService

        return SpecialistService.objects.filter(
            service_id=service_id, specialist_id=specialist_id
        ).exists()

    @staticmethod
    def check_working_hours_conflict(specialist_id, date, start_time, end_time):
        """
        Check if appointment is within specialist working hours

        Args:
            specialist_id: UUID of the specialist
            date: Date of the appointment
            start_time: Time of appointment start
            end_time: Time of appointment end

        Returns:
            Boolean indicating if appointment conflicts with working hours
        """
        # Get day of week
        weekday = date.weekday()

        # Adjust for Python's weekday (0 = Monday) vs our schema (0 = Sunday)
        if weekday == 6:  # If Python's Sunday (6)
            weekday = 0  # Set to our Sunday (0)
        else:
            weekday += 1  # Otherwise add 1

        try:
            # Get working hours for this day
            working_hours = SpecialistWorkingHours.objects.get(
                specialist_id=specialist_id, weekday=weekday
            )

            # Check if day off
            if working_hours.is_off:
                return True  # Conflict if day off

            # Check if appointment is within working hours
            if start_time < working_hours.from_hour or end_time > working_hours.to_hour:
                return True  # Conflict if outside working hours

            return False  # No conflict

        except SpecialistWorkingHours.DoesNotExist:
            return True  # Conflict if no working hours defined

    @staticmethod
    def check_shop_hours_conflict(shop_id, date, start_time, end_time):
        """
        Check if appointment is within shop hours

        Args:
            shop_id: UUID of the shop
            date: Date of the appointment
            start_time: Time of appointment start
            end_time: Time of appointment end

        Returns:
            Boolean indicating if appointment conflicts with shop hours
        """
        # Get day of week
        weekday = date.weekday()

        # Adjust for Python's weekday (0 = Monday) vs our schema (0 = Sunday)
        if weekday == 6:  # If Python's Sunday (6)
            weekday = 0  # Set to our Sunday (0)
        else:
            weekday += 1  # Otherwise add 1

        try:
            # Get shop hours for this day
            shop_hours = ShopHours.objects.get(shop_id=shop_id, weekday=weekday)

            # Check if shop is closed
            if shop_hours.is_closed:
                return True  # Conflict if shop closed

            # Check if appointment is within shop hours
            if start_time < shop_hours.from_hour or end_time > shop_hours.to_hour:
                return True  # Conflict if outside shop hours

            return False  # No conflict

        except ShopHours.DoesNotExist:
            return True  # Conflict if no shop hours defined
