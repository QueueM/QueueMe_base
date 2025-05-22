import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.db.models import Avg, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def update_shop_analytics(shop_id, date):
    """Update analytics for a shop on a specific date"""
    from django.contrib.contenttypes.models import ContentType

    from apps.bookingapp.models import Appointment
    from apps.queueapp.models import QueueTicket
    from apps.reportanalyticsapp.models import ShopAnalytics
    from apps.reviewapp.models import Review
    from apps.shopapp.models import Shop

    try:
        # Parse date string to date object
        date_obj = datetime.fromisoformat(date).date()

        # Get shop
        shop = Shop.objects.get(id=shop_id)

        # Get or create analytics record
        analytics, created = ShopAnalytics.objects.get_or_create(
            shop=shop, date=date_obj
        )

        # Time range for the day
        # unused_unused_day_start = datetime.combine(date_obj, datetime.min.time())
        # unused_unused_day_end = datetime.combine(date_obj, datetime.max.time())

        # Update booking metrics
        bookings = Appointment.objects.filter(shop=shop, start_time__date=date_obj)

        analytics.total_bookings = bookings.count()
        analytics.bookings_completed = bookings.filter(status="completed").count()
        analytics.bookings_cancelled = bookings.filter(status="cancelled").count()
        analytics.bookings_no_show = bookings.filter(status="no_show").count()

        # Update revenue metrics
        revenue = (
            bookings.filter(status="completed").aggregate(total=Sum("service__price"))[
                "total"
            ]
            or 0
        )
        analytics.total_revenue = revenue

        # Queue metrics
        tickets = QueueTicket.objects.filter(queue__shop=shop, join_time__date=date_obj)

        # Average wait time
        wait_time_data = tickets.filter(
            status="served", actual_wait_time__isnull=False
        ).aggregate(avg_wait=Avg("actual_wait_time"))

        if wait_time_data["avg_wait"] is not None:
            analytics.avg_wait_time = wait_time_data["avg_wait"]

        # Calculate peak hours
        hour_distribution = {}
        for hour in range(24):
            bookings_count = bookings.filter(start_time__hour=hour).count()

            tickets_count = tickets.filter(join_time__hour=hour).count()

            hour_distribution[str(hour)] = bookings_count + tickets_count

        analytics.peak_hours = hour_distribution

        # Customer ratings
        shop_content_type = ContentType.objects.get_for_model(Shop)
        reviews = Review.objects.filter(
            content_type=shop_content_type, object_id=shop.id, created_at__date=date_obj
        )

        if reviews.exists():
            avg_rating = reviews.aggregate(avg=Avg("rating"))["avg"]
            if avg_rating is not None:
                analytics.customer_ratings = avg_rating

        # Customer metrics
        unique_customers = (
            Appointment.objects.filter(shop=shop, start_time__date=date_obj)
            .values("customer")
            .distinct()
            .count()
        )

        # Check which are new vs returning
        customer_ids = bookings.values_list("customer_id", flat=True).distinct()

        new_count = 0
        for customer_id in customer_ids:
            # Check if customer has previous bookings
            previous_bookings = Appointment.objects.filter(
                shop=shop, customer_id=customer_id, start_time__date__lt=date_obj
            ).exists()

            if not previous_bookings:
                new_count += 1

        analytics.new_customers = new_count
        analytics.returning_customers = unique_customers - new_count

        # Save updated analytics
        analytics.save()

        logger.info(f"Updated analytics for shop {shop.name} on {date}")

        return f"Analytics updated for shop {shop_id} on {date}"

    except Exception as e:
        logger.error(f"Error updating shop analytics: {e}")
        raise


