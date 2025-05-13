# apps/reportanalyticsapp/services/analytics_service.py
"""
Analytics Service

Provides comprehensive business analytics functions, including performance metrics,
trends analysis, user engagement, and operational efficiency indicators.
"""

from datetime import timedelta

from django.db.models import Avg, Case, Count, F, FloatField, Sum, Value, When
from django.db.models.functions import Extract, ExtractWeekDay, TruncDay, TruncMonth, TruncWeek
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.queueapp.models import QueueTicket
from apps.reportanalyticsapp.queries import business_queries, platform_queries, specialist_queries
from apps.reviewapp.models import Review
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist, SpecialistWorkingHours
from core.cache.cache_manager import cache_with_key_prefix


class AnalyticsService:
    """
    Service for analyzing business data and generating actionable insights.
    Includes methods for calculating KPIs, analyzing trends, and generating reports.
    """

    TIME_PERIODS = {
        "today": 0,
        "yesterday": 1,
        "last_7_days": 7,
        "last_30_days": 30,
        "last_90_days": 90,
        "last_year": 365,
    }

    GROUPING_PERIODS = {"daily": "day", "weekly": "week", "monthly": "month"}

    @staticmethod
    @cache_with_key_prefix("shop_performance", timeout=3600)  # Cache for 1 hour
    def get_shop_performance(shop_id, period="last_30_days"):
        """
        Get comprehensive shop performance metrics for the specified period.

        Args:
            shop_id (uuid): The shop ID to analyze
            period (str): Time period for analysis ('today', 'yesterday', 'last_7_days', 'last_30_days', 'last_90_days', 'last_year')

        Returns:
            dict: Comprehensive performance metrics
        """
        days = AnalyticsService.TIME_PERIODS.get(period, 30)

        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get shop
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return {"error": "Shop not found"}

        # Get appointment metrics
        appointment_metrics = AnalyticsService._get_appointment_metrics(
            shop_id, start_date, end_date
        )

        # Get queue metrics
        queue_metrics = AnalyticsService._get_queue_metrics(shop_id, start_date, end_date)

        # Get review metrics
        review_metrics = AnalyticsService._get_review_metrics(shop_id, start_date, end_date)

        # Get specialist metrics
        specialist_metrics = AnalyticsService._get_specialist_metrics(shop_id, start_date, end_date)

        # Get service metrics
        service_metrics = AnalyticsService._get_service_metrics(shop_id, start_date, end_date)

        # Get financial metrics
        financial_metrics = AnalyticsService._get_financial_metrics(shop_id, start_date, end_date)

        # Get customer metrics
        customer_metrics = AnalyticsService._get_customer_metrics(shop_id, start_date, end_date)

        return {
            "shop_name": shop.name,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "appointments": appointment_metrics,
            "queues": queue_metrics,
            "reviews": review_metrics,
            "specialists": specialist_metrics,
            "services": service_metrics,
            "financial": financial_metrics,
            "customers": customer_metrics,
            "summary": {
                "total_revenue": financial_metrics["total_revenue"],
                "appointment_count": appointment_metrics["total_count"],
                "queue_count": queue_metrics["total_count"],
                "average_rating": review_metrics["average_rating"],
                "new_customer_count": customer_metrics["new_customer_count"],
                "returning_customer_rate": customer_metrics["returning_rate"],
                "busiest_day": appointment_metrics.get("busiest_day", {}).get("day", "N/A"),
                "most_popular_service": service_metrics.get("most_popular", {}).get("name", "N/A"),
                "top_specialist": specialist_metrics.get("top_performer", {}).get("name", "N/A"),
            },
        }

    @staticmethod
    def get_time_series_data(shop_id, metric_type, start_date, end_date, grouping="daily"):
        """
        Get time series data for the specified metric type and time period.

        Args:
            shop_id (uuid): The shop ID to analyze
            metric_type (str): Type of metric ('appointments', 'revenue', 'queues', 'reviews', 'ratings')
            start_date (datetime): Start date for analysis
            end_date (datetime): End date for analysis
            grouping (str): Time grouping ('daily', 'weekly', 'monthly')

        Returns:
            list: Time series data for the specified metric
        """
        group_by = AnalyticsService.GROUPING_PERIODS.get(grouping, "day")

        if metric_type == "appointments":
            return AnalyticsService._get_appointment_time_series(
                shop_id, start_date, end_date, group_by
            )
        elif metric_type == "revenue":
            return AnalyticsService._get_revenue_time_series(
                shop_id, start_date, end_date, group_by
            )
        elif metric_type == "queues":
            return AnalyticsService._get_queue_time_series(shop_id, start_date, end_date, group_by)
        elif metric_type == "reviews":
            return AnalyticsService._get_review_count_time_series(
                shop_id, start_date, end_date, group_by
            )
        elif metric_type == "ratings":
            return AnalyticsService._get_ratings_time_series(
                shop_id, start_date, end_date, group_by
            )
        else:
            return []

    @staticmethod
    def get_platform_metrics(period="last_30_days", admin_id=None):
        """
        Get platform-wide metrics for Queue Me admins.

        Args:
            period (str): Time period for analysis
            admin_id (uuid, optional): Admin user ID for permission checking

        Returns:
            dict: Platform-wide metrics
        """
        # In a real implementation, check if admin has permission

        days = AnalyticsService.TIME_PERIODS.get(period, 30)

        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get metrics using platform queries
        active_shops = platform_queries.get_active_shops_count(start_date, end_date)
        new_shops = platform_queries.get_new_shops_count(start_date, end_date)
        total_appointments = platform_queries.get_total_appointments_count(start_date, end_date)
        total_revenue = platform_queries.get_total_platform_revenue(start_date, end_date)
        subscription_revenue = platform_queries.get_subscription_revenue(start_date, end_date)
        ad_revenue = platform_queries.get_ad_revenue(start_date, end_date)
        merchant_revenue = platform_queries.get_merchant_revenue(start_date, end_date)
        active_users = platform_queries.get_active_users_count(start_date, end_date)
        new_users = platform_queries.get_new_users_count(start_date, end_date)

        return {
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "shops": {
                "active_count": active_shops,
                "new_count": new_shops,
                "growth_rate": (new_shops / active_shops * 100) if active_shops else 0,
            },
            "appointments": {
                "total_count": total_appointments,
                "avg_per_day": total_appointments / days if days else 0,
            },
            "revenue": {
                "total": total_revenue,
                "subscription": subscription_revenue,
                "ads": ad_revenue,
                "merchant": merchant_revenue,
                "avg_per_day": total_revenue / days if days else 0,
            },
            "users": {
                "active_count": active_users,
                "new_count": new_users,
                "growth_rate": (new_users / active_users * 100) if active_users else 0,
            },
        }

    @staticmethod
    def get_comparison_metrics(shop_id, comparison_period="previous"):
        """
        Compare current period with previous period.

        Args:
            shop_id (uuid): The shop ID to analyze
            comparison_period (str): Comparison period type ('previous', 'same_last_year')

        Returns:
            dict: Comparative metrics between current and previous periods
        """
        # Current period: last 30 days
        current_end = timezone.now()
        current_start = current_end - timedelta(days=30)

        # Previous period
        if comparison_period == "same_last_year":
            previous_end = current_end - timedelta(days=365)
            previous_start = previous_end - timedelta(days=30)
        else:  # 'previous'
            previous_end = current_start
            previous_start = previous_end - timedelta(days=30)

        # Get metrics for both periods
        current_metrics = AnalyticsService.get_shop_performance(shop_id, "last_30_days")

        # Calculate previous period metrics
        previous_appointment_metrics = AnalyticsService._get_appointment_metrics(
            shop_id, previous_start, previous_end
        )
        previous_revenue = AnalyticsService._get_financial_metrics(
            shop_id, previous_start, previous_end
        )["total_revenue"]
        previous_reviews = AnalyticsService._get_review_metrics(
            shop_id, previous_start, previous_end
        )

        # Calculate changes
        appointment_change = AnalyticsService._calculate_percentage_change(
            current_metrics["appointments"]["total_count"],
            previous_appointment_metrics["total_count"],
        )

        revenue_change = AnalyticsService._calculate_percentage_change(
            current_metrics["financial"]["total_revenue"], previous_revenue
        )

        rating_change = AnalyticsService._calculate_percentage_change(
            current_metrics["reviews"]["average_rating"],
            previous_reviews["average_rating"],
        )

        return {
            "current_period": {"start_date": current_start, "end_date": current_end},
            "previous_period": {"start_date": previous_start, "end_date": previous_end},
            "comparison_type": comparison_period,
            "metrics": {
                "appointments": {
                    "current": current_metrics["appointments"]["total_count"],
                    "previous": previous_appointment_metrics["total_count"],
                    "change": appointment_change,
                },
                "revenue": {
                    "current": current_metrics["financial"]["total_revenue"],
                    "previous": previous_revenue,
                    "change": revenue_change,
                },
                "rating": {
                    "current": current_metrics["reviews"]["average_rating"],
                    "previous": previous_reviews["average_rating"],
                    "change": rating_change,
                },
            },
        }

    @staticmethod
    def get_service_performance(shop_id, start_date=None, end_date=None, limit=10):
        """
        Get detailed performance metrics for each service in the shop.

        Args:
            shop_id (uuid): The shop ID to analyze
            start_date (datetime, optional): Start date for analysis
            end_date (datetime, optional): End date for analysis
            limit (int): Maximum number of services to return

        Returns:
            list: Service performance data
        """
        if not start_date:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=30)

        # Get service metrics from business queries
        services = business_queries.get_service_performance(shop_id, start_date, end_date, limit)

        # Calculate additional metrics for each service
        result = []
        for service in services:
            service_id = service["id"]

            # Get detailed booking metrics for this service
            bookings = Appointment.objects.filter(
                service_id=service_id,
                start_time__gte=start_date,
                start_time__lte=end_date,
            )

            # Calculate on-time performance
            on_time_count = bookings.filter(
                check_in_time__isnull=False,
                check_in_time__lte=F("start_time") + timedelta(minutes=10),
            ).count()

            on_time_rate = (
                (on_time_count / service["booking_count"] * 100)
                if service["booking_count"] > 0
                else 0
            )

            # Get cancellation rate
            cancellation_count = bookings.filter(status="cancelled").count()
            cancellation_rate = (
                (cancellation_count / service["booking_count"] * 100)
                if service["booking_count"] > 0
                else 0
            )

            # Get conversion rate from views to bookings
            # This requires tracking view data which might be in another table
            conversion_rate = 0  # Placeholder

            # Enhance service data
            service_data = {
                **service,
                "on_time_rate": round(on_time_rate, 2),
                "cancellation_rate": round(cancellation_rate, 2),
                "conversion_rate": conversion_rate,
            }

            result.append(service_data)

        return result

    @staticmethod
    def get_specialist_performance(shop_id, start_date=None, end_date=None, limit=10):
        """
        Get detailed performance metrics for each specialist in the shop.

        Args:
            shop_id (uuid): The shop ID to analyze
            start_date (datetime, optional): Start date for analysis
            end_date (datetime, optional): End date for analysis
            limit (int): Maximum number of specialists to return

        Returns:
            list: Specialist performance data
        """
        if not start_date:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=30)

        # Get specialist metrics from specialist queries
        specialists = specialist_queries.get_specialist_performance(
            shop_id, start_date, end_date, limit
        )

        # Calculate additional metrics for each specialist
        result = []
        for specialist in specialists:
            specialist_id = specialist["id"]

            # Get detailed booking metrics for this specialist
            bookings = Appointment.objects.filter(
                specialist_id=specialist_id,
                start_time__gte=start_date,
                start_time__lte=end_date,
            )

            # Calculate service time efficiency
            completed_bookings = bookings.filter(
                status="completed", start_time__isnull=False, end_time__isnull=False
            )

            total_duration = sum(
                [(b.end_time - b.start_time).total_seconds() / 60 for b in completed_bookings],
                0,
            )

            scheduled_duration = sum([b.service.duration for b in completed_bookings], 0)

            efficiency_rate = (
                (scheduled_duration / total_duration * 100) if total_duration > 0 else 0
            )

            # Calculate return customer rate
            customer_ids = list(bookings.values_list("customer_id", flat=True).distinct())

            if customer_ids:
                # Count customers who had previous bookings with this specialist
                return_customer_count = (
                    Appointment.objects.filter(
                        specialist_id=specialist_id,
                        customer_id__in=customer_ids,
                        start_time__lt=start_date,
                    )
                    .values("customer_id")
                    .distinct()
                    .count()
                )

                return_rate = return_customer_count / len(customer_ids) * 100
            else:
                return_rate = 0

            # Enhance specialist data
            specialist_data = {
                **specialist,
                "efficiency_rate": round(efficiency_rate, 2),
                "return_customer_rate": round(return_rate, 2),
            }

            result.append(specialist_data)

        return result

    @staticmethod
    def get_customer_segments(shop_id, start_date=None, end_date=None):
        """
        Segment customers based on booking patterns, spending, and service preferences.

        Args:
            shop_id (uuid): The shop ID to analyze
            start_date (datetime, optional): Start date for analysis
            end_date (datetime, optional): End date for analysis

        Returns:
            dict: Customer segmentation analysis
        """
        if not start_date:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=180)  # 6 months for better segmentation

        # Get all customers who made bookings in this shop
        bookings = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lte=end_date
        )

        customer_ids = bookings.values_list("customer_id", flat=True).distinct()

        # Calculate metrics for each customer
        customer_metrics = {}
        for customer_id in customer_ids:
            customer_bookings = bookings.filter(customer_id=customer_id)

            # Calculate total spending
            total_spent = sum([b.service.price for b in customer_bookings])

            # Calculate booking frequency
            booking_count = customer_bookings.count()

            # Calculate average time between bookings
            sorted_dates = sorted([b.start_time for b in customer_bookings])
            if len(sorted_dates) > 1:
                date_diffs = [
                    (sorted_dates[i] - sorted_dates[i - 1]).days
                    for i in range(1, len(sorted_dates))
                ]
                avg_days_between = sum(date_diffs) / len(date_diffs)
            else:
                avg_days_between = None

            # Get most frequently booked service
            service_counts = {}
            for booking in customer_bookings:
                service_id = str(booking.service_id)
                service_counts[service_id] = service_counts.get(service_id, 0) + 1

            most_frequent_service = (
                max(service_counts.items(), key=lambda x: x[1])[0] if service_counts else None
            )

            # Store metrics
            customer_metrics[str(customer_id)] = {
                "total_spent": total_spent,
                "booking_count": booking_count,
                "avg_days_between": avg_days_between,
                "most_frequent_service": most_frequent_service,
                "last_booking_date": sorted_dates[-1] if sorted_dates else None,
            }

        # Segment customers
        high_value_threshold = 1000  # SAR
        high_frequency_threshold = 5  # bookings
        inactive_threshold = 60  # days

        high_value = []
        high_frequency = []
        regular = []
        at_risk = []
        inactive = []
        one_time = []

        for customer_id, metrics in customer_metrics.items():
            # High value customers
            if metrics["total_spent"] >= high_value_threshold:
                high_value.append(customer_id)

            # High frequency customers
            if metrics["booking_count"] >= high_frequency_threshold:
                high_frequency.append(customer_id)

            # One-time customers
            if metrics["booking_count"] == 1:
                one_time.append(customer_id)

            # At-risk and inactive customers
            last_booking = metrics["last_booking_date"]
            if last_booking:
                days_since_last = (end_date - last_booking).days

                if days_since_last > inactive_threshold:
                    inactive.append(customer_id)
                elif days_since_last > (inactive_threshold // 2):
                    at_risk.append(customer_id)

            # Regular customers (by exclusion)
            is_regular = (
                customer_id not in high_value
                and customer_id not in high_frequency
                and customer_id not in one_time
                and customer_id not in at_risk
                and customer_id not in inactive
            )

            if is_regular:
                regular.append(customer_id)

        return {
            "segments": {
                "high_value": {
                    "count": len(high_value),
                    "percentage": (
                        round(len(high_value) / len(customer_ids) * 100, 2) if customer_ids else 0
                    ),
                },
                "high_frequency": {
                    "count": len(high_frequency),
                    "percentage": (
                        round(len(high_frequency) / len(customer_ids) * 100, 2)
                        if customer_ids
                        else 0
                    ),
                },
                "regular": {
                    "count": len(regular),
                    "percentage": (
                        round(len(regular) / len(customer_ids) * 100, 2) if customer_ids else 0
                    ),
                },
                "at_risk": {
                    "count": len(at_risk),
                    "percentage": (
                        round(len(at_risk) / len(customer_ids) * 100, 2) if customer_ids else 0
                    ),
                },
                "inactive": {
                    "count": len(inactive),
                    "percentage": (
                        round(len(inactive) / len(customer_ids) * 100, 2) if customer_ids else 0
                    ),
                },
                "one_time": {
                    "count": len(one_time),
                    "percentage": (
                        round(len(one_time) / len(customer_ids) * 100, 2) if customer_ids else 0
                    ),
                },
            },
            "total_customers": len(customer_ids),
            "analysis_period": {"start_date": start_date, "end_date": end_date},
        }

    # Private helper methods

    @staticmethod
    def _get_appointment_metrics(shop_id, start_date, end_date):
        """Get key appointment metrics for the shop"""
        # Get all appointments in the period
        appointments = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lte=end_date
        )

        # Total count
        total_count = appointments.count()

        # Completed count
        completed_count = appointments.filter(status="completed").count()

        # Cancelled count
        cancelled_count = appointments.filter(status="cancelled").count()

        # No-show count
        no_show_count = appointments.filter(status="no_show").count()

        # Completion rate
        completion_rate = (completed_count / total_count * 100) if total_count > 0 else 0

        # Average duration
        avg_duration = (
            appointments.filter(
                status="completed", start_time__isnull=False, end_time__isnull=False
            )
            .annotate(duration_minutes=Extract(F("end_time") - F("start_time"), "epoch") / 60)
            .aggregate(avg_duration=Avg("duration_minutes"))["avg_duration"]
            or 0
        )

        # Busiest day
        busiest_day = (
            appointments.annotate(appointment_date=TruncDay("start_time"))
            .values("appointment_date")
            .annotate(count=Count("id"))
            .order_by("-count")
            .first()
        )

        # Distribution by day of week
        day_distribution = (
            appointments.annotate(day_of_week=ExtractWeekDay("start_time"))
            .values("day_of_week")
            .annotate(count=Count("id"))
            .order_by("day_of_week")
        )

        day_names = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]
        day_distribution_dict = {
            day_names[item["day_of_week"] % 7]: item["count"] for item in day_distribution
        }

        return {
            "total_count": total_count,
            "completed_count": completed_count,
            "cancelled_count": cancelled_count,
            "no_show_count": no_show_count,
            "completion_rate": round(completion_rate, 2),
            "average_duration_minutes": round(avg_duration, 2),
            "busiest_day": {
                "day": (
                    busiest_day["appointment_date"].strftime("%Y-%m-%d") if busiest_day else None
                ),
                "count": busiest_day["count"] if busiest_day else 0,
            },
            "day_distribution": day_distribution_dict,
        }

    @staticmethod
    def _get_queue_metrics(shop_id, start_date, end_date):
        """Get key queue metrics for the shop"""
        # Get all queue tickets in the period
        tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id, join_time__gte=start_date, join_time__lte=end_date
        )

        # Total count
        total_count = tickets.count()

        # Served count
        served_count = tickets.filter(status="served").count()

        # Skipped count
        skipped_count = tickets.filter(status="skipped").count()

        # Cancelled count
        cancelled_count = tickets.filter(status="cancelled").count()

        # Service rate
        service_rate = (served_count / total_count * 100) if total_count > 0 else 0

        # Average wait time (from join to serve)
        avg_wait_time = (
            tickets.filter(status="served", join_time__isnull=False, serve_time__isnull=False)
            .annotate(wait_minutes=Extract(F("serve_time") - F("join_time"), "epoch") / 60)
            .aggregate(avg_wait=Avg("wait_minutes"))["avg_wait"]
            or 0
        )

        # Average service time (from serve to complete)
        avg_service_time = (
            tickets.filter(status="served", serve_time__isnull=False, complete_time__isnull=False)
            .annotate(service_minutes=Extract(F("complete_time") - F("serve_time"), "epoch") / 60)
            .aggregate(avg_service=Avg("service_minutes"))["avg_service"]
            or 0
        )

        # Wait time accuracy (expected vs actual)
        wait_time_accuracy = (
            tickets.filter(
                status="served",
                estimated_wait_time__gt=0,
                actual_wait_time__isnull=False,
            )
            .annotate(
                accuracy_pct=Case(
                    When(
                        estimated_wait_time__gt=0,
                        then=100 * F("actual_wait_time") / F("estimated_wait_time"),
                    ),
                    default=Value(0),
                    output_field=FloatField(),
                )
            )
            .aggregate(avg_accuracy=Avg("accuracy_pct"))["avg_accuracy"]
            or 0
        )

        return {
            "total_count": total_count,
            "served_count": served_count,
            "skipped_count": skipped_count,
            "cancelled_count": cancelled_count,
            "service_rate": round(service_rate, 2),
            "average_wait_minutes": round(avg_wait_time, 2),
            "average_service_minutes": round(avg_service_time, 2),
            "wait_time_accuracy": round(wait_time_accuracy, 2),
        }

    @staticmethod
    def _get_review_metrics(shop_id, start_date, end_date):
        """Get key review metrics for the shop"""
        # Get shop reviews
        shop_reviews = Review.objects.filter(
            content_type__model="shop",
            object_id=shop_id,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get specialist reviews for the shop
        specialist_ids = Specialist.objects.filter(employee__shop_id=shop_id).values_list(
            "id", flat=True
        )

        specialist_reviews = Review.objects.filter(
            content_type__model="specialist",
            object_id__in=specialist_ids,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get service reviews for the shop
        service_ids = Service.objects.filter(shop_id=shop_id).values_list("id", flat=True)

        service_reviews = Review.objects.filter(
            content_type__model="service",
            object_id__in=service_ids,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Combine all reviews
        all_reviews = list(shop_reviews) + list(specialist_reviews) + list(service_reviews)

        # Total count
        total_count = len(all_reviews)

        # Calculate average rating
        if total_count > 0:
            avg_rating = sum(review.rating for review in all_reviews) / total_count
        else:
            avg_rating = 0

        # Rating distribution
        rating_distribution = {
            "5_star": sum(1 for review in all_reviews if review.rating == 5),
            "4_star": sum(1 for review in all_reviews if review.rating == 4),
            "3_star": sum(1 for review in all_reviews if review.rating == 3),
            "2_star": sum(1 for review in all_reviews if review.rating == 2),
            "1_star": sum(1 for review in all_reviews if review.rating == 1),
        }

        # Calculate positive ratio (4 and 5 stars)
        positive_reviews = rating_distribution["5_star"] + rating_distribution["4_star"]
        positive_ratio = (positive_reviews / total_count * 100) if total_count > 0 else 0

        # Calculate review rate (vs total appointments and queues)
        appointments = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_date,
            start_time__lte=end_date,
            status="completed",
        ).count()

        tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id,
            join_time__gte=start_date,
            join_time__lte=end_date,
            status="served",
        ).count()

        total_services = appointments + tickets

        review_rate = (total_count / total_services * 100) if total_services > 0 else 0

        return {
            "total_count": total_count,
            "average_rating": round(avg_rating, 2),
            "rating_distribution": rating_distribution,
            "positive_ratio": round(positive_ratio, 2),
            "review_rate": round(review_rate, 2),
            "shop_reviews_count": shop_reviews.count(),
            "specialist_reviews_count": specialist_reviews.count(),
            "service_reviews_count": service_reviews.count(),
        }

    @staticmethod
    def _get_specialist_metrics(shop_id, start_date, end_date):
        """Get key specialist metrics for the shop"""
        specialists = Specialist.objects.filter(employee__shop_id=shop_id, employee__is_active=True)

        if not specialists.exists():
            return {
                "total_count": 0,
                "top_performer": None,
                "booking_distribution": {},
                "average_utilization": 0,
            }

        # Get top performer by completed appointments
        specialist_stats = []

        for specialist in specialists:
            # Get all appointments in the period
            appointments = Appointment.objects.filter(
                specialist_id=specialist.id,
                start_time__gte=start_date,
                start_time__lte=end_date,
            )

            # Count completed appointments
            completed_count = appointments.filter(status="completed").count()

            # Calculate average rating
            reviews = Review.objects.filter(
                content_type__model="specialist",
                object_id=specialist.id,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )

            avg_rating = reviews.aggregate(avg_rating=Avg("rating"))["avg_rating"] or 0

            # Calculate utilization rate
            # Get total working minutes in the period
            working_hours = SpecialistWorkingHours.objects.filter(
                specialist_id=specialist.id, is_off=False
            )

            # We need to calculate total working minutes across the period
            # This is a simplified approach (assumes consistent weekly schedule)
            total_working_minutes = 0
            days_in_period = (end_date - start_date).days + 1

            # Calculate working minutes per week
            working_minutes_per_week = 0
            for wh in working_hours:
                if not wh.is_off:
                    minutes_per_day = (wh.to_hour.hour * 60 + wh.to_hour.minute) - (
                        wh.from_hour.hour * 60 + wh.from_hour.minute
                    )
                    working_minutes_per_week += minutes_per_day

            # Scale to the full period
            total_working_minutes = working_minutes_per_week * (days_in_period / 7)

            # Calculate booked minutes
            booked_minutes = (
                appointments.aggregate(total_minutes=Sum("service__duration"))["total_minutes"] or 0
            )

            # Calculate utilization rate
            utilization_rate = (
                (booked_minutes / total_working_minutes * 100) if total_working_minutes > 0 else 0
            )

            specialist_stats.append(
                {
                    "id": specialist.id,
                    "name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
                    "completed_appointments": completed_count,
                    "avg_rating": avg_rating,
                    "utilization_rate": utilization_rate,
                }
            )

        # Sort by completed appointments
        specialist_stats.sort(key=lambda x: x["completed_appointments"], reverse=True)

        # Get booking distribution among specialists
        total_bookings = sum(s["completed_appointments"] for s in specialist_stats)

        booking_distribution = {}
        if total_bookings > 0:
            for specialist in specialist_stats:
                percentage = specialist["completed_appointments"] / total_bookings * 100
                booking_distribution[specialist["name"]] = round(percentage, 2)

        # Calculate average utilization
        avg_utilization = (
            sum(s["utilization_rate"] for s in specialist_stats) / len(specialist_stats)
            if specialist_stats
            else 0
        )

        return {
            "total_count": specialists.count(),
            "top_performer": specialist_stats[0] if specialist_stats else None,
            "booking_distribution": booking_distribution,
            "average_utilization": round(avg_utilization, 2),
            "specialists": specialist_stats,
        }

    @staticmethod
    def _get_service_metrics(shop_id, start_date, end_date):
        """Get key service metrics for the shop"""
        services = Service.objects.filter(shop_id=shop_id, is_active=True)

        if not services.exists():
            return {
                "total_count": 0,
                "most_popular": None,
                "booking_distribution": {},
                "average_price": 0,
            }

        # Get most popular service by bookings
        service_stats = []

        for service in services:
            # Get all appointments in the period
            appointments = Appointment.objects.filter(
                service_id=service.id,
                start_time__gte=start_date,
                start_time__lte=end_date,
            )

            # Count completed appointments
            booking_count = appointments.count()
            completed_count = appointments.filter(status="completed").count()

            # Calculate revenue from this service
            revenue = service.price * completed_count

            # Calculate average rating
            reviews = Review.objects.filter(
                content_type__model="service",
                object_id=service.id,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )

            avg_rating = reviews.aggregate(avg_rating=Avg("rating"))["avg_rating"] or 0

            service_stats.append(
                {
                    "id": service.id,
                    "name": service.name,
                    "booking_count": booking_count,
                    "completed_count": completed_count,
                    "revenue": revenue,
                    "avg_rating": avg_rating,
                    "price": service.price,
                }
            )

        # Sort by booking count
        service_stats.sort(key=lambda x: x["booking_count"], reverse=True)

        # Get booking distribution among services
        total_bookings = sum(s["booking_count"] for s in service_stats)

        booking_distribution = {}
        if total_bookings > 0:
            for service in service_stats:
                percentage = service["booking_count"] / total_bookings * 100
                booking_distribution[service["name"]] = round(percentage, 2)

        # Calculate average price
        avg_price = (
            sum(s["price"] for s in service_stats) / len(service_stats) if service_stats else 0
        )

        return {
            "total_count": services.count(),
            "most_popular": service_stats[0] if service_stats else None,
            "booking_distribution": booking_distribution,
            "average_price": round(avg_price, 2),
            "services": service_stats,
        }

    @staticmethod
    def _get_financial_metrics(shop_id, start_date, end_date):
        """Get key financial metrics for the shop"""
        # Get completed appointments
        appointments = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_date,
            start_time__lte=end_date,
            status="completed",
        )

        # Calculate total revenue
        # This is a simplified approach assuming price is the revenue
        total_revenue = 0
        for appointment in appointments:
            total_revenue += appointment.service.price

        # Calculate by service type
        revenue_by_service = {}
        for appointment in appointments:
            service_name = appointment.service.name
            revenue_by_service[service_name] = (
                revenue_by_service.get(service_name, 0) + appointment.service.price
            )

        # Calculate by day
        revenue_by_day = {}
        for appointment in appointments:
            day = appointment.start_time.strftime("%Y-%m-%d")
            revenue_by_day[day] = revenue_by_day.get(day, 0) + appointment.service.price

        # Calculate average revenue per appointment
        avg_revenue_per_appointment = (
            total_revenue / appointments.count() if appointments.count() > 0 else 0
        )

        # Calculate days in period
        days_in_period = (end_date - start_date).days + 1

        # Calculate average daily revenue
        avg_daily_revenue = total_revenue / days_in_period if days_in_period > 0 else 0

        return {
            "total_revenue": total_revenue,
            "revenue_by_service": revenue_by_service,
            "revenue_by_day": revenue_by_day,
            "average_revenue_per_appointment": round(avg_revenue_per_appointment, 2),
            "average_daily_revenue": round(avg_daily_revenue, 2),
        }

    @staticmethod
    def _get_customer_metrics(shop_id, start_date, end_date):
        """Get key customer metrics for the shop"""
        # Get all appointments in the period
        appointments = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lte=end_date
        )

        # Get unique customers
        customer_ids = appointments.values_list("customer_id", flat=True).distinct()

        # Get new vs returning customers
        new_customers = []
        returning_customers = []

        for customer_id in customer_ids:
            # Check if customer had previous appointments
            previous_appointments = Appointment.objects.filter(
                shop_id=shop_id, customer_id=customer_id, start_time__lt=start_date
            ).exists()

            if previous_appointments:
                returning_customers.append(customer_id)
            else:
                new_customers.append(customer_id)

        # Calculate returning customer rate
        returning_rate = (len(returning_customers) / len(customer_ids) * 100) if customer_ids else 0

        # Calculate appointment frequency
        appointments_per_customer = appointments.count() / len(customer_ids) if customer_ids else 0

        # Calculate customer retention
        # This requires data from before the start date
        # Find customers who had appointments in the previous period
        previous_period_start = start_date - (end_date - start_date)
        previous_period_customers = set(
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=previous_period_start,
                start_time__lt=start_date,
            )
            .values_list("customer_id", flat=True)
            .distinct()
        )

        # Find how many of those returned in the current period
        current_period_customers = set(customer_ids)
        returning_from_previous = previous_period_customers.intersection(current_period_customers)

        retention_rate = (
            (len(returning_from_previous) / len(previous_period_customers) * 100)
            if previous_period_customers
            else 0
        )

        return {
            "total_customer_count": len(customer_ids),
            "new_customer_count": len(new_customers),
            "returning_customer_count": len(returning_customers),
            "returning_rate": round(returning_rate, 2),
            "appointments_per_customer": round(appointments_per_customer, 2),
            "retention_rate": round(retention_rate, 2),
        }

    @staticmethod
    def _get_appointment_time_series(shop_id, start_date, end_date, group_by="day"):
        """Generate appointment time series data"""
        appointments = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lte=end_date
        )

        # Group by appropriate time unit
        if group_by == "day":
            appointments = appointments.annotate(period=TruncDay("start_time"))
        elif group_by == "week":
            appointments = appointments.annotate(period=TruncWeek("start_time"))
        else:  # month
            appointments = appointments.annotate(period=TruncMonth("start_time"))

        # Aggregate by period
        data = (
            appointments.values("period")
            .annotate(
                total=Count("id"),
                completed=Count(Case(When(status="completed", then=1))),
            )
            .order_by("period")
        )

        # Format for time series
        result = []
        for item in data:
            result.append(
                {
                    "date": item["period"].strftime("%Y-%m-%d"),
                    "total": item["total"],
                    "completed": item["completed"],
                }
            )

        return result

    @staticmethod
    def _get_revenue_time_series(shop_id, start_date, end_date, group_by="day"):
        """Generate revenue time series data"""
        # We need to use raw SQL or complex Django ORM queries to aggregate revenue
        # This is a simplified version

        completed_appointments = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_date,
            start_time__lte=end_date,
            status="completed",
        )

        # Group by appropriate time unit
        if group_by == "day":
            completed_appointments = completed_appointments.annotate(period=TruncDay("start_time"))
        elif group_by == "week":
            completed_appointments = completed_appointments.annotate(period=TruncWeek("start_time"))
        else:  # month
            completed_appointments = completed_appointments.annotate(
                period=TruncMonth("start_time")
            )

        # Calculate revenue for each appointment and group by period
        # In a real implementation, you might want to use a more efficient approach
        revenue_by_period = {}

        for appointment in completed_appointments:
            period_key = appointment.period.strftime("%Y-%m-%d")

            if period_key not in revenue_by_period:
                revenue_by_period[period_key] = 0

            revenue_by_period[period_key] += appointment.service.price

        # Format for time series
        result = []
        for period, revenue in sorted(revenue_by_period.items()):
            result.append({"date": period, "revenue": revenue})

        return result

    @staticmethod
    def _get_queue_time_series(shop_id, start_date, end_date, group_by="day"):
        """Generate queue time series data"""
        tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id, join_time__gte=start_date, join_time__lte=end_date
        )

        # Group by appropriate time unit
        if group_by == "day":
            tickets = tickets.annotate(period=TruncDay("join_time"))
        elif group_by == "week":
            tickets = tickets.annotate(period=TruncWeek("join_time"))
        else:  # month
            tickets = tickets.annotate(period=TruncMonth("join_time"))

        # Aggregate by period
        data = (
            tickets.values("period")
            .annotate(
                total=Count("id"),
                served=Count(Case(When(status="served", then=1))),
                avg_wait=Avg(
                    Case(
                        When(
                            status="served",
                            join_time__isnull=False,
                            serve_time__isnull=False,
                            then=Extract(F("serve_time") - F("join_time"), "epoch") / 60,
                        ),
                        default=None,
                        output_field=FloatField(),
                    )
                ),
            )
            .order_by("period")
        )

        # Format for time series
        result = []
        for item in data:
            result.append(
                {
                    "date": item["period"].strftime("%Y-%m-%d"),
                    "total": item["total"],
                    "served": item["served"],
                    "average_wait_minutes": (round(item["avg_wait"], 2) if item["avg_wait"] else 0),
                }
            )

        return result

    @staticmethod
    def _get_review_count_time_series(shop_id, start_date, end_date, group_by="day"):
        """Generate review count time series data"""
        # Get shop reviews
        shop_reviews = Review.objects.filter(
            content_type__model="shop",
            object_id=shop_id,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get specialist reviews for the shop
        specialist_ids = Specialist.objects.filter(employee__shop_id=shop_id).values_list(
            "id", flat=True
        )

        specialist_reviews = Review.objects.filter(
            content_type__model="specialist",
            object_id__in=specialist_ids,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get service reviews for the shop
        service_ids = Service.objects.filter(shop_id=shop_id).values_list("id", flat=True)

        service_reviews = Review.objects.filter(
            content_type__model="service",
            object_id__in=service_ids,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Combine all reviews
        all_reviews = shop_reviews.union(specialist_reviews, service_reviews)

        # Group by appropriate time unit
        if group_by == "day":
            all_reviews = all_reviews.annotate(period=TruncDay("created_at"))
        elif group_by == "week":
            all_reviews = all_reviews.annotate(period=TruncWeek("created_at"))
        else:  # month
            all_reviews = all_reviews.annotate(period=TruncMonth("created_at"))

        # Aggregate by period
        data = all_reviews.values("period").annotate(count=Count("id")).order_by("period")

        # Format for time series
        result = []
        for item in data:
            result.append({"date": item["period"].strftime("%Y-%m-%d"), "count": item["count"]})

        return result

    @staticmethod
    def _get_ratings_time_series(shop_id, start_date, end_date, group_by="day"):
        """Generate average rating time series data"""
        # Get shop reviews
        shop_reviews = Review.objects.filter(
            content_type__model="shop",
            object_id=shop_id,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get specialist reviews for the shop
        specialist_ids = Specialist.objects.filter(employee__shop_id=shop_id).values_list(
            "id", flat=True
        )

        specialist_reviews = Review.objects.filter(
            content_type__model="specialist",
            object_id__in=specialist_ids,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get service reviews for the shop
        service_ids = Service.objects.filter(shop_id=shop_id).values_list("id", flat=True)

        service_reviews = Review.objects.filter(
            content_type__model="service",
            object_id__in=service_ids,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Combine all reviews
        all_reviews = shop_reviews.union(specialist_reviews, service_reviews)

        # Group by appropriate time unit
        if group_by == "day":
            all_reviews = all_reviews.annotate(period=TruncDay("created_at"))
        elif group_by == "week":
            all_reviews = all_reviews.annotate(period=TruncWeek("created_at"))
        else:  # month
            all_reviews = all_reviews.annotate(period=TruncMonth("created_at"))

        # Aggregate by period
        data = (
            all_reviews.values("period")
            .annotate(avg_rating=Avg("rating"), count=Count("id"))
            .order_by("period")
        )

        # Format for time series
        result = []
        for item in data:
            result.append(
                {
                    "date": item["period"].strftime("%Y-%m-%d"),
                    "average_rating": round(item["avg_rating"], 2),
                    "count": item["count"],
                }
            )

        return result

    @staticmethod
    def _calculate_percentage_change(current, previous):
        """Calculate percentage change between two values"""
        if previous == 0:
            return 100 if current > 0 else 0

        return round((current - previous) / previous * 100, 2)
