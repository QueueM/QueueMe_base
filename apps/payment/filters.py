from django_filters import rest_framework as filters

from .models import Refund, Transaction


class TransactionFilter(filters.FilterSet):
    """Filter for transactions"""

    user = filters.UUIDFilter(field_name="user__id")
    min_amount = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount = filters.NumberFilter(field_name="amount", lookup_expr="lte")
    status = filters.CharFilter(field_name="status")
    transaction_type = filters.CharFilter(field_name="transaction_type")
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Transaction
        fields = [
            "user",
            "status",
            "transaction_type",
            "min_amount",
            "max_amount",
            "created_after",
            "created_before",
        ]


class RefundFilter(filters.FilterSet):
    """Filter for refunds"""

    transaction = filters.UUIDFilter(field_name="transaction__id")
    min_amount = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount = filters.NumberFilter(field_name="amount", lookup_expr="lte")
    status = filters.CharFilter(field_name="status")
    refunded_by = filters.UUIDFilter(field_name="refunded_by__id")
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Refund
        fields = [
            "transaction",
            "status",
            "refunded_by",
            "min_amount",
            "max_amount",
            "created_after",
            "created_before",
        ]
