from datetime import datetime, timedelta

from django.db.models import Count, ExpressionWrapper, F, Sum, fields
from django.db.models.functions import ExtractHour, TruncDate

from apps.employeeapp.models import Employee


class WorkloadOptimizer:
    """
    Advanced workload optimization and analysis for employees
    Uses historical data to analyze workload distribution, identify patterns,
    and optimize future scheduling
    """

    @staticmethod
    def analyze_employee_workload(employee_id, start_date, end_date):
        """
        Analyze an employee's workload for a date range
        Args:
            employee_id: Employee ID
            start_date: Start date
            end_date: End date
        Returns:
            Dictionary with workload analysis
        """
        employee = Employee.objects.get(id=employee_id)

        # Base result structure
        result = {
            "employee_id": str(employee_id),
            "employee_name": f"{employee.first_name} {employee.last_name}",
            "period": {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "days": (end_date - start_date).days + 1,
            },
            "workload": {
                "total_appointments": 0,
                "hours_worked": 0,
                "daily_average": 0,
                "busiest_day": None,
                "slowest_day": None,
                "peak_hours": [],
                "distribution": {},
            },
            "comparison": {
                "shop_average": 0,
                "relative_workload": 0,  # 1.0 means average, 2.0 means twice the average
            },
            "recommendations": [],
        }

        # Check if employee is a specialist (only specialists have appointments)
        if not employee.is_specialist:
            return result

        # Get appointment data from booking app
        try:
            from django.db.models.functions import ExtractWeekDay

            from apps.bookingapp.models import Appointment

            # Get appointments in date range
            appointments = Appointment.objects.filter(
                specialist=employee.specialist,
                start_time__date__gte=start_date,
                start_time__date__lte=end_date,
                status__in=["completed", "in_progress", "scheduled", "confirmed"],
            )

            # Skip further analysis if no appointments
            if not appointments.exists():
                return result

            # Calculate total appointments
            total_appointments = appointments.count()
            result["workload"]["total_appointments"] = total_appointments

            # Calculate hours worked
            # Using ExpressionWrapper to get duration in hours
            duration_expr = ExpressionWrapper(
                F("end_time") - F("start_time"), output_field=fields.DurationField()
            )

            appointments_with_duration = appointments.annotate(duration=duration_expr)

            total_duration = appointments_with_duration.aggregate(total=Sum("duration"))["total"]

            if total_duration:
                hours_worked = total_duration.total_seconds() / 3600
                result["workload"]["hours_worked"] = round(hours_worked, 2)
                result["workload"]["daily_average"] = round(
                    hours_worked / ((end_date - start_date).days + 1), 2
                )

            # Get busiest day
            daily_appointments = (
                appointments.annotate(day=TruncDate("start_time"))
                .values("day")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            if daily_appointments.exists():
                busiest_day = daily_appointments.first()
                result["workload"]["busiest_day"] = {
                    "date": busiest_day["day"].strftime("%Y-%m-%d"),
                    "appointments": busiest_day["count"],
                }

                slowest_day = daily_appointments.last()
                result["workload"]["slowest_day"] = {
                    "date": slowest_day["day"].strftime("%Y-%m-%d"),
                    "appointments": slowest_day["count"],
                }

                # Daily distribution
                result["workload"]["distribution"]["daily"] = [
                    {
                        "date": item["day"].strftime("%Y-%m-%d"),
                        "appointments": item["count"],
                    }
                    for item in daily_appointments
                ]

            # Get peak hours
            hourly_appointments = (
                appointments.annotate(hour=ExtractHour("start_time"))
                .values("hour")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            if hourly_appointments.exists():
                # Take top 3 busiest hours
                peak_hours = hourly_appointments[:3]
                result["workload"]["peak_hours"] = [
                    {
                        "hour": item["hour"],
                        "hour_display": f"{item['hour']}:00",
                        "appointments": item["count"],
                    }
                    for item in peak_hours
                ]

                # Hourly distribution
                result["workload"]["distribution"]["hourly"] = [
                    {
                        "hour": item["hour"],
                        "hour_display": f"{item['hour']}:00",
                        "appointments": item["count"],
                    }
                    for item in hourly_appointments
                ]

            # Get weekday distribution
            weekday_appointments = (
                appointments.annotate(weekday=ExtractWeekDay("start_time"))
                .values("weekday")
                .annotate(count=Count("id"))
                .order_by("weekday")
            )

            if weekday_appointments.exists():
                # Map Django's weekday to our format (1-7 to 0-6)
                weekday_map = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 0}
                weekday_names = dict(
                    [
                        (k, v)
                        for k, (v, _) in enumerate(Employee.EmployeeWorkingHours.WEEKDAY_CHOICES)
                    ]
                )

                result["workload"]["distribution"]["weekday"] = [
                    {
                        "weekday": weekday_map[item["weekday"]],
                        "weekday_name": weekday_names[weekday_map[item["weekday"]]],
                        "appointments": item["count"],
                    }
                    for item in weekday_appointments
                ]

            # Compare with shop average
            # Get all appointments in the shop
            shop_appointments = Appointment.objects.filter(
                specialist__employee__shop=employee.shop,
                start_time__date__gte=start_date,
                start_time__date__lte=end_date,
                status__in=["completed", "in_progress", "scheduled", "confirmed"],
            )

            # Get count of specialists in shop
            specialist_count = Employee.objects.filter(
                shop=employee.shop, is_active=True, specialist__isnull=False
            ).count()

            if specialist_count > 0:
                shop_total = shop_appointments.count()
                shop_average = shop_total / specialist_count
                result["comparison"]["shop_average"] = round(shop_average, 2)

                if shop_average > 0:
                    relative_workload = total_appointments / shop_average
                    result["comparison"]["relative_workload"] = round(relative_workload, 2)

            # Generate workload optimization recommendations
            WorkloadOptimizer._generate_recommendations(result, employee)

            return result

        except ImportError:
            # Bookingapp not available, return base result
            return result

    @staticmethod
    def _generate_recommendations(result, employee):
        """
        Generate workload optimization recommendations based on analysis
        Args:
            result: Workload analysis results
            employee: Employee object
        """
        recommendations = []

        # If overloaded (>20% above average)
        if result["comparison"]["relative_workload"] > 1.2:
            recommendations.append(
                {
                    "type": "high_workload",
                    "message": f"Workload is {round((result['comparison']['relative_workload'] - 1) * 100)}% above shop average. Consider reducing appointments or redistributing work.",
                }
            )

        # If underutilized (>20% below average)
        elif (
            result["comparison"]["relative_workload"] < 0.8
            and result["comparison"]["relative_workload"] > 0
        ):
            recommendations.append(
                {
                    "type": "low_workload",
                    "message": f"Workload is {round((1 - result['comparison']['relative_workload']) * 100)}% below shop average. Consider increasing appointments or expanding services offered.",
                }
            )

        # Check for imbalanced weekday distribution
        if "weekday" in result["workload"]["distribution"]:
            weekday_data = result["workload"]["distribution"]["weekday"]
            if len(weekday_data) >= 2:
                max_day = max(weekday_data, key=lambda x: x["appointments"])
                min_day = min(weekday_data, key=lambda x: x["appointments"])

                if max_day["appointments"] > 0 and min_day["appointments"] >= 0:
                    ratio = max_day["appointments"] / (min_day["appointments"] or 1)

                    if ratio > 3:  # 3x difference between busiest and slowest day
                        recommendations.append(
                            {
                                "type": "weekday_imbalance",
                                "message": f"Workload is heavily concentrated on {max_day['weekday_name']}s. Consider redistributing appointments more evenly throughout the week.",
                            }
                        )

        # Check for concentrated peak hours
        if result["workload"]["peak_hours"]:
            peak_appointments = sum(
                hour["appointments"] for hour in result["workload"]["peak_hours"]
            )

            if peak_appointments > 0 and result["workload"]["total_appointments"] > 0:
                peak_percentage = peak_appointments / result["workload"]["total_appointments"]

                if peak_percentage > 0.6:  # 60% of work in peak hours
                    peak_hours_str = ", ".join(
                        [hour["hour_display"] for hour in result["workload"]["peak_hours"]]
                    )
                    recommendations.append(
                        {
                            "type": "concentrated_hours",
                            "message": f"{round(peak_percentage * 100)}% of appointments are concentrated during {peak_hours_str}. Consider spreading appointments across more hours to reduce peak pressure.",
                        }
                    )

        # Add recommendations to result
        result["recommendations"] = recommendations

    @staticmethod
    def get_optimal_assignment(shop_id, service_id, date, time_slot):
        """
        Get the optimal specialist assignment for a service at a specific time
        Uses workload analysis to balance assignments across specialists
        Args:
            shop_id: Shop ID
            service_id: Service ID
            date: Date
            time_slot: Time slot (start_time, end_time)
        Returns:
            Recommended specialist ID or None
        """
        try:
            from apps.employeeapp.services.schedule_service import ScheduleService
            from apps.serviceapp.models import Service
            from apps.specialistsapp.models import SpecialistService

            # Get service
            # unused_unused_service = Service.objects.get(id=service_id)
            # Get specialists who can provide this service
            specialist_services = SpecialistService.objects.filter(
                service_id=service_id,
                specialist__employee__shop_id=shop_id,
                specialist__employee__is_active=True,
            )

            if not specialist_services.exists():
                return None

            # Filter specialists who are available at this time
            available_specialists = []
            for specialist_service in specialist_services:
                specialist = specialist_service.specialist
                employee = specialist.employee

                # Convert string times to time objects if needed
                start_time = (
                    time_slot[0]
                    if isinstance(time_slot[0], datetime.time)
                    else datetime.strptime(time_slot[0], "%H:%M").time()
                )
                end_time = (
                    time_slot[1]
                    if isinstance(time_slot[1], datetime.time)
                    else datetime.strptime(time_slot[1], "%H:%M").time()
                )

                # Check if specialist is available
                if ScheduleService.can_employee_work_at_time(
                    employee.id, date, start_time, end_time
                ):
                    available_specialists.append(specialist)

            if not available_specialists:
                return None

            # If only one specialist available, return that one
            if len(available_specialists) == 1:
                return available_specialists[0].id

            # Calculate workload for all available specialists
            start_of_week = date - timedelta(days=date.weekday())
            end_of_week = start_of_week + timedelta(days=6)

            # Get all appointments for this week
            from apps.bookingapp.models import Appointment

            # Prepare workload data
            specialist_workloads = []

            for specialist in available_specialists:
                # Get specialist's appointments for this week
                appointments = Appointment.objects.filter(
                    specialist=specialist,
                    start_time__date__gte=start_of_week,
                    start_time__date__lte=end_of_week,
                    status__in=["scheduled", "confirmed", "in_progress", "completed"],
                )

                # Calculate total appointment duration
                total_minutes = 0
                for appointment in appointments:
                    duration = (appointment.end_time - appointment.start_time).total_seconds() / 60
                    total_minutes += duration

                # Check if specialist is primary for this service
                is_primary = SpecialistService.objects.filter(
                    specialist=specialist, service_id=service_id, is_primary=True
                ).exists()

                # Store workload data
                specialist_workloads.append(
                    {
                        "specialist": specialist,
                        "workload_minutes": total_minutes,
                        "appointment_count": appointments.count(),
                        "is_primary": is_primary,
                    }
                )

            # Sort by workload (ascending) and primary status (primary specialists first)
            sorted_specialists = sorted(
                specialist_workloads,
                key=lambda x: (not x["is_primary"], x["workload_minutes"]),
            )

            # Return specialist with lowest workload
            return sorted_specialists[0]["specialist"].id

        except ImportError:
            # Required apps not available, return None
            return None
