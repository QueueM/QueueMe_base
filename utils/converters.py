"""
Data type conversion utilities for Queue Me platform.

This module provides functions for converting between different data types,
especially for handling user input and preparing data for database storage
or API responses.
"""

import datetime
import decimal
import uuid
from typing import Any, Optional, Union

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime, parse_time


def to_boolean(value: Any) -> bool:
    """
    Convert various input types to boolean.

    Args:
        value: Input value (string, int, bool, etc.)

    Returns:
        Boolean representation of the value
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        value = value.lower().strip()
        if value in ("true", "t", "yes", "y", "1", "on"):
            return True
        if value in ("false", "f", "no", "n", "0", "off"):
            return False

    return bool(value)


def to_decimal(value: Any, decimal_places: int = 2) -> Optional[decimal.Decimal]:
    """
    Convert a value to Decimal with specified precision.

    Args:
        value: Input value
        decimal_places: Number of decimal places

    Returns:
        Decimal or None if conversion fails
    """
    if value is None:
        return None

    try:
        if isinstance(value, str):
            # Remove non-numeric chars except decimal separator
            value = "".join(c for c in value if c.isdigit() or c in ".-")

        dec = decimal.Decimal(str(value))
        return dec.quantize(decimal.Decimal(10) ** -decimal_places)
    except (decimal.InvalidOperation, ValueError, TypeError):
        return None


def to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """
    Convert a value to integer.

    Args:
        value: Input value
        default: Default value if conversion fails

    Returns:
        Integer or default if conversion fails
    """
    if value is None:
        return default

    try:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return default

            # Handle comma-separated numbers
            value = value.replace(",", "")

        return int(float(value))
    except (ValueError, TypeError):
        return default


def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Convert a value to float.

    Args:
        value: Input value
        default: Default value if conversion fails

    Returns:
        Float or default if conversion fails
    """
    if value is None:
        return default

    try:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return default

            # Handle comma-separated numbers
            value = value.replace(",", "")

        return float(value)
    except (ValueError, TypeError):
        return default


def to_date(value: Any) -> Optional[datetime.date]:
    """
    Convert a value to date.

    Args:
        value: Input value (string, date object, etc.)

    Returns:
        Date object or None if conversion fails
    """
    if value is None:
        return None

    if isinstance(value, datetime.date):
        return value

    if isinstance(value, datetime.datetime):
        return value.date()

    if isinstance(value, str):
        try:
            # Try Django's date parser
            parsed = parse_date(value)
            if parsed:
                return parsed

            # Try datetime parser and convert to date
            parsed = parse_datetime(value)
            if parsed:
                return parsed.date()
        except ValueError:
            pass

    return None


def to_datetime(
    value: Any, default_timezone: bool = True
) -> Optional[datetime.datetime]:
    """
    Convert a value to datetime.

    Args:
        value: Input value (string, datetime object, etc.)
        default_timezone: Whether to add timezone if missing

    Returns:
        Datetime object or None if conversion fails
    """
    if value is None:
        return None

    if isinstance(value, datetime.datetime):
        # Ensure timezone awareness
        if default_timezone and value.tzinfo is None:
            return timezone.make_aware(value)
        return value

    if isinstance(value, datetime.date):
        # Convert date to datetime with midnight time
        dt = datetime.datetime.combine(value, datetime.time.min)
        if default_timezone:
            return timezone.make_aware(dt)
        return dt

    if isinstance(value, str):
        try:
            # Try Django's datetime parser
            parsed = parse_datetime(value)
            if parsed:
                # Ensure timezone awareness
                if default_timezone and parsed.tzinfo is None:
                    return timezone.make_aware(parsed)
                return parsed

            # Try date parser and convert to datetime
            parsed = parse_date(value)
            if parsed:
                dt = datetime.datetime.combine(parsed, datetime.time.min)
                if default_timezone:
                    return timezone.make_aware(dt)
                return dt
        except ValueError:
            pass

    return None


def to_time(value: Any) -> Optional[datetime.time]:
    """
    Convert a value to time.

    Args:
        value: Input value (string, time object, etc.)

    Returns:
        Time object or None if conversion fails
    """
    if value is None:
        return None

    if isinstance(value, datetime.time):
        return value

    if isinstance(value, datetime.datetime):
        return value.time()

    if isinstance(value, str):
        try:
            # Try Django's time parser
            parsed = parse_time(value)
            if parsed:
                return parsed
        except ValueError:
            pass

    return None


def to_halala(amount: Union[int, float, decimal.Decimal, str]) -> int:
    """
    Convert SAR amount to halala (1 SAR = 100 halala).

    Args:
        amount: Amount in SAR

    Returns:
        Amount in halala (integer)
    """
    if amount is None:
        return 0

    decimal_amount = to_decimal(amount)
    if decimal_amount is None:
        return 0

    # Convert to halala (multiply by 100)
    return int(decimal_amount * 100)


def from_halala(amount: int) -> decimal.Decimal:
    """
    Convert halala amount to SAR (100 halala = 1 SAR).

    Args:
        amount: Amount in halala

    Returns:
        Amount in SAR (Decimal)
    """
    if amount is None:
        return decimal.Decimal("0.00")

    # Convert to SAR (divide by 100)
    return decimal.Decimal(amount) / 100


def serialize_uuid(uuid_obj: Optional[uuid.UUID]) -> Optional[str]:
    """
    Convert UUID to string.

    Args:
        uuid_obj: UUID object

    Returns:
        String representation or None
    """
    if uuid_obj is None:
        return None

    return str(uuid_obj)


def deserialize_uuid(uuid_str: Optional[str]) -> Optional[uuid.UUID]:
    """
    Convert string to UUID.

    Args:
        uuid_str: UUID string

    Returns:
        UUID object or None
    """
    if not uuid_str:
        return None

    try:
        return uuid.UUID(uuid_str)
    except (ValueError, AttributeError, TypeError):
        return None


def format_phone_number(phone: str, country_code: str = "SA") -> str:
    """
    Format a phone number according to country standards.

    Args:
        phone: Phone number
        country_code: ISO country code

    Returns:
        Formatted phone number
    """
    if not phone:
        return ""

    # Strip non-digit characters
    digits = "".join(c for c in phone if c.isdigit())

    if country_code == "SA":  # Saudi Arabia
        # Ensure starts with country code
        if len(digits) == 9 and digits.startswith("5"):
            # Add Saudi country code
            return f"+966{digits}"
        elif len(digits) == 10 and digits.startswith("05"):
            # Replace leading 0 with country code
            return f"+966{digits[1:]}"
        elif len(digits) >= 11 and (
            digits.startswith("966") or digits.startswith("00966")
        ):
            # Normalize existing country code
            return f"+966{digits[-9:]}"

    # Default: return with + if missing
    if not digits.startswith("+"):
        return f"+{digits}"
    return digits
