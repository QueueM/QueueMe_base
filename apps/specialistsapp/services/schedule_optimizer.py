from datetime import datetime, time, timedelta

from django.db.models import Avg, F, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.bookingapp.models import Appointment
from apps.shopapp.models import ShopHours
from apps.specialistsapp.models import Specialist, SpecialistWorkingHours


class ScheduleOptimizer:
    """
    Advanced service for optimizing specialist schedules based on
    historical booking data and demand patterns.
    """

    def analyze_booking_patterns(self, specialist_id, days_back=30):
        """
        Analyze booking patterns for a specialist to identify peak hours.

        Args:
            specialist_id: UUID of the specialist
            days_back: Number of days of historical data to analyze

        Returns:
            Dictionary with analysis results
        """
        specialist = Specialist.objects.get(id=specialist_id)

        # Get date range for analysis
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days_back)

        # Get all completed appointments in date range
        appointments = Appointment.objects.filter(
            specialist=specialist,
            start_time__gte=start_date,
            start_time__lte=end_date,
            status__in=["completed"],
        )

        # Analyze by day of week
        day_of_week_data = {}
        for day in range(7):  # 0=Sunday, 6=Saturday
            day_appointments = appointments.filter(
                start_time__week_day=day + 1
            )  # Django uses 1-7 (Sunday=1)
            day_of_week_data[day] = {
                "count": day_appointments.count(),
                "avg_duration": day_appointments.aggregate(
                    Avg(F("end_time") - F("start_time"))
                ).get("end_time__avg__avg")
                or 0,
            }

        # Analyze by hour of day
        hour_of_day_data = {}
        for hour in range(24):
            hour_appointments = appointments.filter(start_time__hour=hour)
            hour_of_day_data[hour] = {"count": hour_appointments.count()}

        # Identify peak days and hours
        peak_day = (
            max(day_of_week_data.items(), key=lambda x: x[1]["count"])[0]
            if day_of_week_data
            else None
        )
        peak_hour = (
            max(hour_of_day_data.items(), key=lambda x: x[1]["count"])[0]
            if hour_of_day_data
            else None
        )

        # Calculate utilization rate
        total_working_hours = self._calculate_specialist_working_hours(specialist)
        total_appointment_hours = appointments.aggregate(
            total=Sum(F("end_time") - F("start_time"))
        ).get("total") or timedelta(0)

        utilization_rate = (
            (total_appointment_hours.total_seconds() / 3600)
            / (total_working_hours * days_back)
            if total_working_hours > 0
            else 0
        )

        # Group data by service
        service_data = {}
        for appointment in appointments:
            service_id = str(appointment.service.id)
            if service_id not in service_data:
                service_data[service_id] = {
                    "name": appointment.service.name,
                    "count": 0,
                    "total_duration": timedelta(0),
                }

            service_data[service_id]["count"] += 1
            service_data[service_id]["total_duration"] += (
                appointment.end_time - appointment.start_time
            )

        # Calculate average duration for each service
        for service_id, data in service_data.items():
            if data["count"] > 0:
                data["avg_duration"] = data["total_duration"].total_seconds() / (
                    60 * data["count"]
                )
            else:
                data["avg_duration"] = 0

            # Remove timedelta object for serialization
            data.pop("total_duration")

        # Return analysis results
        return {
            "total_appointments": appointments.count(),
            "utilization_rate": utilization_rate,
            "peak_day": peak_day,
            "peak_hour": peak_hour,
            "day_of_week_data": day_of_week_data,
            "hour_of_day_data": hour_of_day_data,
            "service_data": service_data,
        }

    def suggest_optimal_schedule(self, specialist_id):
        """
        Suggest an optimal working schedule for a specialist based on
        booking patterns and shop hours.

        Args:
            specialist_id: UUID of the specialist

        Returns:
            Dictionary with suggested schedule
        """
        specialist = Specialist.objects.get(id=specialist_id)
        shop = specialist.employee.shop

        # Get booking pattern analysis
        analysis = self.analyze_booking_patterns(specialist_id)

        # Get shop hours
        shop_hours_dict = {}
        for day in range(7):  # 0=Sunday, 6=Saturday
            try:
                shop_hour = ShopHours.objects.get(shop=shop, weekday=day)
                if not shop_hour.is_closed:
                    shop_hours_dict[day] = {
                        "from_hour": shop_hour.from_hour,
                        "to_hour": shop_hour.to_hour,
                    }
            except ShopHours.DoesNotExist:
                pass

        # Get current specialist working hours
        current_hours = {}
        for working_hour in SpecialistWorkingHours.objects.filter(
            specialist=specialist
        ):
            current_hours[working_hour.weekday] = {
                "from_hour": working_hour.from_hour,
                "to_hour": working_hour.to_hour,
                "is_off": working_hour.is_off,
            }

        # Generate suggested schedule based on booking patterns and shop hours
        suggested_hours = {}

        for day in range(7):
            # Skip if shop is closed on this day
            if day not in shop_hours_dict:
                suggested_hours[day] = {
                    "is_off": True,
                    "reason": _("Shop is closed on this day"),
                }
                continue

            # Get day's booking data
            day_data = analysis["day_of_week_data"].get(day, {"count": 0})

            # Determine if specialist should work on this day
            if day_data["count"] < 2:  # Very low demand
                suggested_hours[day] = {
                    "is_off": True,
                    "reason": _("Low demand on this day"),
                }
                continue

            # Get shop hours for this day
            shop_from_hour = shop_hours_dict[day]["from_hour"]
            shop_to_hour = shop_hours_dict[day]["to_hour"]

            # Get peak hours from analysis
            peak_hours = [
                hour
                for hour, data in analysis["hour_of_day_data"].items()
                if data["count"] > 0
            ]

            # Determine optimal working hours
            if peak_hours:
                # Ensure working hours cover peak hours
                min_peak_hour = min(peak_hours)
                max_peak_hour = max(peak_hours) + 1  # Add 1 to include the full hour

                # Convert to time objects
                from_hour = max(
                    shop_from_hour,
                    time(
                        hour=max(min_peak_hour - 1, 0), minute=0
                    ),  # Start 1 hour before peak
                )
                to_hour = min(
                    shop_to_hour,
                    time(
                        hour=min(max_peak_hour + 1, 23), minute=59
                    ),  # End 1 hour after peak
                )

                suggested_hours[day] = {
                    "is_off": False,
                    "from_hour": from_hour,
                    "to_hour": to_hour,
                    "reason": _("Based on peak hours"),
                }
            else:
                # No clear peak hours, use shop hours
                suggested_hours[day] = {
                    "is_off": False,
                    "from_hour": shop_from_hour,
                    "to_hour": shop_to_hour,
                    "reason": _("No clear peak hours, using shop hours"),
                }

        # Compare with current hours and generate recommendations
        recommendations = []

        for day in range(7):
            if day not in suggested_hours:
                continue

            suggested = suggested_hours[day]
            current = current_hours.get(day)

            if not current:
                # No current hours set for this day
                if not suggested["is_off"]:
                    recommendations.append(
                        {
                            "day": day,
                            "action": "add",
                            "from_hour": (
                                suggested["from_hour"].strftime("%H:%M")
                                if hasattr(suggested["from_hour"], "strftime")
                                else None
                            ),
                            "to_hour": (
                                suggested["to_hour"].strftime("%H:%M")
                                if hasattr(suggested["to_hour"], "strftime")
                                else None
                            ),
                            "reason": suggested["reason"],
                        }
                    )
            elif current["is_off"] and not suggested["is_off"]:
                # Currently off but should be working
                recommendations.append(
                    {
                        "day": day,
                        "action": "add",
                        "from_hour": (
                            suggested["from_hour"].strftime("%H:%M")
                            if hasattr(suggested["from_hour"], "strftime")
                            else None
                        ),
                        "to_hour": (
                            suggested["to_hour"].strftime("%H:%M")
                            if hasattr(suggested["to_hour"], "strftime")
                            else None
                        ),
                        "reason": suggested["reason"],
                    }
                )
            elif not current["is_off"] and suggested["is_off"]:
                # Currently working but should be off
                recommendations.append(
                    {"day": day, "action": "remove", "reason": suggested["reason"]}
                )
            elif not current["is_off"] and not suggested["is_off"]:
                # Check if hours should be adjusted
                current_from = current["from_hour"]
                current_to = current["to_hour"]
                suggested_from = suggested["from_hour"]
                suggested_to = suggested["to_hour"]

                if current_from != suggested_from or current_to != suggested_to:
                    recommendations.append(
                        {
                            "day": day,
                            "action": "modify",
                            "from_hour": (
                                suggested_from.strftime("%H:%M")
                                if hasattr(suggested_from, "strftime")
                                else None
                            ),
                            "to_hour": (
                                suggested_to.strftime("%H:%M")
                                if hasattr(suggested_to, "strftime")
                                else None
                            ),
                            "current_from_hour": (
                                current_from.strftime("%H:%M")
                                if hasattr(current_from, "strftime")
                                else None
                            ),
                            "current_to_hour": (
                                current_to.strftime("%H:%M")
                                if hasattr(current_to, "strftime")
                                else None
                            ),
                            "reason": suggested["reason"],
                        }
                    )

        return {
            "specialist_id": str(specialist.id),
            "specialist_name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
            "analysis": analysis,
            "current_hours": current_hours,
            "suggested_hours": suggested_hours,
            "recommendations": recommendations,
        }

    def apply_schedule_recommendations(self, specialist_id, recommendations):
        """
        Apply the recommended schedule changes to a specialist.

        Args:
            specialist_id: UUID of the specialist
            recommendations: List of recommendations to apply

        Returns:
            Boolean indicating success
        """
        specialist = Specialist.objects.get(id=specialist_id)

        for recommendation in recommendations:
            day = recommendation.get("day")
            action = recommendation.get("action")

            if action == "add" or action == "modify":
                # Parse time strings
                from_hour_str = recommendation.get("from_hour")
                to_hour_str = recommendation.get("to_hour")

                if not from_hour_str or not to_hour_str:
                    continue

                from_hour = datetime.strptime(from_hour_str, "%H:%M").time()
                to_hour = datetime.strptime(to_hour_str, "%H:%M").time()

                # Update or create working hours
                working_hour, created = SpecialistWorkingHours.objects.update_or_create(
                    specialist=specialist,
                    weekday=day,
                    defaults={
                        "from_hour": from_hour,
                        "to_hour": to_hour,
                        "is_off": False,
                    },
                )
            elif action == "remove":
                # Mark day as off
                working_hour, created = SpecialistWorkingHours.objects.update_or_create(
                    specialist=specialist, weekday=day, defaults={"is_off": True}
                )

        return True

    def optimize_specialist_workload(self, shop_id):
        """
        Optimize workload distribution across specialists in a shop.

        Args:
            shop_id: UUID of the shop

        Returns:
            Dictionary with optimization suggestions
        """
        from apps.shopapp.models import Shop

        shop = Shop.objects.get(id=shop_id)

        # Get all active specialists in shop
        specialists = Specialist.objects.filter(
            employee__shop=shop, employee__is_active=True
        )

        if not specialists.exists():
            return {
                "shop_id": str(shop_id),
                "message": _("No active specialists found in this shop"),
            }

        # Get current workload for each specialist
        workload_data = {}

        for specialist in specialists:
            # Get upcoming appointments
            upcoming_appointments = Appointment.objects.filter(
                specialist=specialist,
                start_time__gte=timezone.now(),
                status__in=["scheduled", "confirmed"],
            )

            # Calculate total hours booked
            total_hours = 0
            for appointment in upcoming_appointments:
                duration = (
                    appointment.end_time - appointment.start_time
                ).total_seconds() / 3600
                total_hours += duration

            # Calculate available hours based on working schedule
            available_hours = self._calculate_specialist_available_hours(specialist)

            # Calculate utilization percentage
            utilization = (
                (total_hours / available_hours) * 100 if available_hours > 0 else 0
            )

            workload_data[str(specialist.id)] = {
                "name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
                "upcoming_appointments": upcoming_appointments.count(),
                "total_booked_hours": total_hours,
                "available_hours": available_hours,
                "utilization_percentage": utilization,
            }

        # Identify overloaded and underloaded specialists
        avg_utilization = sum(
            data["utilization_percentage"] for data in workload_data.values()
        ) / len(workload_data)

        overloaded = {}
        underloaded = {}

        for specialist_id, data in workload_data.items():
            # Overloaded if utilization is >30% above average
            if data["utilization_percentage"] > avg_utilization * 1.3:
                overloaded[specialist_id] = data

            # Underloaded if utilization is <30% below average
            if data["utilization_percentage"] < avg_utilization * 0.7:
                underloaded[specialist_id] = data

        # Generate optimization suggestions
        suggestions = []

        # If we have both overloaded and underloaded specialists, suggest redistributing
        if overloaded and underloaded:
            for over_id, over_data in overloaded.items():
                over_specialist = Specialist.objects.get(id=over_id)

                # Get services provided by overloaded specialist
                over_services = over_specialist.specialist_services.all()

                for under_id, under_data in underloaded.items():
                    under_specialist = Specialist.objects.get(id=under_id)

                    # Get services provided by underloaded specialist
                    under_services = under_specialist.specialist_services.all()

                    # Find common services between the two specialists
                    common_services = [
                        s1
                        for s1 in over_services
                        if any(s2.service_id == s1.service_id for s2 in under_services)
                    ]

                    if common_services:
                        # Suggest redistributing appointments for common services
                        for service in common_services:
                            # Find upcoming appointments for overloaded specialist with this service
                            service_appointments = Appointment.objects.filter(
                                specialist=over_specialist,
                                service=service.service,
                                start_time__gte=timezone.now(),
                                status__in=["scheduled", "confirmed"],
                            )

                            for appointment in service_appointments[
                                :2
                            ]:  # Limit to a few suggestions
                                suggestions.append(
                                    {
                                        "type": "redistribute_appointment",
                                        "appointment_id": str(appointment.id),
                                        "service_id": str(service.service.id),
                                        "service_name": service.service.name,
                                        "from_specialist_id": str(over_specialist.id),
                                        "from_specialist_name": over_data["name"],
                                        "to_specialist_id": str(under_specialist.id),
                                        "to_specialist_name": under_data["name"],
                                        "appointment_time": appointment.start_time.strftime(
                                            "%Y-%m-%d %H:%M"
                                        ),
                                        "reason": _(
                                            "Balance workload between specialists"
                                        ),
                                    }
                                )

        return {
            "shop_id": str(shop_id),
            "avg_utilization": avg_utilization,
            "workload_data": workload_data,
            "overloaded_specialists": list(overloaded.keys()),
            "underloaded_specialists": list(underloaded.keys()),
            "suggestions": suggestions,
        }

    def _calculate_specialist_working_hours(self, specialist):
        """Calculate total weekly working hours for a specialist"""
        total_hours = 0

        for working_hour in SpecialistWorkingHours.objects.filter(
            specialist=specialist, is_off=False
        ):
            from_hour = working_hour.from_hour
            to_hour = working_hour.to_hour

            # Calculate hours
            from_minutes = from_hour.hour * 60 + from_hour.minute
            to_minutes = to_hour.hour * 60 + to_hour.minute

            hours = (to_minutes - from_minutes) / 60
            total_hours += hours

        return total_hours

    def _calculate_specialist_available_hours(self, specialist):
        """
        Calculate available hours for a specialist for the next 7 days
        based on working schedule
        """
        total_hours = 0
        today = timezone.now().date()

        # Check next 7 days
        for i in range(7):
            check_date = today + timedelta(days=i)
            weekday = check_date.weekday()

            # Convert to our weekday format (0=Sunday)
            if weekday == 6:  # If it's Sunday in Python's format
                weekday = 0
            else:
                weekday += 1

            # Get working hours for this day
            try:
                working_hour = SpecialistWorkingHours.objects.get(
                    specialist=specialist, weekday=weekday
                )

                if not working_hour.is_off:
                    from_hour = working_hour.from_hour
                    to_hour = working_hour.to_hour

                    # Calculate hours
                    from_minutes = from_hour.hour * 60 + from_hour.minute
                    to_minutes = to_hour.hour * 60 + to_hour.minute

                    hours = (to_minutes - from_minutes) / 60
                    total_hours += hours
            except SpecialistWorkingHours.DoesNotExist:
                pass

        return total_hours