@shared_task
def update_specialist_analytics(specialist_id, date):
    """Update analytics for a specialist on a specific date"""
    from django.contrib.contenttypes.models import ContentType

    from apps.bookingapp.models import Appointment
    from apps.reportanalyticsapp.models import SpecialistAnalytics
    from apps.reviewapp.models import Review
    from apps.specialistsapp.models import Specialist

    try:
        # Parse date string to date object
        date_obj = datetime.fromisoformat(date).date()

        # Get specialist
        specialist = Specialist.objects.get(id=specialist_id)

        # Get or create analytics record
        analytics, created = SpecialistAnalytics.objects.get_or_create(
            specialist=specialist, date=date_obj
        )

        # Time range for the day
        # unused_unused_day_start = datetime.combine(date_obj, datetime.min.time())
        # unused_unused_day_end = datetime.combine(date_obj, datetime.max.time())

        # Update booking metrics
        bookings = Appointment.objects.filter(
            specialist=specialist, start_time__date=date_obj
        )

        analytics.total_bookings = bookings.count()
        analytics.bookings_completed = bookings.filter(status="completed").count()
        analytics.bookings_cancelled = bookings.filter(status="cancelled").count()
        analytics.bookings_no_show = bookings.filter(status="no_show").count()

        # Calculate service time and duration metrics
        completed_bookings = bookings.filter(status="completed")
        if completed_bookings.exists():
            # Total service time (in minutes)
            total_time = sum(
                [
                    (booking.end_time - booking.start_time).total_seconds() / 60
                    for booking in completed_bookings
                ]
            )
            analytics.total_service_time = int(total_time)

            # Average service duration
            analytics.avg_service_duration = int(
                total_time / completed_bookings.count()
            )

        # Customer ratings
        specialist_content_type = ContentType.objects.get_for_model(Specialist)
        reviews = Review.objects.filter(
            content_type=specialist_content_type,
            object_id=specialist.id,
            created_at__date=date_obj,
        )

        if reviews.exists():
            avg_rating = reviews.aggregate(avg=Avg("rating"))["avg"]
            if avg_rating is not None:
                analytics.customer_ratings = avg_rating

        # Calculate utilization rate
        try:
            from apps.specialistsapp.models import SpecialistWorkingHours

            # Get working hours for this day of week
            weekday = date_obj.weekday()
            # Adjust to match our 0-indexed weekday (0 = Sunday)
            if weekday == 6:  # If Python's Sunday (6)
                weekday = 0
            else:
                weekday += 1

            working_hours = SpecialistWorkingHours.objects.filter(
                specialist=specialist, weekday=weekday, is_off=False
            ).first()

            if working_hours:
                # Calculate total available minutes
                from_time = working_hours.from_hour
                to_time = working_hours.to_hour

                # Convert to minutes since midnight
                from_minutes = from_time.hour * 60 + from_time.minute
                to_minutes = to_time.hour * 60 + to_time.minute

                total_available_minutes = to_minutes - from_minutes

                # Calculate utilization
                if total_available_minutes > 0:
                    utilization = (
                        analytics.total_service_time / total_available_minutes
                    ) * 100
                    analytics.utilization_rate = min(utilization, 100)  # Cap at 100%
        except Exception as e:
            logger.warning(f"Error calculating utilization rate: {e}")

        # Save updated analytics
        analytics.save()

        logger.info(f"Updated analytics for specialist {specialist_id} on {date}")

        return f"Analytics updated for specialist {specialist_id} on {date}"

    except Exception as e:
        logger.error(f"Error updating specialist analytics: {e}")
        raise


@shared_task
def generate_daily_analytics_snapshot():
    """Generate daily analytics snapshot for all entities"""
    from apps.reportanalyticsapp.services.analytics_service import AnalyticsService

    yesterday = (timezone.now() - timedelta(days=1)).date()

    try:
        # Generate shop snapshots
        AnalyticsService.generate_snapshot(
            snapshot_type="shop", frequency="daily", reference_date=yesterday
        )

        # Generate specialist snapshots
        AnalyticsService.generate_snapshot(
            snapshot_type="specialist", frequency="daily", reference_date=yesterday
        )

        # Generate platform snapshots
        AnalyticsService.generate_snapshot(
            snapshot_type="platform", frequency="daily", reference_date=yesterday
        )

        logger.info(f"Generated daily analytics snapshots for {yesterday}")
        return "Daily analytics snapshots generated successfully"
    except Exception as e:
        logger.error(f"Error generating daily analytics snapshots: {e}")
        raise


@shared_task
def generate_weekly_analytics_snapshot():
    """Generate weekly analytics snapshot for all entities"""
    from apps.reportanalyticsapp.services.analytics_service import AnalyticsService

    # Calculate last week's end date (last Saturday)
    today = timezone.now().date()
    days_since_saturday = (today.weekday() + 1) % 7  # 0 = Sunday in our system
    last_saturday = today - timedelta(days=days_since_saturday)

    # Last week's start date (Sunday before last Saturday)
    last_sunday = last_saturday - timedelta(days=6)

    try:
        # Generate shop snapshots
        AnalyticsService.generate_snapshot(
            snapshot_type="shop",
            frequency="weekly",
            reference_date=last_saturday,
            start_date=last_sunday,
            end_date=last_saturday,
        )

        # Generate specialist snapshots
        AnalyticsService.generate_snapshot(
            snapshot_type="specialist",
            frequency="weekly",
            reference_date=last_saturday,
            start_date=last_sunday,
            end_date=last_saturday,
        )

        # Generate platform snapshots
        AnalyticsService.generate_snapshot(
            snapshot_type="platform",
            frequency="weekly",
            reference_date=last_saturday,
            start_date=last_sunday,
            end_date=last_saturday,
        )

        logger.info(
            f"Generated weekly analytics snapshots for week ending {last_saturday}"
        )
        return "Weekly analytics snapshots generated successfully"
    except Exception as e:
        logger.error(f"Error generating weekly analytics snapshots: {e}")
        raise


