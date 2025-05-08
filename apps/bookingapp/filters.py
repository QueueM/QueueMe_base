# apps/bookingapp/filters.py
from datetime import timedelta

from django.utils import timezone
from django_filters import rest_framework as filters

from apps.bookingapp.models import Appointment, MultiServiceBooking


class AppointmentFilter(filters.FilterSet):
    """Advanced filter for appointments with many search options"""

    # Date filtering
    start_date = filters.DateFilter(field_name="start_time", lookup_expr="date__gte")
    end_date = filters.DateFilter(field_name="start_time", lookup_expr="date__lte")

    # Status filtering
    status = filters.CharFilter(field_name="status")
    statuses = filters.MultipleChoiceFilter(
        field_name="status", choices=Appointment.STATUS_CHOICES
    )

    # Payment status filtering
    payment_status = filters.CharFilter(field_name="payment_status")

    # Customer filtering
    customer = filters.UUIDFilter(field_name="customer__id")
    phone_number = filters.CharFilter(field_name="customer__phone_number")

    # Shop filtering
    shop = filters.UUIDFilter(field_name="shop__id")
    shop_name = filters.CharFilter(field_name="shop__name", lookup_expr="icontains")

    # Service filtering
    service = filters.UUIDFilter(field_name="service__id")
    service_name = filters.CharFilter(
        field_name="service__name", lookup_expr="icontains"
    )

    # Specialist filtering
    specialist = filters.UUIDFilter(field_name="specialist__id")

    # Time range helpers
    today = filters.BooleanFilter(method="filter_today")
    upcoming = filters.BooleanFilter(method="filter_upcoming")
    past = filters.BooleanFilter(method="filter_past")
    this_week = filters.BooleanFilter(method="filter_this_week")
    this_month = filters.BooleanFilter(method="filter_this_month")

    class Meta:
        model = Appointment
        fields = [
            "status",
            "payment_status",
            "start_date",
            "end_date",
            "customer",
            "shop",
            "service",
            "specialist",
            "today",
            "upcoming",
            "past",
            "this_week",
            "this_month",
        ]

    def filter_today(self, queryset, name, value):
        if value:
            today = timezone.now().date()
            return queryset.filter(start_time__date=today)
        return queryset

    def filter_upcoming(self, queryset, name, value):
        if value:
            now = timezone.now()
            return queryset.filter(start_time__gt=now)
        return queryset

    def filter_past(self, queryset, name, value):
        if value:
            now = timezone.now()
            return queryset.filter(start_time__lt=now)
        return queryset

    def filter_this_week(self, queryset, name, value):
        if value:
            today = timezone.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return queryset.filter(
                start_time__date__gte=start_of_week, start_time__date__lte=end_of_week
            )
        return queryset

    def filter_this_month(self, queryset, name, value):
        if value:
            today = timezone.now().date()
            start_of_month = today.replace(day=1)
            # Handle variable month lengths
            if today.month == 12:
                next_month = today.replace(year=today.year + 1, month=1, day=1)
            else:
                next_month = today.replace(month=today.month + 1, day=1)
            end_of_month = next_month - timedelta(days=1)
            return queryset.filter(
                start_time__date__gte=start_of_month, start_time__date__lte=end_of_month
            )
        return queryset


class MultiServiceBookingFilter(filters.FilterSet):
    """Filter for multi-service bookings"""

    # Date filtering
    start_date = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    end_date = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    # Customer filtering
    customer = filters.UUIDFilter(field_name="customer__id")

    # Shop filtering
    shop = filters.UUIDFilter(field_name="shop__id")

    # Payment status filtering
    payment_status = filters.CharFilter(field_name="payment_status")

    class Meta:
        model = MultiServiceBooking
        fields = ["customer", "shop", "payment_status", "start_date", "end_date"]
