import django_filters
from django.utils.translation import gettext_lazy as _

from .models import (
    AdminNotification,
    AuditLog,
    MaintenanceSchedule,
    SupportTicket,
    VerificationRequest,
)


class VerificationRequestFilter(django_filters.FilterSet):
    submitted_after = django_filters.DateTimeFilter(
        field_name="submitted_at", lookup_expr="gte", label=_("Submitted After")
    )
    submitted_before = django_filters.DateTimeFilter(
        field_name="submitted_at", lookup_expr="lte", label=_("Submitted Before")
    )
    shop_name = django_filters.CharFilter(
        field_name="shop__name", lookup_expr="icontains", label=_("Shop Name")
    )
    company_name = django_filters.CharFilter(
        field_name="shop__company__name",
        lookup_expr="icontains",
        label=_("Company Name"),
    )

    class Meta:
        model = VerificationRequest
        fields = ["status", "verified_by"]


class SupportTicketFilter(django_filters.FilterSet):
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte", label=_("Created After")
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte", label=_("Created Before")
    )
    created_by_name = django_filters.CharFilter(
        method="filter_by_creator_name", label=_("Creator Name")
    )

    class Meta:
        model = SupportTicket
        fields = ["status", "priority", "category", "assigned_to"]

    def filter_by_creator_name(self, queryset, name, value):
        # Filter based on creator's name (which could be in multiple fields based on user type)
        return queryset.filter(created_by__profile__name__icontains=value)


class AdminNotificationFilter(django_filters.FilterSet):
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte", label=_("Created After")
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte", label=_("Created Before")
    )

    class Meta:
        model = AdminNotification
        fields = ["level", "is_read"]


class AuditLogFilter(django_filters.FilterSet):
    timestamp_after = django_filters.DateTimeFilter(
        field_name="timestamp", lookup_expr="gte", label=_("After")
    )
    timestamp_before = django_filters.DateTimeFilter(
        field_name="timestamp", lookup_expr="lte", label=_("Before")
    )
    actor_name = django_filters.CharFilter(
        field_name="actor__profile__name",
        lookup_expr="icontains",
        label=_("Actor Name"),
    )

    class Meta:
        model = AuditLog
        fields = ["action", "entity_type"]


class MaintenanceScheduleFilter(django_filters.FilterSet):
    start_after = django_filters.DateTimeFilter(
        field_name="start_time", lookup_expr="gte", label=_("Starts After")
    )
    start_before = django_filters.DateTimeFilter(
        field_name="start_time", lookup_expr="lte", label=_("Starts Before")
    )

    class Meta:
        model = MaintenanceSchedule
        fields = ["status"]
