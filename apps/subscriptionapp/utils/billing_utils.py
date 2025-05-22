# apps/subscriptionapp/utils/billing_utils.py
from decimal import Decimal

from django.utils.translation import gettext_lazy as _

from apps.subscriptionapp.constants import PERIOD_DISCOUNT


def calculate_period_price(monthly_price, period):
    """Calculate price for a specific subscription period with discount"""
    monthly_price = Decimal(monthly_price)

    if period == "monthly":
        return monthly_price

    # Get number of months in period
    months = {"monthly": 1, "quarterly": 3, "semi_annual": 6, "annual": 12}.get(
        period, 1
    )

    # Get discount percentage for period
    discount_percent = PERIOD_DISCOUNT.get(period, 0)

    # Calculate total price with discount
    total_price = monthly_price * months
    discount_amount = total_price * (Decimal(discount_percent) / 100)

    final_price = total_price - discount_amount

    # Round to 2 decimal places
    return round(final_price, 2)


def format_price(price, currency="SAR"):
    """Format price with currency"""
    price = Decimal(price)

    if currency == "SAR":
        return f"{price:.2f} {_('SAR')}"

    return f"{price:.2f} {currency}"


def calculate_prorated_amount(original_amount, days_used, total_days):
    """Calculate prorated amount based on days used"""
    if total_days <= 0:
        return Decimal("0.00")

    original_amount = Decimal(original_amount)
    days_used = Decimal(days_used)
    total_days = Decimal(total_days)

    # Calculate prorated amount
    prorated_amount = original_amount * (days_used / total_days)

    # Round to 2 decimal places
    return round(prorated_amount, 2)


def calculate_plan_change_amount(
    old_plan_price, new_plan_price, days_remaining, total_days
):
    """Calculate amount to charge or refund when changing plans"""
    old_plan_price = Decimal(old_plan_price)
    new_plan_price = Decimal(new_plan_price)
    days_remaining = Decimal(days_remaining)
    total_days = Decimal(total_days)

    # Calculate prorated amount for remaining days on old plan
    old_plan_remaining = old_plan_price * (days_remaining / total_days)

    # Calculate prorated amount for remaining days on new plan
    new_plan_remaining = new_plan_price * (days_remaining / total_days)

    # Calculate difference (positive = charge, negative = refund)
    difference = new_plan_remaining - old_plan_remaining

    # Round to 2 decimal places
    return round(difference, 2)
