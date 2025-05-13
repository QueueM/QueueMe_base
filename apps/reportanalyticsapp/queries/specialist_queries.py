# apps/reportanalyticsapp/queries/specialist_queries.py

import logging

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce, ExtractDay, ExtractHour, TruncDate

from apps.bookingapp.models import Appointment
from apps.payment.models import Transaction
from apps.reviewapp.models import Review
from apps.specialistsapp.models import Specialist

logger = logging.getLogger(__name__)


class SpecialistQueries:
    """
    Advanced queries for specialist-related analytics.
    """

    def get_specialist_performance(self, specialist_id, start_date, end_date):
        """
        Get detailed specialist performance metrics.

        Args:
            specialist_id: Specialist ID
            start_date: Start date
            end_date: End date

        Returns:
            dict: Specialist performance data
        """
        specialist = Specialist.objects.get(id=specialist_id)

        # Get bookings data
        bookings = Appointment.objects.filter(
            specialist_id=specialist_id,
            start_time__gte=start_date,
            start_time__lt=end_date,
        )

        total_bookings = bookings.count()
        completed_bookings = bookings.filter(status="completed").count()
        cancelled_bookings = bookings.filter(status="cancelled").count()
        no_show_bookings = bookings.filter(status="no_show").count()

        # Calculate rates
        completion_rate = 0
        cancellation_rate = 0
        no_show_rate = 0

        if total_bookings > 0:
            completion_rate = (completed_bookings / total_bookings) * 100
            cancellation_rate = (cancelled_bookings / total_bookings) * 100
            no_show_rate = (no_show_bookings / total_bookings) * 100

        # Calculate revenue
        revenue = (
            Transaction.objects.filter(
                content_type__model="appointment",
                content_object__specialist_id=specialist_id,
                created_at__gte=start_date,
                created_at__lt=end_date,
                status="succeeded",
            ).aggregate(total=Coalesce(Sum("amount"), 0))["total"]
            or 0
        )

        # Calculate revenue per booking
        revenue_per_booking = 0
        if completed_bookings > 0:
            revenue_per_booking = revenue / completed_bookings

        # Get ratings data
        ratings = Review.objects.filter(
            content_type__model="specialist",
            object_id=specialist_id,
            created_at__gte=start_date,
            created_at__lt=end_date,
        ).aggregate(avg_rating=Coalesce(Avg("rating"), 0), count=Count("id"))

        # Get rating distribution
        rating_distribution = (
            Review.objects.filter(
                content_type__model="specialist",
                object_id=specialist_id,
                created_at__gte=start_date,
                created_at__lt=end_date,
            )
            .values("rating")
            .annotate(count=Count("id"))
            .order_by("rating")
        )

        # Convert to dictionary
        rating_dict = {str(item["rating"]): item["count"] for item in rating_distribution}

        # Get service-specific performance
        service_performance = (
            bookings.values("service__id", "service__name")
            .annotate(
                count=Count("id"),
                completed=Count("id", filter=Q(status="completed")),
                cancelled=Count("id", filter=Q(status="cancelled")),
                no_show=Count("id", filter=Q(status="no_show")),
                revenue=Coalesce(
                    Sum("transaction__amount", filter=Q(transaction__status="succeeded")),
                    0,
                ),
            )
            .order_by("-count")
        )

        service_data = []
        for service in service_performance:
            if service["service__id"] and service["service__name"]:
                completion_rate_service = 0
                if service["count"] > 0:
                    completion_rate_service = (service["completed"] / service["count"]) * 100

                revenue_per_booking_service = 0
                if service["completed"] > 0:
                    revenue_per_booking_service = service["revenue"] / service["completed"]

                service_data.append(
                    {
                        "id": service["service__id"],
                        "name": service["service__name"],
                        "bookings": service["count"],
                        "completed": service["completed"],
                        "cancelled": service["cancelled"],
                        "no_show": service["no_show"],
                        "revenue": service["revenue"],
                        "completion_rate": round(completion_rate_service, 2),
                        "revenue_per_booking": round(revenue_per_booking_service, 2),
                    }
                )

        # Get daily booking trend
        daily_bookings = (
            bookings.annotate(date=TruncDate("start_time"))
            .values("date")
            .annotate(
                count=Count("id"),
                completed=Count("id", filter=Q(status="completed")),
                cancelled=Count("id", filter=Q(status="cancelled")),
                no_show=Count("id", filter=Q(status="no_show")),
                revenue=Coalesce(
                    Sum("transaction__amount", filter=Q(transaction__status="succeeded")),
                    0,
                ),
            )
            .order_by("date")
        )

        # Format as time series
        booking_series = {}
        for entry in daily_bookings:
            date_str = entry["date"].isoformat()
            booking_series[date_str] = entry["count"]

        # Get hourly distribution
        hourly_distribution = (
            bookings.annotate(hour=ExtractHour("start_time"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )

        # Convert to dictionary
        hourly_dict = {str(item["hour"]): item["count"] for item in hourly_distribution}

        # Get day of week distribution
        day_distribution = (
            bookings.annotate(day=ExtractDay("start_time"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        # Convert to dictionary
        day_dict = {str(item["day"]): item["count"] for item in day_distribution}

        # Get utilization rate
        # This is complex and depends on working hours configuration
        # For simplicity, we'll calculate a basic utilization
        days_in_period = (end_date - start_date).days
        if days_in_period == 0:
            days_in_period = 1

        # Assuming 8 hours per day average
        max_hours = days_in_period * 8

        # Calculate total booked hours based on service duration
        total_booked_hours = 0
        for booking in bookings:
            duration_hours = booking.service.duration / 60
            total_booked_hours += duration_hours

        utilization_rate = 0
        if max_hours > 0:
            utilization_rate = (total_booked_hours / max_hours) * 100

        # Get bookings per day
        bookings_per_day = 0
        if days_in_period > 0:
            bookings_per_day = total_bookings / days_in_period

        # Format results
        result = {
            "entity_id": specialist_id,
            "entity_type": "specialist",
            "entity_name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
            "metrics": {
                "total_bookings": total_bookings,
                "completed_bookings": completed_bookings,
                "cancelled_bookings": cancelled_bookings,
                "no_show_bookings": no_show_bookings,
                "completion_rate": round(completion_rate, 2),
                "cancellation_rate": round(cancellation_rate, 2),
                "no_show_rate": round(no_show_rate, 2),
                "total_revenue": revenue,
                "revenue_per_booking": round(revenue_per_booking, 2),
                "avg_rating": round(ratings["avg_rating"], 2),
                "review_count": ratings["count"],
                "utilization_rate": round(utilization_rate, 2),
                "bookings_per_day": round(bookings_per_day, 2),
            },
            "service_performance": service_data,
            "rating_distribution": rating_dict,
            "hourly_distribution": hourly_dict,
            "day_distribution": day_dict,
            "time_series": {"daily_bookings": booking_series},
        }

        return result
