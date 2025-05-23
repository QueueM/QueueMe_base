import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_phone_number(value):
    """
    Validate Saudi Arabian phone numbers.
    Valid formats: +966XXXXXXXXX, 966XXXXXXXXX, 05XXXXXXXX, 5XXXXXXXX
    """
    # Remove spaces and dashes
    phone = re.sub(r"[\s-]", "", value)
    # Check for valid Saudi format
    saudi_pattern = r"^(?:\+966|966|05|5)\d{8,9}$"
    if not re.match(saudi_pattern, phone):
        raise ValidationError(
            _(
                "Enter a valid Saudi Arabian phone number. Examples: +966501234567, 966501234567, 0501234567, 501234567"
            ),
            code="invalid_phone",
        )
    # Normalize the phone number to international format
    if phone.startswith("05"):
        phone = "966" + phone[1:]
    elif phone.startswith("5"):
        phone = "966" + phone
    elif phone.startswith("+966"):
        phone = phone[1:]
    return phone


def normalize_phone_number(phone_number):
    """
    Convert phone number to standard 966XXXXXXXXX format
    """
    if not phone_number:
        return phone_number
    # Remove spaces, dashes, and parentheses
    phone = re.sub(r"[\s\-\(\)]", "", phone_number)
    # Handle different formats
    if phone.startswith("05"):
        phone = "966" + phone[1:]
    elif phone.startswith("5"):
        phone = "966" + phone
    elif phone.startswith("+966"):
        phone = phone[1:]
    return phone


def validate_saudi_phone_number(phone_number: str) -> bool:
    """
    Validate Saudi phone number format.

    Args:
        phone_number: Normalized phone number string

    Returns:
        True if valid Saudi phone number, False otherwise
    """
    if not phone_number:
        return False

    # Check if it's already normalized (starts with +966)
    if phone_number.startswith("+966"):
        number_part = phone_number[4:]  # Remove +966
        return len(number_part) == 9 and number_part.isdigit()

    # Check if it's in 966XXXXXXXXX format
    if phone_number.startswith("966"):
        number_part = phone_number[3:]  # Remove 966
        return len(number_part) == 9 and number_part.isdigit()

    # For other formats, try to validate using the existing pattern
    saudi_pattern = r"^(?:\+966|966|05|5)\d{8,9}$"
    phone = re.sub(r"[\s-]", "", phone_number)
    return bool(re.match(saudi_pattern, phone))
