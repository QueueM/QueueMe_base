"""
Data validation utilities for Queue Me platform.

This module provides validation functions for various types of data,
including phone numbers, emails, coordinates, amounts, etc.
"""

import os
import re
from datetime import date
from decimal import Decimal
from typing import List, Optional, Union

from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email
from django.utils.translation import gettext_lazy as _

from .constants import (
    ALLOWED_AUDIO_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    MAX_FILE_SIZE_MB,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PHONE_FORMATS,
)


def validate_phone_number(value: str) -> bool:
    """
    Validate a phone number against Saudi Arabia format.

    Args:
        value: Phone number to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If phone number is invalid
    """
    if not value:
        raise ValidationError(_("Phone number is required"))

    # Remove non-digit characters for comparison
    digits_only = "".join(c for c in value if c.isdigit())

    # Check Saudi Arabia phone format (9665xxxxxxxx)
    saudi_pattern = PHONE_FORMATS.get("SA")
    if saudi_pattern and not re.match(saudi_pattern, digits_only):
        if digits_only.startswith("5") and len(digits_only) == 9:
            # Looks like a Saudi number without country code, let it pass
            return True
        elif digits_only.startswith("05") and len(digits_only) == 10:
            # Looks like a Saudi number with leading 0, let it pass
            return True
        else:
            raise ValidationError(_("Invalid Saudi Arabia phone number format"))

    return True


def validate_email(value: str) -> bool:
    """
    Validate an email address.

    Args:
        value: Email to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If email is invalid
    """
    if not value:
        raise ValidationError(_("Email is required"))

    try:
        django_validate_email(value)
        return True
    except ValidationError:
        raise ValidationError(_("Invalid email format"))


def validate_password(
    value: str,
    min_length: int = PASSWORD_MIN_LENGTH,
    max_length: int = PASSWORD_MAX_LENGTH,
) -> bool:
    """
    Validate a password for strength requirements.

    Args:
        value: Password to validate
        min_length: Minimum password length
        max_length: Maximum password length

    Returns:
        True if valid

    Raises:
        ValidationError: If password is invalid
    """
    if not value:
        raise ValidationError(_("Password is required"))

    if len(value) < min_length:
        raise ValidationError(
            _("Password must be at least {0} characters").format(min_length)
        )

    if len(value) > max_length:
        raise ValidationError(
            _("Password cannot exceed {0} characters").format(max_length)
        )

    # Check for at least one digit
    if not any(c.isdigit() for c in value):
        raise ValidationError(_("Password must contain at least one digit"))

    # Check for at least one letter
    if not any(c.isalpha() for c in value):
        raise ValidationError(_("Password must contain at least one letter"))

    return True


def validate_coordinate(value: float, is_latitude: bool = True) -> bool:
    """
    Validate a geographic coordinate.

    Args:
        value: Coordinate value
        is_latitude: Whether the coordinate is a latitude

    Returns:
        True if valid

    Raises:
        ValidationError: If coordinate is invalid
    """
    if value is None:
        raise ValidationError(_("Coordinate value is required"))

    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValidationError(_("Coordinate must be a number"))

    if is_latitude and (value < -90 or value > 90):
        raise ValidationError(_("Latitude must be between -90 and 90"))

    if not is_latitude and (value < -180 or value > 180):
        raise ValidationError(_("Longitude must be between -180 and 180"))

    return True


def validate_location(lat: float, lng: float) -> bool:
    """
    Validate a geographic location (latitude and longitude).

    Args:
        lat: Latitude
        lng: Longitude

    Returns:
        True if valid

    Raises:
        ValidationError: If location is invalid
    """
    validate_coordinate(lat, is_latitude=True)
    validate_coordinate(lng, is_latitude=False)
    return True


def validate_amount(
    value: Union[int, float, Decimal, str],
    min_value: float = 0,
    max_value: Optional[float] = None,
    currency: str = "SAR",
) -> bool:
    """
    Validate a currency amount.

    Args:
        value: Amount to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value (optional)
        currency: Currency code

    Returns:
        True if valid

    Raises:
        ValidationError: If amount is invalid
    """
    if value is None:
        raise ValidationError(_("Amount is required"))

    try:
        if isinstance(value, str):
            # Remove currency symbols and thousands separators
            cleaned_value = "".join(c for c in value if c.isdigit() or c in ".-")
            value = Decimal(cleaned_value)
        else:
            value = Decimal(str(value))
    except (ValueError, TypeError, Decimal.InvalidOperation):
        raise ValidationError(_("Invalid amount format"))

    if value < min_value:
        raise ValidationError(
            _("Amount must be at least {0} {1}").format(min_value, currency)
        )

    if max_value is not None and value > max_value:
        raise ValidationError(
            _("Amount cannot exceed {0} {1}").format(max_value, currency)
        )

    return True


