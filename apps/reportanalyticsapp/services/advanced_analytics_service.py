"""
Advanced Analytics Service

This module provides sophisticated analytics capabilities including
predictive analytics, trend detection, segmentation, and data visualization
for detailed business insights.
"""

import calendar
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.db import connection, models
from django.db.models import (
    Avg,
    Case,
    Count,
    DateField,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    Max,
    Min,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import ExtractHour, TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.customersapp.models import Customer
from apps.reviewapp.models import Review
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist
from core.cache.advanced_cache import AdvancedCache, cache_key, cached

logger = logging.getLogger(__name__)

# Initialize cache
analytics_cache = AdvancedCache("analytics", default_ttl=3600)  # 1 hour default TTL


class AdvancedAnalyticsService:
    """
    Comprehensive analytics service providing sophisticated insights
    for business optimization and decision making
    """

    @staticmethod
    @cached(namespace="analytics", ttl=3600)
    def get_business_performance_metrics(
        shop_id: str,
        date_from: datetime,
        date_to: datetime,
        granularity: str = "day",  # day, week, month
        include_financials: bool = False,
        compare_to_previous: bool = False,
    ) -> Dict[str, Any]:
        """
        Get comprehensive business performance metrics

        Args:
            shop_id: Shop ID
            date_from: Start date for metrics
            date_to: End date for metrics
            granularity: Time grouping granularity (day, week, month)
            include_financials: Whether to include revenue metrics
            compare_to_previous: Whether to include comparison with previous period

        Returns:
            Dictionary with performance metrics
        """
        try:
            # Validate date range
            if date_from > date_to:
                return {
                    "success": False,
                    "message": "Start date must be before end date",
                }

            # Set truncation function based on granularity
            if granularity == "week":
                trunc_func = TruncWeek("start_time")
                period_name = "Week"
            elif granularity == "month":
                trunc_func = TruncMonth("start_time")
                period_name = "Month"
            else:  # default to day
                trunc_func = TruncDate("start_time")
                period_name = "Date"

            # Get base queryset for appointments
            appointments = Appointment.objects.filter(
                shop_id=shop_id, start_time__gte=date_from, start_time__lte=date_to
            )

            # Get metrics grouped by period
            period_metrics = (
                appointments.annotate(period=trunc_func)
                .values("period")
                .annotate(
                    completed=Count(
                        Case(
                            When(status="completed", then=1),
                            output_field=IntegerField(),
                        )
                    ),
                    cancelled=Count(
                        Case(
                            When(status="cancelled", then=1),
                            output_field=IntegerField(),
                        )
                    ),
                    no_show=Count(
                        Case(When(status="no_show", then=1), output_field=IntegerField())
                    ),
                    total=Count("id"),
                    distinct_customers=Count("customer_id", distinct=True),
                )
                .order_by("period")
            )

            # Add revenue metrics if requested
            if include_financials:
                period_metrics = period_metrics.annotate(
                    revenue=Sum(
                        Case(
                            When(payment_status="paid", then=F("service__price")),
                            default=Value(0),
                            output_field=DecimalField(),
                        )
                    ),
                    expected_revenue=Sum("service__price"),
                    lost_revenue=Sum(
                        Case(
                            When(
                                Q(status="cancelled") | Q(status="no_show"),
                                then=F("service__price"),
                            ),
                            default=Value(0),
                            output_field=DecimalField(),
                        )
                    ),
                )

            # Calculate total metrics
            totals = {
                "completed": appointments.filter(status="completed").count(),
                "cancelled": appointments.filter(status="cancelled").count(),
                "no_show": appointments.filter(status="no_show").count(),
                "total": appointments.count(),
                "distinct_customers": appointments.values("customer_id").distinct().count(),
                "avg_utilization": None,  # Calculated below
            }

            # Add financial totals if requested
            if include_financials:
                revenue_metrics = appointments.filter(payment_status="paid").aggregate(
                    revenue=Sum("service__price")
                )
                expected_revenue = appointments.aggregate(expected_revenue=Sum("service__price"))
                lost_revenue = appointments.filter(
                    Q(status="cancelled") | Q(status="no_show")
                ).aggregate(lost_revenue=Sum("service__price"))

                totals["revenue"] = revenue_metrics["revenue"] or 0
                totals["expected_revenue"] = expected_revenue["expected_revenue"] or 0
                totals["lost_revenue"] = lost_revenue["lost_revenue"] or 0

                if totals["expected_revenue"] > 0:
                    totals["revenue_realization"] = (
                        float(totals["revenue"]) / float(totals["expected_revenue"])
                    ) * 100
                else:
                    totals["revenue_realization"] = 0

            # Calculate period-over-period comparison if requested
            previous_period_data = None
            if compare_to_previous:
                # Calculate previous period date range (same duration)
                period_delta = date_to - date_from
                previous_from = date_from - period_delta - timedelta(days=1)
                previous_to = date_from - timedelta(days=1)

                # Get previous period metrics
                previous_period_data = AdvancedAnalyticsService.get_business_performance_metrics(
                    shop_id=shop_id,
                    date_from=previous_from,
                    date_to=previous_to,
                    granularity=granularity,
                    include_financials=include_financials,
                    compare_to_previous=False,  # Prevent infinite recursion
                )

            # Calculate staff utilization
            utilization_data = AdvancedAnalyticsService._calculate_staff_utilization(
                shop_id, date_from, date_to
            )
            if utilization_data:
                totals["avg_utilization"] = utilization_data.get("avg_utilization", 0)

            # Format and return results
            return {
                "success": True,
                "date_range": {
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                },
                "granularity": granularity,
                "periods": list(period_metrics),
                "period_name": period_name,
                "totals": totals,
                "previous_period": (
                    previous_period_data.get("totals", None) if previous_period_data else None
                ),
                "utilization": utilization_data,
            }

        except Exception as e:
            logger.error(f"Error calculating business performance metrics: {e}")
            return {"success": False, "message": f"Error calculating metrics: {str(e)}"}

    @staticmethod
    @cached(namespace="analytics", ttl=7200)
    def get_customer_insights(
        shop_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        segment_by: Optional[str] = None,  # age, gender, location, service_preference
    ) -> Dict[str, Any]:
        """
        Get detailed customer insights with optional segmentation

        Args:
            shop_id: Shop ID
            date_from: Optional start date filter
            date_to: Optional end date filter
            segment_by: Optional segmentation criteria

        Returns:
            Dictionary with customer insights
        """
        try:
            # Set default date range if not provided (last 90 days)
            if not date_to:
                date_to = timezone.now()
            if not date_from:
                date_from = date_to - timedelta(days=90)

            # Get base queryset for appointments
            appointments = Appointment.objects.filter(shop_id=shop_id)

            # Apply date filter if provided
            if date_from and date_to:
                appointments = appointments.filter(
                    start_time__gte=date_from, start_time__lte=date_to
                )

            # Get unique customers from appointments
            customer_ids = appointments.values_list("customer_id", flat=True).distinct()
            customers = Customer.objects.filter(id__in=customer_ids)

            # Calculate general metrics
            total_customers = customers.count()
            new_customers = customers.filter(
                created_at__gte=date_from, created_at__lte=date_to
            ).count()

            repeat_bookers = (
                appointments.values("customer_id")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
                .count()
            )

            # Retention calculation (customers who booked in both first and second half of period)
            period_midpoint = date_from + (date_to - date_from) / 2
            first_half_customers = set(
                appointments.filter(start_time__lt=period_midpoint).values_list(
                    "customer_id", flat=True
                )
            )
            second_half_customers = set(
                appointments.filter(start_time__gte=period_midpoint).values_list(
                    "customer_id", flat=True
                )
            )
            retained_customers = len(first_half_customers.intersection(second_half_customers))
            retention_rate = (
                (retained_customers / len(first_half_customers)) * 100
                if first_half_customers
                else 0
            )

            # Calculate booking frequency
            booking_frequency = (
                appointments.values("customer_id")
                .annotate(count=Count("id"))
                .aggregate(avg_bookings=Avg("count"))
            )

            # Average spend per customer
            avg_spend = (
                appointments.filter(payment_status="paid")
                .values("customer_id")
                .annotate(total_spent=Sum("service__price"))
                .aggregate(avg_spend=Avg("total_spent"))
            )

            # Customer satisfaction metrics
            customer_satisfaction = None
            try:
                reviews = Review.objects.filter(
                    shop_id=shop_id, created_at__gte=date_from, created_at__lte=date_to
                )

                if reviews.exists():
                    avg_rating = reviews.aggregate(avg_rating=Avg("rating"))
                    rating_distribution = list(
                        reviews.values("rating").annotate(count=Count("id")).order_by("rating")
                    )

                    customer_satisfaction = {
                        "avg_rating": avg_rating["avg_rating"],
                        "rating_distribution": rating_distribution,
                        "review_count": reviews.count(),
                    }
            except Exception as e:
                # Review model might not be available
                pass

            # Prepare result
            result = {
                "total_customers": total_customers,
                "new_customers": new_customers,
                "repeat_bookers": repeat_bookers,
                "retention_rate": retention_rate,
                "avg_bookings_per_customer": (
                    booking_frequency["avg_bookings"] if booking_frequency["avg_bookings"] else 0
                ),
                "avg_spend_per_customer": (avg_spend["avg_spend"] if avg_spend["avg_spend"] else 0),
                "customer_satisfaction": customer_satisfaction,
            }

            # Apply segmentation if requested
            if segment_by:
                segmentation = AdvancedAnalyticsService._segment_customers(
                    shop_id, customers, appointments, segment_by
                )
                result["segmentation"] = segmentation

            return {
                "success": True,
                "date_range": {
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                },
                "data": result,
            }

        except Exception as e:
            logger.error(f"Error calculating customer insights: {e}")
            return {
                "success": False,
                "message": f"Error calculating customer insights: {str(e)}",
            }

    @staticmethod
    @cached(namespace="analytics", ttl=43200)  # 12 hours cache
    def predict_booking_trends(
        shop_id: str, days_ahead: int = 30, include_seasonality: bool = True
    ) -> Dict[str, Any]:
        """
        Predict booking trends for upcoming period

        Args:
            shop_id: Shop ID
            days_ahead: Number of days to predict
            include_seasonality: Whether to account for weekly/monthly patterns

        Returns:
            Dictionary with booking trend predictions
        """
        try:
            # Calculate date ranges
            today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            future_date = today + timedelta(days=days_ahead)

            # Historical data (3x the prediction period to capture patterns)
            historical_start = today - timedelta(days=days_ahead * 3)

            # Get historical bookings
            historical_bookings = Appointment.objects.filter(
                shop_id=shop_id, start_time__gte=historical_start, start_time__lt=today
            )

            # Group by date to get daily counts
            daily_counts = (
                historical_bookings.annotate(date=TruncDate("start_time"))
                .values("date")
                .annotate(count=Count("id"))
                .order_by("date")
            )

            # Convert to list and fill in missing dates with zero
            date_counts = {}
            current_date = historical_start
            while current_date < today:
                date_counts[current_date.date()] = 0
                current_date += timedelta(days=1)

            for item in daily_counts:
                date_counts[item["date"]] = item["count"]

            historical_data = [
                {"date": date.isoformat(), "bookings": count} for date, count in date_counts.items()
            ]

            # Calculate moving average
            window_size = min(14, len(historical_data))  # 2 weeks or less if not enough data
            if window_size < 3:
                return {
                    "success": False,
                    "message": "Insufficient historical data for prediction",
                }

            moving_avg = []
            counts_list = [item["bookings"] for item in historical_data]

            for i in range(len(counts_list) - window_size + 1):
                window = counts_list[i : i + window_size]
                avg = sum(window) / window_size
                moving_avg.append(avg)

            # Calculate day-of-week factors if seasonality is requested
            day_of_week_factors = {}
            if include_seasonality:
                # Group historical data by day of week
                dow_counts = (
                    historical_bookings.annotate(
                        dow=models.functions.Extract("start_time", "dow")  # 0=Sunday, 6=Saturday
                    )
                    .values("dow")
                    .annotate(count=Count("id"))
                    .order_by("dow")
                )

                # Calculate average bookings by day of week
                dow_avg = {}
                for item in dow_counts:
                    dow_avg[item["dow"]] = item["count"]

                # Fill in missing days with overall average
                overall_avg = sum(dow_avg.values()) / len(dow_avg) if dow_avg else 1
                for dow in range(7):
                    if dow not in dow_avg:
                        dow_avg[dow] = overall_avg

                # Calculate day of week factors (relative to overall average)
                for dow, count in dow_avg.items():
                    day_of_week_factors[dow] = count / overall_avg if overall_avg > 0 else 1

            # Predict future bookings
            prediction = []

            # Base prediction on trend (last value of moving average)
            base_prediction = (
                moving_avg[-1]
                if moving_avg
                else (sum(counts_list) / len(counts_list) if counts_list else 0)
            )

            # Apply trend and seasonality to predict future dates
            current_date = today
            while current_date < future_date:
                date_str = current_date.date().isoformat()

                # Apply day-of-week factor if seasonality is enabled
                factor = 1.0
                if include_seasonality and day_of_week_factors:
                    dow = current_date.weekday()
                    factor = day_of_week_factors.get(dow, 1.0)

                # Calculate prediction
                predicted_bookings = max(0, round(base_prediction * factor))

                prediction.append(
                    {
                        "date": date_str,
                        "predicted_bookings": predicted_bookings,
                    }
                )

                current_date += timedelta(days=1)

            # Check if there are existing bookings for the prediction period
            existing_bookings = (
                Appointment.objects.filter(
                    shop_id=shop_id, start_time__gte=today, start_time__lt=future_date
                )
                .annotate(date=TruncDate("start_time"))
                .values("date")
                .annotate(count=Count("id"))
                .order_by("date")
            )

            # Add existing bookings to prediction
            existing_count_by_date = {
                item["date"].isoformat(): item["count"] for item in existing_bookings
            }

            for item in prediction:
                item["existing_bookings"] = existing_count_by_date.get(item["date"], 0)

            return {
                "success": True,
                "historical_data": historical_data,
                "prediction": prediction,
                "moving_average": moving_avg,
                "day_of_week_factors": (day_of_week_factors if include_seasonality else None),
            }

        except Exception as e:
            logger.error(f"Error predicting booking trends: {e}")
            return {"success": False, "message": f"Error predicting trends: {str(e)}"}

    @staticmethod
    @cached(namespace="analytics", ttl=86400)  # 24 hours cache
    def get_revenue_analytics(
        shop_id: str,
        date_from: datetime,
        date_to: datetime,
        granularity: str = "day",  # day, week, month
        include_comparison: bool = False,
    ) -> Dict[str, Any]:
        """
        Get detailed revenue analytics with breakdowns and trends

        Args:
            shop_id: Shop ID
            date_from: Start date for analytics
            date_to: End date for analytics
            granularity: Time grouping granularity
            include_comparison: Whether to include comparison with previous period

        Returns:
            Dictionary with revenue analytics
        """
        try:
            # Set truncation function based on granularity
            if granularity == "week":
                trunc_func = TruncWeek("start_time")
                period_name = "Week"
            elif granularity == "month":
                trunc_func = TruncMonth("start_time")
                period_name = "Month"
            else:  # default to day
                trunc_func = TruncDate("start_time")
                period_name = "Date"

            # Get base queryset for completed paid appointments
            completed_appointments = Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=date_from,
                start_time__lte=date_to,
                status="completed",
                payment_status="paid",
            )

            # Calculate total revenue
            total_revenue = (
                completed_appointments.aggregate(total=Sum("service__price"))["total"] or 0
            )

            # Get revenue by period
            revenue_by_period = (
                completed_appointments.annotate(period=trunc_func)
                .values("period")
                .annotate(revenue=Sum("service__price"), appointments=Count("id"))
                .order_by("period")
            )

            # Calculate revenue by service category
            revenue_by_category = (
                completed_appointments.values("service__category")
                .annotate(revenue=Sum("service__price"), appointments=Count("id"))
                .order_by("-revenue")
            )

            # Calculate revenue by service
            revenue_by_service = (
                completed_appointments.values("service__id", "service__name")
                .annotate(revenue=Sum("service__price"), appointments=Count("id"))
                .order_by("-revenue")[:10]
            )  # Top 10 services

            # Calculate revenue by specialist
            revenue_by_specialist = (
                completed_appointments.values("specialist__id", "specialist__employee__name")
                .annotate(revenue=Sum("service__price"), appointments=Count("id"))
                .order_by("-revenue")
            )

            # Calculate average service price and appointment value
            avg_metrics = completed_appointments.aggregate(
                avg_price=Avg("service__price"), total_services=Count("id")
            )

            # Calculate previous period comparison if requested
            previous_period_data = None
            if include_comparison:
                # Calculate previous period date range (same duration)
                period_delta = date_to - date_from
                previous_from = date_from - period_delta - timedelta(days=1)
                previous_to = date_from - timedelta(days=1)

                # Get previous period revenue
                previous_revenue = (
                    Appointment.objects.filter(
                        shop_id=shop_id,
                        start_time__gte=previous_from,
                        start_time__lte=previous_to,
                        status="completed",
                        payment_status="paid",
                    ).aggregate(total=Sum("service__price"))["total"]
                    or 0
                )

                # Calculate growth
                growth = 0
                if previous_revenue > 0:
                    growth = (
                        (float(total_revenue) - float(previous_revenue)) / float(previous_revenue)
                    ) * 100

                previous_period_data = {
                    "date_range": {
                        "from": previous_from.isoformat(),
                        "to": previous_to.isoformat(),
                    },
                    "total_revenue": previous_revenue,
                    "growth_percentage": growth,
                }

            # Calculate potential revenue (including no-shows and cancellations)
            potential_appointments = Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=date_from,
                start_time__lte=date_to,
                status__in=["completed", "cancelled", "no_show"],
            )

            potential_revenue = (
                potential_appointments.aggregate(total=Sum("service__price"))["total"] or 0
            )

            lost_revenue = (
                potential_appointments.filter(
                    Q(status="cancelled") | Q(status="no_show")
                ).aggregate(total=Sum("service__price"))["total"]
                or 0
            )

            # Format and return results
            return {
                "success": True,
                "date_range": {
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                },
                "granularity": granularity,
                "period_name": period_name,
                "total_revenue": total_revenue,
                "potential_revenue": potential_revenue,
                "lost_revenue": lost_revenue,
                "revenue_realization": (
                    (total_revenue / potential_revenue * 100) if potential_revenue > 0 else 0
                ),
                "avg_service_price": avg_metrics["avg_price"] or 0,
                "total_paid_appointments": avg_metrics["total_services"] or 0,
                "revenue_by_period": list(revenue_by_period),
                "revenue_by_category": list(revenue_by_category),
                "top_services": list(revenue_by_service),
                "revenue_by_specialist": list(revenue_by_specialist),
                "previous_period": previous_period_data,
            }

        except Exception as e:
            logger.error(f"Error calculating revenue analytics: {e}")
            return {
                "success": False,
                "message": f"Error calculating revenue analytics: {str(e)}",
            }

    @staticmethod
    @cached(namespace="analytics", ttl=21600)  # 6 hours cache
    def get_operational_efficiency_metrics(
        shop_id: str, date_from: datetime, date_to: datetime
    ) -> Dict[str, Any]:
        """
        Get operational efficiency metrics to identify optimization opportunities

        Args:
            shop_id: Shop ID
            date_from: Start date for metrics
            date_to: End date for metrics

        Returns:
            Dictionary with operational efficiency metrics
        """
        try:
            # Get all appointments in the period
            appointments = Appointment.objects.filter(
                shop_id=shop_id, start_time__gte=date_from, start_time__lte=date_to
            )

            # Calculate basic metrics
            total_appointments = appointments.count()
            completed_appointments = appointments.filter(status="completed").count()
            cancelled_appointments = appointments.filter(status="cancelled").count()
            no_show_appointments = appointments.filter(status="no_show").count()

            completion_rate = (
                (completed_appointments / total_appointments * 100) if total_appointments > 0 else 0
            )
            cancellation_rate = (
                (cancelled_appointments / total_appointments * 100) if total_appointments > 0 else 0
            )
            no_show_rate = (
                (no_show_appointments / total_appointments * 100) if total_appointments > 0 else 0
            )

            # Calculate buffer time metrics
            buffer_metrics = Service.objects.filter(shop_id=shop_id).aggregate(
                avg_buffer_before=Avg("buffer_before"),
                avg_buffer_after=Avg("buffer_after"),
            )

            # Calculate booking lead time (how far in advance appointments are booked)
            lead_time_data = appointments.annotate(
                lead_time=ExpressionWrapper(
                    F("start_time") - F("created_at"),
                    output_field=models.DurationField(),
                )
            ).aggregate(
                avg_lead_time=Avg("lead_time"),
                min_lead_time=Min("lead_time"),
                max_lead_time=Max("lead_time"),
            )

            # Calculate time slot utilization
            all_possible_slots = AdvancedAnalyticsService._calculate_total_available_slots(
                shop_id, date_from, date_to
            )

            if all_possible_slots and all_possible_slots > 0:
                slot_utilization = (completed_appointments / all_possible_slots) * 100
            else:
                slot_utilization = 0

            # Calculate peak hours
            hour_distribution = (
                appointments.annotate(hour=ExtractHour("start_time"))
                .values("hour")
                .annotate(count=Count("id"))
                .order_by("hour")
            )

            # Find peak hours (top 3)
            peak_hours = sorted(hour_distribution, key=lambda x: x["count"], reverse=True)[:3]

            # Calculate average durations
            duration_metrics = (
                appointments.filter(status="completed")
                .annotate(
                    actual_duration=ExpressionWrapper(
                        F("end_time") - F("start_time"),
                        output_field=models.DurationField(),
                    )
                )
                .aggregate(
                    avg_duration=Avg("actual_duration"),
                    scheduled_duration=Avg("service__duration"),
                )
            )

            # Format and return results
            result = {
                "appointment_metrics": {
                    "total": total_appointments,
                    "completed": completed_appointments,
                    "cancelled": cancelled_appointments,
                    "no_show": no_show_appointments,
                    "completion_rate": completion_rate,
                    "cancellation_rate": cancellation_rate,
                    "no_show_rate": no_show_rate,
                },
                "time_efficiency": {
                    "avg_buffer_before": buffer_metrics["avg_buffer_before"] or 0,
                    "avg_buffer_after": buffer_metrics["avg_buffer_after"] or 0,
                    "avg_lead_time_days": (
                        lead_time_data["avg_lead_time"].total_seconds() / 86400
                        if lead_time_data["avg_lead_time"]
                        else 0
                    ),
                    "min_lead_time_days": (
                        lead_time_data["min_lead_time"].total_seconds() / 86400
                        if lead_time_data["min_lead_time"]
                        else 0
                    ),
                    "max_lead_time_days": (
                        lead_time_data["max_lead_time"].total_seconds() / 86400
                        if lead_time_data["max_lead_time"]
                        else 0
                    ),
                    "slot_utilization": slot_utilization,
                    "hour_distribution": list(hour_distribution),
                    "peak_hours": peak_hours,
                },
                "duration_metrics": {
                    "avg_actual_minutes": (
                        duration_metrics["avg_duration"].total_seconds() / 60
                        if duration_metrics["avg_duration"]
                        else 0
                    ),
                    "avg_scheduled_minutes": duration_metrics["scheduled_duration"] or 0,
                    "scheduling_accuracy": (
                        (duration_metrics["avg_duration"].total_seconds() / 60)
                        / duration_metrics["scheduled_duration"]
                        * 100
                        if duration_metrics["avg_duration"]
                        and duration_metrics["scheduled_duration"]
                        else 0
                    ),
                },
            }

            return {
                "success": True,
                "date_range": {
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                },
                "data": result,
            }

        except Exception as e:
            logger.error(f"Error calculating operational efficiency metrics: {e}")
            return {
                "success": False,
                "message": f"Error calculating efficiency metrics: {str(e)}",
            }

    # ---- Private Helper Methods ----

    @staticmethod
    def _calculate_staff_utilization(
        shop_id: str, date_from: datetime, date_to: datetime
    ) -> Dict[str, Any]:
        """Calculate staff utilization metrics"""
        try:
            # Get all specialists in the shop
            specialists = Specialist.objects.filter(shop_id=shop_id)

            if not specialists.exists():
                return None

            # Get shop information for working hours
            try:
                shop = Shop.objects.get(id=shop_id)
                opening_time = shop.opening_time
                closing_time = shop.closing_time
                working_days = shop.working_days or [
                    0,
                    1,
                    2,
                    3,
                    4,
                ]  # Default to Monday-Friday
            except Shop.DoesNotExist:
                # Default working hours if shop settings not available
                opening_time = "09:00:00"
                closing_time = "17:00:00"
                working_days = [0, 1, 2, 3, 4]  # Monday-Friday

            # Calculate total working hours in period
            total_working_hours = 0
            current_date = date_from.date()
            end_date = date_to.date()

            while current_date <= end_date:
                # Check if this is a working day
                if current_date.weekday() in working_days:
                    # Parse opening and closing times
                    if isinstance(opening_time, str):
                        opening_hours, opening_minutes, opening_seconds = map(
                            int, opening_time.split(":")
                        )
                    else:
                        opening_hours, opening_minutes, opening_seconds = (
                            opening_time.hour,
                            opening_time.minute,
                            opening_time.second,
                        )

                    if isinstance(closing_time, str):
                        closing_hours, closing_minutes, closing_seconds = map(
                            int, closing_time.split(":")
                        )
                    else:
                        closing_hours, closing_minutes, closing_seconds = (
                            closing_time.hour,
                            closing_time.minute,
                            closing_time.second,
                        )

                    # Calculate hours in this day
                    hours = closing_hours - opening_hours
                    minutes = closing_minutes - opening_minutes
                    total_hours = hours + (minutes / 60)

                    total_working_hours += total_hours

                current_date += timedelta(days=1)

            # Calculate total available specialist hours
            total_available_hours = total_working_hours * specialists.count()

            # Get all completed appointments
            appointments = Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=date_from,
                start_time__lte=date_to,
                status="completed",
            )

            # Calculate booked hours
            total_booked_minutes = 0
            for appointment in appointments:
                # Use actual duration if available, otherwise use service duration
                if appointment.end_time and appointment.start_time:
                    duration = (appointment.end_time - appointment.start_time).total_seconds() / 60
                else:
                    duration = appointment.service.duration if appointment.service else 0

                total_booked_minutes += duration

            total_booked_hours = total_booked_minutes / 60

            # Calculate utilization percentage
            utilization = (
                (total_booked_hours / total_available_hours * 100)
                if total_available_hours > 0
                else 0
            )

            # Calculate per-specialist utilization
            specialist_utilization = []
            for specialist in specialists:
                specialist_appointments = appointments.filter(specialist=specialist)

                # Calculate booked hours for this specialist
                specialist_booked_minutes = 0
                for appointment in specialist_appointments:
                    if appointment.end_time and appointment.start_time:
                        duration = (
                            appointment.end_time - appointment.start_time
                        ).total_seconds() / 60
                    else:
                        duration = appointment.service.duration if appointment.service else 0

                    specialist_booked_minutes += duration

                specialist_booked_hours = specialist_booked_minutes / 60

                # Calculate personal utilization
                personal_utilization = (
                    (specialist_booked_hours / total_working_hours * 100)
                    if total_working_hours > 0
                    else 0
                )

                specialist_data = {
                    "id": str(specialist.id),
                    "name": (
                        specialist.employee.name
                        if hasattr(specialist, "employee")
                        else f"Specialist {specialist.id}"
                    ),
                    "booked_hours": specialist_booked_hours,
                    "available_hours": total_working_hours,
                    "utilization": personal_utilization,
                    "appointment_count": specialist_appointments.count(),
                }

                specialist_utilization.append(specialist_data)

            # Sort by utilization (descending)
            specialist_utilization.sort(key=lambda x: x["utilization"], reverse=True)

            return {
                "total_available_hours": total_available_hours,
                "total_booked_hours": total_booked_hours,
                "avg_utilization": utilization,
                "specialist_count": specialists.count(),
                "specialists": specialist_utilization,
            }

        except Exception as e:
            logger.error(f"Error calculating staff utilization: {e}")
            return None

    @staticmethod
    def _segment_customers(
        shop_id: str, customers, appointments, segment_by: str
    ) -> Dict[str, Any]:
        """Segment customers by criteria"""
        segmentation = {}

        if segment_by == "age":
            # Age brackets
            age_brackets = {
                "Under 18": {"min": 0, "max": 17},
                "18-24": {"min": 18, "max": 24},
                "25-34": {"min": 25, "max": 34},
                "35-44": {"min": 35, "max": 44},
                "45-54": {"min": 45, "max": 54},
                "55-64": {"min": 55, "max": 64},
                "65+": {"min": 65, "max": 150},
                "Unknown": {"min": None, "max": None},
            }

            age_distribution = {}
            for bracket, range_vals in age_brackets.items():
                if range_vals["min"] is not None and range_vals["max"] is not None:
                    count = customers.filter(
                        age__gte=range_vals["min"], age__lte=range_vals["max"]
                    ).count()
                else:
                    # Count customers with no age data
                    count = customers.filter(Q(age__isnull=True) | Q(age=0)).count()

                age_distribution[bracket] = count

            segmentation = {"type": "age", "distribution": age_distribution}

        elif segment_by == "gender":
            # Gender distribution
            gender_distribution = {}
            gender_counts = customers.values("gender").annotate(count=Count("id"))

            for item in gender_counts:
                gender = item["gender"] or "Unknown"
                gender_distribution[gender] = item["count"]

            segmentation = {"type": "gender", "distribution": gender_distribution}

        elif segment_by == "location":
            # Location distribution
            try:
                # Group by city or region
                location_distribution = {}
                location_counts = customers.values("city").annotate(count=Count("id"))

                for item in location_counts:
                    city = item["city"] or "Unknown"
                    location_distribution[city] = item["count"]

                segmentation = {
                    "type": "location",
                    "distribution": location_distribution,
                }
            except Exception as e:
                # Customer model might not have location fields
                segmentation = {
                    "type": "location",
                    "error": "Location data not available",
                }

        elif segment_by == "service_preference":
            # Service preference distribution
            service_preferences = {}
            service_counts = (
                appointments.values("service__id", "service__name", "service__category")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            for item in service_counts:
                service_name = item["service__name"] or f"Service {item['service__id']}"
                service_preferences[service_name] = {
                    "count": item["count"],
                    "category": item["service__category"] or "Uncategorized",
                }

            # Group by category
            category_preferences = {}
            for service, data in service_preferences.items():
                category = data["category"]
                if category not in category_preferences:
                    category_preferences[category] = 0

                category_preferences[category] += data["count"]

            segmentation = {
                "type": "service_preference",
                "services": service_preferences,
                "categories": category_preferences,
            }

        return segmentation

    @staticmethod
    def _calculate_total_available_slots(
        shop_id: str, date_from: datetime, date_to: datetime
    ) -> int:
        """Calculate total available appointment slots in period"""
        try:
            # Get shop information for working hours
            try:
                shop = Shop.objects.get(id=shop_id)
                opening_time = shop.opening_time
                closing_time = shop.closing_time
                working_days = shop.working_days or [
                    0,
                    1,
                    2,
                    3,
                    4,
                ]  # Default to Monday-Friday
                slot_duration = 30  # Default 30-minute slots
            except Shop.DoesNotExist:
                return 0

            # Get all specialists
            specialists = Specialist.objects.filter(shop_id=shop_id).count()
            if specialists == 0:
                return 0

            # Calculate slots per day
            if isinstance(opening_time, str):
                opening_hours, opening_minutes = map(int, opening_time.split(":")[:2])
            else:
                opening_hours, opening_minutes = opening_time.hour, opening_time.minute

            if isinstance(closing_time, str):
                closing_hours, closing_minutes = map(int, closing_time.split(":")[:2])
            else:
                closing_hours, closing_minutes = closing_time.hour, closing_time.minute

            # Calculate minutes in working day
            opening_minutes_total = opening_hours * 60 + opening_minutes
            closing_minutes_total = closing_hours * 60 + closing_minutes
            working_minutes = closing_minutes_total - opening_minutes_total

            # Calculate slots per day per specialist
            slots_per_day_per_specialist = working_minutes // slot_duration

            # Count working days in period
            working_day_count = 0
            current_date = date_from.date()
            end_date = date_to.date()

            while current_date <= end_date:
                if current_date.weekday() in working_days:
                    working_day_count += 1
                current_date += timedelta(days=1)

            # Calculate total possible slots
            total_possible_slots = working_day_count * slots_per_day_per_specialist * specialists

            return total_possible_slots

        except Exception as e:
            logger.error(f"Error calculating total available slots: {e}")
            return 0
