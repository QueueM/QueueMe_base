from django.db import models
from django_filters import rest_framework as filters

from apps.shopDashboardApp.constants import (
    KPI_CATEGORY_CHOICES,
    REPORT_FREQUENCY_CHOICES,
    WIDGET_TYPE_CHOICES,
)
from apps.shopDashboardApp.models import (
    DashboardLayout,
    DashboardSettings,
    DashboardWidget,
    ScheduledReport,
)


class DashboardWidgetFilter(filters.FilterSet):
    """Filter for dashboard widgets"""

    widget_type = filters.ChoiceFilter(choices=WIDGET_TYPE_CHOICES)
    category = filters.ChoiceFilter(choices=KPI_CATEGORY_CHOICES)
    is_visible = filters.BooleanFilter()
    title = filters.CharFilter(lookup_expr="icontains")
    # Exclude position from direct filtering
    position = None

    class Meta:
        model = DashboardWidget
        fields = ["widget_type", "category", "is_visible", "title"]
        filter_overrides = {
            models.JSONField: {
                "filter_class": filters.CharFilter,
                "extra": lambda f: {
                    "lookup_expr": "icontains",
                },
            },
        }


class ScheduledReportFilter(filters.FilterSet):
    """Filter for scheduled reports"""

    name = filters.CharFilter(lookup_expr="icontains")
    frequency = filters.ChoiceFilter(choices=REPORT_FREQUENCY_CHOICES)
    is_active = filters.BooleanFilter()
    # Exclude recipients from direct filtering
    recipients = None

    class Meta:
        model = ScheduledReport
        fields = ["name", "frequency", "is_active", "created_at"]
        filter_overrides = {
            models.JSONField: {
                "filter_class": filters.CharFilter,
                "extra": lambda f: {
                    "lookup_expr": "icontains",
                },
            },
        }


class DashboardLayoutFilter(filters.FilterSet):
    """Filter for dashboard layouts"""

    name = filters.CharFilter(lookup_expr="icontains")
    is_default = filters.BooleanFilter()

    class Meta:
        model = DashboardLayout
        fields = ["name", "is_default", "created_at"]
        # Add the same filter_overrides in case this model uses JSONField
        filter_overrides = {
            models.JSONField: {
                "filter_class": filters.CharFilter,
                "extra": lambda f: {
                    "lookup_expr": "icontains",
                },
            },
        }


class DashboardSettingsFilter(filters.FilterSet):
    """Filter for dashboard settings"""

    class Meta:
        model = DashboardSettings
        fields = ["default_date_range", "auto_refresh_interval"]
        # Add the same filter_overrides in case this model uses JSONField
        filter_overrides = {
            models.JSONField: {
                "filter_class": filters.CharFilter,
                "extra": lambda f: {
                    "lookup_expr": "icontains",
                },
            },
        }
