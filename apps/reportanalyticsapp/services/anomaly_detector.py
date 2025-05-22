# apps/reportanalyticsapp/services/anomaly_detector.py
"""
Anomaly Detector Service

Statistical algorithms to detect anomalies in business metrics,
identifying unusual patterns and outliers that might require attention.
"""

from datetime import datetime, timedelta

import numpy as np
from django.db.models import Avg, Count, F, Q
from django.db.models.functions import Extract
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.queueapp.models import QueueTicket
from apps.reviewapp.models import Review
from core.cache.cache_manager import cache_with_key_prefix


class AnomalyDetector:
    """
    Service for detecting anomalies in business metrics using statistical methods.
    """

    # Z-score threshold for anomaly detection (standard deviations from mean)
    Z_SCORE_THRESHOLD = 2.5

    # IQR threshold for outlier detection (multiplier for interquartile range)
    IQR_THRESHOLD = 1.5

    # Minimum data points required for meaningful analysis
    MIN_DATA_POINTS = 7

    # Metrics that can be analyzed for anomalies
    SUPPORTED_METRICS = [
        "appointment_count",
        "cancellation_rate",
        "no_show_rate",
        "wait_time",
        "service_time",
        "ratings",
        "revenue",
        "completion_rate",
    ]

    @staticmethod
    @cache_with_key_prefix("anomaly_analysis", timeout=3600)  # Cache for 1 hour
    def detect_anomalies(shop_id, metric_type, lookback_days=30, analysis_window=7):
        """
        Detect anomalies in the specified metric for the given shop.

        Args:
            shop_id (uuid): The shop ID to analyze
            metric_type (str): Type of metric to analyze (from SUPPORTED_METRICS)
            lookback_days (int): Number of days to look back for baseline
            analysis_window (int): Number of recent days to analyze for anomalies

        Returns:
            dict: Anomaly detection results with anomalous data points and statistics
        """
        if metric_type not in AnomalyDetector.SUPPORTED_METRICS:
            return {
                "error": f"Unsupported metric type. Supported types are: {', '.join(AnomalyDetector.SUPPORTED_METRICS)}"
            }

        # Calculate date ranges
        end_date = timezone.now()
        analysis_start = end_date - timedelta(days=analysis_window)
        baseline_start = end_date - timedelta(days=lookback_days)

        # Get baseline data for the metric
        baseline_data = AnomalyDetector._get_metric_data(
            shop_id, metric_type, baseline_start, analysis_start
        )

        # Get analysis window data for the metric
        analysis_data = AnomalyDetector._get_metric_data(
            shop_id, metric_type, analysis_start, end_date
        )

        # Check if we have enough data
        if len(baseline_data) < AnomalyDetector.MIN_DATA_POINTS:
            return {
                "error": f"Insufficient baseline data. Need at least {AnomalyDetector.MIN_DATA_POINTS} data points.",
                "baseline_count": len(baseline_data),
            }

        # Calculate baseline statistics
        baseline_stats = AnomalyDetector._calculate_baseline_stats(baseline_data)

        # Detect anomalies using Z-score method
        z_score_anomalies = AnomalyDetector._detect_anomalies_z_score(
            analysis_data, baseline_stats
        )

        # Detect anomalies using IQR method
        iqr_anomalies = AnomalyDetector._detect_anomalies_iqr(
            analysis_data, baseline_stats
        )

        # Combine anomalies (union of both methods)
        combined_anomalies = AnomalyDetector._combine_anomalies(
            z_score_anomalies, iqr_anomalies
        )

        return {
            "metric_type": metric_type,
            "baseline_period": {
                "start_date": baseline_start,
                "end_date": analysis_start,
            },
            "analysis_period": {"start_date": analysis_start, "end_date": end_date},
            "baseline_statistics": baseline_stats,
            "data_points": len(analysis_data),
            "anomalies": {
                "z_score": z_score_anomalies,
                "iqr": iqr_anomalies,
                "combined": combined_anomalies,
            },
            "anomaly_count": len(combined_anomalies),
            "anomaly_percentage": (
                round(len(combined_anomalies) / len(analysis_data) * 100, 2)
                if analysis_data
                else 0
            ),
        }

    @staticmethod
    def detect_multiple_metric_anomalies(shop_id, lookback_days=30, analysis_window=7):
        """
        Detect anomalies across multiple metrics for the given shop.

        Args:
            shop_id (uuid): The shop ID to analyze
            lookback_days (int): Number of days to look back for baseline
            analysis_window (int): Number of recent days to analyze for anomalies

        Returns:
            dict: Anomaly detection results for multiple metrics
        """
        results = {}

        for metric_type in AnomalyDetector.SUPPORTED_METRICS:
            results[metric_type] = AnomalyDetector.detect_anomalies(
                shop_id, metric_type, lookback_days, analysis_window
            )

        # Count total anomalies across all metrics
        total_anomalies = sum(
            result["anomaly_count"]
            for result in results.values()
            if "anomaly_count" in result
        )

        # Get most anomalous metric
        metrics_with_anomalies = {
            metric: result["anomaly_count"]
            for metric, result in results.items()
            if "anomaly_count" in result and result["anomaly_count"] > 0
        }

        most_anomalous_metric = None

        if metrics_with_anomalies:
            most_anomalous_metric = max(
                metrics_with_anomalies.items(), key=lambda x: x[1]
            )[0]

        return {
            "shop_id": shop_id,
            "total_anomalies": total_anomalies,
            "most_anomalous_metric": most_anomalous_metric,
            "metrics": results,
        }

    @staticmethod
    def monitor_shop_health(shop_id):
        """
        Monitor overall shop health based on anomaly detection across key metrics.

        Args:
            shop_id (uuid): The shop ID to analyze

        Returns:
            dict: Shop health assessment with anomaly summary and recommendations
        """
        # Detect anomalies with different windows
        short_term = AnomalyDetector.detect_multiple_metric_anomalies(
            shop_id, 30, 7
        )  # 7-day window
        medium_term = AnomalyDetector.detect_multiple_metric_anomalies(
            shop_id, 90, 30
        )  # 30-day window

        # Calculate health score (0-100)
        # For simplicity, we'll use a basic formula based on anomaly counts
        max_possible_anomalies = (
            len(AnomalyDetector.SUPPORTED_METRICS) * 5
        )  # Assuming max 5 anomalies per metric

        short_term_score = 100 - min(
            100, (short_term["total_anomalies"] / max_possible_anomalies * 100)
        )
        medium_term_score = 100 - min(
            100, (medium_term["total_anomalies"] / max_possible_anomalies * 100)
        )

        # Weighted average (short term more important)
        health_score = short_term_score * 0.7 + medium_term_score * 0.3

        # Generate recommendations based on anomalies
        recommendations = AnomalyDetector._generate_recommendations(
            short_term, medium_term
        )

        # Determine health status
        if health_score >= 90:
            health_status = "Excellent"
        elif health_score >= 75:
            health_status = "Good"
        elif health_score >= 60:
            health_status = "Fair"
        elif health_score >= 40:
            health_status = "Concerning"
        else:
            health_status = "Critical"

        return {
            "shop_id": shop_id,
            "health_score": round(health_score, 2),
            "health_status": health_status,
            "anomaly_summary": {
                "short_term": {
                    "total_anomalies": short_term["total_anomalies"],
                    "most_anomalous_metric": short_term["most_anomalous_metric"],
                },
                "medium_term": {
                    "total_anomalies": medium_term["total_anomalies"],
                    "most_anomalous_metric": medium_term["most_anomalous_metric"],
                },
            },
            "recommendations": recommendations,
        }

    @staticmethod
    def analyze_seasonal_patterns(shop_id, metric_type, days=365):
        """
        Analyze seasonal patterns and identify recurring anomalies.

        Args:
            shop_id (uuid): The shop ID to analyze
            metric_type (str): Type of metric to analyze
            days (int): Number of days to look back for seasonal analysis

        Returns:
            dict: Seasonal pattern analysis with recurring anomalies
        """
        if metric_type not in AnomalyDetector.SUPPORTED_METRICS:
            return {
                "error": f"Unsupported metric type. Supported types are: {', '.join(AnomalyDetector.SUPPORTED_METRICS)}"
            }

        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get metric data for the entire period
        data = AnomalyDetector._get_metric_data(
            shop_id, metric_type, start_date, end_date
        )

        if len(data) < 30:  # Need at least 30 data points for seasonal analysis
            return {
                "error": "Insufficient data for seasonal analysis. Need at least 30 data points.",
                "data_count": len(data),
            }

        # Analyze weekly patterns
        weekly_patterns = AnomalyDetector._analyze_weekly_patterns(data)

        # Analyze monthly patterns
        monthly_patterns = AnomalyDetector._analyze_monthly_patterns(data)

        # Detect recurring anomalies
        recurring_anomalies = AnomalyDetector._detect_recurring_anomalies(data)

        return {
            "metric_type": metric_type,
            "analysis_period": {"start_date": start_date, "end_date": end_date},
            "data_points": len(data),
            "weekly_patterns": weekly_patterns,
            "monthly_patterns": monthly_patterns,
            "recurring_anomalies": recurring_anomalies,
        }

    # Private helper methods

    @staticmethod
    def _get_metric_data(shop_id, metric_type, start_date, end_date):
        """Get time series data for the specified metric"""
        result = []

        if metric_type == "appointment_count":
            # Daily appointment counts
            appointments = (
                Appointment.objects.filter(
                    shop_id=shop_id,
                    start_time__gte=start_date,
                    start_time__lte=end_date,
                )
                .extra(select={"date": "DATE(start_time)"})
                .values("date")
                .annotate(value=Count("id"))
                .order_by("date")
            )

            result = [
                {"date": item["date"], "value": item["value"]} for item in appointments
            ]

        elif metric_type == "cancellation_rate":
            # Daily cancellation rates
            appointments = (
                Appointment.objects.filter(
                    shop_id=shop_id,
                    start_time__gte=start_date,
                    start_time__lte=end_date,
                )
                .extra(select={"date": "DATE(start_time)"})
                .values("date")
                .annotate(
                    total=Count("id"),
                    cancelled=Count("id", filter=Q(status="cancelled")),
                )
                .order_by("date")
            )

            result = [
                {
                    "date": item["date"],
                    "value": (
                        (item["cancelled"] / item["total"] * 100)
                        if item["total"] > 0
                        else 0
                    ),
                }
                for item in appointments
            ]

        elif metric_type == "no_show_rate":
            # Daily no-show rates
            appointments = (
                Appointment.objects.filter(
                    shop_id=shop_id,
                    start_time__gte=start_date,
                    start_time__lte=end_date,
                )
                .extra(select={"date": "DATE(start_time)"})
                .values("date")
                .annotate(
                    total=Count("id"), no_show=Count("id", filter=Q(status="no_show"))
                )
                .order_by("date")
            )

            result = [
                {
                    "date": item["date"],
                    "value": (
                        (item["no_show"] / item["total"] * 100)
                        if item["total"] > 0
                        else 0
                    ),
                }
                for item in appointments
            ]

        elif metric_type == "wait_time":
            # Daily average wait times for queue
            tickets = (
                QueueTicket.objects.filter(
                    queue__shop_id=shop_id,
                    join_time__gte=start_date,
                    join_time__lte=end_date,
                    status="served",
                    join_time__isnull=False,
                    serve_time__isnull=False,
                )
                .extra(select={"date": "DATE(join_time)"})
                .values("date")
                .annotate(avg_wait=Avg("actual_wait_time"))
                .order_by("date")
            )

            result = [
                {"date": item["date"], "value": item["avg_wait"] or 0}
                for item in tickets
            ]

        elif metric_type == "service_time":
            # Daily average service times
            appointments = (
                Appointment.objects.filter(
                    shop_id=shop_id,
                    start_time__gte=start_date,
                    start_time__lte=end_date,
                    status="completed",
                    start_time__isnull=False,
                    end_time__isnull=False,
                )
                .extra(select={"date": "DATE(start_time)"})
                .values("date")
                .annotate(
                    avg_service_time=Avg(
                        Extract(F("end_time") - F("start_time"), "epoch") / 60
                    )
                )
                .order_by("date")
            )

            result = [
                {"date": item["date"], "value": item["avg_service_time"] or 0}
                for item in appointments
            ]

        elif metric_type == "ratings":
            # Daily average ratings
            # Need to combine shop, specialist, and service reviews
            # This is simplified
            shop_reviews = (
                Review.objects.filter(
                    content_type__model="shop",
                    object_id=shop_id,
                    created_at__gte=start_date,
                    created_at__lte=end_date,
                )
                .extra(select={"date": "DATE(created_at)"})
                .values("date")
                .annotate(avg_rating=Avg("rating"))
                .order_by("date")
            )

            result = [
                {"date": item["date"], "value": item["avg_rating"] or 0}
                for item in shop_reviews
            ]

        elif metric_type == "revenue":
            # Daily revenue
            # This needs to join with service prices
            # For simplicity, using a simpler approach
            completed_appointments = Appointment.objects.filter(
                shop_id=shop_id,
                start_time__gte=start_date,
                start_time__lte=end_date,
                status="completed",
            )

            # Group by date
            revenue_by_day = {}
            for appointment in completed_appointments:
                date_key = appointment.start_time.date()

                if date_key not in revenue_by_day:
                    revenue_by_day[date_key] = 0

                revenue_by_day[date_key] += appointment.service.price

            # Format result
            result = [
                {"date": date, "value": revenue}
                for date, revenue in sorted(revenue_by_day.items())
            ]

        elif metric_type == "completion_rate":
            # Daily completion rates
            appointments = (
                Appointment.objects.filter(
                    shop_id=shop_id,
                    start_time__gte=start_date,
                    start_time__lte=end_date,
                )
                .extra(select={"date": "DATE(start_time)"})
                .values("date")
                .annotate(
                    total=Count("id"),
                    completed=Count("id", filter=Q(status="completed")),
                )
                .order_by("date")
            )

            result = [
                {
                    "date": item["date"],
                    "value": (
                        (item["completed"] / item["total"] * 100)
                        if item["total"] > 0
                        else 0
                    ),
                }
                for item in appointments
            ]

        return result

    @staticmethod
    def _calculate_baseline_stats(data):
        """Calculate baseline statistics from data"""
        if not data:
            return {
                "mean": 0,
                "median": 0,
                "std_dev": 0,
                "min": 0,
                "max": 0,
                "count": 0,
                "percentiles": {"25": 0, "75": 0, "95": 0},
            }

        values = [item["value"] for item in data]

        # Basic statistics
        mean = np.mean(values)
        median = np.median(values)
        std_dev = np.std(values)
        min_val = np.min(values)
        max_val = np.max(values)

        # Percentiles
        p25 = np.percentile(values, 25)
        p75 = np.percentile(values, 75)
        p95 = np.percentile(values, 95)

        # Calculate IQR
        iqr = p75 - p25

        return {
            "mean": mean,
            "median": median,
            "std_dev": std_dev,
            "min": min_val,
            "max": max_val,
            "count": len(values),
            "percentiles": {"25": p25, "75": p75, "95": p95},
            "iqr": iqr,
        }

    @staticmethod
    def _detect_anomalies_z_score(data, baseline_stats):
        """Detect anomalies using Z-score method"""
        if not data:
            return []

        anomalies = []

        for item in data:
            # Calculate Z-score
            z_score = (
                ((item["value"] - baseline_stats["mean"]) / baseline_stats["std_dev"])
                if baseline_stats["std_dev"] > 0
                else 0
            )

            # Check if anomalous
            if abs(z_score) > AnomalyDetector.Z_SCORE_THRESHOLD:
                direction = "high" if z_score > 0 else "low"
                severity = abs(z_score) / AnomalyDetector.Z_SCORE_THRESHOLD

                anomalies.append(
                    {
                        "date": item["date"],
                        "value": item["value"],
                        "expected": baseline_stats["mean"],
                        "deviation": item["value"] - baseline_stats["mean"],
                        "z_score": z_score,
                        "direction": direction,
                        "severity": min(5, severity),  # Cap at 5
                        "method": "z_score",
                    }
                )

        return anomalies

    @staticmethod
    def _detect_anomalies_iqr(data, baseline_stats):
        """Detect anomalies using IQR method"""
        if not data or baseline_stats["iqr"] == 0:
            return []

        anomalies = []

        # Calculate upper and lower bounds
        p25 = baseline_stats["percentiles"]["25"]
        p75 = baseline_stats["percentiles"]["75"]
        iqr = baseline_stats["iqr"]

        lower_bound = p25 - (AnomalyDetector.IQR_THRESHOLD * iqr)
        upper_bound = p75 + (AnomalyDetector.IQR_THRESHOLD * iqr)

        for item in data:
            if item["value"] < lower_bound or item["value"] > upper_bound:
                # Determine direction and severity
                if item["value"] > upper_bound:
                    direction = "high"
                    deviation = (item["value"] - upper_bound) / iqr
                else:
                    direction = "low"
                    deviation = (lower_bound - item["value"]) / iqr

                severity = deviation / AnomalyDetector.IQR_THRESHOLD

                anomalies.append(
                    {
                        "date": item["date"],
                        "value": item["value"],
                        "expected": baseline_stats["median"],
                        "deviation": item["value"] - baseline_stats["median"],
                        "iqr_score": deviation,
                        "direction": direction,
                        "severity": min(5, severity),  # Cap at 5
                        "method": "iqr",
                    }
                )

        return anomalies

    @staticmethod
    def _combine_anomalies(z_score_anomalies, iqr_anomalies):
        """Combine anomalies from different methods"""
        # Use a dictionary to track anomalies by date
        combined_anomalies = {}

        # Add Z-score anomalies
        for anomaly in z_score_anomalies:
            combined_anomalies[anomaly["date"]] = anomaly

        # Add IQR anomalies (if not already present from Z-score)
        for anomaly in iqr_anomalies:
            if anomaly["date"] not in combined_anomalies:
                combined_anomalies[anomaly["date"]] = anomaly
            else:
                # If already present, update with more severe method
                existing = combined_anomalies[anomaly["date"]]
                if anomaly["severity"] > existing["severity"]:
                    combined_anomalies[anomaly["date"]] = anomaly

        # Convert dict back to list and sort by date
        result = list(combined_anomalies.values())
        result.sort(key=lambda x: x["date"])

        return result

    @staticmethod
    def _analyze_weekly_patterns(data):
        """Analyze weekly patterns in the data"""
        if not data:
            return {}

        # Group data by day of week
        days_of_week = [0, 1, 2, 3, 4, 5, 6]  # 0 = Monday, 6 = Sunday
        day_data = {day: [] for day in days_of_week}

        for item in data:
            # Convert date string to datetime and get weekday
            if isinstance(item["date"], str):
                date = datetime.strptime(item["date"], "%Y-%m-%d").date()
            else:
                date = item["date"]

            weekday = date.weekday()
            day_data[weekday].append(item["value"])

        # Calculate statistics for each day
        day_stats = {}
        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        for day, values in day_data.items():
            if values:
                day_stats[day_names[day]] = {
                    "mean": np.mean(values),
                    "median": np.median(values),
                    "std_dev": np.std(values) if len(values) > 1 else 0,
                    "min": np.min(values),
                    "max": np.max(values),
                    "count": len(values),
                }
            else:
                day_stats[day_names[day]] = {
                    "mean": 0,
                    "median": 0,
                    "std_dev": 0,
                    "min": 0,
                    "max": 0,
                    "count": 0,
                }

        # Find day with highest average
        highest_day = max(day_stats.items(), key=lambda x: x[1]["mean"])

        # Find day with lowest average
        lowest_day = min(day_stats.items(), key=lambda x: x[1]["mean"])

        return {
            "day_statistics": day_stats,
            "highest_day": {"day": highest_day[0], "mean": highest_day[1]["mean"]},
            "lowest_day": {"day": lowest_day[0], "mean": lowest_day[1]["mean"]},
            "weekly_pattern_strength": AnomalyDetector._calculate_pattern_strength(
                [stats["mean"] for day, stats in day_stats.items()]
            ),
        }

    @staticmethod
    def _analyze_monthly_patterns(data):
        """Analyze monthly patterns in the data"""
        if not data:
            return {}

        # Group data by month
        months = list(range(1, 13))  # 1-12
        month_data = {month: [] for month in months}

        for item in data:
            # Convert date string to datetime and get month
            if isinstance(item["date"], str):
                date = datetime.strptime(item["date"], "%Y-%m-%d").date()
            else:
                date = item["date"]

            month = date.month
            month_data[month].append(item["value"])

        # Calculate statistics for each month
        month_stats = {}
        month_names = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]

        for month, values in month_data.items():
            if values:
                month_stats[month_names[month - 1]] = {
                    "mean": np.mean(values),
                    "median": np.median(values),
                    "std_dev": np.std(values) if len(values) > 1 else 0,
                    "min": np.min(values),
                    "max": np.max(values),
                    "count": len(values),
                }
            else:
                month_stats[month_names[month - 1]] = {
                    "mean": 0,
                    "median": 0,
                    "std_dev": 0,
                    "min": 0,
                    "max": 0,
                    "count": 0,
                }

        # Find month with highest average
        highest_month = max(month_stats.items(), key=lambda x: x[1]["mean"])

        # Find month with lowest average
        lowest_month = min(month_stats.items(), key=lambda x: x[1]["mean"])

        return {
            "month_statistics": month_stats,
            "highest_month": {
                "month": highest_month[0],
                "mean": highest_month[1]["mean"],
            },
            "lowest_month": {"month": lowest_month[0], "mean": lowest_month[1]["mean"]},
            "monthly_pattern_strength": AnomalyDetector._calculate_pattern_strength(
                [stats["mean"] for month, stats in month_stats.items()]
            ),
        }

    @staticmethod
    def _detect_recurring_anomalies(data):
        """Detect recurring anomalies in the time series"""
        if not data:
            return []

        # Group anomalies by day of week
        day_of_week_data = {}

        for item in data:
            # Convert date string to datetime and get weekday
            if isinstance(item["date"], str):
                date = datetime.strptime(item["date"], "%Y-%m-%d").date()
            else:
                date = item["date"]

            weekday = date.weekday()
            day_name = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ][weekday]

            if day_name not in day_of_week_data:
                day_of_week_data[day_name] = []

            day_of_week_data[day_name].append(item["value"])

        # Calculate statistics for each day of week
        all_values = [item["value"] for item in data]
        overall_mean = np.mean(all_values)
        overall_std = np.std(all_values)

        recurring_anomalies = []

        for day, values in day_of_week_data.items():
            day_mean = np.mean(values)
            # unused_unused_day_std = np.std(values) if len(values) > 1 else 0

            # Compare day mean to overall mean
            z_score = (day_mean - overall_mean) / overall_std if overall_std > 0 else 0

            if abs(z_score) > AnomalyDetector.Z_SCORE_THRESHOLD and len(values) >= 3:
                direction = "high" if z_score > 0 else "low"

                recurring_anomalies.append(
                    {
                        "day": day,
                        "mean_value": day_mean,
                        "overall_mean": overall_mean,
                        "deviation": day_mean - overall_mean,
                        "z_score": z_score,
                        "direction": direction,
                        "sample_size": len(values),
                    }
                )

        return recurring_anomalies

    @staticmethod
    def _calculate_pattern_strength(values):
        """Calculate the strength of a pattern based on variance-to-mean ratio"""
        if not values or sum(values) == 0:
            return 0

        mean = np.mean(values)
        variance = np.var(values)

        # Coefficient of variation as a measure of pattern strength
        cv = np.sqrt(variance) / mean if mean > 0 else 0

        # Normalize to 0-100 scale
        strength = min(100, cv * 100)

        return round(strength, 2)

    @staticmethod
    def _generate_recommendations(short_term, medium_term):
        """Generate actionable recommendations based on detected anomalies"""
        recommendations = []

        # Check appointment count anomalies
        if "appointment_count" in short_term["metrics"]:
            appointment_anomalies = (
                short_term["metrics"]["appointment_count"]
                .get("anomalies", {})
                .get("combined", [])
            )
            if appointment_anomalies:
                # Check if most anomalies are negative (low appointment count)
                low_count = sum(
                    1 for a in appointment_anomalies if a.get("direction") == "low"
                )
                if low_count > len(appointment_anomalies) / 2:
                    recommendations.append(
                        "Consider running a promotion or special offer to boost appointment bookings."
                    )

        # Check cancellation rate anomalies
        if "cancellation_rate" in short_term["metrics"]:
            cancellation_anomalies = (
                short_term["metrics"]["cancellation_rate"]
                .get("anomalies", {})
                .get("combined", [])
            )
            if cancellation_anomalies:
                # Check if most anomalies are positive (high cancellation rate)
                high_count = sum(
                    1 for a in cancellation_anomalies if a.get("direction") == "high"
                )
                if high_count > len(cancellation_anomalies) / 2:
                    recommendations.append(
                        "Review your cancellation policy and consider reminder messages to reduce cancellations."
                    )

        # Check no-show rate anomalies
        if "no_show_rate" in short_term["metrics"]:
            no_show_anomalies = (
                short_term["metrics"]["no_show_rate"]
                .get("anomalies", {})
                .get("combined", [])
            )
            if no_show_anomalies:
                # Check if most anomalies are positive (high no-show rate)
                high_count = sum(
                    1 for a in no_show_anomalies if a.get("direction") == "high"
                )
                if high_count > len(no_show_anomalies) / 2:
                    recommendations.append(
                        "Implement additional reminder notifications or consider a deposit policy for appointments."
                    )

        # Check wait time anomalies
        if "wait_time" in short_term["metrics"]:
            wait_time_anomalies = (
                short_term["metrics"]["wait_time"]
                .get("anomalies", {})
                .get("combined", [])
            )
            if wait_time_anomalies:
                # Check if most anomalies are positive (high wait times)
                high_count = sum(
                    1 for a in wait_time_anomalies if a.get("direction") == "high"
                )
                if high_count > len(wait_time_anomalies) / 2:
                    recommendations.append(
                        "Consider adding more staff during peak hours or optimizing your service delivery process."
                    )

        # Check ratings anomalies
        if "ratings" in short_term["metrics"]:
            rating_anomalies = (
                short_term["metrics"]["ratings"]
                .get("anomalies", {})
                .get("combined", [])
            )
            if rating_anomalies:
                # Check if most anomalies are negative (low ratings)
                low_count = sum(
                    1 for a in rating_anomalies if a.get("direction") == "low"
                )
                if low_count > len(rating_anomalies) / 2:
                    recommendations.append(
                        "Review recent customer feedback and address any service quality issues immediately."
                    )

        # Check revenue anomalies
        if "revenue" in short_term["metrics"]:
            revenue_anomalies = (
                short_term["metrics"]["revenue"]
                .get("anomalies", {})
                .get("combined", [])
            )
            if revenue_anomalies:
                # Check if most anomalies are negative (low revenue)
                low_count = sum(
                    1 for a in revenue_anomalies if a.get("direction") == "low"
                )
                if low_count > len(revenue_anomalies) / 2:
                    recommendations.append(
                        "Review your pricing strategy and consider service packages or upselling opportunities."
                    )

        # Add general recommendations if few specific ones
        if len(recommendations) < 2:
            recommendations.append(
                "Regularly monitor your key performance metrics and compare them to industry benchmarks."
            )
            recommendations.append(
                "Set up alerting for significant deviations in critical metrics like revenue and customer satisfaction."
            )

        return recommendations
