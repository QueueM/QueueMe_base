# apps/reportanalyticsapp/services/dashboard_service.py
"""
Dashboard Service

Provides real-time metrics and visualization data for interactive dashboards.
Powers shop dashboard, admin dashboard, and specialist dashboards with
current performance indicators and actionable insights.
"""

from datetime import datetime, timedelta

from django.db.models import Avg, Case, Count, Sum, When
from django.db.models.functions import Extract, TruncDay, TruncHour
from django.utils import timezone

from apps.authapp.models import User
from apps.bookingapp.models import Appointment
from apps.queueapp.models import Queue, QueueTicket
from apps.reportanalyticsapp.services.analytics_service import AnalyticsService
from apps.reportanalyticsapp.services.anomaly_detector import AnomalyDetector
from apps.reviewapp.models import Review
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist, SpecialistService
from core.cache.cache_manager import cache_with_key_prefix


class DashboardService:
    """
    Service for generating real-time dashboard data and visualizations.
    """

    @staticmethod
    @cache_with_key_prefix("shop_dashboard", timeout=300)  # Cache for 5 minutes
    def get_shop_dashboard_data(shop_id):
        """
        Get comprehensive dashboard data for a shop.

        Args:
            shop_id (uuid): The shop ID to analyze

        Returns:
            dict: Complete dashboard data for shop overview
        """
        # Get shop
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return {"error": "Shop not found"}

        # Get current date for filtering
        now = timezone.now()
        today_start = timezone.make_aware(
            datetime.combine(now.date(), datetime.min.time())
        )
        today_end = timezone.make_aware(
            datetime.combine(now.date(), datetime.max.time())
        )

        # Get week and month date ranges
        week_start = today_start - timedelta(days=now.weekday())
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

        month_start = today_start.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(
                year=month_start.year + 1, month=1, day=1
            ) - timedelta(days=1)
        else:
            month_end = month_start.replace(
                month=month_start.month + 1, day=1
            ) - timedelta(days=1)
        month_end = timezone.make_aware(
            datetime.combine(month_end, datetime.max.time())
        )

        # Dashboard sections:
        # 1. Overview cards with key metrics
        overview = DashboardService._get_shop_overview(
            shop_id,
            today_start,
            today_end,
            week_start,
            week_end,
            month_start,
            month_end,
        )

        # 2. Today's schedule
        todays_schedule = DashboardService._get_todays_schedule(
            shop_id, today_start, today_end
        )

        # 3. Live queue status
        queue_status = DashboardService._get_queue_status(shop_id)

        # 4. Revenue chart (weekly)
        revenue_chart = DashboardService._get_revenue_chart(
            shop_id, week_start, week_end
        )

        # 5. Appointment statistics by day of week
        appointment_stats = DashboardService._get_appointment_stats_by_day(
            shop_id, week_start - timedelta(days=28), week_end
        )

        # 6. Service popularity
        service_popularity = DashboardService._get_service_popularity(
            shop_id, month_start, month_end
        )

        # 7. Specialist performance
        specialist_performance = DashboardService._get_specialist_performance(
            shop_id, month_start, month_end
        )

        # 8. Recent reviews
        recent_reviews = DashboardService._get_recent_reviews(shop_id, limit=5)

        # 9. Alerts and recommendations
        alerts = DashboardService._get_alerts_and_recommendations(shop_id)

        return {
            "shop_id": str(shop_id),
            "shop_name": shop.name,
            "timestamp": now,
            "overview": overview,
            "todays_schedule": todays_schedule,
            "queue_status": queue_status,
            "revenue_chart": revenue_chart,
            "appointment_stats": appointment_stats,
            "service_popularity": service_popularity,
            "specialist_performance": specialist_performance,
            "recent_reviews": recent_reviews,
            "alerts": alerts,
        }

    @staticmethod
    def get_specialist_dashboard_data(specialist_id):
        """
        Get dashboard data for a specific specialist.

        Args:
            specialist_id (uuid): The specialist ID to analyze

        Returns:
            dict: Dashboard data for specialist overview
        """
        # Get specialist
        try:
            specialist = Specialist.objects.get(id=specialist_id)
            shop_id = specialist.employee.shop_id
        except Specialist.DoesNotExist:
            return {"error": "Specialist not found"}

        # Get current date for filtering
        now = timezone.now()
        today_start = timezone.make_aware(
            datetime.combine(now.date(), datetime.min.time())
        )
        today_end = timezone.make_aware(
            datetime.combine(now.date(), datetime.max.time())
        )

        # Get week and month date ranges
        week_start = today_start - timedelta(days=now.weekday())
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

        month_start = today_start.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(
                year=month_start.year + 1, month=1, day=1
            ) - timedelta(days=1)
        else:
            month_end = month_start.replace(
                month=month_start.month + 1, day=1
            ) - timedelta(days=1)
        month_end = timezone.make_aware(
            datetime.combine(month_end, datetime.max.time())
        )

        # Dashboard sections:
        # 1. Overview cards with key metrics
        overview = DashboardService._get_specialist_overview(
            specialist_id,
            today_start,
            today_end,
            week_start,
            week_end,
            month_start,
            month_end,
        )

        # 2. Today's schedule
        todays_schedule = DashboardService._get_specialist_schedule(
            specialist_id, today_start, today_end
        )

        # 3. Bookings chart (weekly)
        bookings_chart = DashboardService._get_specialist_bookings_chart(
            specialist_id, week_start, week_end
        )

        # 4. Service distribution
        service_distribution = DashboardService._get_specialist_service_distribution(
            specialist_id, month_start, month_end
        )

        # 5. Recent reviews
        recent_reviews = DashboardService._get_specialist_reviews(
            specialist_id, limit=5
        )

        # 6. Performance comparison with other specialists
        performance_comparison = DashboardService._get_specialist_comparison(
            specialist_id, shop_id, month_start, month_end
        )

        return {
            "specialist_id": str(specialist_id),
            "specialist_name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
            "shop_id": str(shop_id),
            "timestamp": now,
            "overview": overview,
            "todays_schedule": todays_schedule,
            "bookings_chart": bookings_chart,
            "service_distribution": service_distribution,
            "recent_reviews": recent_reviews,
            "performance_comparison": performance_comparison,
        }

    @staticmethod
    def get_admin_dashboard_data():
        """
        Get dashboard data for Queue Me admin overview.

        Returns:
            dict: Dashboard data for platform overview
        """
        # Get current date for filtering
        now = timezone.now()
        today_start = timezone.make_aware(
            datetime.combine(now.date(), datetime.min.time())
        )
        today_end = timezone.make_aware(
            datetime.combine(now.date(), datetime.max.time())
        )

        # Get week and month date ranges
        week_start = today_start - timedelta(days=now.weekday())
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

        month_start = today_start.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(
                year=month_start.year + 1, month=1, day=1
            ) - timedelta(days=1)
        else:
            month_end = month_start.replace(
                month=month_start.month + 1, day=1
            ) - timedelta(days=1)
        month_end = timezone.make_aware(
            datetime.combine(month_end, datetime.max.time())
        )

        # Dashboard sections:
        # 1. Platform overview
        platform_overview = DashboardService._get_platform_overview(
            today_start, today_end, week_start, week_end, month_start, month_end
        )

        # 2. Shops growth chart
        shops_growth = DashboardService._get_shops_growth_chart(
            month_start - timedelta(days=365), month_end
        )

        # 3. User growth chart
        users_growth = DashboardService._get_users_growth_chart(
            month_start - timedelta(days=365), month_end
        )

        # 4. Revenue breakdown
        revenue_breakdown = DashboardService._get_revenue_breakdown(
            month_start, month_end
        )

        # 5. Top performing shops
        top_shops = DashboardService._get_top_performing_shops(month_start, month_end)

        # 6. Popular categories
        popular_categories = DashboardService._get_popular_categories(
            month_start, month_end
        )

        # 7. System health
        system_health = DashboardService._get_system_health()

        # 8. Recent activities
        recent_activities = DashboardService._get_recent_admin_activities(limit=10)

        return {
            "timestamp": now,
            "platform_overview": platform_overview,
            "shops_growth": shops_growth,
            "users_growth": users_growth,
            "revenue_breakdown": revenue_breakdown,
            "top_shops": top_shops,
            "popular_categories": popular_categories,
            "system_health": system_health,
            "recent_activities": recent_activities,
        }

    @staticmethod
    def get_real_time_metrics(shop_id=None, specialist_id=None):
        """
        Get real-time metrics for a shop or specialist.

        Args:
            shop_id (uuid, optional): The shop ID to analyze
            specialist_id (uuid, optional): The specialist ID to analyze

        Returns:
            dict: Real-time metrics
        """
        now = timezone.now()

        if shop_id:
            # Get real-time metrics for a shop

            # Active appointments (in progress)
            active_appointments = Appointment.objects.filter(
                shop_id=shop_id, status="in_progress"
            ).count()

            # Upcoming appointments today
            upcoming_appointments = Appointment.objects.filter(
                shop_id=shop_id,
                start_time__date=now.date(),
                start_time__gt=now,
                status="scheduled",
            ).count()

            # Queue status
            queues = Queue.objects.filter(shop_id=shop_id, status="open")

            waiting_customers = QueueTicket.objects.filter(
                queue__in=queues, status="waiting"
            ).count()

            # Active specialists
            active_specialists = Specialist.objects.filter(
                employee__shop_id=shop_id, employee__is_active=True
            ).count()

            return {
                "shop_id": str(shop_id),
                "timestamp": now,
                "active_appointments": active_appointments,
                "upcoming_appointments": upcoming_appointments,
                "waiting_customers": waiting_customers,
                "active_specialists": active_specialists,
                "estimated_wait_time": DashboardService._estimate_average_wait_time(
                    shop_id
                ),
            }

        elif specialist_id:
            # Get real-time metrics for a specialist

            try:
                specialist = Specialist.objects.get(id=specialist_id)
                shop_id = specialist.employee.shop_id
            except Specialist.DoesNotExist:
                return {"error": "Specialist not found"}

            # Active appointment
            active_appointment = Appointment.objects.filter(
                specialist_id=specialist_id, status="in_progress"
            ).first()

            # Next appointment
            next_appointment = (
                Appointment.objects.filter(
                    specialist_id=specialist_id, start_time__gt=now, status="scheduled"
                )
                .order_by("start_time")
                .first()
            )

            # Today's remaining appointments
            remaining_appointments = Appointment.objects.filter(
                specialist_id=specialist_id,
                start_time__date=now.date(),
                start_time__gt=now,
                status="scheduled",
            ).count()

            return {
                "specialist_id": str(specialist_id),
                "shop_id": str(shop_id),
                "timestamp": now,
                "is_active": specialist.employee.is_active,
                "current_appointment": (
                    {
                        "id": (
                            str(active_appointment.id) if active_appointment else None
                        ),
                        "service": (
                            active_appointment.service.name
                            if active_appointment
                            else None
                        ),
                        "customer": (
                            active_appointment.customer.phone_number
                            if active_appointment
                            else None
                        ),
                        "end_time": (
                            active_appointment.end_time if active_appointment else None
                        ),
                    }
                    if active_appointment
                    else None
                ),
                "next_appointment": (
                    {
                        "id": str(next_appointment.id) if next_appointment else None,
                        "service": (
                            next_appointment.service.name if next_appointment else None
                        ),
                        "start_time": (
                            next_appointment.start_time if next_appointment else None
                        ),
                    }
                    if next_appointment
                    else None
                ),
                "remaining_appointments": remaining_appointments,
            }

        return {"error": "Either shop_id or specialist_id must be provided"}

    @staticmethod
    def get_custom_dashboard(shop_id, metrics, start_date=None, end_date=None):
        """
        Get customized dashboard data with selected metrics.

        Args:
            shop_id (uuid): The shop ID to analyze
            metrics (list): List of metric names to include
            start_date (datetime, optional): Start date for analysis
            end_date (datetime, optional): End date for analysis

        Returns:
            dict: Custom dashboard data with selected metrics
        """
        # Get shop
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return {"error": "Shop not found"}

        # Set default date range if not provided
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Initialize result dictionary
        result = {
            "shop_id": str(shop_id),
            "shop_name": shop.name,
            "period": {"start_date": start_date, "end_date": end_date},
            "metrics": {},
        }

        # Get requested metrics
        available_metrics = {
            "appointments": DashboardService._get_appointment_metrics,
            "revenue": DashboardService._get_revenue_metrics,
            "reviews": DashboardService._get_review_metrics,
            "queue": DashboardService._get_queue_metrics,
            "specialists": DashboardService._get_specialist_metrics,
            "services": DashboardService._get_service_metrics,
            "customers": DashboardService._get_customer_metrics,
            "comparison": DashboardService._get_comparison_metrics,
        }

        for metric in metrics:
            if metric in available_metrics:
                result["metrics"][metric] = available_metrics[metric](
                    shop_id, start_date, end_date
                )

        return result

    # Private helper methods

    @staticmethod
    def _get_shop_overview(
        shop_id, today_start, today_end, week_start, week_end, month_start, month_end
    ):
        """Get overview metrics for a shop dashboard"""
        # Today's appointments
        today_appointments = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=today_start, start_time__lte=today_end
        )

        today_appointment_count = today_appointments.count()
        completed_today = today_appointments.filter(status="completed").count()
        cancelled_today = today_appointments.filter(status="cancelled").count()

        # Today's queue
        today_queue_tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id, join_time__gte=today_start, join_time__lte=today_end
        )

        today_queue_count = today_queue_tickets.count()
        served_today = today_queue_tickets.filter(status="served").count()

        # Today's revenue
        today_revenue = 0
        for appointment in today_appointments.filter(status="completed"):
            today_revenue += appointment.service.price

        # This week's revenue
        week_appointments = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=week_start,
            start_time__lte=week_end,
            status="completed",
        )

        week_revenue = 0
        for appointment in week_appointments:
            week_revenue += appointment.service.price

        # This month's revenue
        month_appointments = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=month_start,
            start_time__lte=month_end,
            status="completed",
        )

        month_revenue = 0
        for appointment in month_appointments:
            month_revenue += appointment.service.price

        # Recent ratings
        recent_reviews = Review.objects.filter(
            content_type__model="shop",
            object_id=shop_id,
            created_at__gte=week_start,
            created_at__lte=week_end,
        )

        avg_rating = (
            recent_reviews.aggregate(avg_rating=Avg("rating"))["avg_rating"] or 0
        )

        return {
            "today_appointments": today_appointment_count,
            "completed_today": completed_today,
            "cancelled_today": cancelled_today,
            "today_queue": today_queue_count,
            "served_today": served_today,
            "today_revenue": round(today_revenue, 2),
            "week_revenue": round(week_revenue, 2),
            "month_revenue": round(month_revenue, 2),
            "recent_rating": round(avg_rating, 2),
        }

    @staticmethod
    def _get_todays_schedule(shop_id, today_start, today_end):
        """Get today's appointment schedule for a shop"""
        appointments = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=today_start, start_time__lte=today_end
        ).order_by("start_time")

        result = []

        for appointment in appointments:
            result.append(
                {
                    "id": str(appointment.id),
                    "customer_name": appointment.customer.phone_number,  # Using phone as fallback
                    "service": appointment.service.name,
                    "specialist": f"{appointment.specialist.employee.first_name} {appointment.specialist.employee.last_name}",
                    "start_time": appointment.start_time.strftime(
                        "%I:%M %p"
                    ),  # 12-hour format with AM/PM
                    "end_time": appointment.end_time.strftime("%I:%M %p"),
                    "status": appointment.status,
                    "is_checked_in": appointment.check_in_time is not None,
                }
            )

        return result

    @staticmethod
    def _get_queue_status(shop_id):
        """Get current queue status for a shop"""
        queues = Queue.objects.filter(shop_id=shop_id)

        result = []

        for queue in queues:
            # Get waiting tickets
            waiting_tickets = QueueTicket.objects.filter(
                queue=queue, status="waiting"
            ).order_by("position")

            # Get currently serving tickets
            serving_tickets = QueueTicket.objects.filter(
                queue=queue, status__in=["called", "serving"]
            )

            queue_data = {
                "id": str(queue.id),
                "name": queue.name,
                "status": queue.status,
                "waiting_count": waiting_tickets.count(),
                "serving_count": serving_tickets.count(),
                "estimated_wait_time": DashboardService._estimate_average_wait_time(
                    shop_id, queue.id
                ),
                "next_in_line": None,
            }

            # Get next in line
            if waiting_tickets.exists():
                next_ticket = waiting_tickets.first()
                queue_data["next_in_line"] = {
                    "ticket_id": str(next_ticket.id),
                    "ticket_number": next_ticket.ticket_number,
                    "customer_name": next_ticket.customer.phone_number,  # Using phone as fallback
                    "wait_time_minutes": (
                        timezone.now() - next_ticket.join_time
                    ).total_seconds()
                    / 60,
                    "position": next_ticket.position,
                }

            result.append(queue_data)

        return result

    @staticmethod
    def _estimate_average_wait_time(shop_id, queue_id=None):
        """Estimate average wait time for a queue"""
        # Get recent served tickets to calculate average wait time
        filters = {"queue__shop_id": shop_id, "status": "served"}

        if queue_id:
            filters["queue_id"] = queue_id

        recent_tickets = QueueTicket.objects.filter(
            **filters,
            serve_time__isnull=False,
            join_time__isnull=False,
            serve_time__gte=timezone.now() - timedelta(hours=24),  # Last 24 hours
        )

        if not recent_tickets.exists():
            return 0  # No recent data

        # Calculate average wait time
        total_wait_time = 0
        count = 0

        for ticket in recent_tickets:
            wait_time = (
                ticket.serve_time - ticket.join_time
            ).total_seconds() / 60  # in minutes
            total_wait_time += wait_time
            count += 1

        if count == 0:
            return 0

        avg_wait_time = total_wait_time / count

        # Get number of waiting tickets and active specialists
        waiting_tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id, status="waiting"
        ).count()

        active_specialists = Specialist.objects.filter(
            employee__shop_id=shop_id, employee__is_active=True
        ).count()

        # Adjust wait time based on waiting tickets and available specialists
        if active_specialists > 0:
            estimated_wait = (avg_wait_time * waiting_tickets) / active_specialists
        else:
            estimated_wait = avg_wait_time * waiting_tickets

        return round(estimated_wait, 0)

    @staticmethod
    def _get_revenue_chart(shop_id, start_date, end_date):
        """Get revenue chart data for a shop"""
        # Get completed appointments
        appointments = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_date,
            start_time__lte=end_date,
            status="completed",
        )

        # Group by day
        appointments = appointments.annotate(day=TruncDay("start_time"))

        # Initialize revenue by day
        revenue_by_day = {}

        # Loop through each day in the range
        current_date = start_date.date()
        while current_date <= end_date.date():
            revenue_by_day[current_date.strftime("%Y-%m-%d")] = 0
            current_date += timedelta(days=1)

        # Calculate revenue for each appointment and add to the appropriate day
        for appointment in appointments:
            day_key = appointment.day.strftime("%Y-%m-%d")
            revenue_by_day[day_key] += appointment.service.price

        # Format for chart
        chart_data = {
            "labels": list(revenue_by_day.keys()),
            "datasets": [
                {"label": "Revenue (SAR)", "data": list(revenue_by_day.values())}
            ],
        }

        return chart_data

    @staticmethod
    def _get_appointment_stats_by_day(shop_id, start_date, end_date):
        """Get appointment statistics by day of week"""
        # Get all appointments in the period
        appointments = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lte=end_date
        )

        # Group by day of week
        appointments_by_day = (
            appointments.annotate(day_of_week=Extract("start_time", "dow"))
            .values("day_of_week")
            .annotate(
                total=Count("id"),
                completed=Count(Case(When(status="completed", then=1))),
                cancelled=Count(Case(When(status="cancelled", then=1))),
                no_show=Count(Case(When(status="no_show", then=1))),
            )
            .order_by("day_of_week")
        )

        # Format result
        result = {}
        day_names = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]

        for i, name in enumerate(day_names):
            # Find stats for this day
            day_stats = next(
                (stats for stats in appointments_by_day if stats["day_of_week"] == i),
                None,
            )

            if day_stats:
                result[name] = {
                    "total": day_stats["total"],
                    "completed": day_stats["completed"],
                    "cancelled": day_stats["cancelled"],
                    "no_show": day_stats["no_show"],
                    "completion_rate": (
                        round((day_stats["completed"] / day_stats["total"] * 100), 2)
                        if day_stats["total"] > 0
                        else 0
                    ),
                }
            else:
                result[name] = {
                    "total": 0,
                    "completed": 0,
                    "cancelled": 0,
                    "no_show": 0,
                    "completion_rate": 0,
                }

        return result

    @staticmethod
    def _get_service_popularity(shop_id, start_date, end_date):
        """Get service popularity metrics"""
        # Get services
        services = Service.objects.filter(shop_id=shop_id, is_active=True)

        result = []

        for service in services:
            # Get appointments for this service
            appointments = Appointment.objects.filter(
                service=service, start_time__gte=start_date, start_time__lte=end_date
            )

            # Calculate metrics
            total_bookings = appointments.count()
            completed_bookings = appointments.filter(status="completed").count()

            # Calculate revenue
            revenue = service.price * completed_bookings

            # Get reviews
            reviews = Review.objects.filter(
                content_type__model="service",
                object_id=service.id,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )

            avg_rating = reviews.aggregate(avg_rating=Avg("rating"))["avg_rating"] or 0

            result.append(
                {
                    "id": str(service.id),
                    "name": service.name,
                    "bookings": total_bookings,
                    "completed": completed_bookings,
                    "revenue": round(revenue, 2),
                    "rating": round(avg_rating, 2),
                    "duration": service.duration,
                    "price": service.price,
                }
            )

        # Sort by bookings (descending)
        result.sort(key=lambda x: x["bookings"], reverse=True)

        return result

    @staticmethod
    def _get_specialist_performance(shop_id, start_date, end_date):
        """Get specialist performance metrics"""
        # Get specialists
        specialists = Specialist.objects.filter(
            employee__shop_id=shop_id, employee__is_active=True
        )

        result = []

        for specialist in specialists:
            # Get appointments for this specialist
            appointments = Appointment.objects.filter(
                specialist=specialist,
                start_time__gte=start_date,
                start_time__lte=end_date,
            )

            # Calculate metrics
            total_bookings = appointments.count()
            completed_bookings = appointments.filter(status="completed").count()
            cancelled_bookings = appointments.filter(status="cancelled").count()
            no_show_bookings = appointments.filter(status="no_show").count()

            # Calculate completion rate
            completion_rate = (
                (completed_bookings / total_bookings * 100) if total_bookings > 0 else 0
            )

            # Get reviews
            reviews = Review.objects.filter(
                content_type__model="specialist",
                object_id=specialist.id,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )

            avg_rating = reviews.aggregate(avg_rating=Avg("rating"))["avg_rating"] or 0

            result.append(
                {
                    "id": str(specialist.id),
                    "name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
                    "bookings": total_bookings,
                    "completed": completed_bookings,
                    "cancelled": cancelled_bookings,
                    "no_show": no_show_bookings,
                    "completion_rate": round(completion_rate, 2),
                    "rating": round(avg_rating, 2),
                }
            )

        # Sort by bookings (descending)
        result.sort(key=lambda x: x["bookings"], reverse=True)

        return result

    @staticmethod
    def _get_recent_reviews(shop_id, limit=5):
        """Get recent reviews for a shop"""
        # Get shop reviews
        shop_reviews = Review.objects.filter(
            content_type__model="shop", object_id=shop_id
        )

        # Get specialist reviews for the shop
        specialist_ids = Specialist.objects.filter(
            employee__shop_id=shop_id
        ).values_list("id", flat=True)

        specialist_reviews = Review.objects.filter(
            content_type__model="specialist", object_id__in=specialist_ids
        )

        # Get service reviews for the shop
        service_ids = Service.objects.filter(shop_id=shop_id).values_list(
            "id", flat=True
        )

        service_reviews = Review.objects.filter(
            content_type__model="service", object_id__in=service_ids
        )

        # Combine all reviews
        all_reviews = shop_reviews.union(specialist_reviews, service_reviews).order_by(
            "-created_at"
        )[:limit]

        result = []

        for review in all_reviews:
            # Get target type and name
            target_type = review.content_type.model
            target_name = "Unknown"

            if target_type == "shop":
                try:
                    shop = Shop.objects.get(id=review.object_id)
                    target_name = shop.name
                except Shop.DoesNotExist:
                    pass
            elif target_type == "specialist":
                try:
                    specialist = Specialist.objects.get(id=review.object_id)
                    target_name = f"{specialist.employee.first_name} {specialist.employee.last_name}"
                except Specialist.DoesNotExist:
                    pass
            elif target_type == "service":
                try:
                    service = Service.objects.get(id=review.object_id)
                    target_name = service.name
                except Service.DoesNotExist:
                    pass

            result.append(
                {
                    "id": str(review.id),
                    "target_type": target_type,
                    "target_name": target_name,
                    "customer_name": review.customer.phone_number,  # Using phone as fallback
                    "rating": review.rating,
                    "comment": review.comment,
                    "created_at": review.created_at,
                }
            )

        return result

    @staticmethod
    def _get_alerts_and_recommendations(shop_id):
        """Get alerts and recommendations for a shop"""
        alerts = []

        # Check for appointment anomalies
        appointment_anomalies = AnomalyDetector.detect_anomalies(
            shop_id, "appointment_count"
        )

        if (
            "anomalies" in appointment_anomalies
            and len(appointment_anomalies["anomalies"]["combined"]) > 0
        ):
            for anomaly in appointment_anomalies["anomalies"]["combined"]:
                if anomaly["direction"] == "low":
                    alerts.append(
                        {
                            "type": "warning",
                            "message": f"Unusually low appointment bookings detected on {anomaly['date']}",
                            "recommendation": "Consider running a promotion or special offer to boost bookings.",
                        }
                    )

        # Check for cancellation anomalies
        cancellation_anomalies = AnomalyDetector.detect_anomalies(
            shop_id, "cancellation_rate"
        )

        if (
            "anomalies" in cancellation_anomalies
            and len(cancellation_anomalies["anomalies"]["combined"]) > 0
        ):
            for anomaly in cancellation_anomalies["anomalies"]["combined"]:
                if anomaly["direction"] == "high":
                    alerts.append(
                        {
                            "type": "warning",
                            "message": f"Unusually high cancellation rate detected on {anomaly['date']}",
                            "recommendation": "Review your cancellation policy and consider additional appointment reminders.",
                        }
                    )

        # Check for long wait times
        wait_time_anomalies = AnomalyDetector.detect_anomalies(shop_id, "wait_time")

        if (
            "anomalies" in wait_time_anomalies
            and len(wait_time_anomalies["anomalies"]["combined"]) > 0
        ):
            for anomaly in wait_time_anomalies["anomalies"]["combined"]:
                if anomaly["direction"] == "high":
                    alerts.append(
                        {
                            "type": "warning",
                            "message": f"Unusually long wait times detected on {anomaly['date']}",
                            "recommendation": "Consider adding more staff during peak hours.",
                        }
                    )

        # Check for low ratings
        rating_anomalies = AnomalyDetector.detect_anomalies(shop_id, "ratings")

        if (
            "anomalies" in rating_anomalies
            and len(rating_anomalies["anomalies"]["combined"]) > 0
        ):
            for anomaly in rating_anomalies["anomalies"]["combined"]:
                if anomaly["direction"] == "low":
                    alerts.append(
                        {
                            "type": "alert",
                            "message": f"Unusually low ratings received on {anomaly['date']}",
                            "recommendation": "Review customer feedback and address any service quality issues.",
                        }
                    )

        # General recommendations (if no specific issues)
        if len(alerts) == 0:
            # Get underutilized time slots
            now = timezone.now()
            week_start = now - timedelta(days=now.weekday())
            week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

            appointments_by_hour = (
                Appointment.objects.filter(
                    shop_id=shop_id,
                    start_time__gte=week_start - timedelta(days=28),  # Last 4 weeks
                    start_time__lte=week_end,
                )
                .annotate(
                    hour=TruncHour("start_time"), weekday=Extract("start_time", "dow")
                )
                .values("hour", "weekday")
                .annotate(count=Count("id"))
                .order_by("weekday", "hour")
            )

            # Find hours with low booking counts
            low_booking_slots = []

            for slot in appointments_by_hour:
                if slot["count"] <= 2:  # Arbitrary threshold
                    day_name = [
                        "Sunday",
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                    ][slot["weekday"]]
                    hour_str = datetime.strptime(str(slot["hour"]), "%H").strftime(
                        "%I %p"
                    )  # 12-hour format

                    low_booking_slots.append(f"{day_name} at {hour_str}")

            if low_booking_slots:
                alerts.append(
                    {
                        "type": "info",
                        "message": f"Underutilized time slots detected: {', '.join(low_booking_slots[:3])}",
                        "recommendation": "Consider promotional offers during these times to increase bookings.",
                    }
                )

            # Add general recommendation
            alerts.append(
                {
                    "type": "info",
                    "message": "Everything is running smoothly!",
                    "recommendation": "Regularly check your service metrics to maintain high performance.",
                }
            )

        return alerts

    @staticmethod
    def _get_specialist_overview(
        specialist_id,
        today_start,
        today_end,
        week_start,
        week_end,
        month_start,
        month_end,
    ):
        """Get overview metrics for a specialist dashboard"""
        # Today's appointments
        today_appointments = Appointment.objects.filter(
            specialist_id=specialist_id,
            start_time__gte=today_start,
            start_time__lte=today_end,
        )

        today_appointment_count = today_appointments.count()
        completed_today = today_appointments.filter(status="completed").count()

        # Week's appointments
        week_appointments = Appointment.objects.filter(
            specialist_id=specialist_id,
            start_time__gte=week_start,
            start_time__lte=week_end,
        )

        week_appointment_count = week_appointments.count()
        completed_week = week_appointments.filter(status="completed").count()

        # Month's appointments
        month_appointments = Appointment.objects.filter(
            specialist_id=specialist_id,
            start_time__gte=month_start,
            start_time__lte=month_end,
        )

        month_appointment_count = month_appointments.count()

        # Calculate completion rate
        completion_rate = (
            (completed_week / week_appointment_count * 100)
            if week_appointment_count > 0
            else 0
        )

        # Recent ratings
        recent_reviews = Review.objects.filter(
            content_type__model="specialist",
            object_id=specialist_id,
            created_at__gte=week_start,
            created_at__lte=week_end,
        )

        avg_rating = (
            recent_reviews.aggregate(avg_rating=Avg("rating"))["avg_rating"] or 0
        )

        return {
            "today_appointments": today_appointment_count,
            "completed_today": completed_today,
            "week_appointments": week_appointment_count,
            "completed_week": completed_week,
            "month_appointments": month_appointment_count,
            "completion_rate": round(completion_rate, 2),
            "recent_rating": round(avg_rating, 2),
        }

    @staticmethod
    def _get_specialist_schedule(specialist_id, today_start, today_end):
        """Get today's appointment schedule for a specialist"""
        appointments = Appointment.objects.filter(
            specialist_id=specialist_id,
            start_time__gte=today_start,
            start_time__lte=today_end,
        ).order_by("start_time")

        result = []

        for appointment in appointments:
            result.append(
                {
                    "id": str(appointment.id),
                    "customer_name": appointment.customer.phone_number,  # Using phone as fallback
                    "service": appointment.service.name,
                    "start_time": appointment.start_time.strftime(
                        "%I:%M %p"
                    ),  # 12-hour format with AM/PM
                    "end_time": appointment.end_time.strftime("%I:%M %p"),
                    "status": appointment.status,
                    "is_checked_in": appointment.check_in_time is not None,
                }
            )

        return result

    @staticmethod
    def _get_specialist_bookings_chart(specialist_id, start_date, end_date):
        """Get bookings chart data for a specialist"""
        # Get appointments
        appointments = Appointment.objects.filter(
            specialist_id=specialist_id,
            start_time__gte=start_date,
            start_time__lte=end_date,
        )

        # Group by day
        appointments = (
            appointments.annotate(day=TruncDay("start_time"))
            .values("day")
            .annotate(
                total=Count("id"),
                completed=Count(Case(When(status="completed", then=1))),
                cancelled=Count(Case(When(status="cancelled", then=1))),
                no_show=Count(Case(When(status="no_show", then=1))),
            )
            .order_by("day")
        )

        # Initialize data by day
        days = []
        total_data = []
        completed_data = []
        cancelled_data = []
        no_show_data = []

        # Loop through each day in the range
        current_date = start_date.date()
        while current_date <= end_date.date():
            day_key = current_date.strftime("%Y-%m-%d")
            days.append(day_key)

            # Find stats for this day
            day_stats = next(
                (
                    stats
                    for stats in appointments
                    if stats["day"].strftime("%Y-%m-%d") == day_key
                ),
                None,
            )

            if day_stats:
                total_data.append(day_stats["total"])
                completed_data.append(day_stats["completed"])
                cancelled_data.append(day_stats["cancelled"])
                no_show_data.append(day_stats["no_show"])
            else:
                total_data.append(0)
                completed_data.append(0)
                cancelled_data.append(0)
                no_show_data.append(0)

            current_date += timedelta(days=1)

        # Format for chart
        chart_data = {
            "labels": days,
            "datasets": [
                {"label": "Total", "data": total_data},
                {"label": "Completed", "data": completed_data},
                {"label": "Cancelled", "data": cancelled_data},
                {"label": "No Show", "data": no_show_data},
            ],
        }

        return chart_data

    @staticmethod
    def _get_specialist_service_distribution(specialist_id, start_date, end_date):
        """Get service distribution for a specialist"""
        # Get all services provided by the specialist
        specialist_services = SpecialistService.objects.filter(
            specialist_id=specialist_id
        ).select_related("service")

        result = []

        for specialist_service in specialist_services:
            service = specialist_service.service

            # Get appointments for this service
            appointments = Appointment.objects.filter(
                specialist_id=specialist_id,
                service_id=service.id,
                start_time__gte=start_date,
                start_time__lte=end_date,
            )

            # Calculate metrics
            total_bookings = appointments.count()
            completed_bookings = appointments.filter(status="completed").count()

            if total_bookings == 0:
                continue  # Skip services with no bookings

            result.append(
                {
                    "id": str(service.id),
                    "name": service.name,
                    "bookings": total_bookings,
                    "completed": completed_bookings,
                    "duration": service.duration,
                    "is_primary": specialist_service.is_primary,
                }
            )

        # Sort by bookings (descending)
        result.sort(key=lambda x: x["bookings"], reverse=True)

        return result

    @staticmethod
    def _get_specialist_reviews(specialist_id, limit=5):
        """Get recent reviews for a specialist"""
        reviews = Review.objects.filter(
            content_type__model="specialist", object_id=specialist_id
        ).order_by("-created_at")[:limit]

        result = []

        for review in reviews:
            result.append(
                {
                    "id": str(review.id),
                    "customer_name": review.customer.phone_number,  # Using phone as fallback
                    "rating": review.rating,
                    "comment": review.comment,
                    "created_at": review.created_at,
                }
            )

        return result

    @staticmethod
    def _get_specialist_comparison(specialist_id, shop_id, start_date, end_date):
        """Get performance comparison with other specialists in the shop"""
        try:
            specialist = Specialist.objects.get(id=specialist_id)
        except Specialist.DoesNotExist:
            return {"error": "Specialist not found"}

        # Get all active specialists in the shop
        shop_specialists = Specialist.objects.filter(
            employee__shop_id=shop_id, employee__is_active=True
        ).exclude(id=specialist_id)

        # Get comparison metrics
        comparison = {}

        # 1. Booking count
        specialist_bookings = Appointment.objects.filter(
            specialist_id=specialist_id,
            start_time__gte=start_date,
            start_time__lte=end_date,
        ).count()

        shop_avg_bookings = 0
        for other_specialist in shop_specialists:
            other_bookings = Appointment.objects.filter(
                specialist_id=other_specialist.id,
                start_time__gte=start_date,
                start_time__lte=end_date,
            ).count()
            shop_avg_bookings += other_bookings

        shop_avg_bookings = (
            shop_avg_bookings / shop_specialists.count()
            if shop_specialists.count() > 0
            else 0
        )

        comparison["booking_count"] = {
            "specialist_value": specialist_bookings,
            "shop_average": round(shop_avg_bookings, 2),
            "difference": specialist_bookings - shop_avg_bookings,
            "is_better": specialist_bookings > shop_avg_bookings,
        }

        # 2. Completion rate
        specialist_appointments = Appointment.objects.filter(
            specialist_id=specialist_id,
            start_time__gte=start_date,
            start_time__lte=end_date,
        )

        specialist_completion_rate = 0
        if specialist_appointments.count() > 0:
            specialist_completed = specialist_appointments.filter(
                status="completed"
            ).count()
            specialist_completion_rate = (
                specialist_completed / specialist_appointments.count()
            ) * 100

        shop_completion_rates = []
        for other_specialist in shop_specialists:
            other_appointments = Appointment.objects.filter(
                specialist_id=other_specialist.id,
                start_time__gte=start_date,
                start_time__lte=end_date,
            )

            if other_appointments.count() > 0:
                other_completed = other_appointments.filter(status="completed").count()
                other_rate = (other_completed / other_appointments.count()) * 100
                shop_completion_rates.append(other_rate)

        shop_avg_completion_rate = (
            sum(shop_completion_rates) / len(shop_completion_rates)
            if shop_completion_rates
            else 0
        )

        comparison["completion_rate"] = {
            "specialist_value": round(specialist_completion_rate, 2),
            "shop_average": round(shop_avg_completion_rate, 2),
            "difference": round(
                specialist_completion_rate - shop_avg_completion_rate, 2
            ),
            "is_better": specialist_completion_rate > shop_avg_completion_rate,
        }

        # 3. Average rating
        specialist_reviews = Review.objects.filter(
            content_type__model="specialist",
            object_id=specialist_id,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        specialist_avg_rating = (
            specialist_reviews.aggregate(avg_rating=Avg("rating"))["avg_rating"] or 0
        )

        shop_ratings = []
        for other_specialist in shop_specialists:
            other_reviews = Review.objects.filter(
                content_type__model="specialist",
                object_id=other_specialist.id,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )

            other_rating = (
                other_reviews.aggregate(avg_rating=Avg("rating"))["avg_rating"] or 0
            )
            if other_rating > 0:
                shop_ratings.append(other_rating)

        shop_avg_rating = sum(shop_ratings) / len(shop_ratings) if shop_ratings else 0

        comparison["rating"] = {
            "specialist_value": round(specialist_avg_rating, 2),
            "shop_average": round(shop_avg_rating, 2),
            "difference": round(specialist_avg_rating - shop_avg_rating, 2),
            "is_better": specialist_avg_rating > shop_avg_rating,
        }

        return comparison

    @staticmethod
    def _get_platform_overview(
        today_start, today_end, week_start, week_end, month_start, month_end
    ):
        """Get overview metrics for admin dashboard"""
        # Active shops
        active_shops = Shop.objects.filter(is_active=True).count()

        # Today's registrations
        new_shops_today = Shop.objects.filter(
            created_at__gte=today_start, created_at__lte=today_end
        ).count()
        new_customers_today = User.objects.filter(
            user_type="customer",
            date_joined__gte=today_start,
            date_joined__lte=today_end,
        ).count()

        # Today's appointments
        today_appointments = Appointment.objects.filter(
            start_time__gte=today_start, start_time__lte=today_end
        ).count()

        # Today's revenue (from all sources)
        # Subscription revenue
        from apps.subscriptionapp.models import Subscription

        subscription_revenue = (
            Subscription.objects.filter(
                payment_date__gte=today_start,
                payment_date__lte=today_end,
                status="active",
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        # Ad revenue
        from apps.marketingapp.models import Advertisement

        ad_revenue = (
            Advertisement.objects.filter(
                payment_date__gte=today_start,
                payment_date__lte=today_end,
                status="active",
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        # Merchant revenue (commission on bookings)
        # Assuming 5% commission on all completed appointments
        completed_appointments = Appointment.objects.filter(
            start_time__gte=today_start, start_time__lte=today_end, status="completed"
        )

        merchant_revenue = 0
        for appointment in completed_appointments:
            merchant_revenue += appointment.service.price * 0.05  # 5% commission

        total_revenue = subscription_revenue + ad_revenue + merchant_revenue

        # Monthly active users
        monthly_active_users = User.objects.filter(
            last_login__gte=month_start, last_login__lte=month_end
        ).count()

        return {
            "active_shops": active_shops,
            "new_shops_today": new_shops_today,
            "new_customers_today": new_customers_today,
            "today_appointments": today_appointments,
            "today_revenue": round(total_revenue, 2),
            "monthly_active_users": monthly_active_users,
            "revenue_breakdown": {
                "subscription": round(subscription_revenue, 2),
                "ads": round(ad_revenue, 2),
                "merchant": round(merchant_revenue, 2),
            },
        }

    @staticmethod
    def _get_shops_growth_chart(start_date, end_date):
        """Get shops growth chart data"""
        # Group by month
        shops = (
            Shop.objects.filter(created_at__gte=start_date, created_at__lte=end_date)
            .annotate(month=TruncDay("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        # Calculate cumulative count
        cumulative_count = 0
        result = []

        for month in shops:
            cumulative_count += month["count"]
            result.append(
                {
                    "month": month["month"].strftime("%Y-%m"),
                    "new_shops": month["count"],
                    "total_shops": cumulative_count,
                }
            )

        return result

    @staticmethod
    def _get_users_growth_chart(start_date, end_date):
        """Get users growth chart data"""
        # Group by month
        users = (
            User.objects.filter(date_joined__gte=start_date, date_joined__lte=end_date)
            .annotate(month=TruncDay("date_joined"))
            .values("month", "user_type")
            .annotate(count=Count("id"))
            .order_by("month", "user_type")
        )

        # Initialize result
        months = []
        current_date = start_date.replace(day=1)
        while current_date <= end_date:
            months.append(current_date.strftime("%Y-%m"))

            # Increment month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)

        # Initialize data
        customer_data = {month: 0 for month in months}
        employee_data = {month: 0 for month in months}
        admin_data = {month: 0 for month in months}

        # Populate data
        for user in users:
            month_key = user["month"].strftime("%Y-%m")

            if user["user_type"] == "customer":
                customer_data[month_key] = user["count"]
            elif user["user_type"] == "employee":
                employee_data[month_key] = user["count"]
            elif user["user_type"] == "admin":
                admin_data[month_key] = user["count"]

        # Format for chart
        result = {
            "months": months,
            "customers": [customer_data[month] for month in months],
            "employees": [employee_data[month] for month in months],
            "admins": [admin_data[month] for month in months],
        }

        return result

    @staticmethod
    def _get_revenue_breakdown(start_date, end_date):
        """Get revenue breakdown by source"""
        # Subscription revenue
        from apps.subscriptionapp.models import Subscription

        subscription_revenue = (
            Subscription.objects.filter(
                payment_date__gte=start_date,
                payment_date__lte=end_date,
                status="active",
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        # Ad revenue
        from apps.marketingapp.models import Advertisement

        ad_revenue = (
            Advertisement.objects.filter(
                payment_date__gte=start_date,
                payment_date__lte=end_date,
                status="active",
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        # Merchant revenue (commission on bookings)
        # Assuming 5% commission on all completed appointments
        completed_appointments = Appointment.objects.filter(
            start_time__gte=start_date, start_time__lte=end_date, status="completed"
        )

        merchant_revenue = 0
        for appointment in completed_appointments:
            merchant_revenue += appointment.service.price * 0.05  # 5% commission

        total_revenue = subscription_revenue + ad_revenue + merchant_revenue

        return {
            "total": round(total_revenue, 2),
            "breakdown": {
                "subscription": round(subscription_revenue, 2),
                "subscription_percent": (
                    round(subscription_revenue / total_revenue * 100, 2)
                    if total_revenue > 0
                    else 0
                ),
                "ads": round(ad_revenue, 2),
                "ads_percent": (
                    round(ad_revenue / total_revenue * 100, 2)
                    if total_revenue > 0
                    else 0
                ),
                "merchant": round(merchant_revenue, 2),
                "merchant_percent": (
                    round(merchant_revenue / total_revenue * 100, 2)
                    if total_revenue > 0
                    else 0
                ),
            },
        }

    @staticmethod
    def _get_top_performing_shops(start_date, end_date):
        """Get top performing shops by various metrics"""
        shops = Shop.objects.filter(is_active=True)

        shop_metrics = []

        for shop in shops:
            # Get appointments
            appointments = Appointment.objects.filter(
                shop_id=shop.id, start_time__gte=start_date, start_time__lte=end_date
            )

            # Calculate metrics
            booking_count = appointments.count()
            completed_count = appointments.filter(status="completed").count()

            # Calculate revenue
            revenue = 0
            for appointment in appointments.filter(status="completed"):
                revenue += appointment.service.price

            # Get reviews
            reviews = Review.objects.filter(
                content_type__model="shop",
                object_id=shop.id,
                created_at__gte=start_date,
                created_at__lte=end_date,
            )

            avg_rating = reviews.aggregate(avg_rating=Avg("rating"))["avg_rating"] or 0

            # Add to metrics
            shop_metrics.append(
                {
                    "id": str(shop.id),
                    "name": shop.name,
                    "city": shop.location.city if shop.location else "Unknown",
                    "booking_count": booking_count,
                    "completed_count": completed_count,
                    "revenue": revenue,
                    "avg_rating": avg_rating,
                }
            )

        # Sort by different metrics
        by_bookings = sorted(
            shop_metrics, key=lambda x: x["booking_count"], reverse=True
        )[:5]
        by_revenue = sorted(shop_metrics, key=lambda x: x["revenue"], reverse=True)[:5]
        by_rating = sorted(shop_metrics, key=lambda x: x["avg_rating"], reverse=True)[
            :5
        ]

        return {
            "by_bookings": by_bookings,
            "by_revenue": by_revenue,
            "by_rating": by_rating,
        }

    @staticmethod
    def _get_popular_categories(start_date, end_date):
        """Get popular categories based on service bookings"""
        # Get all services booked in the period
        from apps.categoriesapp.models import Category
        from apps.serviceapp.models import Service

        # Get all categories
        categories = Category.objects.filter(
            parent__isnull=False
        )  # Child categories only

        category_metrics = []

        for category in categories:
            # Get services in this category
            services = Service.objects.filter(category=category)

            if not services.exists():
                continue

            # Get appointments for these services
            appointments = Appointment.objects.filter(
                service__in=services,
                start_time__gte=start_date,
                start_time__lte=end_date,
            )

            # Calculate metrics
            booking_count = appointments.count()

            if booking_count == 0:
                continue

            # Get parent category
            parent = category.parent

            category_metrics.append(
                {
                    "id": str(category.id),
                    "name": category.name,
                    "parent_name": parent.name if parent else "None",
                    "booking_count": booking_count,
                }
            )

        # Sort by booking count
        category_metrics.sort(key=lambda x: x["booking_count"], reverse=True)

        return category_metrics[:10]  # Top 10

    @staticmethod
    def _get_system_health():
        """Get system health metrics"""
        # This would typically connect to monitoring systems
        # For demonstration, we'll return synthetic data
        return {
            "server_uptime": "99.8%",
            "api_response_time": "215ms",
            "database_size": "1.2GB",
            "active_connections": 325,
            "memory_usage": "62%",
            "cpu_usage": "48%",
            "status": "healthy",
        }

    @staticmethod
    def _get_recent_admin_activities(limit=10):
        """Get recent admin activities"""
        # This would typically come from an admin activity log
        # For demonstration, we'll return synthetic data
        activities = [
            {
                "user": "admin1",
                "action": "Approved shop verification",
                "timestamp": timezone.now() - timedelta(hours=2),
            },
            {
                "user": "admin2",
                "action": "Created new category",
                "timestamp": timezone.now() - timedelta(hours=5),
            },
            {
                "user": "admin1",
                "action": "Modified subscription plan",
                "timestamp": timezone.now() - timedelta(hours=8),
            },
            {
                "user": "admin3",
                "action": "Approved ad campaign",
                "timestamp": timezone.now() - timedelta(days=1),
            },
            {
                "user": "admin2",
                "action": "Updated system settings",
                "timestamp": timezone.now() - timedelta(days=1, hours=4),
            },
        ]

        return activities[:limit]

    # Methods for custom dashboard

    @staticmethod
    def _get_appointment_metrics(shop_id, start_date, end_date):
        """Get appointment metrics for custom dashboard"""
        return AnalyticsService._get_appointment_metrics(shop_id, start_date, end_date)

    @staticmethod
    def _get_revenue_metrics(shop_id, start_date, end_date):
        """Get revenue metrics for custom dashboard"""
        return AnalyticsService._get_financial_metrics(shop_id, start_date, end_date)

    @staticmethod
    def _get_review_metrics(shop_id, start_date, end_date):
        """Get review metrics for custom dashboard"""
        return AnalyticsService._get_review_metrics(shop_id, start_date, end_date)

    @staticmethod
    def _get_queue_metrics(shop_id, start_date, end_date):
        """Get queue metrics for custom dashboard"""
        return AnalyticsService._get_queue_metrics(shop_id, start_date, end_date)

    @staticmethod
    def _get_specialist_metrics(shop_id, start_date, end_date):
        """Get specialist metrics for custom dashboard"""
        return AnalyticsService._get_specialist_metrics(shop_id, start_date, end_date)

    @staticmethod
    def _get_service_metrics(shop_id, start_date, end_date):
        """Get service metrics for custom dashboard"""
        return AnalyticsService._get_service_metrics(shop_id, start_date, end_date)

    @staticmethod
    def _get_customer_metrics(shop_id, start_date, end_date):
        """Get customer metrics for custom dashboard"""
        return AnalyticsService._get_customer_metrics(shop_id, start_date, end_date)

    @staticmethod
    def _get_comparison_metrics(shop_id, start_date, end_date):
        """Get comparison metrics for custom dashboard"""
        # Get prior period
        (end_date - start_date).days
        # unused_unused_prior_start = prior_end - timedelta(days=period_length)

        return AnalyticsService.get_comparison_metrics(shop_id, "previous")
