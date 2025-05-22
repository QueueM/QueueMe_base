import django_filters
from django.utils.translation import gettext_lazy as _

from apps.subscriptionapp.models import (
    Feature,
    Plan,
    PlanCoupon,
    Subscription,
    SubscriptionEvent,
    SubscriptionInvoice,
)


class FeatureFilter(django_filters.FilterSet):
    """Filter for features"""

    is_active = django_filters.BooleanFilter(label=_("Active"))
    is_numeric = django_filters.BooleanFilter(label=_("Numeric"))
    name = django_filters.CharFilter(lookup_expr="icontains", label=_("Name"))
    key = django_filters.CharFilter(lookup_expr="icontains", label=_("Key"))

    class Meta:
        model = Feature
        fields = ["is_active", "is_numeric", "name", "key"]


class PlanFilter(django_filters.FilterSet):
    """Filter for plans"""

    is_active = django_filters.BooleanFilter(label=_("Active"))
    is_public = django_filters.BooleanFilter(label=_("Public"))
    is_popular = django_filters.BooleanFilter(label=_("Popular"))
    billing_cycle = django_filters.ChoiceFilter(
        choices=Plan.BILLING_CYCLE_CHOICES, label=_("Billing Cycle")
    )
    price_min = django_filters.NumberFilter(
        field_name="price", lookup_expr="gte", label=_("Min Price")
    )
    price_max = django_filters.NumberFilter(
        field_name="price", lookup_expr="lte", label=_("Max Price")
    )
    name = django_filters.CharFilter(lookup_expr="icontains", label=_("Name"))
    feature = django_filters.UUIDFilter(
        field_name="plan_features__feature", label=_("Has Feature")
    )

    class Meta:
        model = Plan
        fields = ["is_active", "is_public", "is_popular", "billing_cycle", "name"]


class SubscriptionFilter(django_filters.FilterSet):
    """Filter for subscriptions"""

    status = django_filters.ChoiceFilter(
        choices=Subscription.STATUS_CHOICES, label=_("Status")
    )
    company = django_filters.UUIDFilter(label=_("Company"))
    plan = django_filters.UUIDFilter(label=_("Plan"))
    is_auto_renew = django_filters.BooleanFilter(label=_("Auto Renew"))
    start_date_after = django_filters.DateFilter(
        field_name="start_date", lookup_expr="gte", label=_("Start Date After")
    )
    start_date_before = django_filters.DateFilter(
        field_name="start_date", lookup_expr="lte", label=_("Start Date Before")
    )
    end_date_after = django_filters.DateFilter(
        field_name="end_date", lookup_expr="gte", label=_("End Date After")
    )
    end_date_before = django_filters.DateFilter(
        field_name="end_date", lookup_expr="lte", label=_("End Date Before")
    )

    class Meta:
        model = Subscription
        fields = ["status", "company", "plan", "is_auto_renew"]


class SubscriptionInvoiceFilter(django_filters.FilterSet):
    """Filter for subscription invoices"""

    status = django_filters.ChoiceFilter(
        choices=SubscriptionInvoice.STATUS_CHOICES, label=_("Status")
    )
    subscription = django_filters.UUIDFilter(label=_("Subscription"))
    company = django_filters.UUIDFilter(
        field_name="subscription__company", label=_("Company")
    )
    issue_date_after = django_filters.DateFilter(
        field_name="issue_date", lookup_expr="gte", label=_("Issue Date After")
    )
    issue_date_before = django_filters.DateFilter(
        field_name="issue_date", lookup_expr="lte", label=_("Issue Date Before")
    )
    due_date_after = django_filters.DateFilter(
        field_name="due_date", lookup_expr="gte", label=_("Due Date After")
    )
    due_date_before = django_filters.DateFilter(
        field_name="due_date", lookup_expr="lte", label=_("Due Date Before")
    )

    class Meta:
        model = SubscriptionInvoice
        fields = ["status", "subscription"]


class SubscriptionEventFilter(django_filters.FilterSet):
    """Filter for subscription events"""

    event_type = django_filters.ChoiceFilter(
        choices=SubscriptionEvent.EVENT_TYPE_CHOICES, label=_("Event Type")
    )
    subscription = django_filters.UUIDFilter(label=_("Subscription"))
    company = django_filters.UUIDFilter(
        field_name="subscription__company", label=_("Company")
    )
    created_at_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="gte", label=_("Created After")
    )
    created_at_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="lte", label=_("Created Before")
    )

    class Meta:
        model = SubscriptionEvent
        fields = ["event_type", "subscription"]


class PlanCouponFilter(django_filters.FilterSet):
    """Filter for plan coupons"""

    is_active = django_filters.BooleanFilter(label=_("Active"))
    type = django_filters.ChoiceFilter(choices=PlanCoupon.TYPE_CHOICES, label=_("Type"))
    expires_after = django_filters.DateFilter(
        field_name="expires_at", lookup_expr="gte", label=_("Expires After")
    )
    expires_before = django_filters.DateFilter(
        field_name="expires_at", lookup_expr="lte", label=_("Expires Before")
    )
    applicable_plan = django_filters.UUIDFilter(
        field_name="applicable_plans", label=_("Applicable Plan")
    )
    code = django_filters.CharFilter(lookup_expr="iexact", label=_("Code"))

    class Meta:
        model = PlanCoupon
        fields = ["is_active", "type", "code"]
