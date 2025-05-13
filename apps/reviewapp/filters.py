from django_filters import rest_framework as filters

from apps.reviewapp.models import (
    PlatformReview,
    ReviewReport,
    ServiceReview,
    ShopReview,
    SpecialistReview,
)


class ShopReviewFilter(filters.FilterSet):
    """Filters for shop reviews"""

    rating_min = filters.NumberFilter(field_name="rating", lookup_expr="gte")
    rating_max = filters.NumberFilter(field_name="rating", lookup_expr="lte")
    date_from = filters.DateFilter(field_name="created_at", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="created_at", lookup_expr="lte")
    status = filters.CharFilter(field_name="status")
    verified_only = filters.BooleanFilter(field_name="is_verified_purchase")

    class Meta:
        model = ShopReview
        fields = [
            "shop",
            "rating_min",
            "rating_max",
            "status",
            "verified_only",
            "date_from",
            "date_to",
        ]


class SpecialistReviewFilter(filters.FilterSet):
    """Filters for specialist reviews"""

    rating_min = filters.NumberFilter(field_name="rating", lookup_expr="gte")
    rating_max = filters.NumberFilter(field_name="rating", lookup_expr="lte")
    date_from = filters.DateFilter(field_name="created_at", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="created_at", lookup_expr="lte")
    status = filters.CharFilter(field_name="status")
    verified_only = filters.BooleanFilter(field_name="is_verified_purchase")

    class Meta:
        model = SpecialistReview
        fields = [
            "specialist",
            "rating_min",
            "rating_max",
            "status",
            "verified_only",
            "date_from",
            "date_to",
        ]


class ServiceReviewFilter(filters.FilterSet):
    """Filters for service reviews"""

    rating_min = filters.NumberFilter(field_name="rating", lookup_expr="gte")
    rating_max = filters.NumberFilter(field_name="rating", lookup_expr="lte")
    date_from = filters.DateFilter(field_name="created_at", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="created_at", lookup_expr="lte")
    status = filters.CharFilter(field_name="status")
    verified_only = filters.BooleanFilter(field_name="is_verified_purchase")

    class Meta:
        model = ServiceReview
        fields = [
            "service",
            "rating_min",
            "rating_max",
            "status",
            "verified_only",
            "date_from",
            "date_to",
        ]


class PlatformReviewFilter(filters.FilterSet):
    """Filters for platform reviews"""

    rating_min = filters.NumberFilter(field_name="rating", lookup_expr="gte")
    rating_max = filters.NumberFilter(field_name="rating", lookup_expr="lte")
    date_from = filters.DateFilter(field_name="created_at", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="created_at", lookup_expr="lte")
    category = filters.CharFilter(field_name="category")

    class Meta:
        model = PlatformReview
        fields = ["rating_min", "rating_max", "category", "date_from", "date_to"]


class ReviewReportFilter(filters.FilterSet):
    """Filters for review reports"""

    status = filters.CharFilter(field_name="status")
    reason = filters.CharFilter(field_name="reason")
    date_from = filters.DateFilter(field_name="created_at", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = ReviewReport
        fields = ["status", "reason", "date_from", "date_to"]
