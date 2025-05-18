import django_filters
from django.db import models

from .enums import ServiceLocationType, ServiceStatus
from .models import Service


class ServiceFilter(django_filters.FilterSet):
    """Filter for services"""

    shop = django_filters.UUIDFilter(field_name="shop__id")
    category = django_filters.UUIDFilter(field_name="category__id")
    parent_category = django_filters.UUIDFilter(field_name="category__parent__id")
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    max_duration = django_filters.NumberFilter(field_name="duration", lookup_expr="lte")
    service_location = django_filters.ChoiceFilter(choices=ServiceLocationType.choices)
    status = django_filters.ChoiceFilter(choices=ServiceStatus.choices)
    is_featured = django_filters.BooleanFilter()
    search = django_filters.CharFilter(method="filter_search")
    specialist = django_filters.UUIDFilter(field_name="specialists__id")
    city = django_filters.CharFilter(field_name="shop__location__city")

    class Meta:
        model = Service
        fields = [
            "shop",
            "category",
            "parent_category",
            "min_price",
            "max_price",
            "max_duration",
            "service_location",
            "status",
            "is_featured",
            "specialist",
            "city",
        ]

    def filter_search(self, queryset, name, value):
        """Filter by search term in name or description"""
        if not value:
            return queryset

        return queryset.filter(
            models.Q(name__icontains=value)
            | models.Q(description__icontains=value)
            | models.Q(short_description__icontains=value)
        )
