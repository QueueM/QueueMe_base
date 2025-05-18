import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_card_number(value):
    """
    Validate a credit card number
    """
    # Remove spaces and dashes
    card_number = re.sub(r"[\s-]", "", value)

    # Basic validation
    if not card_number.isdigit():
        raise ValidationError(_("Card number must contain only digits"))

    if len(card_number) < 13 or len(card_number) > 19:
        raise ValidationError(_("Card number must be between 13 and 19 digits"))

    # Luhn algorithm check
    digits = [int(d) for d in card_number]
    checksum = 0

    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit

    if checksum % 10 != 0:
        raise ValidationError(_("Invalid card number (fails Luhn check)"))


def validate_card_expiry(month, year):
    """
    Validate card expiry date
    """
    from datetime import datetime

    try:
        month = int(month)
        year = int(year)

        if month < 1 or month > 12:
            raise ValidationError(_("Expiry month must be between 1 and 12"))

        # Check if card is expired
        current_year = datetime.now().year
        current_month = datetime.now().month

        if year < current_year or (year == current_year and month < current_month):
            raise ValidationError(_("Card has expired"))

    except (ValueError, TypeError):
        raise ValidationError(_("Invalid expiry date format"))


def validate_cvv(value):
    """
    Validate CVV/CVC code
    """
    # Remove spaces
    cvv = value.strip()

    # Basic validation
    if not cvv.isdigit():
        raise ValidationError(_("CVV must contain only digits"))

    if len(cvv) < 3 or len(cvv) > 4:
        raise ValidationError(_("CVV must be 3 or 4 digits"))