@shared_task
def generate_monthly_analytics_snapshot():
    """Generate monthly analytics snapshot for all entities"""

    from apps.reportanalyticsapp.services.analytics_service import AnalyticsService

    # Calculate last month's end date
    today = timezone.now().date()
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    try:
        # Generate shop snapshots
        AnalyticsService.generate_snapshot(
            snapshot_type="shop",
            frequency="monthly",
            reference_date=last_month_end,
            start_date=last_month_start,
            end_date=last_month_end,
        )

        # Generate specialist snapshots
        AnalyticsService.generate_snapshot(
            snapshot_type="specialist",
            frequency="monthly",
            reference_date=last_month_end,
            start_date=last_month_start,
            end_date=last_month_end,
        )

        # Generate platform snapshots
        AnalyticsService.generate_snapshot(
            snapshot_type="platform",
            frequency="monthly",
            reference_date=last_month_end,
            start_date=last_month_start,
            end_date=last_month_end,
        )

        logger.info(
            f"Generated monthly analytics snapshots for month ending {last_month_end}"
        )
        return "Monthly analytics snapshots generated successfully"
    except Exception as e:
        logger.error(f"Error generating monthly analytics snapshots: {e}")
        raise


@shared_task
def run_scheduled_reports():
    """Run all scheduled reports that are due"""
    from apps.reportanalyticsapp.models import ScheduledReport
    from apps.reportanalyticsapp.services.report_service import ReportService

    now = timezone.now()

    # Find all active scheduled reports that are due
    due_reports = ScheduledReport.objects.filter(is_active=True, next_run__lte=now)

    for report in due_reports:
        try:
            # Execute report
            ReportService.execute_scheduled_report(report)

            # Update last_run and next_run
            report.last_run = now
            report.next_run = report.get_next_run_date()
            report.save()

            logger.info(f"Successfully executed scheduled report: {report.name}")
        except Exception as e:
            logger.error(f"Error running scheduled report {report.name}: {e}")

    return f"Processed {due_reports.count()} scheduled reports"


@shared_task
def detect_anomalies(entity_type, entity_id, metric_type, reference_date):
    """Detect anomalies for a specific entity and metric"""
    from apps.reportanalyticsapp.services.anomaly_detector import AnomalyDetector

    try:
        # Parse date string to date object
        date_obj = datetime.fromisoformat(reference_date).date()

        # Run anomaly detection
        detector = AnomalyDetector()
        anomalies = detector.detect_anomalies(
            entity_type=entity_type,
            entity_id=entity_id,
            metric_type=metric_type,
            reference_date=date_obj,
        )

        if anomalies:
            logger.info(
                f"Detected {len(anomalies)} anomalies for {entity_type} {entity_id}"
            )

        return f"Anomaly detection completed for {entity_type} {entity_id} on {reference_date}"
    except Exception as e:
        logger.error(f"Error in anomaly detection: {e}")
        raise


@shared_task
def generate_report(report_execution_id):
    """Generate a report based on execution record"""
    from apps.reportanalyticsapp.models import ReportExecution
    from apps.reportanalyticsapp.services.report_service import ReportService

    try:
        execution = ReportExecution.objects.get(id=report_execution_id)

        # Update status to running
        execution.status = "running"
        execution.save()

        try:
            # Generate report
            result = ReportService.generate_report(
                report_type=execution.report_type,
                parameters=execution.parameters,
                execution_id=str(execution.id),
            )

            # Update execution with results
            execution.status = "completed"
            execution.result_data = result.get("data")
            execution.file_url = result.get("file_url")
            execution.end_time = timezone.now()
            execution.save()

            # Send notification if needed
            if execution.scheduled_report:
                ReportService.send_report_notification(execution)

            logger.info(f"Successfully generated report: {execution.name}")
            return f"Report {execution.name} generated successfully"

        except Exception as e:
            # Update execution with error
            execution.status = "failed"
            execution.error_message = str(e)
            execution.end_time = timezone.now()
            execution.save()

            logger.error(f"Error generating report {execution.name}: {e}")
            return f"Failed to generate report {execution.name}: {e}"

    except ReportExecution.DoesNotExist:
        logger.error(f"Report execution {report_execution_id} not found")
        return f"Report execution {report_execution_id} not found"
