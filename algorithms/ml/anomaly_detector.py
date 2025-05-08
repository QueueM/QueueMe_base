"""
Business metrics anomaly detection algorithms.

This module provides sophisticated algorithms for detecting anomalies in business
metrics such as booking patterns, revenue, queue wait times, and customer engagement.
These anomalies can be used to alert business owners about unusual changes that
may require attention or represent new opportunities.
"""

import logging
from datetime import datetime, timedelta
from statistics import mean, median, quantiles, stdev
from typing import Dict, List, Tuple

from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Anomaly detection engine for business metrics.

    This class uses statistical methods to identify unusual patterns in business data,
    helping shop owners and Queue Me administrators identify potential issues or
    opportunities that require attention.
    """

    # Configurable thresholds for sensitivity
    ZSCORE_THRESHOLD = 2.5  # Z-score threshold for anomaly detection
    IQR_MULTIPLIER = 1.5  # Multiplier for IQR-based outlier detection

    # Minimum samples required for reliable anomaly detection
    MIN_SAMPLES = 10

    # Business metrics to monitor
    METRICS = [
        "booking_count",
        "revenue",
        "average_wait_time",
        "no_show_rate",
        "review_count",
        "average_rating",
        "cancellation_rate",
        "reel_engagement",
        "customer_retention",
    ]

    def __init__(self, sensitivity: str = "medium"):
        """
        Initialize anomaly detector with configurable sensitivity.

        Args:
            sensitivity: Sensitivity level ('low', 'medium', 'high')
        """
        # Adjust thresholds based on sensitivity
        if sensitivity == "low":
            self.ZSCORE_THRESHOLD = 3.0
            self.IQR_MULTIPLIER = 2.0
        elif sensitivity == "high":
            self.ZSCORE_THRESHOLD = 2.0
            self.IQR_MULTIPLIER = 1.2
        # else keep default (medium)

    def detect_shop_anomalies(
        self,
        shop_id: str,
        metrics: List[str] = None,
        time_range: str = "day",
        comparison_period: int = 30,
    ) -> Dict:
        """
        Detect anomalies in shop metrics compared to historical patterns.

        Args:
            shop_id: The shop ID to analyze
            metrics: List of specific metrics to check (defaults to all)
            time_range: Granularity ('day', 'week', 'month')
            comparison_period: Number of previous periods to use as baseline

        Returns:
            Dictionary with detected anomalies and their details
        """
        try:
            # Use all metrics if none specified
            if not metrics:
                metrics = self.METRICS

            # Get the current period's data
            current_data = self._get_current_period_data(shop_id, metrics, time_range)

            # Get historical data for comparison
            historical_data = self._get_historical_data(
                shop_id, metrics, time_range, comparison_period
            )

            # Detect anomalies by comparing current to historical
            anomalies = {}

            for metric in metrics:
                current_value = current_data.get(metric)

                # Skip if we don't have current data for this metric
                if current_value is None:
                    continue

                historical_values = historical_data.get(metric, [])

                # Skip if not enough historical data
                if len(historical_values) < self.MIN_SAMPLES:
                    continue

                # Perform anomaly detection
                is_anomaly, anomaly_details = self._detect_anomaly(
                    current_value, historical_values, metric
                )

                if is_anomaly:
                    anomalies[metric] = anomaly_details

            return {
                "shop_id": shop_id,
                "time_range": time_range,
                "has_anomalies": len(anomalies) > 0,
                "anomalies": anomalies,
            }

        except Exception as e:
            logger.exception(f"Error detecting shop anomalies: {str(e)}")
            return {
                "shop_id": shop_id,
                "time_range": time_range,
                "has_anomalies": False,
                "anomalies": {},
                "error": str(e),
            }

    def detect_platform_anomalies(
        self,
        metrics: List[str] = None,
        time_range: str = "day",
        comparison_period: int = 30,
    ) -> Dict:
        """
        Detect anomalies in platform-wide metrics.

        Args:
            metrics: List of specific metrics to check (defaults to all)
            time_range: Granularity ('day', 'week', 'month')
            comparison_period: Number of previous periods to use as baseline

        Returns:
            Dictionary with detected anomalies and their details
        """
        try:
            # Platform metrics - slightly different from shop metrics
            platform_metrics = [
                "total_bookings",
                "active_users",
                "new_user_registrations",
                "total_revenue",
                "active_shops",
                "average_platform_rating",
            ]

            # Use all platform metrics if none specified
            if not metrics:
                metrics = platform_metrics

            # Get the current period's data
            current_data = self._get_platform_current_data(metrics, time_range)

            # Get historical data for comparison
            historical_data = self._get_platform_historical_data(
                metrics, time_range, comparison_period
            )

            # Detect anomalies by comparing current to historical
            anomalies = {}

            for metric in metrics:
                current_value = current_data.get(metric)

                # Skip if we don't have current data for this metric
                if current_value is None:
                    continue

                historical_values = historical_data.get(metric, [])

                # Skip if not enough historical data
                if len(historical_values) < self.MIN_SAMPLES:
                    continue

                # Perform anomaly detection
                is_anomaly, anomaly_details = self._detect_anomaly(
                    current_value, historical_values, metric
                )

                if is_anomaly:
                    anomalies[metric] = anomaly_details

            return {
                "time_range": time_range,
                "has_anomalies": len(anomalies) > 0,
                "anomalies": anomalies,
            }

        except Exception as e:
            logger.exception(f"Error detecting platform anomalies: {str(e)}")
            return {
                "time_range": time_range,
                "has_anomalies": False,
                "anomalies": {},
                "error": str(e),
            }

    def detect_specialist_anomalies(
        self,
        specialist_id: str,
        metrics: List[str] = None,
        time_range: str = "day",
        comparison_period: int = 30,
    ) -> Dict:
        """
        Detect anomalies in specialist metrics.

        Args:
            specialist_id: The specialist ID to analyze
            metrics: List of specific metrics to check (defaults to all)
            time_range: Granularity ('day', 'week', 'month')
            comparison_period: Number of previous periods to use as baseline

        Returns:
            Dictionary with detected anomalies and their details
        """
        try:
            # Specialist metrics
            specialist_metrics = [
                "booking_count",
                "revenue",
                "average_rating",
                "no_show_rate",
                "service_time",
                "customer_retention",
            ]

            # Use all specialist metrics if none specified
            if not metrics:
                metrics = specialist_metrics

            # Get the current period's data
            current_data = self._get_specialist_current_data(
                specialist_id, metrics, time_range
            )

            # Get historical data for comparison
            historical_data = self._get_specialist_historical_data(
                specialist_id, metrics, time_range, comparison_period
            )

            # Detect anomalies by comparing current to historical
            anomalies = {}

            for metric in metrics:
                current_value = current_data.get(metric)

                # Skip if we don't have current data for this metric
                if current_value is None:
                    continue

                historical_values = historical_data.get(metric, [])

                # Skip if not enough historical data
                if len(historical_values) < self.MIN_SAMPLES:
                    continue

                # Perform anomaly detection
                is_anomaly, anomaly_details = self._detect_anomaly(
                    current_value, historical_values, metric
                )

                if is_anomaly:
                    anomalies[metric] = anomaly_details

            return {
                "specialist_id": specialist_id,
                "time_range": time_range,
                "has_anomalies": len(anomalies) > 0,
                "anomalies": anomalies,
            }

        except Exception as e:
            logger.exception(f"Error detecting specialist anomalies: {str(e)}")
            return {
                "specialist_id": specialist_id,
                "time_range": time_range,
                "has_anomalies": False,
                "anomalies": {},
                "error": str(e),
            }

    def _detect_anomaly(
        self, current_value: float, historical_values: List[float], metric_name: str
    ) -> Tuple[bool, Dict]:
        """
        Perform anomaly detection using multiple statistical methods.

        Args:
            current_value: The current value to check
            historical_values: List of historical values for comparison
            metric_name: Name of the metric (for context-aware thresholds)

        Returns:
            Tuple of (is_anomaly, anomaly_details)
        """
        # Calculate basic statistics
        hist_mean = mean(historical_values)
        hist_median = median(historical_values)

        # Standard deviation (with at least 2 values)
        if len(historical_values) >= 2:
            hist_stddev = stdev(historical_values)
        else:
            hist_stddev = abs(hist_mean * 0.1)  # Fallback - assume 10% variation

        # Calculate Z-score (standard deviations from mean)
        if hist_stddev > 0:
            z_score = (current_value - hist_mean) / hist_stddev
        else:
            z_score = 0

        # Calculate percentiles for IQR method
        quartiles = quantiles(historical_values, n=4)
        q1, q3 = quartiles[0], quartiles[2]
        iqr = q3 - q1

        # Define bounds using IQR method
        lower_bound = q1 - (self.IQR_MULTIPLIER * iqr)
        upper_bound = q3 + (self.IQR_MULTIPLIER * iqr)

        # Check if the value is an anomaly using either method
        z_score_anomaly = abs(z_score) > self.ZSCORE_THRESHOLD
        iqr_anomaly = current_value < lower_bound or current_value > upper_bound

        # An anomaly if either method detects it (more sensitive)
        # Could use 'and' instead of 'or' for higher confidence (fewer false positives)
        is_anomaly = z_score_anomaly or iqr_anomaly

        # Determine direction and severity
        if is_anomaly:
            direction = "increase" if current_value > hist_mean else "decrease"

            # Calculate percentage change
            percent_change = (
                ((current_value - hist_mean) / hist_mean * 100) if hist_mean != 0 else 0
            )

            # Determine severity
            severity = "medium"  # Default
            abs_z_score = abs(z_score)

            if abs_z_score > self.ZSCORE_THRESHOLD * 2:
                severity = "critical"
            elif abs_z_score > self.ZSCORE_THRESHOLD * 1.5:
                severity = "high"
            elif abs_z_score <= self.ZSCORE_THRESHOLD * 1.2:
                severity = "low"

            # Build anomaly details
            anomaly_details = {
                "current_value": current_value,
                "historical_mean": hist_mean,
                "historical_median": hist_median,
                "z_score": z_score,
                "direction": direction,
                "percent_change": percent_change,
                "severity": severity,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
            }

            # Enhance with metric-specific insights
            anomaly_details["insights"] = self._generate_insights(
                metric_name, direction, percent_change, severity
            )

            return True, anomaly_details
        else:
            # Not an anomaly
            return False, {}

    def _generate_insights(
        self, metric_name: str, direction: str, percent_change: float, severity: str
    ) -> List[str]:
        """
        Generate human-readable insights based on the anomaly.

        Args:
            metric_name: The metric that shows an anomaly
            direction: 'increase' or 'decrease'
            percent_change: Percentage change from baseline
            severity: Anomaly severity level

        Returns:
            List of insight strings
        """
        insights = []
        abs_change = abs(percent_change)

        # Format the percent change for display
        formatted_change = f"{abs_change:.1f}%"

        # Common patterns based on metric and direction
        if metric_name == "booking_count":
            if direction == "increase":
                insights.append(
                    f"Bookings have increased by {formatted_change} compared to normal."
                )
                if severity in ["high", "critical"]:
                    insights.append(
                        "You may need additional staff to handle increased demand."
                    )
            else:
                insights.append(
                    f"Bookings have decreased by {formatted_change} compared to normal."
                )
                if severity in ["high", "critical"]:
                    insights.append(
                        "Check for external factors or recent changes that might explain the drop."
                    )

        elif metric_name == "revenue" or metric_name == "total_revenue":
            if direction == "increase":
                insights.append(
                    f"Revenue has increased by {formatted_change} compared to normal."
                )
                if severity == "critical":
                    insights.append(
                        "This is a significant increase that warrants investigation."
                    )
            else:
                insights.append(
                    f"Revenue has decreased by {formatted_change} compared to normal."
                )
                if severity in ["high", "critical"]:
                    insights.append(
                        "Review pricing, booking volume, and cancellation rates for potential causes."
                    )

        elif metric_name == "average_wait_time":
            if direction == "increase":
                insights.append(
                    f"Wait times have increased by {formatted_change} compared to normal."
                )
                insights.append(
                    "Consider adding more staff or reviewing service efficiency."
                )
            else:
                insights.append(
                    f"Wait times have decreased by {formatted_change} compared to normal."
                )
                insights.append(
                    "Your efficiency has improved or customer volume may be lower than usual."
                )

        elif metric_name == "no_show_rate":
            if direction == "increase":
                insights.append(
                    f"No-show rate has increased by {formatted_change} compared to normal."
                )
                insights.append(
                    "Consider strengthening your reminder system or cancellation policy."
                )
            else:
                insights.append(
                    f"No-show rate has decreased by {formatted_change} compared to normal."
                )
                insights.append(
                    "Your reminder system or booking confirmation process is working well."
                )

        elif (
            metric_name == "average_rating" or metric_name == "average_platform_rating"
        ):
            if direction == "increase":
                insights.append(
                    f"Ratings have improved by {formatted_change} compared to normal."
                )
                insights.append(
                    "Recent changes appear to be having a positive impact on customer satisfaction."
                )
            else:
                insights.append(
                    f"Ratings have decreased by {formatted_change} compared to normal."
                )
                if severity in ["high", "critical"]:
                    insights.append(
                        "Review recent reviews for specific issues that may need addressing."
                    )

        elif metric_name == "cancellation_rate":
            if direction == "increase":
                insights.append(
                    f"Cancellation rate has increased by {formatted_change} compared to normal."
                )
                insights.append(
                    "Review your confirmation process and consider policy adjustments."
                )
            else:
                insights.append(
                    f"Cancellation rate has decreased by {formatted_change} compared to normal."
                )

        elif metric_name == "reel_engagement":
            if direction == "increase":
                insights.append(
                    f"Content engagement has increased by {formatted_change} compared to normal."
                )
                insights.append(
                    "Your recent content is resonating well with customers."
                )
            else:
                insights.append(
                    f"Content engagement has decreased by {formatted_change} compared to normal."
                )
                insights.append(
                    "You may want to review your content strategy or posting frequency."
                )

        elif metric_name == "customer_retention":
            if direction == "increase":
                insights.append(
                    f"Customer retention has improved by {formatted_change} compared to normal."
                )
                insights.append(
                    "Your service quality and customer experience strategies are working well."
                )
            else:
                insights.append(
                    f"Customer retention has decreased by {formatted_change} compared to normal."
                )
                insights.append(
                    "Review the customer experience to identify potential issues."
                )

        elif metric_name == "active_users":
            if direction == "increase":
                insights.append(
                    f"Active users have increased by {formatted_change} compared to normal."
                )
            else:
                insights.append(
                    f"Active users have decreased by {formatted_change} compared to normal."
                )

        elif metric_name == "new_user_registrations":
            if direction == "increase":
                insights.append(
                    f"New user registrations have increased by {formatted_change} compared to normal."
                )
                insights.append(
                    "Your marketing efforts or word-of-mouth referrals may be particularly effective."
                )
            else:
                insights.append(
                    f"New user registrations have decreased by {formatted_change} compared to normal."
                )

        # Add severity-based insight
        if severity == "critical":
            insights.append(
                "This requires immediate attention as it's a major deviation from normal patterns."
            )
        elif severity == "high":
            insights.append("This significant change should be investigated promptly.")

        return insights

    def _get_current_period_data(
        self, shop_id: str, metrics: List[str], time_range: str
    ) -> Dict:
        """
        Get metrics data for the current period.

        Args:
            shop_id: The shop ID
            metrics: List of metrics to retrieve
            time_range: 'day', 'week', or 'month'

        Returns:
            Dictionary with metric values
        """
        # Calculate current period dates
        now = timezone.now()

        if time_range == "day":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == "week":
            # Start of week (Sunday)
            start_date = (now - timedelta(days=now.weekday() + 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif time_range == "month":
            # Start of month
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            # Default to day
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Initialize results
        results = {}

        # Get relevant models based on the requested metrics
        if any(
            m in metrics for m in ["booking_count", "no_show_rate", "cancellation_rate"]
        ):
            from apps.bookingapp.models import Appointment

            # Total bookings in period
            if "booking_count" in metrics:
                booking_count = Appointment.objects.filter(
                    shop_id=shop_id, created_at__gte=start_date
                ).count()
                results["booking_count"] = booking_count

            # No-show rate
            if "no_show_rate" in metrics:
                total_appointments = Appointment.objects.filter(
                    shop_id=shop_id,
                    start_time__gte=start_date,
                    status__in=["completed", "no_show"],
                ).count()

                no_shows = Appointment.objects.filter(
                    shop_id=shop_id, start_time__gte=start_date, status="no_show"
                ).count()

                if total_appointments > 0:
                    no_show_rate = no_shows / total_appointments
                    results["no_show_rate"] = no_show_rate

            # Cancellation rate
            if "cancellation_rate" in metrics:
                total_bookings = Appointment.objects.filter(
                    shop_id=shop_id, created_at__gte=start_date
                ).count()

                cancellations = Appointment.objects.filter(
                    shop_id=shop_id, created_at__gte=start_date, status="cancelled"
                ).count()

                if total_bookings > 0:
                    cancellation_rate = cancellations / total_bookings
                    results["cancellation_rate"] = cancellation_rate

        # Revenue
        if "revenue" in metrics:
            from apps.payment.models import Transaction

            total_revenue = (
                Transaction.objects.filter(
                    content_type__model="appointment",
                    content_object__shop_id=shop_id,
                    status="succeeded",
                    created_at__gte=start_date,
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )

            results["revenue"] = float(total_revenue)

        # Average wait time
        if "average_wait_time" in metrics:
            from apps.queueapp.models import QueueTicket

            wait_times = QueueTicket.objects.filter(
                queue__shop_id=shop_id,
                status="served",
                complete_time__gte=start_date,
                actual_wait_time__isnull=False,
            ).values_list("actual_wait_time", flat=True)

            if wait_times:
                avg_wait_time = sum(wait_times) / len(wait_times)
                results["average_wait_time"] = avg_wait_time

        # Reviews
        if any(m in metrics for m in ["review_count", "average_rating"]):
            from apps.reviewapp.models import Review

            # Review count
            if "review_count" in metrics:
                review_count = Review.objects.filter(
                    content_type__model="shop",
                    object_id=shop_id,
                    created_at__gte=start_date,
                ).count()
                results["review_count"] = review_count

            # Average rating
            if "average_rating" in metrics:
                ratings = Review.objects.filter(
                    content_type__model="shop",
                    object_id=shop_id,
                    created_at__gte=start_date,
                ).values_list("rating", flat=True)

                if ratings:
                    avg_rating = sum(ratings) / len(ratings)
                    results["average_rating"] = avg_rating

        # Content engagement
        if "reel_engagement" in metrics:
            from apps.reelsapp.models import Reel, ReelEngagement

            # Get reels from this shop in the period
            reels = Reel.objects.filter(shop_id=shop_id, created_at__gte=start_date)

            if reels.exists():
                # Count engagements (likes, comments, shares)
                engagement_count = ReelEngagement.objects.filter(reel__in=reels).count()

                # Normalize by number of reels
                avg_engagement = engagement_count / reels.count()
                results["reel_engagement"] = avg_engagement

        # Customer retention
        if "customer_retention" in metrics:
            from apps.bookingapp.models import Appointment

            # Get unique customers who had appointments before this period
            previous_customers = (
                Appointment.objects.filter(shop_id=shop_id, created_at__lt=start_date)
                .values_list("customer_id", flat=True)
                .distinct()
            )

            # Count how many returned in this period
            returning_customers = (
                Appointment.objects.filter(
                    shop_id=shop_id,
                    created_at__gte=start_date,
                    customer_id__in=previous_customers,
                )
                .values_list("customer_id", flat=True)
                .distinct()
                .count()
            )

            if previous_customers:
                retention_rate = returning_customers / len(set(previous_customers))
                results["customer_retention"] = retention_rate

        return results

    def _get_historical_data(
        self, shop_id: str, metrics: List[str], time_range: str, comparison_period: int
    ) -> Dict:
        """
        Get historical metrics data for comparison.

        Args:
            shop_id: The shop ID
            metrics: List of metrics to retrieve
            time_range: 'day', 'week', or 'month'
            comparison_period: Number of previous periods to include

        Returns:
            Dictionary with lists of historical values for each metric
        """
        # Calculate period boundaries for historical data
        now = timezone.now()

        # Initialize results
        historical_data = {metric: [] for metric in metrics}

        # Generate periods for historical data collection
        periods = []

        if time_range == "day":
            for i in range(1, comparison_period + 1):
                periods.append((now - timedelta(days=i), now - timedelta(days=i - 1)))
        elif time_range == "week":
            for i in range(1, comparison_period + 1):
                periods.append((now - timedelta(weeks=i), now - timedelta(weeks=i - 1)))
        elif time_range == "month":
            # Approximate months as 30 days for simplicity
            for i in range(1, comparison_period + 1):
                periods.append(
                    (now - timedelta(days=i * 30), now - timedelta(days=(i - 1) * 30))
                )

        # Collect data for each period
        for start_date, end_date in periods:
            # Get data for this period
            period_data = self._get_period_data(shop_id, metrics, start_date, end_date)

            # Add to historical collections
            for metric in metrics:
                if metric in period_data and period_data[metric] is not None:
                    historical_data[metric].append(period_data[metric])

        return historical_data

    def _get_period_data(
        self, shop_id: str, metrics: List[str], start_date: datetime, end_date: datetime
    ) -> Dict:
        """
        Get metrics data for a specific historical period.

        Args:
            shop_id: The shop ID
            metrics: List of metrics to retrieve
            start_date: Period start datetime
            end_date: Period end datetime

        Returns:
            Dictionary with metric values for the period
        """
        # Implementation is similar to _get_current_period_data
        # but with specified date range instead of 'current period'
        results = {}

        # Get relevant models based on the requested metrics
        if any(
            m in metrics for m in ["booking_count", "no_show_rate", "cancellation_rate"]
        ):
            from apps.bookingapp.models import Appointment

            # Total bookings in period
            if "booking_count" in metrics:
                booking_count = Appointment.objects.filter(
                    shop_id=shop_id, created_at__gte=start_date, created_at__lt=end_date
                ).count()
                results["booking_count"] = booking_count

            # No-show rate
            if "no_show_rate" in metrics:
                total_appointments = Appointment.objects.filter(
                    shop_id=shop_id,
                    start_time__gte=start_date,
                    start_time__lt=end_date,
                    status__in=["completed", "no_show"],
                ).count()

                no_shows = Appointment.objects.filter(
                    shop_id=shop_id,
                    start_time__gte=start_date,
                    start_time__lt=end_date,
                    status="no_show",
                ).count()

                if total_appointments > 0:
                    no_show_rate = no_shows / total_appointments
                    results["no_show_rate"] = no_show_rate

            # Cancellation rate
            if "cancellation_rate" in metrics:
                total_bookings = Appointment.objects.filter(
                    shop_id=shop_id, created_at__gte=start_date, created_at__lt=end_date
                ).count()

                cancellations = Appointment.objects.filter(
                    shop_id=shop_id,
                    created_at__gte=start_date,
                    created_at__lt=end_date,
                    status="cancelled",
                ).count()

                if total_bookings > 0:
                    cancellation_rate = cancellations / total_bookings
                    results["cancellation_rate"] = cancellation_rate

        # Revenue
        if "revenue" in metrics:
            from apps.payment.models import Transaction

            total_revenue = (
                Transaction.objects.filter(
                    content_type__model="appointment",
                    content_object__shop_id=shop_id,
                    status="succeeded",
                    created_at__gte=start_date,
                    created_at__lt=end_date,
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )

            results["revenue"] = float(total_revenue)

        # Average wait time
        if "average_wait_time" in metrics:
            from apps.queueapp.models import QueueTicket

            wait_times = QueueTicket.objects.filter(
                queue__shop_id=shop_id,
                status="served",
                complete_time__gte=start_date,
                complete_time__lt=end_date,
                actual_wait_time__isnull=False,
            ).values_list("actual_wait_time", flat=True)

            if wait_times:
                avg_wait_time = sum(wait_times) / len(wait_times)
                results["average_wait_time"] = avg_wait_time

        # Reviews
        if any(m in metrics for m in ["review_count", "average_rating"]):
            from apps.reviewapp.models import Review

            # Review count
            if "review_count" in metrics:
                review_count = Review.objects.filter(
                    content_type__model="shop",
                    object_id=shop_id,
                    created_at__gte=start_date,
                    created_at__lt=end_date,
                ).count()
                results["review_count"] = review_count

            # Average rating
            if "average_rating" in metrics:
                ratings = Review.objects.filter(
                    content_type__model="shop",
                    object_id=shop_id,
                    created_at__gte=start_date,
                    created_at__lt=end_date,
                ).values_list("rating", flat=True)

                if ratings:
                    avg_rating = sum(ratings) / len(ratings)
                    results["average_rating"] = avg_rating

        # Content engagement
        if "reel_engagement" in metrics:
            from apps.reelsapp.models import Reel, ReelEngagement

            # Get reels from this shop in the period
            reels = Reel.objects.filter(
                shop_id=shop_id, created_at__gte=start_date, created_at__lt=end_date
            )

            if reels.exists():
                # Count engagements (likes, comments, shares)
                engagement_count = ReelEngagement.objects.filter(reel__in=reels).count()

                # Normalize by number of reels
                avg_engagement = engagement_count / reels.count()
                results["reel_engagement"] = avg_engagement

        # Customer retention
        if "customer_retention" in metrics:
            from apps.bookingapp.models import Appointment

            # Get unique customers who had appointments before this period
            previous_period_start = start_date - (end_date - start_date)
            previous_customers = (
                Appointment.objects.filter(
                    shop_id=shop_id,
                    created_at__gte=previous_period_start,
                    created_at__lt=start_date,
                )
                .values_list("customer_id", flat=True)
                .distinct()
            )

            # Count how many returned in this period
            returning_customers = (
                Appointment.objects.filter(
                    shop_id=shop_id,
                    created_at__gte=start_date,
                    created_at__lt=end_date,
                    customer_id__in=previous_customers,
                )
                .values_list("customer_id", flat=True)
                .distinct()
                .count()
            )

            if previous_customers:
                retention_rate = returning_customers / len(set(previous_customers))
                results["customer_retention"] = retention_rate

        return results

    # Platform-wide methods would follow similar patterns but collect data
    # across all shops rather than filtering by a specific shop_id

    def _get_platform_current_data(self, metrics: List[str], time_range: str) -> Dict:
        """Get current period data for platform-wide metrics."""
        # This would be implemented similarly to _get_current_period_data
        # but with platform-wide aggregation instead of shop-specific
        # For brevity, implementation details are omitted
        return {}

    def _get_platform_historical_data(
        self, metrics: List[str], time_range: str, comparison_period: int
    ) -> Dict:
        """Get historical data for platform-wide metrics."""
        # This would be implemented similarly to _get_historical_data
        # but for platform-wide metrics instead of shop-specific
        # For brevity, implementation details are omitted
        return {metric: [] for metric in metrics}

    def _get_specialist_current_data(
        self, specialist_id: str, metrics: List[str], time_range: str
    ) -> Dict:
        """Get current period data for specialist metrics."""
        # This would be implemented similarly to _get_current_period_data
        # but filtering by specialist_id instead of shop_id
        # For brevity, implementation details are omitted
        return {}

    def _get_specialist_historical_data(
        self,
        specialist_id: str,
        metrics: List[str],
        time_range: str,
        comparison_period: int,
    ) -> Dict:
        """Get historical data for specialist metrics."""
        # This would be implemented similarly to _get_historical_data
        # but for specialist-specific metrics
        # For brevity, implementation details are omitted
        return {metric: [] for metric in metrics}


# Additional specialized anomaly detectors could be implemented for specific use cases
class RealtimeAnomalyDetector:
    """
    Real-time anomaly detection for critical operational metrics.

    This class focuses on detecting anomalies that require immediate attention,
    such as sudden spikes in queue wait times or unusual booking patterns.
    """

    def detect_queue_anomalies(self, queue_id: str) -> Dict:
        """
        Detect real-time anomalies in queue metrics.

        Args:
            queue_id: The queue ID to monitor

        Returns:
            Dictionary with detected anomalies and their details
        """
        # Implementation would focus on real-time metrics
        # rather than historical comparisons