def validate_date_range(start_date: date, end_date: date) -> bool:
    """
    Validate a date range.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        True if valid

    Raises:
        ValidationError: If date range is invalid
    """
    if not start_date:
        raise ValidationError(_("Start date is required"))

    if not end_date:
        raise ValidationError(_("End date is required"))

    if start_date > end_date:
        raise ValidationError(_("End date must be after start date"))

    return True


def validate_time_format(value: str) -> bool:
    """
    Validate a time string in HH:MM format.

    Args:
        value: Time string

    Returns:
        True if valid

    Raises:
        ValidationError: If time format is invalid
    """
    if not value:
        raise ValidationError(_("Time is required"))

    time_pattern = r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$"
    if not re.match(time_pattern, value):
        raise ValidationError(_("Time must be in HH:MM format"))

    return True


def validate_file_extension(
    file_path: str, allowed_extensions: Optional[List[str]] = None
) -> bool:
    """
    Validate a file extension against a list of allowed extensions.

    Args:
        file_path: File path or name
        allowed_extensions: List of allowed extensions

    Returns:
        True if valid

    Raises:
        ValidationError: If file extension is invalid
    """
    if not file_path:
        raise ValidationError(_("File path is required"))

    # If no extensions specified, use defaults based on file type
    if allowed_extensions is None:
        allowed_extensions = (
            ALLOWED_IMAGE_EXTENSIONS
            + ALLOWED_VIDEO_EXTENSIONS
            + ALLOWED_AUDIO_EXTENSIONS
        )

    # Normalize extensions to lowercase with leading dot
    allowed_extensions = [
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in allowed_extensions
    ]

    # Get file extension
    file_ext = os.path.splitext(file_path)[1].lower()

    if file_ext not in allowed_extensions:
        raise ValidationError(
            _(
                "File extension '{0}' is not allowed. Allowed extensions are: {1}"
            ).format(file_ext, ", ".join(allowed_extensions))
        )

    return True


def validate_file_size(file_obj, max_size_mb: int = MAX_FILE_SIZE_MB) -> bool:
    """
    Validate a file size against a maximum size.

    Args:
        file_obj: File object
        max_size_mb: Maximum size in megabytes

    Returns:
        True if valid

    Raises:
        ValidationError: If file size is too large
    """
    if not hasattr(file_obj, "size"):
        raise ValidationError(_("Invalid file object"))

    max_size_bytes = max_size_mb * 1024 * 1024

    if file_obj.size > max_size_bytes:
        raise ValidationError(
            _("File size exceeds maximum of {0} MB").format(max_size_mb)
        )

    return True


def validate_image_file(file_obj, max_size_mb: int = MAX_FILE_SIZE_MB) -> bool:
    """
    Validate an image file (extension and size).

    Args:
        file_obj: File object
        max_size_mb: Maximum size in megabytes

    Returns:
        True if valid

    Raises:
        ValidationError: If file is invalid
    """
    if not file_obj:
        raise ValidationError(_("Image file is required"))

    validate_file_extension(file_obj.name, ALLOWED_IMAGE_EXTENSIONS)
    validate_file_size(file_obj, max_size_mb)

    return True


def validate_video_file(file_obj, max_size_mb: int = MAX_FILE_SIZE_MB) -> bool:
    """
    Validate a video file (extension and size).

    Args:
        file_obj: File object
        max_size_mb: Maximum size in megabytes

    Returns:
        True if valid

    Raises:
        ValidationError: If file is invalid
    """
    if not file_obj:
        raise ValidationError(_("Video file is required"))

    validate_file_extension(file_obj.name, ALLOWED_VIDEO_EXTENSIONS)
    validate_file_size(file_obj, max_size_mb)

    return True


# ---------------------------------------------------------------------------
# Back-compat wrappers expected by older model code
# ---------------------------------------------------------------------------


def validate_image_size(file_obj, max_size_mb: int = MAX_FILE_SIZE_MB) -> bool:
    """
    Backward-compatibility wrapper so models that import `validate_image_size`
    keep working.  Internally delegates to `validate_image_file`.
    """
    return validate_image_file(file_obj, max_size_mb=max_size_mb)


def validate_video_size(file_obj, max_size_mb: int = MAX_FILE_SIZE_MB) -> bool:
    """
    Backward-compatibility wrapper so models that import `validate_video_size`
    keep working.  Internally delegates to `validate_video_file`.
    """
    return validate_video_file(file_obj, max_size_mb=max_size_mb)


def validate_uuid(value: str) -> bool:
    """
    Validate a UUID string.

    Args:
        value: UUID string

    Returns:
        True if valid

    Raises:
        ValidationError: If UUID is invalid
    """
    if not value:
        raise ValidationError(_("UUID is required"))

    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    if not re.match(uuid_pattern, str(value).lower()):
        raise ValidationError(_("Invalid UUID format"))

    return True
