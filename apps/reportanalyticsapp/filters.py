from django_filters import rest_framework as filters

from apps.reportanalyticsapp.models import (
    AnalyticsSnapshot,
    AnomalyDetection,
    ReportExecution,
    ScheduledReport,
    ShopAnalytics,
    SpecialistAnalytics,
)


class ShopAnalyticsFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name="date", lookup_expr="gte")
    end_date = filters.DateFilter(field_name="date", lookup_expr="lte")
    min_bookings = filters.NumberFilter(field_name="total_bookings", lookup_expr="gte")
    min_revenue = filters.NumberFilter(field_name="total_revenue", lookup_expr="gte")
    min_rating = filters.NumberFilter(field_name="customer_ratings", lookup_expr="gte")

    class Meta:
        model = ShopAnalytics
        fields = {
            "shop": ["exact"],
            "date": ["exact", "year", "month"],
            "total_bookings": ["exact", "lt", "gt"],
            "bookings_completed": ["exact", "lt", "gt"],
            "total_revenue": ["exact", "lt", "gt"],
            "customer_ratings": ["exact", "lt", "gt"],
        }


class SpecialistAnalyticsFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name="date", lookup_expr="gte")
    end_date = filters.DateFilter(field_name="date", lookup_expr="lte")
    min_bookings = filters.NumberFilter(field_name="total_bookings", lookup_expr="gte")
    min_rating = filters.NumberFilter(field_name="customer_ratings", lookup_expr="gte")
    shop = filters.UUIDFilter(field_name="specialist__employee__shop", label="Shop ID")

    class Meta:
        model = SpecialistAnalytics
        fields = {
            "specialist": ["exact"],
            "date": ["exact", "year", "month"],
            "total_bookings": ["exact", "lt", "gt"],
            "bookings_completed": ["exact", "lt", "gt"],
            "customer_ratings": ["exact", "lt", "gt"],
            "utilization_rate": ["exact", "lt", "gt"],
        }


class ScheduledReportFilter(filters.FilterSet):
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    next_run_before = filters.DateTimeFilter(field_name="next_run", lookup_expr="lte")

    class Meta:
        model = ScheduledReport
        fields = {
            "report_type": ["exact", "in"],
            "frequency": ["exact", "in"],
            "is_active": ["exact"],
            "created_by": ["exact"],
            "recipient_type": ["exact"],
            "recipient_user": ["exact"],
            "recipient_shop": ["exact"],
        }


class ReportExecutionFilter(filters.FilterSet):
    created_after = filters.DateTimeFilter(field_name="start_time", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="start_time", lookup_expr="lte")

    class Meta:
        model = ReportExecution
        fields = {
            "report_type": ["exact", "in"],
            "status": ["exact", "in"],
            "created_by": ["exact"],
            "scheduled_report": ["exact", "isnull"],
        }


class AnomalyDetectionFilter(filters.FilterSet):
    detected_after = filters.DateFilter(field_name="detection_date", lookup_expr="gte")
    detected_before = filters.DateFilter(field_name="detection_date", lookup_expr="lte")
    acknowledged_only = filters.BooleanFilter(
        field_name="is_acknowledged", lookup_expr="exact"
    )
    unacknowledged_only = filters.BooleanFilter(method="filter_unacknowledged")

    def filter_unacknowledged(self, queryset, name, value):
        if value:
            return queryset.filter(is_acknowledged=False)
        return queryset

    class Meta:
        model = AnomalyDetection
        fields = {
            "entity_type": ["exact", "in"],
            "entity_id": ["exact"],
            "metric_type": ["exact", "in"],
            "severity": ["exact", "in"],
            "detection_date": ["exact"],
            "is_acknowledged": ["exact"],
            "acknowledged_by": ["exact"],
        }


class AnalyticsSnapshotFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name="snapshot_date", lookup_expr="gte")
    end_date = filters.DateFilter(field_name="snapshot_date", lookup_expr="lte")

    class Meta:
        model = AnalyticsSnapshot
        fields = {
            "snapshot_type": ["exact"],
            "frequency": ["exact"],
            "snapshot_date": ["exact", "year", "month"],
        }
