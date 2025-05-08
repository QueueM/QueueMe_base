# apps/discountapp/validators.py
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .constants import (
    MAX_COUPON_CODE_LENGTH,
    MAX_DISCOUNT_PERCENT,
    MIN_COUPON_CODE_LENGTH,
    MIN_DISCOUNT_PERCENT,
)


def validate_coupon_code(code):
    """
    Validates that a coupon code:
    1. Is of appropriate length
    2. Contains only alphanumeric characters and optional dashes
    3. Is uppercase
    """
    if len(code) < MIN_COUPON_CODE_LENGTH or len(code) > MAX_COUPON_CODE_LENGTH:
        raise ValidationError(
            _("Coupon code must be between %(min)s and %(max)s characters long."),
            params={"min": MIN_COUPON_CODE_LENGTH, "max": MAX_COUPON_CODE_LENGTH},
        )

    if not re.match(r"^[A-Z0-9\-]+$", code):
        raise ValidationError(
            _("Coupon code can only contain uppercase letters, numbers, and dashes.")
        )

    # Check if the code is all uppercase (if it contains letters)
    if any(c.isalpha() for c in code) and not code.isupper():
        raise ValidationError(_("Coupon code must be in uppercase."))

    return code


def validate_percentage_discount(value):
    """
    Validates that a percentage discount is between 0 and 100
    """
    if value < MIN_DISCOUNT_PERCENT or value > MAX_DISCOUNT_PERCENT:
        raise ValidationError(
            _("Percentage discount must be between %(min)s and %(max)s."),
            params={"min": MIN_DISCOUNT_PERCENT, "max": MAX_DISCOUNT_PERCENT},
        )

    return value


def validate_fixed_discount(value):
    """
    Validates that a fixed discount is not negative
    """
    if value < 0:
        raise ValidationError(_("Fixed discount amount cannot be negative."))

    return value


def validate_min_purchase_amount(value):
    """
    Validates that minimum purchase amount is not negative
    """
    if value < 0:
        raise ValidationError(_("Minimum purchase amount cannot be negative."))

    return value


def validate_date_range(start_date, end_date):
    """
    Validates that end date is after start date
    """
    if start_date >= end_date:
        raise ValidationError(_("End date must be after start date."))

    return True
