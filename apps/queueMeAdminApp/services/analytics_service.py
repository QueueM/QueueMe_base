import datetime

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from apps.authapp.models import User
from apps.bookingapp.models import Appointment
from apps.payment.models import Transaction
from apps.queueapp.models import QueueTicket
from apps.reviewapp.models import Review
from apps.shopapp.models import Shop


class AnalyticsService:
    """
    Service for generating analytics and reports.
    """

    @staticmethod
    def get_dashboard_stats(days=30):
        """
        Get dashboard statistics for the specified time period.

        Args:
            days: Number of days to include (default: 30)

        Returns:
            dict: Dashboard statistics
        """
        # Calculate date range
        end_date = timezone.now().date()
        start_date = end_date - datetime.timedelta(days=days)

        # Convert to datetime for filtering
        start_datetime = datetime.datetime.combine(start_date, datetime.time.min)
        start_datetime = timezone.make_aware(start_datetime)

        end_datetime = datetime.datetime.combine(end_date, datetime.time.max)
        end_datetime = timezone.make_aware(end_datetime)

        date_range = (start_datetime, end_datetime)

        # New users over time
        new_users = (
            User.objects.filter(date_joined__range=date_range)
            .annotate(date=TruncDate("date_joined"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        # New shops over time
        new_shops = (
            Shop.objects.filter(created_at__range=date_range)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        # Bookings over time
        bookings = (
            Appointment.objects.filter(created_at__range=date_range)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        # Queue tickets over time
        queue_tickets = (
            QueueTicket.objects.filter(join_time__range=date_range)
            .annotate(date=TruncDate("join_time"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        # Payment transactions over time
        transactions = (
            Transaction.objects.filter(created_at__range=date_range)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"), total_amount=Sum("amount"))
            .order_by("date")
        )

        # Reviews over time
        reviews = (
            Review.objects.filter(created_at__range=date_range)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"), avg_rating=Avg("rating"))
            .order_by("date")
        )

        # Get top entities
        top_shops = Shop.objects.annotate(booking_count=Count("appointments")).order_by(
            "-booking_count"
        )[:10]

        # Gather all statistics
        stats = {
            "time_series": {
                "new_users": list(new_users),
                "new_shops": list(new_shops),
                "bookings": list(bookings),
                "queue_tickets": list(queue_tickets),
                "transactions": list(transactions),
                "reviews": list(reviews),
            },
            "top_entities": {
                "shops": [
                    {
                        "id": str(shop.id),
                        "name": shop.name,
                        "booking_count": shop.booking_count,
                    }
                    for shop in top_shops
                ]
            },
            "totals": {
                "users": User.objects.count(),
                "shops": Shop.objects.count(),
                "bookings_period": Appointment.objects.filter(created_at__range=date_range).count(),
                "tickets_period": QueueTicket.objects.filter(join_time__range=date_range).count(),
                "revenue_period": Transaction.objects.filter(
                    created_at__range=date_range, status="succeeded"
                ).aggregate(total=Sum("amount"))["total"]
                or 0,
            },
        }

        return stats

    @staticmethod
    def generate_monthly_report(year=None, month=None):
        """
        Generate a monthly analytics report.

        Args:
            year: Year to report on (default: current year)
            month: Month to report on (default: current month)

        Returns:
            dict: Monthly report data
        """
        # Determine report period
        now = timezone.now()
        year = year or now.year
        month = month or now.month

        # Create date range for the month
        start_date = datetime.date(year, month, 1)
        if month == 12:
            end_date = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

        # Convert to datetime for filtering
        start_datetime = datetime.datetime.combine(start_date, datetime.time.min)
        start_datetime = timezone.make_aware(start_datetime)

        end_datetime = datetime.datetime.combine(end_date, datetime.time.max)
        end_datetime = timezone.make_aware(end_datetime)

        date_range = (start_datetime, end_datetime)

        # Get monthly statistics
        user_count = User.objects.filter(date_joined__range=date_range).count()
        shop_count = Shop.objects.filter(created_at__range=date_range).count()
        booking_count = Appointment.objects.filter(created_at__range=date_range).count()
        queue_count = QueueTicket.objects.filter(join_time__range=date_range).count()

        # Revenue statistics
        revenue_stats = Transaction.objects.filter(
            created_at__range=date_range, status="succeeded"
        ).aggregate(total=Sum("amount"), avg=Avg("amount"))

        # Review statistics
        review_stats = Review.objects.filter(created_at__range=date_range).aggregate(
            count=Count("id"), avg_rating=Avg("rating")
        )

        # Customer retention
        # This is a simplified example - real customer retention would be more complex
        repeat_customers = (
            Appointment.objects.filter(created_at__range=date_range)
            .values("customer")
            .annotate(booking_count=Count("id"))
            .filter(booking_count__gt=1)
            .count()
        )

        # Compile report
        report = {
            "period": {
                "year": year,
                "month": month,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "growth": {
                "new_users": user_count,
                "new_shops": shop_count,
            },
            "activity": {
                "bookings": booking_count,
                "queue_tickets": queue_count,
                "repeat_customers": repeat_customers,
            },
            "revenue": {
                "total": revenue_stats["total"] or 0,
                "average_transaction": revenue_stats["avg"] or 0,
            },
            "satisfaction": {
                "reviews": review_stats["count"] or 0,
                "average_rating": review_stats["avg_rating"] or 0,
            },
        }

        return report

    @staticmethod
    def get_user_growth_metrics(period="month", count=12):
        """
        Get user growth metrics over time.

        Args:
            period: Time period ('day', 'week', 'month')
            count: Number of periods to include

        Returns:
            dict: User growth metrics
        """
        # Determine date truncation function based on period
        if period == "day":
            trunc_func = TruncDate
            delta = datetime.timedelta(days=count)
        elif period == "week":
            trunc_func = TruncWeek
            delta = datetime.timedelta(weeks=count)
        else:  # month
            trunc_func = TruncMonth
            delta = datetime.timedelta(days=count * 30)  # Approximation

        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - delta

        # Get user signups by period
        signups = (
            User.objects.filter(date_joined__gte=start_date)
            .annotate(period=trunc_func("date_joined"))
            .values("period")
            .annotate(count=Count("id"))
            .order_by("period")
        )

        # Calculate growth rate
        growth_data = list(signups)
        for i in range(1, len(growth_data)):
            prev_count = growth_data[i - 1]["count"]
            curr_count = growth_data[i]["count"]

            if prev_count > 0:
                growth_rate = ((curr_count - prev_count) / prev_count) * 100
            else:
                growth_rate = 0

            growth_data[i]["growth_rate"] = growth_rate

        # First period has no growth rate
        if growth_data:
            growth_data[0]["growth_rate"] = 0

        return {"period_type": period, "data": growth_data}
