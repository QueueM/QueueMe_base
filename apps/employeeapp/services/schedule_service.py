from datetime import datetime, timedelta

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.employeeapp.models import Employee, EmployeeLeave, EmployeeWorkingHours


class ScheduleService:
    """
    Service for employee schedule and availability management
    Handles working hours, availability calculation, and schedule generation
    """

    @staticmethod
    @transaction.atomic
    def update_working_hours(employee_id, working_hours_data):
        """
        Update all working hours for an employee
        Args:
            employee_id: Employee ID
            working_hours_data: List of working hours data
        Returns:
            List of updated EmployeeWorkingHours objects
        """
        employee = Employee.objects.get(id=employee_id)

        # Validate that all weekdays are covered
        weekdays = [hours.get("weekday") for hours in working_hours_data]
        if sorted(weekdays) != list(range(7)):
            raise ValueError(
                _("Working hours must be provided for all 7 days of the week.")
            )

        # Delete existing hours
        EmployeeWorkingHours.objects.filter(employee=employee).delete()

        # Create new hours
        created_hours = []
        for hours_data in working_hours_data:
            hours = EmployeeWorkingHours.objects.create(employee=employee, **hours_data)
            created_hours.append(hours)

        return created_hours

    @staticmethod
    def get_employee_working_hours(employee_id, weekday):
        """
        Get working hours for an employee on a specific weekday
        Args:
            employee_id: Employee ID
            weekday: Weekday (0=Sunday, 6=Saturday)
        Returns:
            EmployeeWorkingHours object or None
        """
        try:
            return EmployeeWorkingHours.objects.get(
                employee_id=employee_id, weekday=weekday
            )
        except EmployeeWorkingHours.DoesNotExist:
            return None

    @staticmethod
    def is_employee_on_leave(employee_id, check_date):
        """
        Check if an employee is on approved leave on a specific date
        Args:
            employee_id: Employee ID
            check_date: Date to check
        Returns:
            Boolean
        """
        return EmployeeLeave.objects.filter(
            employee_id=employee_id,
            status="approved",
            start_date__lte=check_date,
            end_date__gte=check_date,
        ).exists()

    @staticmethod
    def get_employee_availability(employee_id, check_date):
        """
        Get an employee's availability for a specific date
        Takes into account working hours and approved leaves
        Args:
            employee_id: Employee ID
            check_date: Date to check
        Returns:
            Dictionary with availability information
        """
        employee = Employee.objects.get(id=employee_id)

        # Check if employee is active
        if not employee.is_active:
            return {"is_available": False, "reason": "inactive", "working_hours": None}

        # Check if the date is in the past
        if check_date < datetime.now().date():
            return {"is_available": False, "reason": "past_date", "working_hours": None}

        # Check if employee is on leave
        if ScheduleService.is_employee_on_leave(employee_id, check_date):
            return {"is_available": False, "reason": "on_leave", "working_hours": None}

        # Get weekday (0=Sunday, 6=Saturday)
        weekday = check_date.weekday()
        # Convert from Python's weekday (0=Monday) to our schema (0=Sunday)
        if weekday == 6:  # If Python's Sunday (6)
            weekday = 0  # Set to our Sunday (0)
        else:
            weekday += 1  # Otherwise add 1

        # Get working hours
        working_hours = ScheduleService.get_employee_working_hours(employee_id, weekday)

        if not working_hours:
            return {
                "is_available": False,
                "reason": "no_working_hours",
                "working_hours": None,
            }

        if working_hours.is_day_off:
            return {
                "is_available": False,
                "reason": "day_off",
                "working_hours": {"weekday": working_hours.weekday, "is_day_off": True},
            }

        # At this point, the employee is available
        availability = {
            "is_available": True,
            "reason": None,
            "working_hours": {
                "weekday": working_hours.weekday,
                "from_hour": working_hours.from_hour.strftime("%H:%M"),
                "to_hour": working_hours.to_hour.strftime("%H:%M"),
                "is_day_off": working_hours.is_day_off,
            },
        }

        # Add break times if any
        if working_hours.break_start and working_hours.break_end:
            availability["working_hours"]["break_start"] = (
                working_hours.break_start.strftime("%H:%M")
            )
            availability["working_hours"]["break_end"] = (
                working_hours.break_end.strftime("%H:%M")
            )

        # If employee is a specialist, we also need to check their appointments
        if employee.is_specialist:
            try:
                from apps.bookingapp.models import Appointment

                # Get appointments for this date
                appointments = Appointment.objects.filter(
                    specialist=employee.specialist,
                    start_time__date=check_date,
                    status__in=["scheduled", "confirmed", "in_progress"],
                ).order_by("start_time")

                if appointments.exists():
                    # Add appointments to availability
                    availability["appointments"] = [
                        {
                            "id": str(appointment.id),
                            "start_time": appointment.start_time.strftime("%H:%M"),
                            "end_time": appointment.end_time.strftime("%H:%M"),
                            "service_name": appointment.service.name,
                            "status": appointment.status,
                        }
                        for appointment in appointments
                    ]

                    # Calculate busy times
                    busy_slots = []
                    for appointment in appointments:
                        busy_slots.append(
                            {
                                "start": appointment.start_time.strftime("%H:%M"),
                                "end": appointment.end_time.strftime("%H:%M"),
                            }
                        )

                    availability["busy_slots"] = busy_slots
            except ImportError:
                # Bookingapp not available, skip
                pass

        return availability

    @staticmethod
    def get_employee_schedule(employee_id, start_date, end_date):
        """
        Get an employee's schedule for a date range
        Includes working hours, leaves, and appointments
        Args:
            employee_id: Employee ID
            start_date: Start date
            end_date: End date
        Returns:
            Dictionary with schedule information for each date
        """
        employee = Employee.objects.get(id=employee_id)

        # Initialize result
        schedule = {}

        # Calculate number of days in range
        delta = end_date - start_date

        # Get all working hours
        working_hours = EmployeeWorkingHours.objects.filter(employee_id=employee_id)
        working_hours_dict = {wh.weekday: wh for wh in working_hours}

        # Get all leaves in date range
        leaves = EmployeeLeave.objects.filter(
            employee_id=employee_id,
            status="approved",
            start_date__lte=end_date,
            end_date__gte=start_date,
        )

        # Get all appointments in date range if employee is a specialist
        appointments = []
        if employee.is_specialist:
            try:
                from apps.bookingapp.models import Appointment

                appointments = Appointment.objects.filter(
                    specialist=employee.specialist,
                    start_time__date__gte=start_date,
                    start_time__date__lte=end_date,
                    status__in=["scheduled", "confirmed", "in_progress"],
                ).order_by("start_time")
            except ImportError:
                # Bookingapp not available, skip
                pass

        # Generate schedule for each day in range
        for i in range(delta.days + 1):
            current_date = start_date + timedelta(days=i)

            # Get weekday (0=Sunday, 6=Saturday)
            weekday = current_date.weekday()
            # Convert from Python's weekday (0=Monday) to our schema (0=Sunday)
            if weekday == 6:  # If Python's Sunday (6)
                weekday = 0  # Set to our Sunday (0)
            else:
                weekday += 1  # Otherwise add 1

            # Initialize day's schedule
            day_schedule = {
                "date": current_date.strftime("%Y-%m-%d"),
                "weekday": weekday,
                "weekday_name": EmployeeWorkingHours.WEEKDAY_CHOICES[weekday][1],
                "is_leave": False,
                "is_day_off": False,
                "appointments": [],
            }

            # Check if on leave
            day_leaves = [
                leave
                for leave in leaves
                if leave.start_date <= current_date <= leave.end_date
            ]
            if day_leaves:
                day_schedule["is_leave"] = True
                day_schedule["leave"] = {
                    "id": str(day_leaves[0].id),
                    "leave_type": day_leaves[0].leave_type,
                    "leave_type_display": day_leaves[0].get_leave_type_display(),
                }

            # Add working hours if not on leave
            if not day_schedule["is_leave"] and weekday in working_hours_dict:
                wh = working_hours_dict[weekday]
                day_schedule["is_day_off"] = wh.is_day_off

                if not wh.is_day_off:
                    day_schedule["working_hours"] = {
                        "from_hour": wh.from_hour.strftime("%H:%M"),
                        "to_hour": wh.to_hour.strftime("%H:%M"),
                    }

                    # Add breaks if any
                    if wh.break_start and wh.break_end:
                        day_schedule["working_hours"]["break_start"] = (
                            wh.break_start.strftime("%H:%M")
                        )
                        day_schedule["working_hours"]["break_end"] = (
                            wh.break_end.strftime("%H:%M")
                        )

            # Add appointments for this day
            day_appointments = [
                apt for apt in appointments if apt.start_time.date() == current_date
            ]
            if day_appointments:
                day_schedule["appointments"] = [
                    {
                        "id": str(appointment.id),
                        "start_time": appointment.start_time.strftime("%H:%M"),
                        "end_time": appointment.end_time.strftime("%H:%M"),
                        "service_name": appointment.service.name,
                        "status": appointment.status,
                    }
                    for appointment in day_appointments
                ]

            # Add to schedule
            schedule[current_date.strftime("%Y-%m-%d")] = day_schedule

        return {
            "employee_id": str(employee_id),
            "employee_name": f"{employee.first_name} {employee.last_name}",
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "schedule": schedule,
        }

    @staticmethod
    def can_employee_work_at_time(employee_id, check_date, start_time, end_time):
        """
        Check if an employee can work at a specific time
        Takes into account working hours, breaks, leaves, and existing appointments
        Args:
            employee_id: Employee ID
            check_date: Date to check
            start_time: Start time (time object)
            end_time: End time (time object)
        Returns:
            Boolean
        """
        # Get availability for date
        availability = ScheduleService.get_employee_availability(
            employee_id, check_date
        )

        # If not available for any reason, return False
        if not availability["is_available"]:
            return False

        # Check if time is within working hours
        working_hours = availability["working_hours"]
        working_start = datetime.strptime(working_hours["from_hour"], "%H:%M").time()
        working_end = datetime.strptime(working_hours["to_hour"], "%H:%M").time()

        if start_time < working_start or end_time > working_end:
            return False

        # Check if time overlaps with break
        if "break_start" in working_hours and "break_end" in working_hours:
            break_start = datetime.strptime(
                working_hours["break_start"], "%H:%M"
            ).time()
            break_end = datetime.strptime(working_hours["break_end"], "%H:%M").time()

            # Check if the requested time period overlaps with break
            if not (end_time <= break_start or start_time >= break_end):
                return False

        # Check if time overlaps with existing appointments
        if "busy_slots" in availability:
            for slot in availability["busy_slots"]:
                slot_start = datetime.strptime(slot["start"], "%H:%M").time()
                slot_end = datetime.strptime(slot["end"], "%H:%M").time()

                # Check if the requested time period overlaps with busy slot
                if not (end_time <= slot_start or start_time >= slot_end):
                    return False

        # If passed all checks, employee can work at this time
        return True
