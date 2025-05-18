# apps/discountapp/filters.py
import django_filters
from django.db.models import F, Q
from django.utils import timezone

from apps.discountapp.models import Coupon, PromotionalCampaign, ServiceDiscount


class ServiceDiscountFilter(django_filters.FilterSet):
    shop = django_filters.UUIDFilter(field_name="shop__id")
    service = django_filters.UUIDFilter(method="filter_service")
    category = django_filters.UUIDFilter(method="filter_category")
    status = django_filters.ChoiceFilter(
        choices=ServiceDiscount.STATUS_CHOICES, method="filter_status"
    )
    discount_type = django_filters.ChoiceFilter(choices=ServiceDiscount.TYPE_CHOICES)
    valid_now = django_filters.BooleanFilter(method="filter_valid_now")
    min_value = django_filters.NumberFilter(field_name="value", lookup_expr="gte")
    max_value = django_filters.NumberFilter(field_name="value", lookup_expr="lte")
    combinable = django_filters.BooleanFilter(field_name="is_combinable")

    class Meta:
        model = ServiceDiscount
        fields = [
            "shop",
            "status",
            "discount_type",
            "valid_now",
            "min_value",
            "max_value",
            "combinable",
        ]

    def filter_service(self, queryset, name, value):
        """Filter by service"""
        return queryset.filter(Q(services__id=value) | Q(apply_to_all_services=True)).distinct()

    def filter_category(self, queryset, name, value):
        """Filter by category"""
        return queryset.filter(Q(categories__id=value) | Q(apply_to_all_services=True)).distinct()

    def filter_status(self, queryset, name, value):
        """Filter by status with auto-calculation"""
        now = timezone.now()

        if value == "active":
            return queryset.filter(
                Q(status="active")
                | (Q(status="scheduled") & Q(start_date__lte=now) & Q(end_date__gte=now))
            )
        elif value == "scheduled":
            return queryset.filter(Q(status="scheduled") & Q(start_date__gt=now))
        elif value == "expired":
            return queryset.filter(Q(status="expired") | (Q(end_date__lt=now)))
        else:
            return queryset.filter(status=value)

    def filter_valid_now(self, queryset, name, value):
        """Filter for currently valid discounts"""
        now = timezone.now()

        if value:
            return queryset.filter(
                Q(status="active")
                & Q(start_date__lte=now)
                & Q(end_date__gte=now)
                & (Q(usage_limit=0) | Q(used_count__lt=F("usage_limit")))
            )
        return queryset


class CouponFilter(django_filters.FilterSet):
    shop = django_filters.UUIDFilter(field_name="shop__id")
    service = django_filters.UUIDFilter(method="filter_service")
    category = django_filters.UUIDFilter(method="filter_category")
    status = django_filters.ChoiceFilter(choices=Coupon.STATUS_CHOICES, method="filter_status")
    discount_type = django_filters.ChoiceFilter(choices=Coupon.TYPE_CHOICES)
    valid_now = django_filters.BooleanFilter(method="filter_valid_now")
    min_value = django_filters.NumberFilter(field_name="value", lookup_expr="gte")
    max_value = django_filters.NumberFilter(field_name="value", lookup_expr="lte")
    combinable = django_filters.BooleanFilter(field_name="is_combinable")
    is_single_use = django_filters.BooleanFilter()
    is_referral = django_filters.BooleanFilter()
    code = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = Coupon
        fields = [
            "shop",
            "status",
            "discount_type",
            "valid_now",
            "min_value",
            "max_value",
            "combinable",
            "is_single_use",
            "is_referral",
            "code",
        ]

    def filter_service(self, queryset, name, value):
        """Filter by service"""
        return queryset.filter(Q(services__id=value) | Q(apply_to_all_services=True)).distinct()

    def filter_category(self, queryset, name, value):
        """Filter by category"""
        return queryset.filter(Q(categories__id=value) | Q(apply_to_all_services=True)).distinct()

    def filter_status(self, queryset, name, value):
        """Filter by status with auto-calculation"""
        now = timezone.now()

        if value == "active":
            return queryset.filter(
                Q(status="active")
                | (Q(status="scheduled") & Q(start_date__lte=now) & Q(end_date__gte=now))
            )
        elif value == "scheduled":
            return queryset.filter(Q(status="scheduled") & Q(start_date__gt=now))
        elif value == "expired":
            return queryset.filter(Q(status="expired") | (Q(end_date__lt=now)))
        else:
            return queryset.filter(status=value)

    def filter_valid_now(self, queryset, name, value):
        """Filter for currently valid coupons"""
        now = timezone.now()

        if value:
            return queryset.filter(
                Q(status="active")
                & Q(start_date__lte=now)
                & Q(end_date__gte=now)
                & (Q(usage_limit=0) | Q(used_count__lt=F("usage_limit")))
            )
        return queryset


class PromotionalCampaignFilter(django_filters.FilterSet):
    shop = django_filters.UUIDFilter(field_name="shop__id")
    campaign_type = django_filters.ChoiceFilter(choices=PromotionalCampaign.TYPE_CHOICES)
    is_active = django_filters.BooleanFilter()
    active_now = django_filters.BooleanFilter(method="filter_active_now")

    class Meta:
        model = PromotionalCampaign
        fields = ["shop", "campaign_type", "is_active", "active_now"]

    def filter_active_now(self, queryset, name, value):
        """Filter for currently active campaigns"""
        now = timezone.now()

        if value:
            return queryset.filter(is_active=True, start_date__lte=now, end_date__gte=now)
        return queryset
