import django_filters
from django.db import models
from django.db.models import Q

from .models import Package


class PackageFilter(django_filters.FilterSet):
    """
    Filter for Packages with advanced filtering options.
    """

    name = django_filters.CharFilter(lookup_expr="icontains")
    min_price = django_filters.NumberFilter(field_name="discounted_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="discounted_price", lookup_expr="lte")
    min_duration = django_filters.NumberFilter(field_name="total_duration", lookup_expr="gte")
    max_duration = django_filters.NumberFilter(field_name="total_duration", lookup_expr="lte")
    min_discount = django_filters.NumberFilter(field_name="discount_percentage", lookup_expr="gte")
    shop = django_filters.UUIDFilter(field_name="shop__id")
    shop_name = django_filters.CharFilter(field_name="shop__name", lookup_expr="icontains")
    category = django_filters.UUIDFilter(field_name="primary_category__id")
    location = django_filters.ChoiceFilter(
        field_name="package_location", choices=Package.LOCATION_CHOICES
    )
    available = django_filters.BooleanFilter(method="filter_available")
    service = django_filters.UUIDFilter(field_name="services__service__id", distinct=True)

    # Advanced search
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Package
        fields = [
            "name",
            "shop",
            "shop_name",
            "status",
            "category",
            "location",
            "min_price",
            "max_price",
            "min_duration",
            "max_duration",
            "min_discount",
            "available",
            "service",
            "search",
        ]

    def filter_available(self, queryset, name, value):
        """
        Filter packages by availability (is_available property).
        This is a complex filter that checks multiple conditions.
        """
        import datetime

        today = datetime.date.today()

        # Base query for active packages
        base_query = Q(status="active")

        # Date range check
        date_query = (Q(start_date__isnull=True) | Q(start_date__lte=today)) & (
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        )

        # Purchase limit check
        purchase_query = Q(max_purchases__isnull=True) | Q(
            current_purchases__lt=models.F("max_purchases")
        )

        if value:  # Available packages
            return queryset.filter(base_query & date_query & purchase_query)
        else:  # Unavailable packages
            return queryset.exclude(base_query & date_query & purchase_query)

    def filter_search(self, queryset, name, value):
        """
        Comprehensive search across multiple fields.
        """
        if not value:
            return queryset

        search_fields = Q(
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(shop__name__icontains=value)
            | Q(services__service__name__icontains=value)
            | Q(primary_category__name__icontains=value)
        )

        return queryset.filter(search_fields).distinct()
