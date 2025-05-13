# apps/reportanalyticsapp/services/report_service.py

import csv
import io
import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4

import pandas as pd
import pytz
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from core.storage.s3_storage import S3Storage

from ..models import Report, ReportExecution, ScheduledReport
from ..queries.business_queries import BusinessQueries
from ..queries.platform_queries import PlatformQueries
from ..queries.specialist_queries import SpecialistQueries
from ..utils.chart_utils import ChartUtils

logger = logging.getLogger(__name__)


class ReportService:
    """
    Comprehensive service for generating, scheduling, and delivering
    sophisticated analytics reports for businesses, specialists, and platform admins.
    """

    REPORT_TYPES = {
        "business_overview": "Business Overview",
        "service_performance": "Service Performance",
        "specialist_performance": "Specialist Performance",
        "booking_analytics": "Booking Analytics",
        "customer_engagement": "Customer Engagement",
        "queue_analytics": "Queue Analytics",
        "revenue_analysis": "Revenue Analysis",
        "platform_usage": "Platform Usage",
        "customer_satisfaction": "Customer Satisfaction",
    }

    TIME_PERIODS = {
        "daily": "Daily",
        "weekly": "Weekly",
        "monthly": "Monthly",
        "quarterly": "Quarterly",
        "yearly": "Yearly",
        "custom": "Custom",
    }

    FORMATS = {
        "pdf": "PDF",
        "excel": "Excel",
        "csv": "CSV",
        "json": "JSON",
        "html": "HTML",
    }

    @staticmethod
    def get_report_data(
        report_type,
        entity_id,
        entity_type,
        time_period,
        start_date=None,
        end_date=None,
        **kwargs,
    ):
        """
        Get report data based on report type and parameters.
        Uses advanced query optimizations and caching for performance.

        Args:
            report_type: Type of report (from REPORT_TYPES)
            entity_id: ID of the entity (shop, specialist, etc.)
            entity_type: Type of entity (shop, specialist, platform)
            time_period: Time period for report (from TIME_PERIODS)
            start_date: Start date for custom period
            end_date: End date for custom period
            **kwargs: Additional parameters for specific reports

        Returns:
            dict: Report data including metrics, insights and visualization configs
        """
        # Calculate date range
        date_range = ReportService._calculate_date_range(time_period, start_date, end_date)

        # Get the appropriate query class
        if entity_type == "shop" or entity_type == "company":
            query_class = BusinessQueries()
        elif entity_type == "specialist":
            query_class = SpecialistQueries()
        elif entity_type == "platform":
            query_class = PlatformQueries()
        else:
            raise ValueError(f"Unsupported entity type: {entity_type}")

        # Generate cache key for potential caching
        # unused_unused_cache_key = f"report_{report_type}_{entity_id}_{entity_type}_{date_range['start'].isoformat()}_{date_range['end'].isoformat()}"

        # Get report data based on report type
        if report_type == "business_overview":
            raw_data = query_class.get_business_overview(
                entity_id, date_range["start"], date_range["end"]
            )
        elif report_type == "service_performance":
            raw_data = query_class.get_service_performance(
                entity_id, date_range["start"], date_range["end"]
            )
        elif report_type == "specialist_performance":
            raw_data = query_class.get_specialist_performance(
                entity_id, date_range["start"], date_range["end"]
            )
        elif report_type == "booking_analytics":
            raw_data = query_class.get_booking_analytics(
                entity_id, date_range["start"], date_range["end"]
            )
        elif report_type == "customer_engagement":
            raw_data = query_class.get_customer_engagement(
                entity_id, date_range["start"], date_range["end"]
            )
        elif report_type == "queue_analytics":
            raw_data = query_class.get_queue_analytics(
                entity_id, date_range["start"], date_range["end"]
            )
        elif report_type == "revenue_analysis":
            raw_data = query_class.get_revenue_analysis(
                entity_id, date_range["start"], date_range["end"]
            )
        elif report_type == "platform_usage":
            raw_data = query_class.get_platform_usage(date_range["start"], date_range["end"])
        elif report_type == "customer_satisfaction":
            raw_data = query_class.get_customer_satisfaction(
                entity_id, date_range["start"], date_range["end"]
            )
        else:
            raise ValueError(f"Unsupported report type: {report_type}")

        # Post-process data
        processed_data = ReportService._post_process_report_data(
            raw_data, report_type, entity_type, date_range
        )

        # Add insights and recommendations
        processed_data["insights"] = ReportService._generate_insights(
            processed_data, report_type, entity_type
        )
        processed_data["recommendations"] = ReportService._generate_recommendations(
            processed_data, report_type, entity_type
        )

        # Add visualization configurations
        processed_data["visualizations"] = ChartUtils.get_visualization_configs(
            processed_data, report_type
        )

        # Add metadata
        processed_data["metadata"] = {
            "report_type": report_type,
            "report_name": ReportService.REPORT_TYPES.get(report_type, report_type),
            "entity_id": entity_id,
            "entity_type": entity_type,
            "time_period": time_period,
            "time_period_name": ReportService.TIME_PERIODS.get(time_period, time_period),
            "start_date": date_range["start"].isoformat(),
            "end_date": date_range["end"].isoformat(),
            "generated_at": timezone.now().isoformat(),
        }

        return processed_data

    @staticmethod
    def _calculate_date_range(time_period, start_date=None, end_date=None):
        """
        Calculate start and end dates based on time period.

        Args:
            time_period: Time period identifier
            start_date: Custom start date (optional)
            end_date: Custom end date (optional)

        Returns:
            dict: With start and end dates
        """
        now = timezone.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if time_period == "custom" and start_date and end_date:
            # Convert string dates to datetime if needed
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.rstrip("Z")).replace(tzinfo=pytz.UTC)
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date.rstrip("Z")).replace(tzinfo=pytz.UTC)

            return {"start": start_date, "end": end_date}

        if time_period == "daily":
            return {
                "start": today,
                "end": today + timedelta(days=1) - timedelta(microseconds=1),
            }
        elif time_period == "weekly":
            start_of_week = today - timedelta(days=today.weekday())
            return {
                "start": start_of_week,
                "end": start_of_week + timedelta(days=7) - timedelta(microseconds=1),
            }
        elif time_period == "monthly":
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(
                    microseconds=1
                )
            else:
                end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(
                    microseconds=1
                )
            return {"start": start_of_month, "end": end_of_month}
        elif time_period == "quarterly":
            quarter = (today.month - 1) // 3 + 1
            start_of_quarter = today.replace(month=(quarter - 1) * 3 + 1, day=1)
            if quarter == 4:
                end_of_quarter = today.replace(year=today.year + 1, month=1, day=1) - timedelta(
                    microseconds=1
                )
            else:
                end_of_quarter = today.replace(month=quarter * 3 + 1, day=1) - timedelta(
                    microseconds=1
                )
            return {"start": start_of_quarter, "end": end_of_quarter}
        elif time_period == "yearly":
            start_of_year = today.replace(month=1, day=1)
            end_of_year = today.replace(year=today.year + 1, month=1, day=1) - timedelta(
                microseconds=1
            )
            return {"start": start_of_year, "end": end_of_year}
        else:
            # Default to last 30 days
            return {"start": today - timedelta(days=30), "end": now}

    @staticmethod
    def _post_process_report_data(raw_data, report_type, entity_type, date_range):
        """
        Post-process raw data to format it correctly and add computed metrics.

        Args:
            raw_data: Raw data from queries
            report_type: Type of report
            entity_type: Type of entity
            date_range: Date range for the report

        Returns:
            dict: Processed data with additional metrics
        """
        processed_data = raw_data.copy()

        # Add growth metrics (compare with previous period)
        if "metrics" in processed_data:
            prev_range = {
                "start": date_range["start"] - (date_range["end"] - date_range["start"]),
                "end": date_range["start"] - timedelta(microseconds=1),
            }

            for metric, value in processed_data["metrics"].items():
                if isinstance(value, (int, float)) and value != 0:
                    # Calculate query for previous period based on entity type and report
                    if entity_type == "shop" or entity_type == "company":
                        query_class = BusinessQueries()
                    elif entity_type == "specialist":
                        query_class = SpecialistQueries()
                    elif entity_type == "platform":
                        query_class = PlatformQueries()

                    # Get specific method for report type
                    method_name = f"get_{report_type}"
                    if hasattr(query_class, method_name):
                        prev_data = getattr(query_class, method_name)(
                            processed_data.get("entity_id"),
                            prev_range["start"],
                            prev_range["end"],
                        )

                        if "metrics" in prev_data and metric in prev_data["metrics"]:
                            prev_value = prev_data["metrics"][metric]
                            if prev_value != 0:
                                growth = ((value - prev_value) / prev_value) * 100
                                processed_data.setdefault("growth_metrics", {})[metric] = round(
                                    growth, 2
                                )
                            else:
                                processed_data.setdefault("growth_metrics", {})[metric] = 100.0
                        else:
                            processed_data.setdefault("growth_metrics", {})[metric] = 100.0

        # Add computed metrics based on raw data
        if report_type == "business_overview":
            if "metrics" in processed_data:
                # Calculate customer retention rate
                if (
                    "total_customers" in processed_data["metrics"]
                    and "returning_customers" in processed_data["metrics"]
                ):
                    total_customers = processed_data["metrics"]["total_customers"]
                    returning_customers = processed_data["metrics"]["returning_customers"]
                    if total_customers > 0:
                        retention_rate = (returning_customers / total_customers) * 100
                        processed_data["metrics"]["retention_rate"] = round(retention_rate, 2)

                # Calculate average booking value
                if (
                    "total_revenue" in processed_data["metrics"]
                    and "total_bookings" in processed_data["metrics"]
                ):
                    total_revenue = processed_data["metrics"]["total_revenue"]
                    total_bookings = processed_data["metrics"]["total_bookings"]
                    if total_bookings > 0:
                        avg_booking_value = total_revenue / total_bookings
                        processed_data["metrics"]["avg_booking_value"] = round(avg_booking_value, 2)

        # Add time series data if applicable
        if "time_series" in processed_data:
            # Ensure all time series have same time points if needed
            pass

        # Add benchmarks if applicable (e.g. compare to industry averages)
        if entity_type in ["shop", "company", "specialist"]:
            processed_data["benchmarks"] = ReportService._get_benchmarks(
                processed_data, report_type, entity_type
            )

        return processed_data

    @staticmethod
    def _generate_insights(data, report_type, entity_type):
        """
        Generate insights based on the report data.
        Uses advanced analytics to identify patterns and notable metrics.

        Args:
            data: Processed report data
            report_type: Type of report
            entity_type: Type of entity

        Returns:
            list: Insights as list of text items
        """
        insights = []

        # Common insights across report types
        if "metrics" in data and "growth_metrics" in data:
            # Find top growing metrics
            growth_metrics = data["growth_metrics"]
            if growth_metrics:
                top_metrics = sorted(growth_metrics.items(), key=lambda x: x[1], reverse=True)[:3]
                for metric, growth in top_metrics:
                    if growth > 10:
                        metric_name = metric.replace("_", " ").title()
                        insights.append(
                            f"{metric_name} has grown significantly by {growth}% compared to previous period"
                        )
                    elif growth < -10:
                        metric_name = metric.replace("_", " ").title()
                        insights.append(
                            f"{metric_name} has decreased by {abs(growth)}% compared to previous period"
                        )

        # Report-specific insights
        if report_type == "business_overview":
            metrics = data.get("metrics", {})

            # Look for notable changes in key business metrics
            if "retention_rate" in metrics:
                retention_rate = metrics["retention_rate"]
                if retention_rate > 70:
                    insights.append(
                        f"Strong customer retention rate of {retention_rate}% indicates high customer satisfaction"
                    )
                elif retention_rate < 40:
                    insights.append(
                        f"Low customer retention rate of {retention_rate}% suggests customer satisfaction issues to address"
                    )

            # Service utilization insights
            if "service_data" in data:
                most_booked = sorted(
                    data["service_data"],
                    key=lambda x: x.get("bookings", 0),
                    reverse=True,
                )
                if most_booked:
                    insights.append(
                        f"Your most popular service is {most_booked[0]['name']} with {most_booked[0].get('bookings', 0)} bookings"
                    )

                # Find underperforming services
                least_booked = sorted(data["service_data"], key=lambda x: x.get("bookings", 0))
                if least_booked and least_booked[0].get("bookings", 0) == 0:
                    insights.append(
                        f"Service {least_booked[0]['name']} has no bookings in this period"
                    )

        elif report_type == "booking_analytics":
            # Look for booking patterns
            if "hourly_distribution" in data:
                hourly = data["hourly_distribution"]
                max_hour = max(hourly.items(), key=lambda x: x[1]) if hourly else None
                if max_hour:
                    insights.append(
                        f"Peak booking hour is {max_hour[0]} with {max_hour[1]} bookings"
                    )

            if "day_distribution" in data:
                days = data["day_distribution"]
                max_day = max(days.items(), key=lambda x: x[1]) if days else None
                if max_day:
                    day_names = [
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                        "Sunday",
                    ]
                    day_name = day_names[int(max_day[0])]
                    insights.append(f"Most bookings occur on {day_name} with {max_day[1]} bookings")

            # Cancellation rate insights
            if "metrics" in data and "cancellation_rate" in data["metrics"]:
                cancel_rate = data["metrics"]["cancellation_rate"]
                if cancel_rate > 20:
                    insights.append(
                        f"High cancellation rate of {cancel_rate}% may indicate scheduling issues"
                    )
                elif cancel_rate < 5:
                    insights.append(
                        f"Low cancellation rate of {cancel_rate}% shows strong customer commitment"
                    )

        elif report_type == "customer_satisfaction":
            if "avg_rating" in data.get("metrics", {}):
                avg_rating = data["metrics"]["avg_rating"]
                if avg_rating >= 4.5:
                    insights.append(
                        f"Excellent average rating of {avg_rating}/5.0 demonstrates strong customer satisfaction"
                    )
                elif avg_rating <= 3.5:
                    insights.append(
                        f"Below average rating of {avg_rating}/5.0 indicates room for improvement"
                    )

            # Analyze review sentiments if available
            if "sentiment_analysis" in data:
                sentiment = data["sentiment_analysis"]
                if "positive_keywords" in sentiment and sentiment["positive_keywords"]:
                    insights.append(
                        f"Customers frequently mention these positive aspects: {', '.join(sentiment['positive_keywords'][:3])}"
                    )
                if "negative_keywords" in sentiment and sentiment["negative_keywords"]:
                    insights.append(
                        f"Areas for improvement based on reviews: {', '.join(sentiment['negative_keywords'][:3])}"
                    )

        # Add 3-5 insights only to keep it focused
        return insights[:5]

    @staticmethod
    def _generate_recommendations(data, report_type, entity_type):
        """
        Generate actionable recommendations based on the report data.
        Uses business rules and best practices to suggest improvements.

        Args:
            data: Processed report data
            report_type: Type of report
            entity_type: Type of entity

        Returns:
            list: Recommendations as list of text items
        """
        recommendations = []

        # General recommendations based on metrics
        if "metrics" in data and "growth_metrics" in data:
            # Find declining metrics
            growth_metrics = data["growth_metrics"]
            if growth_metrics:
                declining_metrics = {k: v for k, v in growth_metrics.items() if v < -10}
                for metric, growth in declining_metrics.items():
                    if metric == "total_bookings":
                        recommendations.append(
                            "Consider running a targeted promotion to increase bookings"
                        )
                    elif metric == "avg_rating":
                        recommendations.append(
                            "Focus on improving service quality to boost ratings"
                        )
                    elif metric == "total_revenue":
                        recommendations.append(
                            "Review pricing strategy or consider package deals to increase revenue"
                        )

        # Report-specific recommendations
        if report_type == "business_overview":
            metrics = data.get("metrics", {})

            # Retention recommendations
            if "retention_rate" in metrics and metrics["retention_rate"] < 50:
                recommendations.append("Implement a customer loyalty program to improve retention")

            # Service utilization recommendations
            if "service_data" in data:
                underutilized = [
                    s for s in data["service_data"] if s.get("utilization_rate", 0) < 40
                ]
                if underutilized:
                    recommendations.append(
                        f"Consider promoting underutilized services like {underutilized[0]['name']} with special offers"
                    )

        elif report_type == "booking_analytics":
            # Peak time optimization
            if "hourly_distribution" in data and "day_distribution" in data:
                hourly = data["hourly_distribution"]
                low_hours = [h for h, count in hourly.items() if count < max(hourly.values()) * 0.3]
                if low_hours:
                    recommendations.append(
                        f"Offer discounts during low-booking hours ({', '.join(low_hours[:3])}) to balance demand"
                    )

            # Cancellation handling
            if (
                "metrics" in data
                and "cancellation_rate" in data["metrics"]
                and data["metrics"]["cancellation_rate"] > 15
            ):
                recommendations.append(
                    "Implement a simple cancellation fee to reduce last-minute cancellations"
                )

        elif report_type == "specialist_performance":
            # Underperforming specialists
            if "specialist_data" in data:
                low_rated = [s for s in data["specialist_data"] if s.get("avg_rating", 5) < 4.0]
                if low_rated:
                    recommendations.append("Consider training for specialists with lower ratings")

            # Unbalanced workloads
            if "specialist_data" in data:
                bookings = [s.get("bookings", 0) for s in data["specialist_data"]]
                if bookings and max(bookings) > 2 * min(bookings) and min(bookings) > 0:
                    recommendations.append(
                        "Workload is unevenly distributed among specialists - consider rebalancing assignments"
                    )

        elif report_type == "customer_satisfaction":
            if "review_topics" in data:
                negative_topics = [t for t in data["review_topics"] if t.get("sentiment", 0) < 0]
                if negative_topics:
                    topic_names = [t["topic"] for t in negative_topics[:2]]
                    recommendations.append(
                        f"Focus on improving these areas mentioned in negative reviews: {', '.join(topic_names)}"
                    )

            if (
                "metrics" in data
                and "response_rate" in data["metrics"]
                and data["metrics"]["response_rate"] < 80
            ):
                recommendations.append(
                    "Improve response rate to customer inquiries to boost satisfaction"
                )

        # Add up to 3 recommendations
        return recommendations[:3]

    @staticmethod
    def _get_benchmarks(data, report_type, entity_type):
        """
        Get benchmarks to compare entity performance against industry averages.

        Args:
            data: Report data
            report_type: Type of report
            entity_type: Type of entity

        Returns:
            dict: Benchmark comparisons
        """
        # In a real implementation, this would query from a benchmark database
        # For now, we'll return some example benchmarks
        benchmarks = {}

        if "metrics" in data:
            metrics = data["metrics"]

            if report_type == "business_overview":
                benchmarks = {
                    "avg_rating": {
                        "entity_value": metrics.get("avg_rating", 0),
                        "industry_avg": 4.2,
                        "percentile": 65 if metrics.get("avg_rating", 0) > 4.2 else 35,
                    },
                    "cancellation_rate": {
                        "entity_value": metrics.get("cancellation_rate", 0),
                        "industry_avg": 12.5,
                        "percentile": (65 if metrics.get("cancellation_rate", 0) < 12.5 else 35),
                    },
                    "retention_rate": {
                        "entity_value": metrics.get("retention_rate", 0),
                        "industry_avg": 55.0,
                        "percentile": (65 if metrics.get("retention_rate", 0) > 55.0 else 35),
                    },
                }
            elif report_type == "specialist_performance":
                benchmarks = {
                    "avg_rating": {
                        "entity_value": metrics.get("avg_rating", 0),
                        "industry_avg": 4.1,
                        "percentile": 60 if metrics.get("avg_rating", 0) > 4.1 else 40,
                    },
                    "bookings_per_day": {
                        "entity_value": metrics.get("bookings_per_day", 0),
                        "industry_avg": 6.2,
                        "percentile": (70 if metrics.get("bookings_per_day", 0) > 6.2 else 30),
                    },
                }

        return benchmarks

    @staticmethod
    @transaction.atomic
    def generate_report(
        report_type,
        entity_id,
        entity_type,
        time_period,
        format="pdf",
        start_date=None,
        end_date=None,
        **kwargs,
    ):
        """
        Generate a report and save it.

        Args:
            report_type: Type of report
            entity_id: ID of the entity
            entity_type: Type of entity
            time_period: Time period for report
            format: Report format (pdf, excel, csv, json)
            start_date: Start date for custom period (optional)
            end_date: End date for custom period (optional)
            **kwargs: Additional parameters

        Returns:
            Report: Generated report object
        """
        # Get entity content type
        if entity_type == "shop":
            from apps.shopapp.models import Shop

            entity_model = Shop
        elif entity_type == "company":
            from apps.companiesapp.models import Company

            entity_model = Company
        elif entity_type == "specialist":
            from apps.specialistsapp.models import Specialist

            entity_model = Specialist
        elif entity_type == "platform":
            # Platform reports are not tied to a specific model
            entity_content_type = None
            entity_object_id = None
        else:
            raise ValueError(f"Unsupported entity type: {entity_type}")

        # Get content type and object ID if not platform
        if entity_type != "platform":
            entity_content_type = ContentType.objects.get_for_model(entity_model)
            entity_object_id = entity_id

        # Get report data
        report_data = ReportService.get_report_data(
            report_type,
            entity_id,
            entity_type,
            time_period,
            start_date,
            end_date,
            **kwargs,
        )

        # Generate report file
        file_url = ReportService._generate_report_file(report_data, format)

        # Create report record
        report = Report.objects.create(
            name=f"{ReportService.REPORT_TYPES.get(report_type, report_type)} - {ReportService.TIME_PERIODS.get(time_period, time_period)}",
            report_type=report_type,
            entity_type=entity_type,
            content_type=entity_content_type,
            object_id=entity_object_id,
            time_period=time_period,
            start_date=report_data["metadata"]["start_date"],
            end_date=report_data["metadata"]["end_date"],
            format=format,
            file_url=file_url,
            data=report_data,
        )

        return report

    @staticmethod
    def _generate_report_file(report_data, format):
        """
        Generate report file in the specified format and upload to storage.

        Args:
            report_data: Report data
            format: Report format

        Returns:
            str: URL to the generated file
        """
        s3_storage = S3Storage()
        file_name = f"reports/{report_data['metadata']['entity_type']}_{report_data['metadata']['report_type']}_{uuid4()}"

        if format == "pdf":
            # In a real implementation, we would render an HTML template and convert to PDF
            # Here we'll simulate by creating a simple text file
            file_content = f"Report: {report_data['metadata']['report_name']}\n"
            file_content += f"Period: {report_data['metadata']['time_period_name']}\n"
            file_content += f"Generated: {report_data['metadata']['generated_at']}\n\n"

            # Add metrics
            if "metrics" in report_data:
                file_content += "METRICS:\n"
                for key, value in report_data["metrics"].items():
                    file_content += f"- {key.replace('_', ' ').title()}: {value}\n"

            # Add insights
            if "insights" in report_data:
                file_content += "\nINSIGHTS:\n"
                for insight in report_data["insights"]:
                    file_content += f"- {insight}\n"

            # Add recommendations
            if "recommendations" in report_data:
                file_content += "\nRECOMMENDATIONS:\n"
                for rec in report_data["recommendations"]:
                    file_content += f"- {rec}\n"

            # Convert to bytes for upload
            file_bytes = io.BytesIO(file_content.encode("utf-8"))
            file_path = f"{file_name}.txt"  # Using .txt as a placeholder for PDF

            # Upload file
            return s3_storage.upload_file_object(file_bytes, file_path, "text/plain")

        elif format == "excel":
            # Create Excel file using pandas
            # unused_unused_df = ReportService._convert_to_dataframe(report_data)
            excel_buffer = io.BytesIO()

            with pd.ExcelWriter(excel_buffer) as writer:
                # Write metrics
                if "metrics" in report_data:
                    metrics_df = pd.DataFrame(
                        list(report_data["metrics"].items()),
                        columns=["Metric", "Value"],
                    )
                    metrics_df["Metric"] = metrics_df["Metric"].str.replace("_", " ").str.title()
                    metrics_df.to_excel(writer, sheet_name="Metrics", index=False)

                # Write time series data if available
                if "time_series" in report_data:
                    for series_name, series_data in report_data["time_series"].items():
                        series_df = pd.DataFrame(
                            list(series_data.items()), columns=["Date", series_name]
                        )
                        series_df.to_excel(
                            writer, sheet_name=f"Series_{series_name[:10]}", index=False
                        )

                # Write entity-specific data
                for key in ["service_data", "specialist_data", "customer_data"]:
                    if key in report_data and isinstance(report_data[key], list):
                        if report_data[key]:
                            entity_df = pd.DataFrame(report_data[key])
                            entity_df.to_excel(
                                writer,
                                sheet_name=key.replace("_", " ").title(),
                                index=False,
                            )

            excel_buffer.seek(0)
            file_path = f"{file_name}.xlsx"

            # Upload file
            return s3_storage.upload_file_object(
                excel_buffer,
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        elif format == "csv":
            # Create CSV file
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)

            # Write metrics
            if "metrics" in report_data:
                writer.writerow(["Metric", "Value"])
                for key, value in report_data["metrics"].items():
                    writer.writerow([key.replace("_", " ").title(), value])

            csv_content = csv_buffer.getvalue()
            csv_bytes = io.BytesIO(csv_content.encode("utf-8"))
            file_path = f"{file_name}.csv"

            # Upload file
            return s3_storage.upload_file_object(csv_bytes, file_path, "text/csv")

        elif format == "json":
            # Create JSON file
            json_content = json.dumps(report_data, indent=2)
            json_bytes = io.BytesIO(json_content.encode("utf-8"))
            file_path = f"{file_name}.json"

            # Upload file
            return s3_storage.upload_file_object(json_bytes, file_path, "application/json")

        elif format == "html":
            # Create HTML file
            html_content = render_to_string(
                "reportanalyticsapp/report_template.html", {"report": report_data}
            )
            html_bytes = io.BytesIO(html_content.encode("utf-8"))
            file_path = f"{file_name}.html"

            # Upload file
            return s3_storage.upload_file_object(html_bytes, file_path, "text/html")

        else:
            raise ValueError(f"Unsupported format: {format}")

    @staticmethod
    def _convert_to_dataframe(report_data):
        """
        Convert report data to pandas DataFrame for Excel export.

        Args:
            report_data: Report data dictionary

        Returns:
            DataFrame: Pandas DataFrame with report data
        """
        # Default empty DataFrame
        df = pd.DataFrame()

        # Process based on data structure
        if "metrics" in report_data:
            df = pd.DataFrame(list(report_data["metrics"].items()), columns=["Metric", "Value"])
            df["Metric"] = df["Metric"].str.replace("_", " ").str.title()

        return df

    @staticmethod
    @transaction.atomic
    def schedule_report(
        report_type,
        entity_id,
        entity_type,
        time_period,
        frequency,
        format="pdf",
        recipients=None,
        start_date=None,
        end_date=None,
        **kwargs,
    ):
        """
        Schedule a report for regular generation and delivery.

        Args:
            report_type: Type of report
            entity_id: ID of the entity
            entity_type: Type of entity
            time_period: Time period for report
            frequency: Frequency of report generation (daily, weekly, monthly)
            format: Report format
            recipients: List of recipient emails
            start_date: Start date for custom period (optional)
            end_date: End date for custom period (optional)
            **kwargs: Additional parameters

        Returns:
            ReportSchedule: Created schedule object
        """
        if recipients is None:
            recipients = []

        # Get entity content type
        if entity_type == "shop":
            from apps.shopapp.models import Shop

            entity_model = Shop
        elif entity_type == "company":
            from apps.companiesapp.models import Company

            entity_model = Company
        elif entity_type == "specialist":
            from apps.specialistsapp.models import Specialist

            entity_model = Specialist
        elif entity_type == "platform":
            # Platform reports are not tied to a specific model
            entity_content_type = None
            entity_object_id = None
        else:
            raise ValueError(f"Unsupported entity type: {entity_type}")

        # Get content type and object ID if not platform
        if entity_type != "platform":
            entity_content_type = ContentType.objects.get_for_model(entity_model)
            entity_object_id = entity_id

        # Create schedule
        schedule = ScheduledReport.objects.create(
            name=f"{ReportService.REPORT_TYPES.get(report_type, report_type)} - {frequency}",
            report_type=report_type,
            entity_type=entity_type,
            content_type=entity_content_type,
            object_id=entity_object_id,
            time_period=time_period,
            frequency=frequency,
            format=format,
            recipients=recipients,
            parameters={
                "start_date": (
                    start_date.isoformat() if isinstance(start_date, datetime) else start_date
                ),
                "end_date": (end_date.isoformat() if isinstance(end_date, datetime) else end_date),
                **kwargs,
            },
            is_active=True,
        )

        return schedule

    @staticmethod
    def execute_scheduled_report(schedule_id):
        """
        Execute a scheduled report generation.

        Args:
            schedule_id: ID of the report schedule

        Returns:
            ReportExecution: Execution record
        """
        try:
            schedule = ScheduledReport.objects.get(id=schedule_id, is_active=True)

            # Generate report
            report = ReportService.generate_report(
                schedule.report_type,
                schedule.object_id,
                schedule.entity_type,
                schedule.time_period,
                schedule.format,
                **schedule.parameters,
            )

            # Create execution record
            execution = ReportExecution.objects.create(
                schedule=schedule, report=report, status="success"
            )

            # Send email to recipients
            if schedule.recipients:
                ReportService.send_report_email(report, schedule.recipients)

            return execution

        except Exception as e:
            logger.error(f"Error executing scheduled report {schedule_id}: {str(e)}")

            # Create failed execution record
            execution = ReportExecution.objects.create(
                schedule_id=schedule_id, status="error", error_message=str(e)
            )

            return execution

    @staticmethod
    def send_report_email(report, recipients):
        """
        Send report via email to recipients.

        Args:
            report: Report object
            recipients: List of recipient emails

        Returns:
            bool: Success status
        """
        try:
            # Prepare email subject and body
            subject = f"Queue Me Report: {report.name}"

            # Render HTML email
            html_content = render_to_string(
                "reportanalyticsapp/email/report_email.html",
                {"report": report, "download_url": report.file_url},
            )

            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body="Please view this email with an HTML compatible email client.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipients,
            )

            email.attach_alternative(html_content, "text/html")

            # Send email
            email.send()

            return True

        except Exception as e:
            logger.error(f"Error sending report email: {str(e)}")
            return False
