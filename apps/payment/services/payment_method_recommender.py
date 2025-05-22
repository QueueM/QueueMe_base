import logging
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from ..constants import (
    DEFAULT_PAYMENT_METHOD_BONUS,
    GENERIC_METHOD_SCORE,
    RECENTLY_ADDED_BONUS,
    SUCCESS_RATE_WEIGHT,
    USAGE_WEIGHT,
)
from ..models import PaymentMethod, Transaction

logger = logging.getLogger(__name__)


class PaymentMethodRecommender:
    """
    Sophisticated algorithm for recommending optimal payment methods to users
    """

    @staticmethod
    def recommend_payment_method(customer, amount, transaction_type=None):
        """
        Recommend the best payment method for a customer

        Args:
            customer: User object
            amount: Transaction amount
            transaction_type: Optional transaction type

        Returns:
            list: Ranked payment methods with scores
        """
        # Get customer's saved payment methods
        saved_methods = PaymentMethod.objects.filter(user=customer)

        # Get usage history (last 90 days)
        start_date = timezone.now() - timedelta(days=90)
        usage_history = (
            Transaction.objects.filter(
                user=customer,
                created_at__gte=start_date,
                status__in=["succeeded", "refunded", "partially_refunded"],
            )
            .values("payment_method")
            .annotate(
                usage_count=Count("id"),
                success_rate=Count(
                    "id",
                    filter=Q(
                        status__in=["succeeded", "refunded", "partially_refunded"]
                    ),
                )
                * 100.0
                / Count("id"),
            )
        )

        # Transform to dictionary for easier lookup
        usage_dict = {}
        for item in usage_history:
            if item["payment_method"]:
                usage_dict[item["payment_method"]] = {
                    "usage_count": item["usage_count"],
                    "success_rate": item["success_rate"],
                }

        # Calculate scores for each method
        scored_methods = []

        for method in saved_methods:
            score = 0

            # Default method bonus (highest priority)
            if method.is_default:
                score += DEFAULT_PAYMENT_METHOD_BONUS

            # Usage frequency factor (more usage = higher score)
            usage_data = usage_dict.get(method.id, {})
            usage_count = usage_data.get("usage_count", 0)
            normalized_usage = min(usage_count / 10.0, 1.0)  # Cap at 1.0 for 10+ usages
            score += normalized_usage * USAGE_WEIGHT

            # Success rate factor
            success_rate = usage_data.get(
                "success_rate", 100.0 if usage_count == 0 else 0.0
            )
            normalized_success = success_rate / 100.0
            score += normalized_success * SUCCESS_RATE_WEIGHT

            # Amount appropriate factor
            amount_score = PaymentMethodRecommender._get_amount_appropriate_score(
                method.type, amount
            )
            score += amount_score

            # Recently added bonus (within last 7 days)
            if method.created_at >= (timezone.now() - timedelta(days=7)):
                score += RECENTLY_ADDED_BONUS

            # Add to scored methods
            scored_methods.append(
                {
                    "method": method,
                    "score": score,
                    "usage_count": usage_count,
                    "success_rate": success_rate,
                }
            )

        # Sort by score (descending)
        scored_methods.sort(key=lambda x: x["score"], reverse=True)

        # Add generic methods if no saved methods or as alternatives
        if not saved_methods or len(scored_methods) < 2:
            generic_methods = PaymentMethodRecommender._get_generic_payment_methods()

            # Filter out methods that are already saved
            saved_types = [m.type for m in saved_methods]
            generic_methods = [
                m for m in generic_methods if m["type"] not in saved_types
            ]

            # Add generic methods with lower scores
            for method in generic_methods:
                scored_methods.append(
                    {
                        "method": method,
                        "score": GENERIC_METHOD_SCORE,
                        "usage_count": 0,
                        "success_rate": 0,
                    }
                )

        return scored_methods

    @staticmethod
    def _get_amount_appropriate_score(payment_type, amount):
        """
        Calculate score based on payment type suitability for amount

        Args:
            payment_type: Type of payment method
            amount: Transaction amount

        Returns:
            float: Score modifier
        """
        # Different payment methods might be more appropriate for different amounts
        if payment_type == "card" and amount > 1000:
            return 0.5  # Good for large amounts
        elif payment_type == "stcpay" and amount < 200:
            return 0.3  # Good for small amounts
        elif payment_type == "apple_pay" and amount < 500:
            return 0.4  # Good for medium amounts
        elif payment_type == "mada":
            return 0.2  # Always decent option in Saudi

        return 0.1  # Default score

    @staticmethod
    def _get_generic_payment_methods():
        """
        Get list of generic payment methods (not saved but available)

        Returns:
            list: Generic payment method info
        """
        return [
            {"type": "card", "name": "Credit Card"},
            {"type": "mada", "name": "Mada"},
            {"type": "stcpay", "name": "STC Pay"},
            {"type": "apple_pay", "name": "Apple Pay"},
        ]
