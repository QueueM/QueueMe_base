from apps.shopDashboardApp.constants import (
    DEFAULT_KPIS,
    TIME_PERIOD_MONTH,
    WIDGET_TYPE_CHART,
    WIDGET_TYPE_KPI,
    WIDGET_TYPE_TABLE,
)
from apps.shopDashboardApp.models import (
    DashboardLayout,
    DashboardPreference,
    DashboardSettings,
    DashboardWidget,
)


class SettingsService:
    """
    Service for managing dashboard settings and configurations.
    Handles default settings, layouts, widgets, and report templates.
    """

    def create_default_settings(self, shop_id):
        """Create default dashboard settings for a shop"""
        settings = DashboardSettings.objects.create(
            shop_id=shop_id,
            default_date_range=TIME_PERIOD_MONTH,
            auto_refresh_interval=0,  # No auto-refresh by default
            custom_theme={},
        )

        return settings

    def create_default_layout(self, shop_id, user_id=None):
        """Create default dashboard layout with widgets for a shop"""
        # Create layout
        layout = DashboardLayout.objects.create(
            shop_id=shop_id,
            name="Default Layout",
            description="Default dashboard layout with standard KPIs and charts",
            is_default=True,
            created_by_id=user_id,
        )

        # Add KPI widgets (top row)
        kpi_positions = [
            {"x": 0, "y": 0, "w": 3, "h": 1},  # Total Revenue
            {"x": 3, "y": 0, "w": 3, "h": 1},  # Total Bookings
            {"x": 6, "y": 0, "w": 3, "h": 1},  # Completed Bookings
            {"x": 9, "y": 0, "w": 3, "h": 1},  # Cancellation Rate
        ]

        kpi_keys = [
            "total_revenue",
            "total_bookings",
            "completed_bookings",
            "cancellation_rate",
        ]

        for i, kpi_key in enumerate(kpi_keys):
            # Find KPI info
            kpi_info = next((kpi for kpi in DEFAULT_KPIS if kpi["key"] == kpi_key), None)

            if kpi_info:
                DashboardWidget.objects.create(
                    layout=layout,
                    title=kpi_info["name"],
                    widget_type=WIDGET_TYPE_KPI,
                    category=kpi_info["category"],
                    kpi_key=kpi_key,
                    position=kpi_positions[i],
                    is_visible=True,
                )

        # Add chart widgets (middle row)
        DashboardWidget.objects.create(
            layout=layout,
            title="Revenue Trend",
            widget_type=WIDGET_TYPE_CHART,
            chart_type="line",
            data_source="revenue_trend",
            position={"x": 0, "y": 1, "w": 6, "h": 2},
            is_visible=True,
        )

        DashboardWidget.objects.create(
            layout=layout,
            title="Bookings by Service",
            widget_type=WIDGET_TYPE_CHART,
            chart_type="pie",
            data_source="bookings_by_service",
            position={"x": 6, "y": 1, "w": 6, "h": 2},
            is_visible=True,
        )

        # Add table widgets (bottom row)
        DashboardWidget.objects.create(
            layout=layout,
            title="Recent Bookings",
            widget_type=WIDGET_TYPE_TABLE,
            data_source="recent_bookings",
            position={"x": 0, "y": 3, "w": 12, "h": 2},
            is_visible=True,
        )

        return layout

    def create_default_preferences(self, user_id):
        """Create default dashboard preferences for a user"""
        # Try to find a default layout for any shop the user has access to
        from apps.employeeapp.models import Employee

        # Find shops the user has access to
        employee = Employee.objects.filter(user_id=user_id).first()
        shop = None

        if employee:
            shop = employee.shop

        # Find or create a default layout
        default_layout = None

        if shop:
            # Try to find an existing default layout
            default_layout = DashboardLayout.objects.filter(shop=shop, is_default=True).first()

            # Create default layout if none exists
            if not default_layout:
                default_layout = self.create_default_layout(shop.id, user_id)

        # Create preferences
        preferences = DashboardPreference.objects.create(
            user_id=user_id,
            preferred_layout=default_layout,
            preferred_date_range=TIME_PERIOD_MONTH,
            favorite_kpis=["total_revenue", "total_bookings", "avg_rating"],
        )

        return preferences

    def get_report_templates(self, shop_id):
        """Get predefined report templates for a shop"""
        # Define standard report templates
        templates = [
            {
                "name": "Daily Performance Summary",
                "description": "Daily summary of key performance metrics",
                "frequency": "daily",
                "time_of_day": "18:00:00",
                "kpis_included": [
                    "total_revenue",
                    "total_bookings",
                    "completed_bookings",
                    "cancellation_rate",
                    "no_show_rate",
                ],
                "charts_included": ["revenue_trend", "booking_status"],
            },
            {
                "name": "Weekly Business Review",
                "description": "Comprehensive weekly review of business performance",
                "frequency": "weekly",
                "day_of_week": 1,  # Monday
                "time_of_day": "09:00:00",
                "kpis_included": [
                    "total_revenue",
                    "avg_revenue_per_booking",
                    "total_bookings",
                    "completed_bookings",
                    "cancellation_rate",
                    "no_show_rate",
                    "total_customers",
                    "new_customers",
                    "returning_customer_rate",
                    "avg_rating",
                ],
                "charts_included": [
                    "revenue_trend",
                    "bookings_by_service",
                    "bookings_by_day",
                    "booking_status",
                    "specialist_performance",
                    "customer_retention",
                ],
            },
            {
                "name": "Monthly Executive Summary",
                "description": "End-of-month executive summary report",
                "frequency": "monthly",
                "day_of_month": 1,  # 1st of month (for previous month)
                "time_of_day": "08:00:00",
                "kpis_included": [
                    "total_revenue",
                    "avg_revenue_per_booking",
                    "total_bookings",
                    "completed_bookings",
                    "cancellation_rate",
                    "no_show_rate",
                    "total_customers",
                    "new_customers",
                    "returning_customer_rate",
                    "avg_queue_wait_time",
                    "avg_rating",
                    "most_popular_service",
                    "top_specialist",
                    "reel_views",
                    "story_views",
                ],
                "charts_included": [
                    "revenue_trend",
                    "bookings_by_service",
                    "bookings_by_day",
                    "booking_status",
                    "specialist_performance",
                    "customer_retention",
                    "queue_wait_times",
                    "rating_distribution",
                ],
            },
        ]

        return templates

    def get_available_theme_options(self):
        """Get available theme options for dashboard customization"""
        return {
            "color_schemes": [
                {
                    "id": "default",
                    "name": "Default",
                    "colors": {
                        "primary": "#1976d2",
                        "secondary": "#dc004e",
                        "success": "#4caf50",
                        "warning": "#ff9800",
                        "error": "#f44336",
                        "background": "#ffffff",
                        "text": "#000000",
                    },
                },
                {
                    "id": "dark",
                    "name": "Dark",
                    "colors": {
                        "primary": "#90caf9",
                        "secondary": "#f48fb1",
                        "success": "#81c784",
                        "warning": "#ffb74d",
                        "error": "#e57373",
                        "background": "#121212",
                        "text": "#ffffff",
                    },
                },
                {
                    "id": "green",
                    "name": "Green",
                    "colors": {
                        "primary": "#2e7d32",
                        "secondary": "#d32f2f",
                        "success": "#388e3c",
                        "warning": "#f57c00",
                        "error": "#c62828",
                        "background": "#f1f8e9",
                        "text": "#1b5e20",
                    },
                },
                {
                    "id": "blue",
                    "name": "Blue",
                    "colors": {
                        "primary": "#1565c0",
                        "secondary": "#c2185b",
                        "success": "#2e7d32",
                        "warning": "#ef6c00",
                        "error": "#b71c1c",
                        "background": "#e3f2fd",
                        "text": "#0d47a1",
                    },
                },
            ],
            "fonts": [
                {"id": "default", "name": "Default", "font": "Roboto"},
                {"id": "serif", "name": "Serif", "font": "Georgia"},
                {"id": "monospace", "name": "Monospace", "font": "Courier New"},
            ],
            "layout_options": [
                {"id": "compact", "name": "Compact"},
                {"id": "comfortable", "name": "Comfortable"},
                {"id": "spacious", "name": "Spacious"},
            ],
        }
