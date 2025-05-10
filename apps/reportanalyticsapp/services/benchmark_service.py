# apps/reportanalyticsapp/services/benchmark_service.py
"""
Benchmark Service

Provides comparative performance analysis across businesses,
allowing shops to understand how they stack up against similar
establishments within their category or region.
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.categoryapp.models import Category
from apps.queueapp.models import QueueTicket
from apps.reportanalyticsapp.services.analytics_service import AnalyticsService
from apps.reviewapp.models import Review
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist
from core.cache.cache_manager import cache_with_key_prefix


class BenchmarkService:
    """
    Service for comparing shop performance against industry benchmarks
    and similar businesses.
    """

    # Benchmark metrics that can be compared
    BENCHMARK_METRICS = [
        "average_rating",
        "cancellation_rate",
        "no_show_rate",
        "wait_time",
        "service_time",
        "revenue_per_appointment",
        "appointments_per_specialist",
        "customer_return_rate",
    ]

    @staticmethod
    @cache_with_key_prefix("shop_benchmarks", timeout=86400)  # Cache for 1 day
    def get_shop_benchmarks(shop_id, period="last_30_days", comparison_type="category"):
        """
        Get benchmarks comparing shop performance against similar shops.

        Args:
            shop_id (uuid): The shop ID to analyze
            period (str): Time period for analysis ('last_30_days', 'last_90_days', 'last_year')
            comparison_type (str): Type of comparison ('category', 'region', 'size')

        Returns:
            dict: Benchmark comparison data
        """
        # Get shop details
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return {"error": "Shop not found"}

        # Calculate date range
        days = AnalyticsService.TIME_PERIODS.get(period, 30)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get similar shops based on comparison type
        similar_shops = BenchmarkService._get_similar_shops(
            shop, comparison_type, max_shops=50  # Limit to reasonable number
        )

        # Exclude the current shop from similar shops
        similar_shop_ids = [s.id for s in similar_shops if s.id != shop_id]

        if not similar_shop_ids:
            return {
                "error": "No similar shops found for benchmarking",
                "shop_id": shop_id,
                "comparison_type": comparison_type,
            }

        # Calculate shop metrics
        shop_metrics = BenchmarkService._calculate_shop_metrics(
            shop_id, start_date, end_date
        )

        # Calculate benchmark metrics across similar shops
        benchmark_metrics = BenchmarkService._calculate_benchmark_metrics(
            similar_shop_ids, start_date, end_date
        )

        # Combine shop and benchmark metrics for comparison
        comparison = BenchmarkService._create_comparison(
            shop_metrics, benchmark_metrics
        )

        return {
            "shop_id": shop_id,
            "shop_name": shop.name,
            "period": period,
            "comparison_type": comparison_type,
            "start_date": start_date,
            "end_date": end_date,
            "similar_shop_count": len(similar_shop_ids),
            "shop_metrics": shop_metrics,
            "benchmark_metrics": benchmark_metrics,
            "comparison": comparison,
        }

    @staticmethod
    def get_industry_benchmarks(category_id=None, region=None, period="last_30_days"):
        """
        Get industry-wide benchmarks for all shops or by category/region.

        Args:
            category_id (uuid, optional): Filter by category
            region (str, optional): Filter by region (city or country)
            period (str): Time period for analysis

        Returns:
            dict: Industry benchmark data
        """
        # Calculate date range
        days = AnalyticsService.TIME_PERIODS.get(period, 30)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Build shop filter
        shop_filter = Q(is_active=True)

        if category_id:
            # Get all child categories if parent category
            try:
                category = Category.objects.get(id=category_id)
                if category.parent is None:  # It's a parent category
                    child_categories = Category.objects.filter(parent=category)
                    child_category_ids = [c.id for c in child_categories]
                    shop_filter &= Q(services__category_id__in=child_category_ids)
                else:
                    shop_filter &= Q(services__category_id=category_id)
            except Category.DoesNotExist:
                return {"error": "Category not found"}

        if region:
            # Check if region is a city or country
            if len(region) <= 3:  # Country code is typically 2-3 chars
                shop_filter &= Q(location__country=region)
            else:
                shop_filter &= Q(location__city=region)

        # Get all shops matching the filter
        shops = Shop.objects.filter(shop_filter).distinct()

        if not shops.exists():
            return {
                "error": "No shops found matching the criteria",
                "category_id": category_id,
                "region": region,
            }

        shop_ids = [shop.id for shop in shops]

        # Calculate industry metrics
        industry_metrics = BenchmarkService._calculate_benchmark_metrics(
            shop_ids, start_date, end_date
        )

        # Get top performers for each metric
        top_performers = BenchmarkService._get_top_performers(
            shop_ids, start_date, end_date
        )

        return {
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "shop_count": len(shop_ids),
            "category_id": category_id,
            "region": region,
            "industry_metrics": industry_metrics,
            "top_performers": top_performers,
        }

    @staticmethod
    def get_performance_percentile(
        shop_id, metric, period="last_30_days", comparison_type="category"
    ):
        """
        Calculate the percentile rank of a shop for a specific metric.

        Args:
            shop_id (uuid): The shop ID to analyze
            metric (str): Metric to calculate percentile for (from BENCHMARK_METRICS)
            period (str): Time period for analysis
            comparison_type (str): Type of comparison ('category', 'region', 'size')

        Returns:
            dict: Percentile rank data
        """
        if metric not in BenchmarkService.BENCHMARK_METRICS:
            return {
                "error": f"Invalid metric. Supported metrics are: {', '.join(BenchmarkService.BENCHMARK_METRICS)}"
            }

        # Get shop benchmarks
        benchmarks = BenchmarkService.get_shop_benchmarks(
            shop_id, period, comparison_type
        )

        if "error" in benchmarks:
            return benchmarks

        # Get shop and benchmark values for the metric
        shop_value = benchmarks["shop_metrics"].get(metric, 0)

        # Get all shops for calculating percentile
        similar_shop_ids = []
        for shop in BenchmarkService._get_similar_shops(
            Shop.objects.get(id=shop_id), comparison_type
        ):
            similar_shop_ids.append(shop.id)

        # Add current shop to the list
        similar_shop_ids.append(shop_id)

        # Calculate date range
        days = AnalyticsService.TIME_PERIODS.get(period, 30)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get all values for the metric across similar shops
        metric_values = BenchmarkService._get_metric_values_by_shop(
            similar_shop_ids, metric, start_date, end_date
        )

        if not metric_values:
            return {
                "error": "Insufficient data to calculate percentile",
                "shop_id": shop_id,
                "metric": metric,
            }

        # Calculate percentile
        sorted_values = sorted(metric_values)
        shop_index = 0

        for i, value in enumerate(sorted_values):
            if value >= shop_value:
                shop_index = i
                break

        # For metrics where lower is better, invert the percentile
        invert_metrics = ["cancellation_rate", "no_show_rate", "wait_time"]
        percentile = shop_index / len(sorted_values) * 100

        if metric in invert_metrics:
            percentile = 100 - percentile

        # Determine performance level based on percentile
        performance_level = BenchmarkService._get_performance_level(percentile)

        return {
            "shop_id": shop_id,
            "metric": metric,
            "shop_value": shop_value,
            "percentile": round(percentile, 2),
            "total_shops": len(similar_shop_ids),
            "performance_level": performance_level,
            "comparison_type": comparison_type,
        }

    @staticmethod
    def get_competitive_analysis(shop_id, competitor_ids=None, period="last_30_days"):
        """
        Perform direct comparison with specific competitors.

        Args:
            shop_id (uuid): The shop ID to analyze
            competitor_ids (list): List of competitor shop IDs (optional)
            period (str): Time period for analysis

        Returns:
            dict: Competitive analysis data
        """
        # Calculate date range
        days = AnalyticsService.TIME_PERIODS.get(period, 30)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get shop details
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return {"error": "Shop not found"}

        # If competitor_ids not provided, find potential competitors
        if not competitor_ids:
            competitors = BenchmarkService._find_potential_competitors(shop)
            competitor_ids = [c.id for c in competitors if c.id != shop_id]

        if not competitor_ids:
            return {"error": "No competitors found for analysis", "shop_id": shop_id}

        # Calculate shop metrics
        shop_metrics = BenchmarkService._calculate_shop_metrics(
            shop_id, start_date, end_date
        )

        # Calculate metrics for each competitor
        competitor_metrics = {}

        for competitor_id in competitor_ids:
            try:
                competitor = Shop.objects.get(id=competitor_id)
                competitor_data = BenchmarkService._calculate_shop_metrics(
                    competitor_id, start_date, end_date
                )

                competitor_metrics[str(competitor_id)] = {
                    "name": competitor.name,
                    "metrics": competitor_data,
                }
            except Shop.DoesNotExist:
                continue

        # Create comparison between shop and competitors
        comparison = {}

        for metric in BenchmarkService.BENCHMARK_METRICS:
            shop_value = shop_metrics.get(metric, 0)

            competitor_values = []
            for comp_id, comp_data in competitor_metrics.items():
                comp_value = comp_data["metrics"].get(metric, 0)
                competitor_values.append(comp_value)

            if competitor_values:
                avg_competitor_value = sum(competitor_values) / len(competitor_values)

                # Calculate difference
                if avg_competitor_value > 0:
                    difference = (
                        (shop_value - avg_competitor_value) / avg_competitor_value
                    ) * 100
                else:
                    difference = 0 if shop_value == 0 else 100

                # Determine if higher is better for this metric
                higher_is_better = metric not in [
                    "cancellation_rate",
                    "no_show_rate",
                    "wait_time",
                ]

                # Determine performance
                if (higher_is_better and difference > 0) or (
                    not higher_is_better and difference < 0
                ):
                    performance = "better"
                elif difference == 0:
                    performance = "same"
                else:
                    performance = "worse"

                comparison[metric] = {
                    "shop_value": shop_value,
                    "avg_competitor_value": avg_competitor_value,
                    "difference_percent": round(difference, 2),
                    "performance": performance,
                }

        return {
            "shop_id": shop_id,
            "shop_name": shop.name,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "competitor_count": len(competitor_metrics),
            "shop_metrics": shop_metrics,
            "competitor_metrics": competitor_metrics,
            "comparison": comparison,
        }

    @staticmethod
    def get_trending_metrics(category_id=None, region=None, period="last_90_days"):
        """
        Identify trending metrics and KPIs across the industry.

        Args:
            category_id (uuid, optional): Filter by category
            region (str, optional): Filter by region
            period (str): Time period for analysis

        Returns:
            dict: Trending metrics data
        """
        # Calculate date range
        days = AnalyticsService.TIME_PERIODS.get(period, 90)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Split the period into smaller segments for trend analysis
        if days >= 90:
            segment_size = 30  # Monthly segments
        elif days >= 28:
            segment_size = 7  # Weekly segments
        else:
            segment_size = 1  # Daily segments

        segments = []
        current_end = end_date

        while current_end > start_date:
            segment_start = max(current_end - timedelta(days=segment_size), start_date)
            segments.append(
                {
                    "start": segment_start,
                    "end": current_end,
                    "label": segment_start.strftime("%Y-%m-%d"),
                }
            )
            current_end = segment_start

        segments.reverse()  # Oldest to newest

        # Build shop filter
        shop_filter = Q(is_active=True)

        if category_id:
            # Get all child categories if parent category
            try:
                category = Category.objects.get(id=category_id)
                if category.parent is None:  # It's a parent category
                    child_categories = Category.objects.filter(parent=category)
                    child_category_ids = [c.id for c in child_categories]
                    shop_filter &= Q(services__category_id__in=child_category_ids)
                else:
                    shop_filter &= Q(services__category_id=category_id)
            except Category.DoesNotExist:
                return {"error": "Category not found"}

        if region:
            # Check if region is a city or country
            if len(region) <= 3:  # Country code is typically 2-3 chars
                shop_filter &= Q(location__country=region)
            else:
                shop_filter &= Q(location__city=region)

        # Get all shops matching the filter
        shops = Shop.objects.filter(shop_filter).distinct()

        if not shops.exists():
            return {
                "error": "No shops found matching the criteria",
                "category_id": category_id,
                "region": region,
            }

        shop_ids = [shop.id for shop in shops]

        # Calculate metrics for each segment
        segment_metrics = []

        for segment in segments:
            metrics = BenchmarkService._calculate_benchmark_metrics(
                shop_ids, segment["start"], segment["end"]
            )

            segment_metrics.append({"period": segment["label"], "metrics": metrics})

        # Analyze trends for each metric
        trends = {}

        for metric in BenchmarkService.BENCHMARK_METRICS:
            values = [
                segment["metrics"].get(metric, {}).get("mean", 0)
                for segment in segment_metrics
            ]

            if not values or all(v == 0 for v in values):
                continue

            # Calculate trend
            if len(values) >= 2:
                first_value = values[0]
                last_value = values[-1]

                if first_value > 0:
                    percent_change = ((last_value - first_value) / first_value) * 100
                else:
                    percent_change = 0 if last_value == 0 else 100

                # Determine if higher is better for this metric
                higher_is_better = metric not in [
                    "cancellation_rate",
                    "no_show_rate",
                    "wait_time",
                ]

                # Determine trend direction
                if abs(percent_change) < 5:
                    direction = "stable"
                else:
                    direction = (
                        "improving"
                        if (higher_is_better and percent_change > 0)
                        or (not higher_is_better and percent_change < 0)
                        else "declining"
                    )

                trends[metric] = {
                    "values": values,
                    "percent_change": round(percent_change, 2),
                    "direction": direction,
                    "significance": BenchmarkService._calculate_trend_significance(
                        values
                    ),
                }

        # Sort trends by significance
        sorted_trends = dict(
            sorted(
                trends.items(), key=lambda item: item[1]["significance"], reverse=True
            )
        )

        return {
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "shop_count": len(shop_ids),
            "segment_count": len(segments),
            "segment_metrics": segment_metrics,
            "trends": sorted_trends,
        }

    # Private helper methods

    @staticmethod
    def _get_similar_shops(shop, comparison_type, max_shops=50):
        """Get similar shops based on comparison type"""
        if comparison_type == "category":
            # Get shops in the same category
            # First, get all service categories for this shop
            service_categories = Category.objects.filter(services__shop=shop).distinct()

            # Then find shops with services in these categories
            similar_shops = Shop.objects.filter(
                services__category__in=service_categories, is_active=True
            ).distinct()

        elif comparison_type == "region":
            # Get shops in the same region (city and country)
            similar_shops = Shop.objects.filter(
                location__city=shop.location.city,
                location__country=shop.location.country,
                is_active=True,
            ).distinct()

        elif comparison_type == "size":
            # Get shops of similar size (by specialist count)
            specialist_count = shop.specialists.count()

            # Define size ranges (small: 1-3, medium: 4-10, large: 11+)
            if specialist_count <= 3:
                min_specialists = 1
                max_specialists = 3
            elif specialist_count <= 10:
                min_specialists = 4
                max_specialists = 10
            else:
                min_specialists = 11
                max_specialists = 1000  # No upper limit

            similar_shops = (
                Shop.objects.annotate(specialist_count=Count("specialists"))
                .filter(
                    specialist_count__gte=min_specialists,
                    specialist_count__lte=max_specialists,
                    is_active=True,
                )
                .distinct()
            )

        else:
            # Default to all active shops
            similar_shops = Shop.objects.filter(is_active=True)

        # Limit to max_shops
        return similar_shops[:max_shops]

    @staticmethod
    def _calculate_shop_metrics(shop_id, start_date, end_date):
        """Calculate metrics for a specific shop"""
        metrics = {}

        # Average rating
        metrics["average_rating"] = BenchmarkService._calculate_average_rating(
            shop_id, start_date, end_date
        )

        # Cancellation rate
        metrics["cancellation_rate"] = BenchmarkService._calculate_cancellation_rate(
            shop_id, start_date, end_date
        )

        # No-show rate
        metrics["no_show_rate"] = BenchmarkService._calculate_no_show_rate(
            shop_id, start_date, end_date
        )

        # Average wait time
        metrics["wait_time"] = BenchmarkService._calculate_wait_time(
            shop_id, start_date, end_date
        )

        # Average service time
        metrics["service_time"] = BenchmarkService._calculate_service_time(
            shop_id, start_date, end_date
        )

        # Revenue per appointment
        metrics["revenue_per_appointment"] = (
            BenchmarkService._calculate_revenue_per_appointment(
                shop_id, start_date, end_date
            )
        )

        # Appointments per specialist
        metrics["appointments_per_specialist"] = (
            BenchmarkService._calculate_appointments_per_specialist(
                shop_id, start_date, end_date
            )
        )

        # Customer return rate
        metrics["customer_return_rate"] = (
            BenchmarkService._calculate_customer_return_rate(
                shop_id, start_date, end_date
            )
        )

        return metrics

    @staticmethod
    def _calculate_benchmark_metrics(shop_ids, start_date, end_date):
        """Calculate aggregate benchmark metrics across multiple shops"""
        if not shop_ids:
            return {}

        results = {}

        # Average rating across shops
        avg_ratings = []
        for shop_id in shop_ids:
            rating = BenchmarkService._calculate_average_rating(
                shop_id, start_date, end_date
            )
            if rating > 0:
                avg_ratings.append(rating)

        if avg_ratings:
            results["average_rating"] = {
                "mean": round(sum(avg_ratings) / len(avg_ratings), 2),
                "min": round(min(avg_ratings), 2),
                "max": round(max(avg_ratings), 2),
                "count": len(avg_ratings),
            }

        # Cancellation rate across shops
        cancellation_rates = []
        for shop_id in shop_ids:
            rate = BenchmarkService._calculate_cancellation_rate(
                shop_id, start_date, end_date
            )
            if rate >= 0:
                cancellation_rates.append(rate)

        if cancellation_rates:
            results["cancellation_rate"] = {
                "mean": round(sum(cancellation_rates) / len(cancellation_rates), 2),
                "min": round(min(cancellation_rates), 2),
                "max": round(max(cancellation_rates), 2),
                "count": len(cancellation_rates),
            }

        # No-show rate across shops
        no_show_rates = []
        for shop_id in shop_ids:
            rate = BenchmarkService._calculate_no_show_rate(
                shop_id, start_date, end_date
            )
            if rate >= 0:
                no_show_rates.append(rate)

        if no_show_rates:
            results["no_show_rate"] = {
                "mean": round(sum(no_show_rates) / len(no_show_rates), 2),
                "min": round(min(no_show_rates), 2),
                "max": round(max(no_show_rates), 2),
                "count": len(no_show_rates),
            }

        # Wait time across shops
        wait_times = []
        for shop_id in shop_ids:
            time = BenchmarkService._calculate_wait_time(shop_id, start_date, end_date)
            if time > 0:
                wait_times.append(time)

        if wait_times:
            results["wait_time"] = {
                "mean": round(sum(wait_times) / len(wait_times), 2),
                "min": round(min(wait_times), 2),
                "max": round(max(wait_times), 2),
                "count": len(wait_times),
            }

        # Service time across shops
        service_times = []
        for shop_id in shop_ids:
            time = BenchmarkService._calculate_service_time(
                shop_id, start_date, end_date
            )
            if time > 0:
                service_times.append(time)

        if service_times:
            results["service_time"] = {
                "mean": round(sum(service_times) / len(service_times), 2),
                "min": round(min(service_times), 2),
                "max": round(max(service_times), 2),
                "count": len(service_times),
            }

        # Revenue per appointment across shops
        revenues = []
        for shop_id in shop_ids:
            revenue = BenchmarkService._calculate_revenue_per_appointment(
                shop_id, start_date, end_date
            )
            if revenue > 0:
                revenues.append(revenue)

        if revenues:
            results["revenue_per_appointment"] = {
                "mean": round(sum(revenues) / len(revenues), 2),
                "min": round(min(revenues), 2),
                "max": round(max(revenues), 2),
                "count": len(revenues),
            }

        # Appointments per specialist across shops
        appointments_per_specialist = []
        for shop_id in shop_ids:
            count = BenchmarkService._calculate_appointments_per_specialist(
                shop_id, start_date, end_date
            )
            if count > 0:
                appointments_per_specialist.append(count)

        if appointments_per_specialist:
            results["appointments_per_specialist"] = {
                "mean": round(
                    sum(appointments_per_specialist) / len(appointments_per_specialist),
                    2,
                ),
                "min": round(min(appointments_per_specialist), 2),
                "max": round(max(appointments_per_specialist), 2),
                "count": len(appointments_per_specialist),
            }

        # Customer return rate across shops
        return_rates = []
        for shop_id in shop_ids:
            rate = BenchmarkService._calculate_customer_return_rate(
                shop_id, start_date, end_date
            )
            if rate >= 0:
                return_rates.append(rate)

        if return_rates:
            results["customer_return_rate"] = {
                "mean": round(sum(return_rates) / len(return_rates), 2),
                "min": round(min(return_rates), 2),
                "max": round(max(return_rates), 2),
                "count": len(return_rates),
            }

        return results

    @staticmethod
    def _create_comparison(shop_metrics, benchmark_metrics):
        """Create comparison between shop and benchmark metrics"""
        comparison = {}

        for metric, value in shop_metrics.items():
            if metric in benchmark_metrics:
                benchmark = benchmark_metrics[metric]

                # Calculate relative performance
                if benchmark["mean"] > 0:
                    relative = ((value - benchmark["mean"]) / benchmark["mean"]) * 100
                else:
                    relative = 0 if value == 0 else 100

                # Determine if higher is better for this metric
                higher_is_better = metric not in [
                    "cancellation_rate",
                    "no_show_rate",
                    "wait_time",
                ]

                # Determine percentile (approximate)
                if value <= benchmark["min"]:
                    percentile = 0
                elif value >= benchmark["max"]:
                    percentile = 100
                else:
                    range_size = benchmark["max"] - benchmark["min"]
                    if range_size > 0:
                        percentile = ((value - benchmark["min"]) / range_size) * 100
                    else:
                        percentile = 50  # Default to middle if min=max

                # Invert percentile for metrics where lower is better
                if not higher_is_better:
                    percentile = 100 - percentile

                # Determine performance level
                performance_level = BenchmarkService._get_performance_level(percentile)

                comparison[metric] = {
                    "shop_value": value,
                    "benchmark_mean": benchmark["mean"],
                    "benchmark_min": benchmark["min"],
                    "benchmark_max": benchmark["max"],
                    "relative_percent": round(relative, 2),
                    "percentile": round(percentile, 2),
                    "performance_level": performance_level,
                }

        return comparison

    @staticmethod
    def _get_metric_values_by_shop(shop_ids, metric, start_date, end_date):
        """Get values for a specific metric for multiple shops"""
        values = []

        for shop_id in shop_ids:
            if metric == "average_rating":
                value = BenchmarkService._calculate_average_rating(
                    shop_id, start_date, end_date
                )
            elif metric == "cancellation_rate":
                value = BenchmarkService._calculate_cancellation_rate(
                    shop_id, start_date, end_date
                )
            elif metric == "no_show_rate":
                value = BenchmarkService._calculate_no_show_rate(
                    shop_id, start_date, end_date
                )
            elif metric == "wait_time":
                value = BenchmarkService._calculate_wait_time(
                    shop_id, start_date, end_date
                )
            elif metric == "service_time":
                value = BenchmarkService._calculate_service_time(
                    shop_id, start_date, end_date
                )
            elif metric == "revenue_per_appointment":
                value = BenchmarkService._calculate_revenue_per_appointment(
                    shop_id, start_date, end_date
                )
            elif metric == "appointments_per_specialist":
                value = BenchmarkService._calculate_appointments_per_specialist(
                    shop_id, start_date, end_date
                )
            elif metric == "customer_return_rate":
                value = BenchmarkService._calculate_customer_return_rate(
                    shop_id, start_date, end_date
                )
            else:
                value = 0

            # Only include valid values
            if value > 0 or (
                metric in ["cancellation_rate", "no_show_rate", "customer_return_rate"]
                and value >= 0
            ):
                values.append(value)

        return values

    @staticmethod
    def _find_potential_competitors(shop):
        """Find potential competitors for a shop based on location and category"""
        # Get shop's categories
        categories = Category.objects.filter(services__shop=shop).distinct()

        # Find shops in the same city with overlapping categories
        competitors = (
            Shop.objects.filter(
                location__city=shop.location.city,
                services__category__in=categories,
                is_active=True,
            )
            .distinct()
            .exclude(id=shop.id)
        )

        return competitors

    @staticmethod
    def _get_top_performers(shop_ids, start_date, end_date):
        """Get top performing shops for each metric"""
        top_performers = {}

        for metric in BenchmarkService.BENCHMARK_METRICS:
            # Get all values for this metric
            shop_values = []

            for shop_id in shop_ids:
                # Continuing benchmark_service.py from where we left off
                if metric == "average_rating":
                    value = BenchmarkService._calculate_average_rating(
                        shop_id, start_date, end_date
                    )
                elif metric == "cancellation_rate":
                    value = BenchmarkService._calculate_cancellation_rate(
                        shop_id, start_date, end_date
                    )
                elif metric == "no_show_rate":
                    value = BenchmarkService._calculate_no_show_rate(
                        shop_id, start_date, end_date
                    )
                elif metric == "wait_time":
                    value = BenchmarkService._calculate_wait_time(
                        shop_id, start_date, end_date
                    )
                elif metric == "service_time":
                    value = BenchmarkService._calculate_service_time(
                        shop_id, start_date, end_date
                    )
                elif metric == "revenue_per_appointment":
                    value = BenchmarkService._calculate_revenue_per_appointment(
                        shop_id, start_date, end_date
                    )
                elif metric == "appointments_per_specialist":
                    value = BenchmarkService._calculate_appointments_per_specialist(
                        shop_id, start_date, end_date
                    )
                elif metric == "customer_return_rate":
                    value = BenchmarkService._calculate_customer_return_rate(
                        shop_id, start_date, end_date
                    )
                else:
                    value = 0

                # Only include valid values
                if value > 0 or (
                    metric in ["cancellation_rate", "no_show_rate"] and value >= 0
                ):
                    try:
                        shop = Shop.objects.get(id=shop_id)
                        shop_values.append(
                            {
                                "shop_id": str(shop_id),
                                "shop_name": shop.name,
                                "value": value,
                            }
                        )
                    except Shop.DoesNotExist:
                        continue

            if not shop_values:
                continue

            # Determine if higher is better for this metric
            higher_is_better = metric not in [
                "cancellation_rate",
                "no_show_rate",
                "wait_time",
            ]

            # Sort values (ascending or descending based on metric)
            if higher_is_better:
                sorted_values = sorted(
                    shop_values, key=lambda x: x["value"], reverse=True
                )
            else:
                sorted_values = sorted(shop_values, key=lambda x: x["value"])

            # Get top 5 performers
            top_performers[metric] = sorted_values[:5]

        return top_performers

    @staticmethod
    def _get_performance_level(percentile):
        """Determine performance level based on percentile"""
        if percentile >= 90:
            return "excellent"
        elif percentile >= 75:
            return "good"
        elif percentile >= 50:
            return "average"
        elif percentile >= 25:
            return "below average"
        else:
            return "poor"

    @staticmethod
    def _calculate_trend_significance(values):
        """Calculate the significance of a trend"""
        if len(values) < 2:
            return 0

        # Calculate average value
        avg_value = sum(values) / len(values)

        if avg_value == 0:
            return 0

        # Calculate variance
        variance = sum((x - avg_value) ** 2 for x in values) / len(values)

        # Calculate coefficient of variation (normalized standard deviation)
        cv = (variance**0.5) / avg_value if avg_value != 0 else 0

        # Calculate trend line slope using simple linear regression
        n = len(values)
        x_mean = (n - 1) / 2  # mean of indices (0, 1, 2, ..., n-1)
        y_mean = avg_value

        numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator != 0 else 0

        # Normalize slope by dividing by the mean value
        normalized_slope = slope / avg_value if avg_value != 0 else 0

        # Combine the coefficient of variation and normalized slope
        significance = (abs(normalized_slope) * 0.7 + cv * 0.3) * 100

        return round(min(significance, 100), 2)  # Cap at 100

    # Individual metric calculation methods

    @staticmethod
    def _calculate_average_rating(shop_id, start_date, end_date):
        """Calculate average rating for a shop"""
        # Get shop reviews
        shop_reviews = Review.objects.filter(
            content_type__model="shop",
            object_id=shop_id,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get specialist reviews for the shop
        specialist_ids = Specialist.objects.filter(
            employee__shop_id=shop_id
        ).values_list("id", flat=True)

        specialist_reviews = Review.objects.filter(
            content_type__model="specialist",
            object_id__in=specialist_ids,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get service reviews for the shop
        service_ids = Service.objects.filter(shop_id=shop_id).values_list(
            "id", flat=True
        )

        service_reviews = Review.objects.filter(
            content_type__model="service",
            object_id__in=service_ids,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Combine all reviews
        all_reviews = (
            list(shop_reviews) + list(specialist_reviews) + list(service_reviews)
        )

        # Calculate average rating
        if all_reviews:
            avg_rating = sum(review.rating for review in all_reviews) / len(all_reviews)
            return round(avg_rating, 2)
        else:
            return 0

    @staticmethod
    def _calculate_cancellation_rate(shop_id, start_date, end_date):
        """Calculate cancellation rate for a shop"""
        # Get all appointments
        appointments = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lte=end_date
        )

        total_count = appointments.count()

        if total_count == 0:
            return -1  # No appointments

        # Count cancelled appointments
        cancelled_count = appointments.filter(status="cancelled").count()

        # Calculate cancellation rate
        cancellation_rate = (cancelled_count / total_count) * 100

        return round(cancellation_rate, 2)

    @staticmethod
    def _calculate_no_show_rate(shop_id, start_date, end_date):
        """Calculate no-show rate for a shop"""
        # Get all appointments
        appointments = Appointment.objects.filter(
            shop_id=shop_id, start_time__gte=start_date, start_time__lte=end_date
        )

        total_count = appointments.count()

        if total_count == 0:
            return -1  # No appointments

        # Count no-show appointments
        no_show_count = appointments.filter(status="no_show").count()

        # Calculate no-show rate
        no_show_rate = (no_show_count / total_count) * 100

        return round(no_show_rate, 2)

    @staticmethod
    def _calculate_wait_time(shop_id, start_date, end_date):
        """Calculate average wait time for a shop"""
        # Get queue tickets
        tickets = QueueTicket.objects.filter(
            queue__shop_id=shop_id,
            join_time__gte=start_date,
            join_time__lte=end_date,
            status="served",
            join_time__isnull=False,
            serve_time__isnull=False,
        )

        if not tickets.exists():
            return 0  # No queue data

        # Calculate average wait time
        total_wait_time = 0
        count = 0

        for ticket in tickets:
            wait_time = (
                ticket.serve_time - ticket.join_time
            ).total_seconds() / 60  # in minutes
            total_wait_time += wait_time
            count += 1

        if count == 0:
            return 0

        avg_wait_time = total_wait_time / count

        return round(avg_wait_time, 2)

    @staticmethod
    def _calculate_service_time(shop_id, start_date, end_date):
        """Calculate average service time for a shop"""
        # Get completed appointments
        appointments = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_date,
            start_time__lte=end_date,
            status="completed",
            start_time__isnull=False,
            end_time__isnull=False,
        )

        if not appointments.exists():
            return 0  # No completed appointments

        # Calculate average service time
        total_service_time = 0
        count = 0

        for appointment in appointments:
            service_time = (
                appointment.end_time - appointment.start_time
            ).total_seconds() / 60  # in minutes
            total_service_time += service_time
            count += 1

        if count == 0:
            return 0

        avg_service_time = total_service_time / count

        return round(avg_service_time, 2)

    @staticmethod
    def _calculate_revenue_per_appointment(shop_id, start_date, end_date):
        """Calculate average revenue per appointment for a shop"""
        # Get completed appointments
        appointments = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_date,
            start_time__lte=end_date,
            status="completed",
        )

        if not appointments.exists():
            return 0  # No completed appointments

        # Calculate total revenue
        total_revenue = 0

        for appointment in appointments:
            # Assuming service price is the revenue
            total_revenue += appointment.service.price

        # Calculate average revenue per appointment
        avg_revenue = total_revenue / appointments.count()

        return round(avg_revenue, 2)

    @staticmethod
    def _calculate_appointments_per_specialist(shop_id, start_date, end_date):
        """Calculate average appointments per specialist for a shop"""
        # Get specialists for the shop
        specialists = Specialist.objects.filter(
            employee__shop_id=shop_id, employee__is_active=True
        )

        if not specialists.exists():
            return 0  # No specialists

        # Get completed appointments
        appointments = Appointment.objects.filter(
            shop_id=shop_id,
            start_time__gte=start_date,
            start_time__lte=end_date,
            status="completed",
        )

        if not appointments.exists():
            return 0  # No completed appointments

        # Calculate appointments per specialist
        appointments_per_specialist = appointments.count() / specialists.count()

        return round(appointments_per_specialist, 2)

    @staticmethod
    def _calculate_customer_return_rate(shop_id, start_date, end_date):
        """Calculate customer return rate for a shop"""
        # Get all customers who had appointments in the period
        customer_ids = (
            Appointment.objects.filter(
                shop_id=shop_id, start_time__gte=start_date, start_time__lte=end_date
            )
            .values_list("customer_id", flat=True)
            .distinct()
        )

        if not customer_ids:
            return -1  # No customers

        # Count returning customers (those who had previous appointments)
        returning_count = 0

        for customer_id in customer_ids:
            # Check if customer had previous appointments before the start date
            previous_appointments = Appointment.objects.filter(
                shop_id=shop_id, customer_id=customer_id, start_time__lt=start_date
            ).exists()

            if previous_appointments:
                returning_count += 1

        # Calculate return rate
        return_rate = (returning_count / len(customer_ids)) * 100

        return round(return_rate, 2)
