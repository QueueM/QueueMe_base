from datetime import datetime, timedelta

from django.utils import timezone

from apps.shopDashboardApp.constants import (
    TIME_PERIOD_CUSTOM,
    TIME_PERIOD_MONTH,
    TIME_PERIOD_QUARTER,
    TIME_PERIOD_TODAY,
    TIME_PERIOD_WEEK,
    TIME_PERIOD_YEAR,
    TIME_PERIOD_YESTERDAY,
)
from apps.shopDashboardApp.exceptions import InvalidDateRangeException
from apps.shopDashboardApp.models import DashboardLayout
from apps.shopDashboardApp.services.kpi_service import KPIService
from apps.shopDashboardApp.services.stats_service import StatsService


class DashboardService:
    """
    Service for dashboard data management and integration.
    Coordinates data from various sources and combines them into a cohesive dashboard.
    """

    def calculate_date_range(self, time_period, start_date=None, end_date=None):
        """
        Calculate start and end dates based on time period.
        For custom time periods, use provided start/end dates.
        """
        today = timezone.now().date()

        if time_period == TIME_PERIOD_TODAY:
            return {"start_date": today, "end_date": today}

        elif time_period == TIME_PERIOD_YESTERDAY:
            yesterday = today - timedelta(days=1)
            return {"start_date": yesterday, "end_date": yesterday}

        elif time_period == TIME_PERIOD_WEEK:
            # Current week (Sunday to today)
            # Get the most recent Sunday
            start_of_week = today - timedelta(days=today.weekday() + 1)
            if start_of_week > today:  # If today is Sunday
                start_of_week = today

            return {"start_date": start_of_week, "end_date": today}

        elif time_period == TIME_PERIOD_MONTH:
            # Current month (1st to today)
            start_of_month = today.replace(day=1)

            return {"start_date": start_of_month, "end_date": today}

        elif time_period == TIME_PERIOD_QUARTER:
            # Current quarter
            current_month = today.month
            quarter_start_month = ((current_month - 1) // 3) * 3 + 1
            start_of_quarter = today.replace(month=quarter_start_month, day=1)

            return {"start_date": start_of_quarter, "end_date": today}

        elif time_period == TIME_PERIOD_YEAR:
            # Current year (Jan 1st to today)
            start_of_year = today.replace(month=1, day=1)

            return {"start_date": start_of_year, "end_date": today}

        elif time_period == TIME_PERIOD_CUSTOM:
            # Custom date range - validate input
            if not start_date or not end_date:
                raise InvalidDateRangeException(
                    "Start date and end date are required for custom range."
                )

            # Parse dates
            try:
                if isinstance(start_date, str):
                    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                if isinstance(end_date, str):
                    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

                # Validate date range
                if start_date > end_date:
                    raise InvalidDateRangeException("Start date cannot be after end date.")

                return {"start_date": start_date, "end_date": end_date}
            except ValueError:
                raise InvalidDateRangeException("Invalid date format. Use YYYY-MM-DD.")

        else:
            raise InvalidDateRangeException(f"Unknown time period: {time_period}")

    def get_dashboard_data(self, shop_id, user_id, time_period, start_date, end_date):
        """
        Get comprehensive dashboard data including KPIs, charts, and tables.
        This method coordinates calls to specialized services for different data types.
        """
        # Initialize services
        kpi_service = KPIService()
        stats_service = StatsService()

        # Get dashboard layout information
        try:
            from apps.shopDashboardApp.models import DashboardPreference

            preference = DashboardPreference.objects.get(user_id=user_id)

            # Check if user has a preferred layout for this shop
            if preference.preferred_layout and preference.preferred_layout.shop_id == shop_id:
                layout = preference.preferred_layout
            else:
                # Get default layout for shop
                layout = DashboardLayout.objects.get(shop_id=shop_id, is_default=True)
        except (DashboardPreference.DoesNotExist, DashboardLayout.DoesNotExist):
            # Create a default layout if none exists
            from apps.shopDashboardApp.services.settings_service import SettingsService

            settings_service = SettingsService()
            layout = settings_service.create_default_layout(shop_id, user_id)

        # Get KPIs based on layout configuration
        kpi_widgets = layout.widgets.filter(widget_type="kpi", is_visible=True)
        kpi_keys = [widget.kpi_key for widget in kpi_widgets if widget.kpi_key]

        # If no specific KPIs defined in layout, get all KPIs
        kpis = kpi_service.get_kpis(shop_id, start_date, end_date, kpi_keys if kpi_keys else None)

        # Get charts based on layout configuration
        chart_widgets = layout.widgets.filter(widget_type="chart", is_visible=True)
        charts = []

        for widget in chart_widgets:
            if widget.chart_type and widget.data_source:
                chart_data = stats_service.get_chart_data(
                    shop_id=shop_id,
                    chart_type=widget.chart_type,
                    data_source=widget.data_source,
                    start_date=start_date,
                    end_date=end_date,
                    config=widget.config,
                )

                # Override chart title with widget title if available
                if widget.title:
                    chart_data["title"] = widget.title

                charts.append(chart_data)

        # Get tables based on layout configuration
        table_widgets = layout.widgets.filter(widget_type="table", is_visible=True)
        tables = []

        for widget in table_widgets:
            if widget.data_source:
                table_data = stats_service.get_table_data(
                    shop_id=shop_id,
                    data_source=widget.data_source,
                    start_date=start_date,
                    end_date=end_date,
                    config=widget.config,
                )

                # Override table title with widget title if available
                if widget.title:
                    table_data["title"] = widget.title

                tables.append(table_data)

        # Compile complete dashboard data
        dashboard_data = {
            "time_period": time_period,
            "date_range": {
                "start_date": (
                    start_date.isoformat() if hasattr(start_date, "isoformat") else start_date
                ),
                "end_date": (end_date.isoformat() if hasattr(end_date, "isoformat") else end_date),
            },
            "kpis": kpis,
            "charts": charts,
            "tables": tables,
        }

        return dashboard_data

    def get_available_widgets(self, shop_id):
        """
        Get list of available widgets that can be added to the dashboard.
        This is used for the dashboard customization UI.
        """
        # KPI widgets
        kpi_widgets = []

        # Get default KPIs from constants
        from apps.shopDashboardApp.constants import DEFAULT_KPIS

        for kpi in DEFAULT_KPIS:
            kpi_widgets.append(
                {
                    "type": "kpi",
                    "title": kpi["name"],
                    "key": kpi["key"],
                    "category": kpi["category"],
                    "format": kpi["format"],
                }
            )

        # Chart widgets
        chart_widgets = [
            {
                "type": "chart",
                "title": "Revenue Trend",
                "chart_type": "line",
                "data_source": "revenue_trend",
                "description": "Shows revenue trend over time",
            },
            {
                "type": "chart",
                "title": "Bookings by Service",
                "chart_type": "pie",
                "data_source": "bookings_by_service",
                "description": "Distribution of bookings by service",
            },
            {
                "type": "chart",
                "title": "Bookings by Day",
                "chart_type": "bar",
                "data_source": "bookings_by_day",
                "description": "Number of bookings by day of week",
            },
            {
                "type": "chart",
                "title": "Booking Status Distribution",
                "chart_type": "doughnut",
                "data_source": "booking_status",
                "description": "Distribution of bookings by status",
            },
            {
                "type": "chart",
                "title": "Specialist Performance",
                "chart_type": "bar",
                "data_source": "specialist_performance",
                "description": "Booking counts by specialist",
            },
            {
                "type": "chart",
                "title": "Customer Retention",
                "chart_type": "line",
                "data_source": "customer_retention",
                "description": "New vs. returning customers over time",
            },
            {
                "type": "chart",
                "title": "Queue Wait Times",
                "chart_type": "line",
                "data_source": "queue_wait_times",
                "description": "Average queue wait time by hour",
            },
            {
                "type": "chart",
                "title": "Rating Distribution",
                "chart_type": "bar",
                "data_source": "rating_distribution",
                "description": "Distribution of ratings (1-5 stars)",
            },
        ]

        # Table widgets
        table_widgets = [
            {
                "type": "table",
                "title": "Recent Bookings",
                "data_source": "recent_bookings",
                "description": "List of recent bookings",
            },
            {
                "type": "table",
                "title": "Top Services",
                "data_source": "top_services",
                "description": "Services ranked by booking volume",
            },
            {
                "type": "table",
                "title": "Top Customers",
                "data_source": "top_customers",
                "description": "Customers ranked by number of bookings",
            },
            {
                "type": "table",
                "title": "Specialist Performance",
                "data_source": "specialist_table",
                "description": "Detailed specialist performance metrics",
            },
            {
                "type": "table",
                "title": "Recent Reviews",
                "data_source": "recent_reviews",
                "description": "List of recent customer reviews",
            },
        ]

        # Other widget types
        other_widgets = [
            {
                "type": "activity",
                "title": "Activity Feed",
                "description": "Real-time activity feed for the shop",
            },
            {
                "type": "notifications",
                "title": "Notifications",
                "description": "Recent notifications and alerts",
            },
            {
                "type": "calendar",
                "title": "Appointment Calendar",
                "description": "Calendar view of upcoming appointments",
            },
        ]

        # Combine all widget types
        return {
            "kpi_widgets": kpi_widgets,
            "chart_widgets": chart_widgets,
            "table_widgets": table_widgets,
            "other_widgets": other_widgets,
        }
