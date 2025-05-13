from datetime import time, timedelta

from django.db.models import Avg, Case, Count, IntegerField, Value, When
from django.db.models.functions import ExtractHour, ExtractMonth, ExtractWeekDay

from apps.bookingapp.models import Appointment
from apps.shopapp.models import Shop, ShopHours


class HoursOptimizer:
    @staticmethod
    def analyze_booking_patterns(shop_id, date_range=90):
        """
        Analyze booking patterns to suggest optimal hours

        Args:
            shop_id: ID of the shop
            date_range: Number of days to look back for booking data

        Returns:
            Dict with analysis results and recommendations
        """
        from django.utils import timezone

        start_date = timezone.now() - timedelta(days=date_range)

        shop = Shop.objects.get(id=shop_id)

        # Get all appointments in the date range
        appointments = Appointment.objects.filter(
            shop=shop,
            start_time__gte=start_date,
            status__in=["completed", "no_show"],  # Include both completed and no-shows
        )

        if not appointments.exists():
            return {
                "status": "insufficient_data",
                "message": "Not enough booking data for analysis",
                "recommendations": [],
            }

        # Analyze by day of week
        day_of_week_distribution = (
            appointments.annotate(weekday=ExtractWeekDay("start_time"))
            .values("weekday")
            .annotate(
                count=Count("id"),
                completion_rate=Avg(
                    # 1 for completed, 0 for no-show
                    Case(
                        When(status="completed", then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
            )
            .order_by("weekday")
        )

        # Convert Django's weekday (1=Sunday) to our schema (0=Sunday)
        day_distribution = {}
        for day in day_of_week_distribution:
            # Django's weekday is 1-7 (Sunday=1)
            django_weekday = day["weekday"]
            # Convert to our 0-6 format (Sunday=0)
            our_weekday = django_weekday - 1 if django_weekday > 0 else 6
            day_distribution[our_weekday] = {
                "count": day["count"],
                "completion_rate": day["completion_rate"],
            }

        # Analyze by hour of day
        hour_distribution = (
            appointments.annotate(hour=ExtractHour("start_time"))
            .values("hour")
            .annotate(
                count=Count("id"),
                completion_rate=Avg(
                    Case(
                        When(status="completed", then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
            )
            .order_by("hour")
        )

        # Get current hours
        current_hours = ShopHours.objects.filter(shop=shop)

        # Calculate recommendations
        recommendations = []

        # Look for days with low booking volume
        for weekday in range(7):
            day_data = day_distribution.get(weekday, {"count": 0, "completion_rate": 0})
            current_day_hours = current_hours.filter(weekday=weekday).first()

            if not current_day_hours:
                continue

            # If day is currently open but has very few bookings
            if not current_day_hours.is_closed and day_data["count"] < 3:
                recommendations.append(
                    {
                        "type": "close_day",
                        "weekday": weekday,
                        "reasoning": f"Very few bookings on this day ({day_data['count']}). Consider closing.",
                    }
                )

            # If day is currently closed but has booking requests
            elif current_day_hours.is_closed and day_data["count"] > 0:
                recommendations.append(
                    {
                        "type": "open_day",
                        "weekday": weekday,
                        "reasoning": f"Received {day_data['count']} booking requests on this closed day. Consider opening.",
                    }
                )

        # Look for optimal operating hours
        if hour_distribution:
            # Find earliest and latest hours with significant bookings
            hour_data = {item["hour"]: item["count"] for item in hour_distribution}
            sorted_hours = sorted(hour_data.items(), key=lambda x: x[0])

            # Get average bookings per hour
            total_bookings = sum(hour_data.values())
            avg_bookings = total_bookings / len(hour_data)
            threshold = max(1, avg_bookings * 0.2)  # At least 20% of average or 1

            # Find earliest hour with significant bookings
            earliest_significant_hour = None
            for hour, count in sorted_hours:
                if count >= threshold:
                    earliest_significant_hour = hour
                    break

            # Find latest hour with significant bookings
            latest_significant_hour = None
            for hour, count in reversed(sorted_hours):
                if count >= threshold:
                    latest_significant_hour = hour
                    break

            # Suggest adjustments if needed
            if earliest_significant_hour is not None and latest_significant_hour is not None:
                for day_hour in current_hours.filter(is_closed=False):
                    current_open_hour = day_hour.from_hour.hour
                    current_close_hour = day_hour.to_hour.hour

                    # Suggest opening later
                    if current_open_hour + 1 < earliest_significant_hour:
                        recommendations.append(
                            {
                                "type": "adjust_opening",
                                "weekday": day_hour.weekday,
                                "current_hour": current_open_hour,
                                "suggested_hour": earliest_significant_hour,
                                "reasoning": f"Few bookings before {earliest_significant_hour}:00. Consider opening later.",
                            }
                        )

                    # Suggest closing earlier
                    if current_close_hour > latest_significant_hour + 2:
                        recommendations.append(
                            {
                                "type": "adjust_closing",
                                "weekday": day_hour.weekday,
                                "current_hour": current_close_hour,
                                "suggested_hour": latest_significant_hour + 1,
                                "reasoning": f"Few bookings after {latest_significant_hour}:00. Consider closing earlier.",
                            }
                        )

        return {
            "status": "success",
            "data": {
                "day_distribution": day_distribution,
                "hour_distribution": {item["hour"]: item["count"] for item in hour_distribution},
                "current_hours": {
                    hour.weekday: {
                        "is_closed": hour.is_closed,
                        "from_hour": (
                            hour.from_hour.strftime("%H:%M") if not hour.is_closed else None
                        ),
                        "to_hour": (hour.to_hour.strftime("%H:%M") if not hour.is_closed else None),
                    }
                    for hour in current_hours
                },
            },
            "recommendations": recommendations,
        }

    @staticmethod
    def apply_recommendations(shop_id, recommendations):
        """
        Apply hours optimization recommendations

        Args:
            shop_id: ID of the shop
            recommendations: List of recommendation objects to apply

        Returns:
            Dict with status and updated hours
        """
        shop = Shop.objects.get(id=shop_id)

        # Track which days were updated
        updated_days = set()

        for recommendation in recommendations:
            recommendation_type = recommendation.get("type")
            weekday = recommendation.get("weekday")

            if weekday is None or not (0 <= weekday <= 6):
                continue

            try:
                shop_hour = ShopHours.objects.get(shop=shop, weekday=weekday)

                if recommendation_type == "close_day":
                    shop_hour.is_closed = True
                    shop_hour.save()
                    updated_days.add(weekday)

                elif recommendation_type == "open_day":
                    shop_hour.is_closed = False
                    shop_hour.from_hour = time(9, 0)  # Default 9 AM
                    shop_hour.to_hour = time(18, 0)  # Default 6 PM
                    shop_hour.save()
                    updated_days.add(weekday)

                elif recommendation_type == "adjust_opening":
                    suggested_hour = recommendation.get("suggested_hour")
                    if suggested_hour is not None and 0 <= suggested_hour <= 23:
                        shop_hour.from_hour = time(suggested_hour, 0)
                        shop_hour.save()
                        updated_days.add(weekday)

                elif recommendation_type == "adjust_closing":
                    suggested_hour = recommendation.get("suggested_hour")
                    if suggested_hour is not None and 0 <= suggested_hour <= 23:
                        shop_hour.to_hour = time(suggested_hour, 0)
                        shop_hour.save()
                        updated_days.add(weekday)

            except ShopHours.DoesNotExist:
                continue

        # Get updated hours
        updated_hours = ShopHours.objects.filter(shop=shop)

        return {
            "status": "success",
            "message": f"Updated hours for {len(updated_days)} days",
            "updated_days": list(updated_days),
            "hours": {
                hour.weekday: {
                    "is_closed": hour.is_closed,
                    "from_hour": (hour.from_hour.strftime("%H:%M") if not hour.is_closed else None),
                    "to_hour": (hour.to_hour.strftime("%H:%M") if not hour.is_closed else None),
                }
                for hour in updated_hours
            },
        }

    @staticmethod
    def suggest_seasonal_hours(shop_id):
        """
        Suggest seasonal adjustments to shop hours based on historical data

        Args:
            shop_id: ID of the shop

        Returns:
            Dict with seasonal recommendations
        """
        from dateutil.relativedelta import relativedelta
        from django.utils import timezone

        shop = Shop.objects.get(id=shop_id)

        # Get one year of data for seasonal analysis
        start_date = timezone.now() - relativedelta(years=1)

        # Get all appointments in the date range
        appointments = Appointment.objects.filter(shop=shop, start_time__gte=start_date)

        if not appointments.exists():
            return {
                "status": "insufficient_data",
                "message": "Not enough booking data for seasonal analysis",
                "recommendations": [],
            }

        # Analyze by month
        month_distribution = (
            appointments.annotate(month=ExtractMonth("start_time"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        month_data = {item["month"]: item["count"] for item in month_distribution}

        # Calculate average bookings per month
        total_bookings = sum(month_data.values())
        avg_bookings = total_bookings / len(month_data) if month_data else 0

        # Identify high and low seasons
        high_season_months = [
            month for month, count in month_data.items() if count > avg_bookings * 1.2
        ]
        low_season_months = [
            month for month, count in month_data.items() if count < avg_bookings * 0.8
        ]

        # Generate recommendations
        recommendations = []

        # Suggest extended hours for high season
        if high_season_months:
            month_names = {
                1: "January",
                2: "February",
                3: "March",
                4: "April",
                5: "May",
                6: "June",
                7: "July",
                8: "August",
                9: "September",
                10: "October",
                11: "November",
                12: "December",
            }

            high_season_names = [month_names[month] for month in high_season_months]

            recommendations.append(
                {
                    "type": "extend_hours",
                    "season": "high",
                    "months": high_season_months,
                    "month_names": high_season_names,
                    "reasoning": "Booking volume is significantly higher during these months. Consider extending hours or adding more staff.",
                }
            )

        # Suggest reduced hours for low season
        if low_season_months:
            month_names = {
                1: "January",
                2: "February",
                3: "March",
                4: "April",
                5: "May",
                6: "June",
                7: "July",
                8: "August",
                9: "September",
                10: "October",
                11: "November",
                12: "December",
            }

            low_season_names = [month_names[month] for month in low_season_months]

            recommendations.append(
                {
                    "type": "reduce_hours",
                    "season": "low",
                    "months": low_season_months,
                    "month_names": low_season_names,
                    "reasoning": "Booking volume is significantly lower during these months. Consider reducing hours to optimize staff resources.",
                }
            )

        return {
            "status": "success",
            "data": {
                "month_distribution": month_data,
                "average_bookings_per_month": avg_bookings,
            },
            "recommendations": recommendations,
        }
