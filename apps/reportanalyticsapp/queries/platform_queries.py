# apps/reportanalyticsapp/queries/platform_queries.py

import logging

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce, TruncDate

from apps.authapp.models import User
from apps.bookingapp.models import Appointment
from apps.companiesapp.models import Company
from apps.followapp.models import Follow
from apps.payment.models import Transaction
from apps.queueapp.models import QueueTicket
from apps.reelsapp.models import Reel
from apps.reviewapp.models import Review
from apps.shopapp.models import Shop
from apps.storiesapp.models import Story
from apps.subscriptionapp.models import Subscription

logger = logging.getLogger(__name__)


class PlatformQueries:
    """
    Advanced queries for platform-wide analytics.
    For Queue Me admins to monitor overall platform performance.
    """

    def get_platform_usage(self, start_date, end_date):
        """
        Get platform-wide usage metrics.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            dict: Platform usage analytics
        """
        # Calculate active users
        active_users = User.objects.filter(
            last_login__gte=start_date, last_login__lt=end_date
        ).count()

        # Calculate new users
        new_users = User.objects.filter(
            date_joined__gte=start_date, date_joined__lt=end_date
        ).count()

        # Calculate user types
        customers = User.objects.filter(user_type="customer").count()
        employees = User.objects.filter(user_type="employee").count()
        admins = User.objects.filter(is_staff=True).count()

        # Calculate active companies and shops
        active_companies = (
            Company.objects.filter(
                Q(subscriptions__status="active")
                | Q(
                    shops__appointments__start_time__gte=start_date,
                    shops__appointments__start_time__lt=end_date,
                )
            )
            .distinct()
            .count()
        )

        active_shops = (
            Shop.objects.filter(
                Q(
                    appointments__start_time__gte=start_date,
                    appointments__start_time__lt=end_date,
                )
                | Q(
                    queue_tickets__join_time__gte=start_date,
                    queue_tickets__join_time__lt=end_date,
                )
            )
            .distinct()
            .count()
        )

        total_shops = Shop.objects.count()

        # Calculate appointment metrics
        total_appointments = Appointment.objects.filter(
            start_time__gte=start_date, start_time__lt=end_date
        ).count()

        completed_appointments = Appointment.objects.filter(
            start_time__gte=start_date, start_time__lt=end_date, status="completed"
        ).count()

        cancelled_appointments = Appointment.objects.filter(
            start_time__gte=start_date, start_time__lt=end_date, status="cancelled"
        ).count()

        # Calculate completion and cancellation rates
        completion_rate = 0
        cancellation_rate = 0

        if total_appointments > 0:
            completion_rate = (completed_appointments / total_appointments) * 100
            cancellation_rate = (cancelled_appointments / total_appointments) * 100

        # Calculate queue metrics
        total_queue_tickets = QueueTicket.objects.filter(
            join_time__gte=start_date, join_time__lt=end_date
        ).count()

        served_tickets = QueueTicket.objects.filter(
            join_time__gte=start_date, join_time__lt=end_date, status="served"
        ).count()

        # Calculate queue service rate
        queue_service_rate = 0
        if total_queue_tickets > 0:
            queue_service_rate = (served_tickets / total_queue_tickets) * 100

        # Calculate content metrics
        total_reels = Reel.objects.filter(
            created_at__gte=start_date, created_at__lt=end_date
        ).count()

        total_stories = Story.objects.filter(
            created_at__gte=start_date, created_at__lt=end_date
        ).count()

        # Calculate review metrics
        total_reviews = Review.objects.filter(
            created_at__gte=start_date, created_at__lt=end_date
        ).count()

        avg_platform_rating = (
            Review.objects.filter(
                created_at__gte=start_date, created_at__lt=end_date
            ).aggregate(avg=Coalesce(Avg("rating"), 0))["avg"]
            or 0
        )

        # Calculate follow metrics
        total_follows = Follow.objects.filter(
            created_at__gte=start_date, created_at__lt=end_date
        ).count()

        # Calculate subscription metrics
        active_subscriptions = Subscription.objects.filter(
            Q(status="active")
            & (
                Q(current_period_start__lte=end_date)
                & (Q(current_period_end__gte=start_date) | Q(current_period_end=None))
            )
        ).count()

        new_subscriptions = Subscription.objects.filter(
            created_at__gte=start_date, created_at__lt=end_date
        ).count()

        expired_subscriptions = Subscription.objects.filter(
            status="expired",
            current_period_end__gte=start_date,
            current_period_end__lt=end_date,
        ).count()

        # Calculate subscription revenue
        subscription_revenue = (
            Transaction.objects.filter(
                transaction_type="subscription",
                created_at__gte=start_date,
                created_at__lt=end_date,
                status="succeeded",
            ).aggregate(total=Coalesce(Sum("amount"), 0))["total"]
            or 0
        )

        # Calculate ad revenue
        ad_revenue = (
            Transaction.objects.filter(
                transaction_type="ad",
                created_at__gte=start_date,
                created_at__lt=end_date,
                status="succeeded",
            ).aggregate(total=Coalesce(Sum("amount"), 0))["total"]
            or 0
        )

        # Calculate total revenue
        total_revenue = subscription_revenue + ad_revenue

        # Calculate daily active users trend
        daily_active_users = (
            User.objects.filter(last_login__gte=start_date, last_login__lt=end_date)
            .annotate(date=TruncDate("last_login"))
            .values("date")
            .annotate(count=Count("id", distinct=True))
            .order_by("date")
        )

        # Format as time series
        dau_series = {}
        for entry in daily_active_users:
            date_str = entry["date"].isoformat()
            dau_series[date_str] = entry["count"]

        # Calculate daily new users trend
        daily_new_users = (
            User.objects.filter(date_joined__gte=start_date, date_joined__lt=end_date)
            .annotate(date=TruncDate("date_joined"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        # Format as time series
        new_users_series = {}
        for entry in daily_new_users:
            date_str = entry["date"].isoformat()
            new_users_series[date_str] = entry["count"]

        # Calculate daily appointments trend
        daily_appointments = (
            Appointment.objects.filter(
                start_time__gte=start_date, start_time__lt=end_date
            )
            .annotate(date=TruncDate("start_time"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        # Format as time series
        appointment_series = {}
        for entry in daily_appointments:
            date_str = entry["date"].isoformat()
            appointment_series[date_str] = entry["count"]

        # Calculate subscription plan distribution
        plan_distribution = (
            Subscription.objects.filter(status="active")
            .values("plan__id", "plan__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        plan_data = []
        for plan in plan_distribution:
            if plan["plan__id"] and plan["plan__name"]:
                plan_data.append(
                    {
                        "id": plan["plan__id"],
                        "name": plan["plan__name"],
                        "count": plan["count"],
                    }
                )

        # Format results
        result = {
            "entity_type": "platform",
            "metrics": {
                "active_users": active_users,
                "new_users": new_users,
                "customers": customers,
                "employees": employees,
                "admins": admins,
                "active_companies": active_companies,
                "active_shops": active_shops,
                "total_shops": total_shops,
                "total_appointments": total_appointments,
                "completed_appointments": completed_appointments,
                "cancelled_appointments": cancelled_appointments,
                "completion_rate": round(completion_rate, 2),
                "cancellation_rate": round(cancellation_rate, 2),
                "total_queue_tickets": total_queue_tickets,
                "served_tickets": served_tickets,
                "queue_service_rate": round(queue_service_rate, 2),
                "total_reels": total_reels,
                "total_stories": total_stories,
                "total_reviews": total_reviews,
                "avg_platform_rating": round(avg_platform_rating, 2),
                "total_follows": total_follows,
                "active_subscriptions": active_subscriptions,
                "new_subscriptions": new_subscriptions,
                "expired_subscriptions": expired_subscriptions,
                "subscription_revenue": subscription_revenue,
                "ad_revenue": ad_revenue,
                "total_revenue": total_revenue,
            },
            "time_series": {
                "daily_active_users": dau_series,
                "daily_new_users": new_users_series,
                "daily_appointments": appointment_series,
            },
            "subscription_plans": plan_data,
        }

        return result
