from celery import shared_task
from django.utils import timezone

from apps.notificationsapp.services.notification_service import NotificationService
from apps.shopDashboardApp.exceptions import ReportGenerationException
from apps.shopDashboardApp.models import ScheduledReport
from apps.shopDashboardApp.services.dashboard_service import DashboardService


@shared_task
def process_scheduled_reports():
    """Process all scheduled reports that are due"""
    now = timezone.now()

    # Get current day of week (0=Sunday, 6=Saturday)
    current_day_of_week = now.weekday() + 1 % 7  # Convert to 0-6 where 0 is Sunday
    current_day_of_month = now.day
    current_time = now.time()

    # Get all active reports
    active_reports = ScheduledReport.objects.filter(is_active=True)

    for report in active_reports:
        should_run = False

        # Check if report should run based on frequency
        if report.frequency == "daily":
            should_run = True
        elif report.frequency == "weekly" and report.day_of_week == current_day_of_week:
            should_run = True
        elif (
            report.frequency == "monthly"
            and report.day_of_month == current_day_of_month
        ):
            should_run = True
        elif report.frequency == "quarterly":
            # Run on 1st day of quarter (Jan, Apr, Jul, Oct)
            if current_day_of_month == 1 and now.month in [1, 4, 7, 10]:
                should_run = True

        # Check if it's time to run the report
        if should_run and current_time >= report.time_of_day:
            # Check if report was already sent today
            if report.last_sent_at and report.last_sent_at.date() == now.date():
                continue

            # Generate and send report
            generate_and_send_report.delay(str(report.id))


@shared_task
def generate_and_send_report(report_id):
    """Generate and send a specific report"""
    try:
        report = ScheduledReport.objects.get(id=report_id)

        # Calculate date range based on report settings
        dashboard_service = DashboardService()
        date_range = dashboard_service.calculate_date_range(report.date_range)

        # Generate report data
        report_data = generate_report_data(
            report.shop_id,
            date_range["start_date"],
            date_range["end_date"],
            report.kpis_included,
            report.charts_included,
        )

        # Generate PDF report
        report_pdf = generate_report_pdf(report, report_data)

        # Send report to recipients
        send_report_to_recipients(report, report_pdf)

        # Update last sent timestamp
        report.last_sent_at = timezone.now()
        report.save()

    except Exception as e:
        raise ReportGenerationException(f"Error generating report: {str(e)}")


def generate_report_data(shop_id, start_date, end_date, kpi_keys, chart_sources):
    """Generate data for report"""
    from apps.shopDashboardApp.services.kpi_service import KPIService
    from apps.shopDashboardApp.services.stats_service import StatsService

    # Get KPI data
    kpi_service = KPIService()
    kpis = kpi_service.get_kpis(shop_id, start_date, end_date, kpi_keys)

    # Get chart data
    stats_service = StatsService()
    charts = []

    for source in chart_sources:
        chart_type = "line"  # Default chart type

        # Determine optimal chart type based on data source
        if source == "bookings_by_service":
            chart_type = "pie"
        elif source == "booking_status":
            chart_type = "doughnut"
        elif source == "specialist_performance":
            chart_type = "bar"

        chart_data = stats_service.get_chart_data(
            shop_id=shop_id,
            chart_type=chart_type,
            data_source=source,
            start_date=start_date,
            end_date=end_date,
        )

        charts.append(chart_data)

    # Get shop information
    from apps.shopapp.models import Shop

    shop = Shop.objects.get(id=shop_id)

    # Return compiled data
    return {
        "shop": {"name": shop.name, "id": str(shop.id)},
        "date_range": {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        },
        "kpis": kpis,
        "charts": charts,
    }


def generate_report_pdf(report, report_data):
    """Generate PDF file from report data"""
    # This would typically use a PDF generation library like WeasyPrint or ReportLab
    # For the purpose of this example, we'll assume it returns a PDF file path

    # TODO: Implement actual PDF generation
    # For now, just return a placeholder
    return f"report_{report.id}.pdf"


def send_report_to_recipients(report, report_pdf):
    """Send report to all recipients"""
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string

    # Get shop information
    from apps.shopapp.models import Shop

    shop = Shop.objects.get(id=report.shop_id)

    # Prepare email context
    context = {
        "report_name": report.name,
        "shop_name": shop.name,
        "date": timezone.now().strftime("%Y-%m-%d"),
        "report_period": report.get_date_range_display(),
    }

    # Render email HTML
    email_html = render_to_string(
        "shopDashboardApp/emails/scheduled_report.html", context
    )

    # Create email message
    email = EmailMessage(
        subject=f"Dashboard Report: {report.name} - {shop.name}",
        body=email_html,
        from_email=None,  # Use default from email
        to=[],  # Will be filled with recipient emails
    )
    email.content_subtype = "html"  # Set content type to HTML

    # Attach PDF
    email.attach_file(report_pdf)

    # Send to each recipient
    for recipient in report.recipients:
        if recipient["type"] == "email":
            # Send directly to email address
            email.to = [recipient["email"]]
            email.send()
        elif recipient["type"] == "internal":
            # Find user email and send
            from apps.authapp.models import User

            try:
                user = User.objects.get(id=recipient["id"])
                if user.email:
                    email.to = [user.email]
                    email.send()
            except User.DoesNotExist:
                pass

    # Also send in-app notification to internal recipients
    for recipient in report.recipients:
        if recipient["type"] == "internal":
            NotificationService.send_notification(
                user_id=recipient["id"],
                notification_type="report_ready",
                data={"report_name": report.name, "report_id": str(report.id)},
                channels=["in_app"],
            )
