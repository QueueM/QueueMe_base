from datetime import datetime, timedelta

from apps.bookingapp.models import Appointment
from apps.shopapp.models import ShopHours
from apps.specialistsapp.models import Specialist, SpecialistWorkingHours

from ..models import Package, PackageAvailability, PackageService


class PackageAvailabilityService:
    """
    Service for calculating available time slots for package bookings.
    Implements advanced availability algorithms with multiple constraint considerations.
    """

    @staticmethod
    def get_package_availability(package_id, date_str):
        """
        Get available time slots for a package on a specific date.
        This takes into account:
        - Package availability rules
        - Shop operating hours
        - All services in the package
        - Specialist availability for each service
        - Existing bookings

        Args:
            package_id: The package ID
            date_str: Date string in YYYY-MM-DD format

        Returns:
            list: List of available time slots for booking the package
        """
        try:
            # Parse date
            date = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Get package and services
            package = Package.objects.get(id=package_id)

            # Check if package is active
            if not package.is_available:
                return []

            # Get day of week (0 = Sunday, 6 = Saturday)
            weekday = date.weekday()
            if weekday == 6:  # Python's Sunday (6) to our Sunday (0)
                weekday = 0
            else:
                weekday += 1

            # Check shop hours first
            try:
                shop_hours = ShopHours.objects.get(shop=package.shop, weekday=weekday)
                if shop_hours.is_closed:
                    return []  # Shop is closed on this day

                shop_open = shop_hours.from_hour
                shop_close = shop_hours.to_hour
            except ShopHours.DoesNotExist:
                return []  # No hours defined for this day

            # Check package availability (if custom defined)
            package_open = shop_open
            package_close = shop_close

            try:
                package_availability = PackageAvailability.objects.get(
                    package=package, weekday=weekday
                )
                if package_availability.is_closed:
                    return []  # Package not available on this day

                package_open = max(package_availability.from_hour, shop_open)
                package_close = min(package_availability.to_hour, shop_close)
            except PackageAvailability.DoesNotExist:
                # Use shop hours if no custom package hours
                pass

            # Get all package services and their specialists
            package_services = PackageService.objects.filter(package=package).order_by(
                "sequence"
            )

            if not package_services.exists():
                return []  # No services in this package

            # Calculate total package duration
            total_duration = sum(ps.effective_duration for ps in package_services)

            # Check for specialists - each service needs at least one available specialist
            service_specialists = {}
            all_services_have_specialists = True

            for ps in package_services:
                service_id = ps.service_id
                specialists = Specialist.objects.filter(
                    specialist_services__service_id=service_id
                )

                if not specialists.exists():
                    all_services_have_specialists = False
                    break

                service_specialists[service_id] = list(specialists)

            if not all_services_have_specialists:
                return []  # At least one service has no specialists

            # Generate possible time slots based on package duration
            possible_slots = []

            # Convert time objects to datetime for easier arithmetic
            # Commenting out unused variable - fix for F841
            # date_obj = datetime.combine(date, time.min)
            package_open_dt = datetime.combine(date, package_open)
            package_close_dt = datetime.combine(date, package_close)

            # Start time is package open time
            current_dt = package_open_dt

            # Account for total time needed
            while current_dt + timedelta(minutes=total_duration) <= package_close_dt:
                slot_start = current_dt
                slot_end = slot_start + timedelta(minutes=total_duration)

                # Add to possible slots
                possible_slots.append((slot_start.time(), slot_end.time()))

                # Move to next slot based on 30-minute granularity
                # This could be adjusted based on business requirements
                current_dt += timedelta(minutes=30)

            # Filter slots based on service and specialist availability
            available_slots = []

            for slot_start, slot_end in possible_slots:
                # Check each service within this package slot
                current_time = slot_start
                all_services_available = True
                assigned_specialists = {}

                for ps in package_services:
                    service = ps.service
                    service_duration = ps.effective_duration
                    service_end_time = PackageAvailabilityService._add_minutes_to_time(
                        current_time, service_duration
                    )

                    # Check if service can be scheduled in this time slot
                    service_available = False

                    for specialist in service_specialists[service.id]:
                        if PackageAvailabilityService._is_specialist_available(
                            specialist,
                            date,
                            current_time,
                            service_end_time,
                            service.buffer_before,
                            service.buffer_after,
                        ):
                            # This specialist is available for this service at this time
                            assigned_specialists[service.id] = specialist.id
                            service_available = True
                            break

                    if not service_available:
                        all_services_available = False
                        break

                    # Move current time to the end of this service
                    current_time = service_end_time

                if all_services_available:
                    # This slot works for all services with available specialists
                    available_slots.append(
                        {
                            "start": slot_start.strftime("%H:%M"),
                            "end": slot_end.strftime("%H:%M"),
                            "duration": total_duration,
                            "specialist_assignments": assigned_specialists,
                        }
                    )

            return available_slots

        except (Package.DoesNotExist, ValueError) as e:
            raise ValueError(f"Error calculating availability: {str(e)}")

    @staticmethod
    def _add_minutes_to_time(time_obj, minutes):
        """
        Add minutes to a time object and return a new time object.

        Args:
            time_obj: Time object
            minutes: Minutes to add

        Returns:
            time: New time object with minutes added
        """
        # Convert to datetime for easier arithmetic
        dummy_date = datetime(2000, 1, 1)  # Any date will do
        datetime_obj = datetime.combine(dummy_date, time_obj)

        # Add minutes
        result_datetime = datetime_obj + timedelta(minutes=minutes)

        # Return just the time part
        return result_datetime.time()

    @staticmethod
    def _is_specialist_available(
        specialist, date, start_time, end_time, buffer_before, buffer_after
    ):
        """
        Check if a specialist is available for a specific time slot.

        Args:
            specialist: Specialist object
            date: Date for the time slot
            start_time: Start time of the service
            end_time: End time of the service
            buffer_before: Buffer time before the service
            buffer_after: Buffer time after the service

        Returns:
            bool: True if specialist is available, False otherwise
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
        # Commenting out unused variable - fix for F841
        # date_obj = datetime.combine(date, time.min)

        # Slot start with buffer before
        slot_start_with_buffer = datetime.combine(date, start_time) - timedelta(
            minutes=buffer_before
        )

        # Slot end with buffer after
        slot_end_with_buffer = datetime.combine(date, end_time) + timedelta(
            minutes=buffer_after
        )

        # Check for overlapping appointments
        overlapping_appointments = Appointment.objects.filter(
            specialist=specialist,
            start_time__lt=slot_end_with_buffer,
            end_time__gt=slot_start_with_buffer,
            status__in=["scheduled", "confirmed", "in_progress"],
        )

        return not overlapping_appointments.exists()

    @staticmethod
    def check_package_service_availability(package_id, date_str, time_str):
        """
        Check if all services in a package can be booked together at the specified time.
        Returns list of assigned specialists to each service if available.

        Args:
            package_id: The package ID
            date_str: Date string in YYYY-MM-DD format
            time_str: Time string in HH:MM format

        Returns:
            dict: Dictionary mapping service IDs to assigned specialist IDs,
                  or None if package cannot be booked at this time
        """
        try:
            # Parse date and time
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_time = datetime.strptime(time_str, "%H:%M").time()

            # Get package and services
            package = Package.objects.get(id=package_id)
            package_services = PackageService.objects.filter(package=package).order_by(
                "sequence"
            )

            if not package_services.exists():
                return None  # No services in this package

            # Check availability of each service
            current_time = start_time
            assigned_specialists = {}

            for ps in package_services:
                service = ps.service
                service_duration = ps.effective_duration
                service_end_time = PackageAvailabilityService._add_minutes_to_time(
                    current_time, service_duration
                )

                # Get specialists for this service
                specialists = Specialist.objects.filter(
                    specialist_services__service_id=service.id
                )

                # Check if any specialist is available
                service_available = False

                for specialist in specialists:
                    if PackageAvailabilityService._is_specialist_available(
                        specialist,
                        date,
                        current_time,
                        service_end_time,
                        service.buffer_before,
                        service.buffer_after,
                    ):
                        # This specialist is available for this service at this time
                        assigned_specialists[str(service.id)] = str(specialist.id)
                        service_available = True
                        break

                if not service_available:
                    return None  # Service cannot be scheduled

                # Move current time to the end of this service
                current_time = service_end_time

            return assigned_specialists

        except (
            Package.DoesNotExist,
            ValueError,
        ):  # Removed unused variable 'e' - fix for F841
            return None
