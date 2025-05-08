"""
Data validation utilities for the Queue Me platform.

This module provides validation functions for various data types.
"""

import re
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


def validate_phone_number(value):
    """
    Validate a phone number.

    Args:
        value (str): Phone number to validate

    Raises:
        ValidationError: If the phone number is invalid
    """
    # Remove non-numeric characters for validation
    digits = re.sub(r"\D", "", value)

    # Saudi mobile numbers should be 9 digits and start with 5
    if len(digits) == 9 and digits.startswith("5"):
        return

    # Check for Saudi numbers with country code
    if len(digits) == 12 and digits.startswith("9665"):
        return

    # Check for international format
    if len(digits) >= 10 and (digits.startswith("00") or digits.startswith("+")):
        return

    raise ValidationError(_("Enter a valid phone number"))


# Create a reusable RegexValidator
phone_regex = RegexValidator(
    regex=r"^\+?[0-9]{8,15}$", message=_("Enter a valid phone number")
)


def validate_uuid(value):
    """
    Validate a UUID.

    Args:
        value (str): UUID to validate

    Raises:
        ValidationError: If the UUID is invalid
    """
    try:
        uuid.UUID(str(value))
    except ValueError:
        raise ValidationError(_("Enter a valid UUID"))


def validate_password_strength(password):
    """
    Validate password strength.

    Args:
        password (str): Password to validate

    Raises:
        ValidationError: If the password is weak
    """
    # Check length
    if len(password) < 8:
        raise ValidationError(_("Password must be at least 8 characters long"))

    # Check for at least one lowercase letter
    if not any(c.islower() for c in password):
        raise ValidationError(_("Password must contain at least one lowercase letter"))

    # Check for at least one uppercase letter
    if not any(c.isupper() for c in password):
        raise ValidationError(_("Password must contain at least one uppercase letter"))

    # Check for at least one digit
    if not any(c.isdigit() for c in password):
        raise ValidationError(_("Password must contain at least one digit"))

    # Check for at least one special character
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/~" for c in password):
        raise ValidationError(_("Password must contain at least one special character"))


def validate_image_extension(value):
    """
    Validate image file extension.

    Args:
        value: Image file to validate

    Raises:
        ValidationError: If the file extension is invalid
    """
    valid_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]

    ext = value.name.lower().split(".")[-1]
    if f".{ext}" not in valid_extensions:
        raise ValidationError(
            _(
                "Unsupported file extension. Allowed extensions: jpg, jpeg, png, gif, webp"
            )
        )


def validate_video_extension(value):
    """
    Validate video file extension.

    Args:
        value: Video file to validate

    Raises:
        ValidationError: If the file extension is invalid
    """
    valid_extensions = [".mp4", ".mov", ".avi", ".webm"]

    ext = value.name.lower().split(".")[-1]
    if f".{ext}" not in valid_extensions:
        raise ValidationError(
            _("Unsupported file extension. Allowed extensions: mp4, mov, avi, webm")
        )


def validate_file_size(value, max_size_mb=5):
    """
    Validate file size.

    Args:
        value: File to validate
        max_size_mb (int): Maximum file size in MB

    Raises:
        ValidationError: If the file is too large
    """
    max_size_bytes = max_size_mb * 1024 * 1024

    if value.size > max_size_bytes:
        raise ValidationError(
            _("File size cannot exceed %(max_size)s MB") % {"max_size": max_size_mb}
        )


def validate_image_size(value, max_size_mb=5):
    """
    Validate both size and extension of image files.

    Args:
        value: Image file to validate
        max_size_mb (int): Maximum file size in MB

    Raises:
        ValidationError: If the file is too large or has an invalid extension
    """
    # Validate file size
    validate_file_size(value, max_size_mb)

    # Validate file extension
    validate_image_extension(value)

    # Additional validation could check image dimensions
    # from django.core.files.images import get_image_dimensions
    # width, height = get_image_dimensions(value)
    # if width > 4000 or height > 4000:
    #     raise ValidationError(_('Image dimensions cannot exceed 4000x4000 pixels'))

    return value


