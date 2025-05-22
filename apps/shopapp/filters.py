import django_filters

from .models import Shop, ShopFollower, ShopHours, ShopVerification


class ShopFilter(django_filters.FilterSet):
    """Filter for shops"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    company = django_filters.UUIDFilter(field_name="company__id")
    city = django_filters.CharFilter(field_name="location__city", lookup_expr="iexact")
    country = django_filters.CharFilter(
        field_name="location__country", lookup_expr="iexact"
    )
    is_verified = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()
    is_featured = django_filters.BooleanFilter()
    min_rating = django_filters.NumberFilter(method="filter_min_rating")
    has_service_category = django_filters.UUIDFilter(
        method="filter_has_service_category"
    )
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = Shop
        fields = [
            "name",
            "company",
            "city",
            "country",
            "is_verified",
            "is_active",
            "is_featured",
            "min_rating",
            "has_service_category",
            "created_after",
            "created_before",
        ]

    def filter_min_rating(self, queryset, name, value):
        """Filter shops by minimum average rating"""
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Avg, OuterRef, Subquery

        from apps.reviewapp.models import Review

        # Get content type for shop
        shop_type = ContentType.objects.get_for_model(Shop)

        # Get average rating for each shop
        rating_subquery = (
            Review.objects.filter(content_type=shop_type, object_id=OuterRef("id"))
            .values("object_id")
            .annotate(avg_rating=Avg("rating"))
            .values("avg_rating")
        )

        # Filter shops by average rating
        return queryset.annotate(avg_rating=Subquery(rating_subquery)).filter(
            avg_rating__gte=value
        )

    def filter_has_service_category(self, queryset, name, value):
        """Filter shops that offer services in the specified category"""
        return queryset.filter(services__category__id=value).distinct()


class ShopHoursFilter(django_filters.FilterSet):
    """Filter for shop hours"""

    shop = django_filters.UUIDFilter()
    weekday = django_filters.NumberFilter()
    is_closed = django_filters.BooleanFilter()

    class Meta:
        model = ShopHours
        fields = ["shop", "weekday", "is_closed"]


class ShopFollowerFilter(django_filters.FilterSet):
    """Filter for shop followers"""

    shop = django_filters.UUIDFilter()
    customer = django_filters.UUIDFilter()
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = ShopFollower
        fields = ["shop", "customer", "created_after", "created_before"]


class ShopVerificationFilter(django_filters.FilterSet):
    """Filter for shop verifications"""

    shop = django_filters.UUIDFilter()
    status = django_filters.ChoiceFilter(choices=ShopVerification.STATUS_CHOICES)
    submitted_after = django_filters.DateTimeFilter(
        field_name="submitted_at", lookup_expr="gte"
    )
    submitted_before = django_filters.DateTimeFilter(
        field_name="submitted_at", lookup_expr="lte"
    )
    processed_by = django_filters.UUIDFilter()

    class Meta:
        model = ShopVerification
        fields = [
            "shop",
            "status",
            "submitted_after",
            "submitted_before",
            "processed_by",
        ]
