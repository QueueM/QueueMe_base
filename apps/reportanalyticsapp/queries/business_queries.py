# apps/reportanalyticsapp/queries/business_queries.py

import logging

from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q, Sum
from django.db.models.functions import Coalesce, ExtractDay, ExtractHour, TruncDate

from apps.authapp.models import User
from apps.bookingapp.models import Appointment
from apps.payment.models import Transaction
from apps.queueapp.models import QueueTicket
from apps.reviewapp.models import Review
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist

logger = logging.getLogger(__name__)


class BusinessQueries:
    """
    Optimized query service for business (shop/company) related analytics.
    Uses advanced database queries with aggregations for performance.
    """

    def get_business_overview(self, shop_id, start_date, end_date):
        """
        Get comprehensive business overview metrics for a shop.

        Args:
            shop_id: Shop ID
            start_date: Start date
            end_date: End date

        Returns:
            dict: Business overview data
        """
        shop = Shop.objects.get(id=shop_id)

        # Get base metrics with optimized queries
        total_bookings = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lt=end_date
        ).count()

        completed_bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_date,
            start_time__lt=end_date,
            status="completed",
        ).count()

        cancelled_bookings = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_date,
            start_time__lt=end_date,
            status="cancelled",
        ).count()

        # Get revenue
        revenue = (
            Transaction.objects.filter(
                content_type__model="appointment",
                content_object__shop_id=shop_id,
                created_at__gte=start_date,
                created_at__lt=end_date,
                status="succeeded",
            ).aggregate(total=Coalesce(Sum("amount"), 0))["total"]
            or 0
        )

        # Get customer metrics
        unique_customers = (
            Appointment.objects.filter(
                shop_id=shop_id, start_time__gte=start_date, start_time__lt=end_date
            )
            .values("customer")
            .distinct()
            .count()
        )

        # Get ratings
        ratings = Review.objects.filter(
            content_type__model="shop",
            object_id=shop_id,
            created_at__gte=start_date,
            created_at__lt=end_date,
        ).aggregate(avg_rating=Coalesce(Avg("rating"), 0), count=Count("id"))

        # Get returning customers (booked before this period)
        returning_customers = (
            Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=start_date,
                start_time__lt=end_date,
                customer__in=Appointment.objects.filter(
                    shop_id=shop_id, start_time__lt=start_date
                ).values("customer"),
            )
            .values("customer")
            .distinct()
            .count()
        )

        # Get service data
        service_data = (
            Service.objects.filter(shop_id=shop_id)
            .annotate(
                bookings=Count(
                    "appointments",
                    filter=Q(
                        appointments__start_time__gte=start_date,
                        appointments__start_time__lt=end_date,
                    ),
                ),
                completed=Count(
                    "appointments",
                    filter=Q(
                        appointments__start_time__gte=start_date,
                        appointments__start_time__lt=end_date,
                        appointments__status="completed",
                    ),
                ),
                cancelled=Count(
                    "appointments",
                    filter=Q(
                        appointments__start_time__gte=start_date,
                        appointments__start_time__lt=end_date,
                        appointments__status="cancelled",
                    ),
                ),
                revenue=Coalesce(
                    Sum(
                        "appointments__transaction__amount",
                        filter=Q(
                            appointments__start_time__gte=start_date,
                            appointments__start_time__lt=end_date,
                            appointments__transaction__status="succeeded",
                        ),
                    ),
                    0,
                ),
            )
            .values("id", "name", "price", "bookings", "completed", "cancelled", "revenue")
        )

        # Calculate cancellation rate
        cancellation_rate = 0
        if total_bookings > 0:
            cancellation_rate = (cancelled_bookings / total_bookings) * 100

        # Calculate completion rate
        completion_rate = 0
        if total_bookings > 0:
            completion_rate = (completed_bookings / total_bookings) * 100

        # Get booking trends (time series)
        # Group by date for the period
        booking_trend = (
            Appointment.objects.filter(
                shop_id=shop_id, start_time__gte=start_date, start_time__lt=end_date
            )
            .annotate(date=TruncDate("start_time"))
            .values("date")
            .annotate(
                count=Count("id"),
                completed=Count("id", filter=Q(status="completed")),
                cancelled=Count("id", filter=Q(status="cancelled")),
            )
            .order_by("date")
        )

        # Format trend data as time series
        trend_series = {}
        for entry in booking_trend:
            date_str = entry["date"].isoformat()
            trend_series[date_str] = entry["count"]

        # Format results
        result = {
            "entity_id": shop_id,
            "entity_type": "shop",
            "entity_name": shop.name,
            "metrics": {
                "total_bookings": total_bookings,
                "completed_bookings": completed_bookings,
                "cancelled_bookings": cancelled_bookings,
                "total_revenue": revenue,
                "total_customers": unique_customers,
                "returning_customers": returning_customers,
                "avg_rating": ratings["avg_rating"],
                "review_count": ratings["count"],
                "cancellation_rate": round(cancellation_rate, 2),
                "completion_rate": round(completion_rate, 2),
            },
            "service_data": list(service_data),
            "time_series": {"bookings": trend_series},
        }

        return result

    def get_service_performance(self, shop_id, start_date, end_date):
        """
        Get detailed service performance metrics.

        Args:
            shop_id: Shop ID
            start_date: Start date
            end_date: End date

        Returns:
            dict: Service performance data
        """
        # Get service metrics with advanced annotations
        service_metrics = (
            Service.objects.filter(shop_id=shop_id)
            .annotate(
                bookings=Count(
                    "appointments",
                    filter=Q(
                        appointments__start_time__gte=start_date,
                        appointments__start_time__lt=end_date,
                    ),
                ),
                completed=Count(
                    "appointments",
                    filter=Q(
                        appointments__start_time__gte=start_date,
                        appointments__start_time__lt=end_date,
                        appointments__status="completed",
                    ),
                ),
                cancelled=Count(
                    "appointments",
                    filter=Q(
                        appointments__start_time__gte=start_date,
                        appointments__start_time__lt=end_date,
                        appointments__status="cancelled",
                    ),
                ),
                no_show=Count(
                    "appointments",
                    filter=Q(
                        appointments__start_time__gte=start_date,
                        appointments__start_time__lt=end_date,
                        appointments__status="no_show",
                    ),
                ),
                revenue=Coalesce(
                    Sum(
                        "appointments__transaction__amount",
                        filter=Q(
                            appointments__start_time__gte=start_date,
                            appointments__start_time__lt=end_date,
                            appointments__transaction__status="succeeded",
                        ),
                    ),
                    0,
                ),
                avg_rating=Coalesce(
                    Avg(
                        "reviews__rating",
                        filter=Q(
                            reviews__created_at__gte=start_date,
                            reviews__created_at__lt=end_date,
                        ),
                    ),
                    0,
                ),
                review_count=Count(
                    "reviews",
                    filter=Q(
                        reviews__created_at__gte=start_date,
                        reviews__created_at__lt=end_date,
                    ),
                ),
            )
            .values(
                "id",
                "name",
                "price",
                "duration",
                "bookings",
                "completed",
                "cancelled",
                "no_show",
                "revenue",
                "avg_rating",
                "review_count",
            )
        )

        # Calculate additional metrics for each service
        service_data = []
        for service in service_metrics:
            # Calculate completion and cancellation rates
            completion_rate = 0
            cancellation_rate = 0
            no_show_rate = 0

            if service["bookings"] > 0:
                completion_rate = (service["completed"] / service["bookings"]) * 100
                cancellation_rate = (service["cancelled"] / service["bookings"]) * 100
                no_show_rate = (service["no_show"] / service["bookings"]) * 100

            # Calculate revenue per booking
            revenue_per_booking = 0
            if service["completed"] > 0:
                revenue_per_booking = service["revenue"] / service["completed"]

            # Add calculated metrics
            service_with_rates = {
                **service,
                "completion_rate": round(completion_rate, 2),
                "cancellation_rate": round(cancellation_rate, 2),
                "no_show_rate": round(no_show_rate, 2),
                "revenue_per_booking": round(revenue_per_booking, 2),
            }

            service_data.append(service_with_rates)

        # Get top-level metrics for all services
        total_bookings = sum(service["bookings"] for service in service_metrics)
        total_completed = sum(service["completed"] for service in service_metrics)
        total_cancelled = sum(service["cancelled"] for service in service_metrics)
        total_no_show = sum(service["no_show"] for service in service_metrics)
        total_revenue = sum(service["revenue"] for service in service_metrics)

        # Calculate overall rates
        overall_completion_rate = 0
        overall_cancellation_rate = 0
        overall_no_show_rate = 0

        if total_bookings > 0:
            overall_completion_rate = (total_completed / total_bookings) * 100
            overall_cancellation_rate = (total_cancelled / total_bookings) * 100
            overall_no_show_rate = (total_no_show / total_bookings) * 100

        # Get average rating across all services
        avg_service_rating = (
            Review.objects.filter(
                content_type__model="service",
                object_id__in=Service.objects.filter(shop_id=shop_id).values_list("id", flat=True),
                created_at__gte=start_date,
                created_at__lt=end_date,
            ).aggregate(avg=Coalesce(Avg("rating"), 0))["avg"]
            or 0
        )

        # Format results
        shop = Shop.objects.get(id=shop_id)

        result = {
            "entity_id": shop_id,
            "entity_type": "shop",
            "entity_name": shop.name,
            "metrics": {
                "total_services": Service.objects.filter(shop_id=shop_id).count(),
                "total_bookings": total_bookings,
                "total_completed": total_completed,
                "total_cancelled": total_cancelled,
                "total_no_show": total_no_show,
                "total_revenue": total_revenue,
                "overall_completion_rate": round(overall_completion_rate, 2),
                "overall_cancellation_rate": round(overall_cancellation_rate, 2),
                "overall_no_show_rate": round(overall_no_show_rate, 2),
                "avg_service_rating": round(avg_service_rating, 2),
            },
            "service_data": service_data,
        }

        return result

    def get_specialist_performance(self, shop_id, start_date, end_date):
        """
        Get detailed specialist performance metrics.

        Args:
            shop_id: Shop ID
            start_date: Start date
            end_date: End date

        Returns:
            dict: Specialist performance data
        """
        # Get specialists for this shop
        specialists = Specialist.objects.filter(employee__shop_id=shop_id)

        # Get specialist metrics with advanced annotations
        specialist_metrics = specialists.annotate(
            bookings=Count(
                "appointments",
                filter=Q(
                    appointments__start_time__gte=start_date,
                    appointments__start_time__lt=end_date,
                ),
            ),
            completed=Count(
                "appointments",
                filter=Q(
                    appointments__start_time__gte=start_date,
                    appointments__start_time__lt=end_date,
                    appointments__status="completed",
                ),
            ),
            cancelled=Count(
                "appointments",
                filter=Q(
                    appointments__start_time__gte=start_date,
                    appointments__start_time__lt=end_date,
                    appointments__status="cancelled",
                ),
            ),
            no_show=Count(
                "appointments",
                filter=Q(
                    appointments__start_time__gte=start_date,
                    appointments__start_time__lt=end_date,
                    appointments__status="no_show",
                ),
            ),
            revenue=Coalesce(
                Sum(
                    "appointments__transaction__amount",
                    filter=Q(
                        appointments__start_time__gte=start_date,
                        appointments__start_time__lt=end_date,
                        appointments__transaction__status="succeeded",
                    ),
                ),
                0,
            ),
            avg_rating=Coalesce(
                Avg(
                    "reviews__rating",
                    filter=Q(
                        reviews__created_at__gte=start_date,
                        reviews__created_at__lt=end_date,
                    ),
                ),
                0,
            ),
            review_count=Count(
                "reviews",
                filter=Q(
                    reviews__created_at__gte=start_date,
                    reviews__created_at__lt=end_date,
                ),
            ),
        ).values(
            "id",
            "employee__first_name",
            "employee__last_name",
            "bookings",
            "completed",
            "cancelled",
            "no_show",
            "revenue",
            "avg_rating",
            "review_count",
        )

        # Calculate additional metrics for each specialist
        specialist_data = []
        for specialist in specialist_metrics:
            # Calculate completion and cancellation rates
            completion_rate = 0
            cancellation_rate = 0
            no_show_rate = 0

            if specialist["bookings"] > 0:
                completion_rate = (specialist["completed"] / specialist["bookings"]) * 100
                cancellation_rate = (specialist["cancelled"] / specialist["bookings"]) * 100
                no_show_rate = (specialist["no_show"] / specialist["bookings"]) * 100

            # Calculate revenue per booking
            revenue_per_booking = 0
            if specialist["completed"] > 0:
                revenue_per_booking = specialist["revenue"] / specialist["completed"]

            # Calculate utilization (appointments / available slots)
            # This would require analyzing working hours which is complex
            # For now, we'll just assume an 8-hour day with 1-hour slots
            days_in_period = (end_date - start_date).days
            if days_in_period == 0:
                days_in_period = 1

            # Assuming 8 slots per day average
            max_slots = days_in_period * 8
            utilization_rate = 0
            if max_slots > 0:
                utilization_rate = (specialist["bookings"] / max_slots) * 100

            # Add full name
            full_name = f"{specialist['employee__first_name']} {specialist['employee__last_name']}"

            # Add calculated metrics
            specialist_with_rates = {
                "id": specialist["id"],
                "name": full_name,
                "bookings": specialist["bookings"],
                "completed": specialist["completed"],
                "cancelled": specialist["cancelled"],
                "no_show": specialist["no_show"],
                "revenue": specialist["revenue"],
                "avg_rating": specialist["avg_rating"],
                "review_count": specialist["review_count"],
                "completion_rate": round(completion_rate, 2),
                "cancellation_rate": round(cancellation_rate, 2),
                "no_show_rate": round(no_show_rate, 2),
                "revenue_per_booking": round(revenue_per_booking, 2),
                "utilization_rate": round(utilization_rate, 2),
                "bookings_per_day": (
                    round(specialist["bookings"] / days_in_period, 2) if days_in_period > 0 else 0
                ),
            }

            specialist_data.append(specialist_with_rates)

        # Get top-level metrics for all specialists
        total_bookings = sum(specialist["bookings"] for specialist in specialist_metrics)
        total_completed = sum(specialist["completed"] for specialist in specialist_metrics)
        total_cancelled = sum(specialist["cancelled"] for specialist in specialist_metrics)
        total_no_show = sum(specialist["no_show"] for specialist in specialist_metrics)
        total_revenue = sum(specialist["revenue"] for specialist in specialist_metrics)

        # Calculate overall rates
        overall_completion_rate = 0
        overall_cancellation_rate = 0
        overall_no_show_rate = 0

        if total_bookings > 0:
            overall_completion_rate = (total_completed / total_bookings) * 100
            overall_cancellation_rate = (total_cancelled / total_bookings) * 100
            overall_no_show_rate = (total_no_show / total_bookings) * 100

        # Get average rating across all specialists
        avg_specialist_rating = (
            Review.objects.filter(
                content_type__model="specialist",
                object_id__in=specialists.values_list("id", flat=True),
                created_at__gte=start_date,
                created_at__lt=end_date,
            ).aggregate(avg=Coalesce(Avg("rating"), 0))["avg"]
            or 0
        )

        # Format results
        shop = Shop.objects.get(id=shop_id)

        result = {
            "entity_id": shop_id,
            "entity_type": "shop",
            "entity_name": shop.name,
            "metrics": {
                "total_specialists": specialists.count(),
                "total_bookings": total_bookings,
                "total_completed": total_completed,
                "total_cancelled": total_cancelled,
                "total_no_show": total_no_show,
                "total_revenue": total_revenue,
                "overall_completion_rate": round(overall_completion_rate, 2),
                "overall_cancellation_rate": round(overall_cancellation_rate, 2),
                "overall_no_show_rate": round(overall_no_show_rate, 2),
                "avg_specialist_rating": round(avg_specialist_rating, 2),
            },
            "specialist_data": specialist_data,
        }

        return result

    def get_booking_analytics(self, shop_id, start_date, end_date):
        """
        Get detailed booking analytics with patterns and trends.

        Args:
            shop_id: Shop ID
            start_date: Start date
            end_date: End date

        Returns:
            dict: Booking analytics data
        """
        # Get all bookings in the period
        bookings = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lt=end_date
        )

        # Get basic metrics
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

        # Get hourly distribution (which hours have most bookings)
        hourly_distribution = (
            bookings.annotate(hour=ExtractHour("start_time"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )

        # Convert to dictionary for easier access
        hourly_dict = {str(item["hour"]): item["count"] for item in hourly_distribution}

        # Get day of week distribution
        day_distribution = (
            bookings.annotate(day=ExtractDay("start_time"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        # Convert to dictionary for easier access
        day_dict = {str(item["day"]): item["count"] for item in day_distribution}

        # Get booking lead time (time between booking creation and appointment)
        lead_times = bookings.annotate(
            lead_time=ExpressionWrapper(
                F("start_time") - F("created_at"), output_field=FloatField()
            )
        ).values_list("lead_time", flat=True)

        # Calculate average lead time in hours
        avg_lead_time = 0
        if lead_times:
            total_seconds = sum(lt.total_seconds() for lt in lead_times if lt)
            avg_lead_time = total_seconds / (3600 * len(lead_times))

        # Get booking trends over the period (daily)
        daily_bookings = (
            bookings.annotate(date=TruncDate("start_time"))
            .values("date")
            .annotate(
                count=Count("id"),
                completed=Count("id", filter=Q(status="completed")),
                cancelled=Count("id", filter=Q(status="cancelled")),
                revenue=Coalesce(
                    Sum("transaction__amount", filter=Q(transaction__status="succeeded")),
                    0,
                ),
            )
            .order_by("date")
        )

        # Format trend data as time series
        trend_series = {}
        for entry in daily_bookings:
            date_str = entry["date"].isoformat()
            trend_series[date_str] = entry["count"]

        # Get online vs walk-in stats
        # For this example, we'll consider appointments without customer_note as walk-ins
        # In a real system, there would likely be a source field
        online_bookings = bookings.filter(notes__isnull=False).count()
        walkin_bookings = total_bookings - online_bookings

        # Get top customers
        top_customers = (
            bookings.values("customer")
            .annotate(
                count=Count("id"),
                total_spent=Coalesce(
                    Sum("transaction__amount", filter=Q(transaction__status="succeeded")),
                    0,
                ),
            )
            .order_by("-count")[:5]
        )

        # Enhance with customer details
        top_customer_data = []
        for customer in top_customers:
            user = User.objects.filter(id=customer["customer"]).first()
            if user:
                top_customer_data.append(
                    {
                        "id": str(user.id),
                        "phone_number": user.phone_number,
                        "bookings": customer["count"],
                        "total_spent": customer["total_spent"],
                    }
                )

        # Format results
        shop = Shop.objects.get(id=shop_id)

        result = {
            "entity_id": shop_id,
            "entity_type": "shop",
            "entity_name": shop.name,
            "metrics": {
                "total_bookings": total_bookings,
                "completed_bookings": completed_bookings,
                "cancelled_bookings": cancelled_bookings,
                "no_show_bookings": no_show_bookings,
                "completion_rate": round(completion_rate, 2),
                "cancellation_rate": round(cancellation_rate, 2),
                "no_show_rate": round(no_show_rate, 2),
                "avg_lead_time_hours": round(avg_lead_time, 2),
                "online_bookings": online_bookings,
                "walkin_bookings": walkin_bookings,
                "online_booking_percentage": (
                    round((online_bookings / total_bookings) * 100, 2) if total_bookings > 0 else 0
                ),
            },
            "hourly_distribution": hourly_dict,
            "day_distribution": day_dict,
            "time_series": {"daily_bookings": trend_series},
            "top_customers": top_customer_data,
        }

        return result

    def get_customer_engagement(self, shop_id, start_date, end_date):
        """
        Get customer engagement analytics.

        Args:
            shop_id: Shop ID
            start_date: Start date
            end_date: End date

        Returns:
            dict: Customer engagement data
        """
        # Get all bookings in the period
        bookings = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lt=end_date
        )

        # Get total customers
        total_customers = bookings.values("customer").distinct().count()

        # Get returning customers (booked before this period)
        returning_customers = (
            bookings.filter(
                customer__in=Appointment.objects.filter(
                    shop_id=shop_id, start_time__lt=start_date
                ).values("customer")
            )
            .values("customer")
            .distinct()
            .count()
        )

        # Get new customers
        new_customers = total_customers - returning_customers

        # Calculate retention rate
        retention_rate = 0
        if total_customers > 0:
            retention_rate = (returning_customers / total_customers) * 100

        # Get booking frequency
        booking_frequency = (
            bookings.values("customer")
            .annotate(count=Count("id"))
            .aggregate(avg=Coalesce(Avg("count"), 0))["avg"]
            or 0
        )

        # Get customer segmentation by booking count
        one_time = bookings.values("customer").annotate(count=Count("id")).filter(count=1).count()
        two_to_five = (
            bookings.values("customer")
            .annotate(count=Count("id"))
            .filter(count__gte=2, count__lte=5)
            .count()
        )
        more_than_five = (
            bookings.values("customer").annotate(count=Count("id")).filter(count__gt=5).count()
        )

        # Get review metrics
        review_metrics = Review.objects.filter(
            content_type__model="shop",
            object_id=shop_id,
            created_at__gte=start_date,
            created_at__lt=end_date,
        ).aggregate(count=Count("id"), avg_rating=Coalesce(Avg("rating"), 0))

        # Get review distribution
        review_distribution = (
            Review.objects.filter(
                content_type__model="shop",
                object_id=shop_id,
                created_at__gte=start_date,
                created_at__lt=end_date,
            )
            .values("rating")
            .annotate(count=Count("id"))
            .order_by("rating")
        )

        # Convert to dictionary
        rating_dict = {str(item["rating"]): item["count"] for item in review_distribution}

        # Get follow metrics
        from apps.followapp.models import Follow

        follow_count = Follow.objects.filter(
            content_type__model="shop",
            object_id=shop_id,
            created_at__gte=start_date,
            created_at__lt=end_date,
        ).count()

        unfollow_count = Follow.objects.filter(
            content_type__model="shop",
            object_id=shop_id,
            is_active=False,
            updated_at__gte=start_date,
            updated_at__lt=end_date,
        ).count()

        # Get chat metrics
        from apps.chatapp.models import Conversation, Message

        chat_metrics = {
            "conversations": Conversation.objects.filter(
                shop_id=shop_id, created_at__gte=start_date, created_at__lt=end_date
            ).count(),
            "messages": Message.objects.filter(
                conversation__shop_id=shop_id,
                created_at__gte=start_date,
                created_at__lt=end_date,
            ).count(),
            "avg_response_time": 0,  # Would require complex query to calculate
        }

        # Format results
        shop = Shop.objects.get(id=shop_id)

        result = {
            "entity_id": shop_id,
            "entity_type": "shop",
            "entity_name": shop.name,
            "metrics": {
                "total_customers": total_customers,
                "new_customers": new_customers,
                "returning_customers": returning_customers,
                "retention_rate": round(retention_rate, 2),
                "avg_bookings_per_customer": round(booking_frequency, 2),
                "one_time_customers": one_time,
                "two_to_five_bookings": two_to_five,
                "more_than_five_bookings": more_than_five,
                "review_count": review_metrics["count"],
                "avg_rating": round(review_metrics["avg_rating"], 2),
                "follow_count": follow_count,
                "unfollow_count": unfollow_count,
                "net_follows": follow_count - unfollow_count,
                "chat_conversations": chat_metrics["conversations"],
                "chat_messages": chat_metrics["messages"],
            },
            "review_distribution": rating_dict,
        }

        return result

    def get_queue_analytics(self, shop_id, start_date, end_date):
        """
        Get queue analytics for a shop.

        Args:
            shop_id: Shop ID
            start_date: Start date
            end_date: End date

        Returns:
            dict: Queue analytics data
        """
        # Get all queue tickets in the period
        tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id, join_time__gte=start_date, join_time__lt=end_date
        )

        # Get basic metrics
        total_tickets = tickets.count()
        served_tickets = tickets.filter(status="served").count()
        skipped_tickets = tickets.filter(status="skipped").count()
        cancelled_tickets = tickets.filter(status="cancelled").count()

        # Calculate service rate
        service_rate = 0
        if total_tickets > 0:
            service_rate = (served_tickets / total_tickets) * 100

        # Calculate skipped rate
        skipped_rate = 0
        if total_tickets > 0:
            skipped_rate = (skipped_tickets / total_tickets) * 100

        # Calculate cancelled rate
        cancelled_rate = 0
        if total_tickets > 0:
            cancelled_rate = (cancelled_tickets / total_tickets) * 100

        # Get average wait time (difference between join_time and serve_time)
        avg_wait_time = (
            tickets.filter(status="served", serve_time__isnull=False)
            .annotate(
                wait_time=ExpressionWrapper(
                    F("serve_time") - F("join_time"), output_field=FloatField()
                )
            )
            .aggregate(avg=Coalesce(Avg("wait_time"), 0))["avg"]
            or 0
        )

        # Convert to minutes
        avg_wait_minutes = (
            avg_wait_time.total_seconds() / 60 if hasattr(avg_wait_time, "total_seconds") else 0
        )

        # Get average service time (difference between serve_time and complete_time)
        avg_service_time = (
            tickets.filter(status="served", serve_time__isnull=False, complete_time__isnull=False)
            .annotate(
                service_time=ExpressionWrapper(
                    F("complete_time") - F("serve_time"), output_field=FloatField()
                )
            )
            .aggregate(avg=Coalesce(Avg("service_time"), 0))["avg"]
            or 0
        )

        # Convert to minutes
        avg_service_minutes = (
            avg_service_time.total_seconds() / 60
            if hasattr(avg_service_time, "total_seconds")
            else 0
        )

        # Get hourly distribution
        hourly_distribution = (
            tickets.annotate(hour=ExtractHour("join_time"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )

        # Convert to dictionary
        hourly_dict = {str(item["hour"]): item["count"] for item in hourly_distribution}

        # Get day distribution
        day_distribution = (
            tickets.annotate(day=ExtractDay("join_time"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        # Convert to dictionary
        day_dict = {str(item["day"]): item["count"] for item in day_distribution}

        # Get queue trends
        daily_tickets = (
            tickets.annotate(date=TruncDate("join_time"))
            .values("date")
            .annotate(
                count=Count("id"),
                served=Count("id", filter=Q(status="served")),
                skipped=Count("id", filter=Q(status="skipped")),
                cancelled=Count("id", filter=Q(status="cancelled")),
            )
            .order_by("date")
        )

        # Format trend data
        trend_series = {}
        for entry in daily_tickets:
            date_str = entry["date"].isoformat()
            trend_series[date_str] = entry["count"]

        # Get wait time accuracy (comparing actual vs. estimated)
        wait_time_accuracy = (
            tickets.filter(
                status="served",
                serve_time__isnull=False,
                actual_wait_time__isnull=False,
                estimated_wait_time__gt=0,
            )
            .annotate(
                accuracy=ExpressionWrapper(
                    F("actual_wait_time") / F("estimated_wait_time") * 100,
                    output_field=FloatField(),
                )
            )
            .aggregate(avg=Coalesce(Avg("accuracy"), 0))["avg"]
            or 0
        )

        # Get queue size distribution

        # This is complex to calculate accurately
        # For simplicity, we'll calculate average queue length
        # In a real implementation, we would need to track queue state over time
        avg_queue_length = (
            tickets.count() / daily_tickets.count() if daily_tickets.count() > 0 else 0
        )

        # Format results
        shop = Shop.objects.get(id=shop_id)

        result = {
            "entity_id": shop_id,
            "entity_type": "shop",
            "entity_name": shop.name,
            "metrics": {
                "total_tickets": total_tickets,
                "served_tickets": served_tickets,
                "skipped_tickets": skipped_tickets,
                "cancelled_tickets": cancelled_tickets,
                "service_rate": round(service_rate, 2),
                "skipped_rate": round(skipped_rate, 2),
                "cancelled_rate": round(cancelled_rate, 2),
                "avg_wait_minutes": round(avg_wait_minutes, 2),
                "avg_service_minutes": round(avg_service_minutes, 2),
                "wait_time_prediction_accuracy": round(wait_time_accuracy, 2),
                "avg_queue_length": round(avg_queue_length, 2),
                "tickets_per_day": (
                    round(total_tickets / daily_tickets.count(), 2)
                    if daily_tickets.count() > 0
                    else 0
                ),
            },
            "hourly_distribution": hourly_dict,
            "day_distribution": day_dict,
            "time_series": {"daily_tickets": trend_series},
        }

        return result

    def get_revenue_analysis(self, shop_id, start_date, end_date):
        """
        Get revenue analysis for a shop.

        Args:
            shop_id: Shop ID
            start_date: Start date
            end_date: End date

        Returns:
            dict: Revenue analysis data
        """
        # Get all transactions for this shop
        transactions = Transaction.objects.filter(
            content_type__model="appointment",
            content_object__shop_id=shop_id,
            created_at__gte=start_date,
            created_at__lt=end_date,
            status="succeeded",
        )

        # Get total revenue
        total_revenue = transactions.aggregate(total=Coalesce(Sum("amount"), 0))["total"] or 0

        # Get daily revenue
        daily_revenue = (
            transactions.annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(total=Coalesce(Sum("amount"), 0))
            .order_by("date")
        )

        # Format as time series
        revenue_series = {}
        for entry in daily_revenue:
            date_str = entry["date"].isoformat()
            revenue_series[date_str] = entry["total"]

        # Get revenue by service
        revenue_by_service = (
            transactions.values("content_object__service_id", "content_object__service__name")
            .annotate(total=Coalesce(Sum("amount"), 0))
            .order_by("-total")
        )

        service_revenue = []
        for entry in revenue_by_service:
            if entry["content_object__service_id"] and entry["content_object__service__name"]:
                service_revenue.append(
                    {
                        "service_id": entry["content_object__service_id"],
                        "service_name": entry["content_object__service__name"],
                        "revenue": entry["total"],
                    }
                )

        # Get revenue by specialist
        revenue_by_specialist = (
            transactions.values(
                "content_object__specialist_id",
                "content_object__specialist__employee__first_name",
                "content_object__specialist__employee__last_name",
            )
            .annotate(total=Coalesce(Sum("amount"), 0))
            .order_by("-total")
        )

        specialist_revenue = []
        for entry in revenue_by_specialist:
            if (
                entry["content_object__specialist_id"]
                and entry["content_object__specialist__employee__first_name"]
                and entry["content_object__specialist__employee__last_name"]
            ):
                full_name = f"{entry['content_object__specialist__employee__first_name']} {entry['content_object__specialist__employee__last_name']}"
                specialist_revenue.append(
                    {
                        "specialist_id": entry["content_object__specialist_id"],
                        "specialist_name": full_name,
                        "revenue": entry["total"],
                    }
                )

        # Get revenue by payment method
        revenue_by_method = (
            transactions.values("payment_type")
            .annotate(total=Coalesce(Sum("amount"), 0))
            .order_by("-total")
        )

        payment_revenue = []
        for entry in revenue_by_method:
            payment_revenue.append(
                {"payment_type": entry["payment_type"], "revenue": entry["total"]}
            )

        # Get average transaction value
        avg_transaction = 0
        if transactions.count() > 0:
            avg_transaction = total_revenue / transactions.count()

        # Get refund data
        from apps.payment.models import Refund

        refunds = Refund.objects.filter(
            transaction__in=transactions,
            created_at__gte=start_date,
            created_at__lt=end_date,
            status="succeeded",
        )

        total_refunds = refunds.aggregate(total=Coalesce(Sum("amount"), 0))["total"] or 0

        refund_rate = 0
        if total_revenue > 0:
            refund_rate = (total_refunds / total_revenue) * 100

        # Calculate net revenue
        net_revenue = total_revenue - total_refunds

        # Format results
        shop = Shop.objects.get(id=shop_id)

        result = {
            "entity_id": shop_id,
            "entity_type": "shop",
            "entity_name": shop.name,
            "metrics": {
                "total_revenue": total_revenue,
                "total_refunds": total_refunds,
                "net_revenue": net_revenue,
                "refund_rate": round(refund_rate, 2),
                "transaction_count": transactions.count(),
                "avg_transaction_value": round(avg_transaction, 2),
                "daily_avg_revenue": (
                    round(total_revenue / daily_revenue.count(), 2)
                    if daily_revenue.count() > 0
                    else 0
                ),
            },
            "time_series": {"daily_revenue": revenue_series},
            "revenue_by_service": service_revenue,
            "revenue_by_specialist": specialist_revenue,
            "revenue_by_payment_method": payment_revenue,
        }

        return result

    def get_customer_satisfaction(self, shop_id, start_date, end_date):
        """
        Get customer satisfaction analysis for a shop.

        Args:
            shop_id: Shop ID
            start_date: Start date
            end_date: End date

        Returns:
            dict: Customer satisfaction data
        """
        # Get all reviews for the shop
        shop_reviews = Review.objects.filter(
            content_type__model="shop",
            object_id=shop_id,
            created_at__gte=start_date,
            created_at__lt=end_date,
        )

        # Get basic metrics
        review_metrics = shop_reviews.aggregate(
            count=Count("id"), avg_rating=Coalesce(Avg("rating"), 0)
        )

        # Get rating distribution
        rating_distribution = (
            shop_reviews.values("rating").annotate(count=Count("id")).order_by("rating")
        )

        # Convert to dictionary
        rating_dict = {str(item["rating"]): item["count"] for item in rating_distribution}

        # Get service reviews
        service_reviews = Review.objects.filter(
            content_type__model="service",
            object_id__in=Service.objects.filter(shop_id=shop_id).values_list("id", flat=True),
            created_at__gte=start_date,
            created_at__lt=end_date,
        )

        service_metrics = service_reviews.aggregate(
            count=Count("id"), avg_rating=Coalesce(Avg("rating"), 0)
        )

        # Get specialist reviews
        specialist_reviews = Review.objects.filter(
            content_type__model="specialist",
            object_id__in=Specialist.objects.filter(employee__shop_id=shop_id).values_list(
                "id", flat=True
            ),
            created_at__gte=start_date,
            created_at__lt=end_date,
        )

        specialist_metrics = specialist_reviews.aggregate(
            count=Count("id"), avg_rating=Coalesce(Avg("rating"), 0)
        )

        # Get overall metrics
        all_reviews = (
            review_metrics["count"] + service_metrics["count"] + specialist_metrics["count"]
        )

        weighted_rating = 0
        if all_reviews > 0:
            weighted_rating = (
                (review_metrics["avg_rating"] * review_metrics["count"])
                + (service_metrics["avg_rating"] * service_metrics["count"])
                + (specialist_metrics["avg_rating"] * specialist_metrics["count"])
            ) / all_reviews

        # Get top-rated services
        top_services = (
            service_reviews.values("object_id", "content_object__name")
            .annotate(avg_rating=Avg("rating"), count=Count("id"))
            .order_by("-avg_rating")[:5]
        )

        service_ratings = []
        for service in top_services:
            if service["object_id"] and service["content_object__name"]:
                service_ratings.append(
                    {
                        "id": service["object_id"],
                        "name": service["content_object__name"],
                        "avg_rating": round(service["avg_rating"], 2),
                        "review_count": service["count"],
                    }
                )

        # Get top-rated specialists
        top_specialists = (
            specialist_reviews.values(
                "object_id",
                "content_object__employee__first_name",
                "content_object__employee__last_name",
            )
            .annotate(avg_rating=Avg("rating"), count=Count("id"))
            .order_by("-avg_rating")[:5]
        )

        specialist_ratings = []
        for specialist in top_specialists:
            if (
                specialist["object_id"]
                and specialist["content_object__employee__first_name"]
                and specialist["content_object__employee__last_name"]
            ):
                full_name = f"{specialist['content_object__employee__first_name']} {specialist['content_object__employee__last_name']}"
                specialist_ratings.append(
                    {
                        "id": specialist["object_id"],
                        "name": full_name,
                        "avg_rating": round(specialist["avg_rating"], 2),
                        "review_count": specialist["count"],
                    }
                )

        # Get simple sentiment analysis on review comments
        # This is a placeholder for more sophisticated NLP analysis
        positive_keywords = [
            "great",
            "excellent",
            "amazing",
            "good",
            "best",
            "wonderful",
            "fantastic",
        ]
        negative_keywords = [
            "bad",
            "poor",
            "terrible",
            "worst",
            "disappointing",
            "awful",
            "horrible",
        ]

        positive_counts = {}
        negative_counts = {}

        for review in shop_reviews:
            if review.comment:
                comment_lower = review.comment.lower()

                for keyword in positive_keywords:
                    if keyword in comment_lower:
                        positive_counts[keyword] = positive_counts.get(keyword, 0) + 1

                for keyword in negative_keywords:
                    if keyword in comment_lower:
                        negative_counts[keyword] = negative_counts.get(keyword, 0) + 1

        # Get top positive and negative keywords
        top_positive = sorted(positive_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_negative = sorted(negative_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        sentiment_analysis = {
            "positive_keywords": [keyword for keyword, count in top_positive],
            "negative_keywords": [keyword for keyword, count in top_negative],
            "positive_keyword_counts": {keyword: count for keyword, count in top_positive},
            "negative_keyword_counts": {keyword: count for keyword, count in top_negative},
        }

        # Format results
        shop = Shop.objects.get(id=shop_id)

        result = {
            "entity_id": shop_id,
            "entity_type": "shop",
            "entity_name": shop.name,
            "metrics": {
                "total_reviews": all_reviews,
                "shop_reviews": review_metrics["count"],
                "service_reviews": service_metrics["count"],
                "specialist_reviews": specialist_metrics["count"],
                "avg_shop_rating": round(review_metrics["avg_rating"], 2),
                "avg_service_rating": round(service_metrics["avg_rating"], 2),
                "avg_specialist_rating": round(specialist_metrics["avg_rating"], 2),
                "weighted_avg_rating": round(weighted_rating, 2),
            },
            "rating_distribution": rating_dict,
            "top_services": service_ratings,
            "top_specialists": specialist_ratings,
            "sentiment_analysis": sentiment_analysis,
        }

        return result
