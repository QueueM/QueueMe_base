import logging

from django.conf import settings
from django.db import transaction

from apps.customersapp.models import SavedPaymentMethod

logger = logging.getLogger(__name__)


class PaymentMethodService:
    """
    Service for managing customer payment methods
    """

    MOYASAR_API_URL = "https://api.moyasar.com/v1"

    @staticmethod
    def validate_payment_token(token, payment_type):
        """
        Validate a payment token with Moyasar
        """
        if not settings.MOYASAR_API_KEY:
            raise ValueError("Moyasar API key not configured")

        # This is just a validation step, not an actual payment
        # In a real implementation, you would validate the token with Moyasar

        # For cards, validate token format
        if payment_type == "card" and not token.startswith("tok_"):
            raise ValueError("Invalid card token format")

        # For STC Pay, validate token format
        if payment_type == "stcpay" and not token.startswith("stc_"):
            raise ValueError("Invalid STC Pay token format")

        return True

    @staticmethod
    @transaction.atomic
    def create_payment_method(
        customer,
        payment_type,
        token,
        last_digits=None,
        expiry_month=None,
        expiry_year=None,
        card_brand=None,
        is_default=False,
    ):
        """
        Create a new payment method for a customer
        """
        # Validate token with Moyasar
        try:
            PaymentMethodService.validate_payment_token(token, payment_type)
        except ValueError as e:
            logger.error(f"Payment token validation failed: {e}")
            raise

        # Check limits (e.g., max 5 cards per customer)
        payment_method_count = SavedPaymentMethod.objects.filter(
            customer=customer, payment_type=payment_type
        ).count()

        if payment_type == "card" and payment_method_count >= 5:
            raise ValueError("Maximum number of saved cards reached (5)")

        # Create payment method
        payment_method = SavedPaymentMethod.objects.create(
            customer=customer,
            payment_type=payment_type,
            token=token,
            last_digits=last_digits,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            card_brand=card_brand,
            is_default=is_default,
        )

        return payment_method

    @staticmethod
    def set_as_default(payment_method):
        """
        Set a payment method as the default
        """
        # Unset current default
        SavedPaymentMethod.objects.filter(
            customer=payment_method.customer, is_default=True
        ).update(is_default=False)

        # Set new default
        payment_method.is_default = True
        payment_method.save()

        return payment_method

    @staticmethod
    def get_default_payment_method(customer):
        """
        Get the customer's default payment method
        """
        return SavedPaymentMethod.objects.filter(
            customer=customer, is_default=True
        ).first()

    @staticmethod
    def recommend_payment_method(customer, amount=None):
        """
        Recommend the best payment method for the customer based on:
        1. Default method
        2. Recently used method
        3. Method appropriate for the amount
        """
        # First check for default method
        default_method = PaymentMethodService.get_default_payment_method(customer)
        if default_method:
            return default_method

        # If no default, get most recently added
        latest_method = (
            SavedPaymentMethod.objects.filter(customer=customer)
            .order_by("-created_at")
            .first()
        )

        if latest_method:
            return latest_method

        # If no methods at all, return None
        return None

    @staticmethod
    @transaction.atomic
    def remove_payment_method(payment_method_id, customer):
        """
        Remove a payment method
        """
        try:
            payment_method = SavedPaymentMethod.objects.get(
                id=payment_method_id, customer=customer
            )

            was_default = payment_method.is_default
            payment_method.delete()

            # If deleted method was default, set another as default
            if was_default:
                # Get another payment method if available
                another_method = SavedPaymentMethod.objects.filter(
                    customer=customer
                ).first()

                if another_method:
                    another_method.is_default = True
                    another_method.save()

            return True
        except SavedPaymentMethod.DoesNotExist:
            return False