def validate_latitude(value):
    """
    Validate latitude value.

    Args:
        value (float): Latitude to validate

    Raises:
        ValidationError: If the latitude is invalid
    """
    try:
        lat = float(value)
        if lat < -90 or lat > 90:
            raise ValidationError(_("Latitude must be between -90 and 90"))
    except (ValueError, TypeError):
        raise ValidationError(_("Enter a valid latitude"))


def validate_longitude(value):
    """
    Validate longitude value.

    Args:
        value (float): Longitude to validate

    Raises:
        ValidationError: If the longitude is invalid
    """
    try:
        lng = float(value)
        if lng < -180 or lng > 180:
            raise ValidationError(_("Longitude must be between -180 and 180"))
    except (ValueError, TypeError):
        raise ValidationError(_("Enter a valid longitude"))


def validate_email(value):
    """
    Validate email address.

    Args:
        value (str): Email to validate

    Raises:
        ValidationError: If the email is invalid
    """
    if not value:
        return

    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_regex, value):
        raise ValidationError(_("Enter a valid email address"))


def validate_username(value):
    """
    Validate username.

    Args:
        value (str): Username to validate

    Raises:
        ValidationError: If the username is invalid
    """
    if not value:
        return

    # Check length
    if len(value) < 3 or len(value) > 30:
        raise ValidationError(_("Username must be between 3 and 30 characters long"))

    # Check for valid characters
    username_regex = r"^[a-zA-Z0-9_\.]+$"
    if not re.match(username_regex, value):
        raise ValidationError(
            _("Username can only contain letters, numbers, underscores, and dots")
        )

    # Check if username starts with a letter or number
    if not value[0].isalnum():
        raise ValidationError(_("Username must start with a letter or number"))


def validate_arabic_text(value):
    """
    Validate that text contains Arabic characters.

    Args:
        value (str): Text to validate

    Raises:
        ValidationError: If the text doesn't contain Arabic characters
    """
    if not value:
        return

    # Arabic Unicode ranges
    arabic_regex = (
        r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
    )
    if not re.search(arabic_regex, value):
        raise ValidationError(_("Text must contain Arabic characters"))


def validate_english_text(value):
    """
    Validate that text contains English characters.

    Args:
        value (str): Text to validate

    Raises:
        ValidationError: If the text doesn't contain English characters
    """
    if not value:
        return

    # English characters and common punctuation
    english_regex = r"[a-zA-Z]"
    if not re.search(english_regex, value):
        raise ValidationError(_("Text must contain English characters"))


def validate_saudi_id(value):
    """
    Validate Saudi national ID.

    Args:
        value (str): ID to validate

    Raises:
        ValidationError: If the ID is invalid
    """
    if not value:
        return

    # Saudi ID is 10 digits and starts with 1 or 2
    digits = re.sub(r"\D", "", value)
    if len(digits) != 10 or not digits.startswith(("1", "2")):
        raise ValidationError(_("Enter a valid Saudi national ID"))

    # TODO: Add checksum validation if required


def validate_time_format(value):
    """
    Validate time format (HH:MM).

    Args:
        value (str): Time to validate

    Raises:
        ValidationError: If the time format is invalid
    """
    if not value:
        return

    time_regex = r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
    if not re.match(time_regex, value):
        raise ValidationError(_("Enter a valid time format (HH:MM)"))


def validate_not_future_date(value):
    """
    Validate that a date is not in the future.

    Args:
        value (date): Date to validate

    Raises:
        ValidationError: If the date is in the future
    """
    from django.utils import timezone

    if value > timezone.now().date():
        raise ValidationError(_("Date cannot be in the future"))


def validate_future_date(value):
    """
    Validate that a date is in the future.

    Args:
        value (date): Date to validate

    Raises:
        ValidationError: If the date is not in the future
    """
    from django.utils import timezone

    if value <= timezone.now().date():
        raise ValidationError(_("Date must be in the future"))
