import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.specialistsapp.models import Specialist


class SpecialistFilter(django_filters.FilterSet):
    shop_id = django_filters.UUIDFilter(field_name="employee__shop__id")
    service_id = django_filters.UUIDFilter(method="filter_by_service")
    category_id = django_filters.UUIDFilter(method="filter_by_category")
    expertise_id = django_filters.UUIDFilter(field_name="expertise__id")
    verified = django_filters.BooleanFilter(field_name="is_verified")
    search = django_filters.CharFilter(method="filter_by_search")
    min_rating = django_filters.NumberFilter(field_name="avg_rating", lookup_expr="gte")
    max_rating = django_filters.NumberFilter(field_name="avg_rating", lookup_expr="lte")
    experience_level = django_filters.CharFilter(field_name="experience_level")
    min_experience = django_filters.NumberFilter(field_name="experience_years", lookup_expr="gte")
    ordering = django_filters.OrderingFilter(
        fields=(
            ("avg_rating", "rating"),
            ("total_bookings", "bookings"),
            ("experience_years", "experience"),
            ("created_at", "created"),
        ),
        field_labels={
            "avg_rating": _("Rating"),
            "total_bookings": _("Booking Count"),
            "experience_years": _("Experience"),
            "created_at": _("Creation Date"),
        },
    )

    class Meta:
        model = Specialist
        fields = [
            "shop_id",
            "service_id",
            "category_id",
            "expertise_id",
            "verified",
            "search",
            "min_rating",
            "max_rating",
            "experience_level",
            "min_experience",
            "ordering",
        ]

    def filter_by_service(self, queryset, name, value):
        """Filter specialists by service"""
        return queryset.filter(specialist_services__service_id=value).distinct()

    def filter_by_category(self, queryset, name, value):
        """Filter specialists by service category"""
        return queryset.filter(
            Q(specialist_services__service__category_id=value) | Q(expertise__id=value)
        ).distinct()

    def filter_by_search(self, queryset, name, value):
        """Filter specialists by search term (name or bio)"""
        return queryset.filter(
            Q(employee__first_name__icontains=value)
            | Q(employee__last_name__icontains=value)
            | Q(bio__icontains=value)
        ).distinct()
