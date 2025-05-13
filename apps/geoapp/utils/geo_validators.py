import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .geo_constants import SAUDI_ARABIA_BOUNDS


def validate_latitude(value):
    """
    Validate that a value is a valid latitude

    Args:
        value: Value to validate

    Raises:
        ValidationError if invalid
    """
    try:
        lat = float(value)
        if lat < -90 or lat > 90:
            raise ValidationError(
                _("Latitude must be between -90 and 90 degrees"),
                code="invalid_latitude",
            )
    except (ValueError, TypeError):
        raise ValidationError(_("Latitude must be a valid number"), code="invalid_latitude")


def validate_longitude(value):
    """
    Validate that a value is a valid longitude

    Args:
        value: Value to validate

    Raises:
        ValidationError if invalid
    """
    try:
        lng = float(value)
        if lng < -180 or lng > 180:
            raise ValidationError(
                _("Longitude must be between -180 and 180 degrees"),
                code="invalid_longitude",
            )
    except (ValueError, TypeError):
        raise ValidationError(_("Longitude must be a valid number"), code="invalid_longitude")


def validate_coordinates_pair(lat, lng):
    """
    Validate that a pair of values are valid coordinates

    Args:
        lat: Latitude value
        lng: Longitude value

    Raises:
        ValidationError if invalid
    """
    validate_latitude(lat)
    validate_longitude(lng)


def validate_saudi_coordinates(lat, lng):
    """
    Validate that coordinates are within Saudi Arabia

    Args:
        lat: Latitude value
        lng: Longitude value

    Raises:
        ValidationError if outside Saudi Arabia
    """
    validate_coordinates_pair(lat, lng)

    lat_float = float(lat)
    lng_float = float(lng)

    bounds = SAUDI_ARABIA_BOUNDS

    if (
        lat_float < bounds["min_lat"]
        or lat_float > bounds["max_lat"]
        or lng_float < bounds["min_lng"]
        or lng_float > bounds["max_lng"]
    ):
        raise ValidationError(
            _("Coordinates must be within Saudi Arabia"), code="outside_saudi_arabia"
        )


def validate_postal_code(value, country_code="SA"):
    """
    Validate a postal code format for a given country

    Args:
        value: Postal code to validate
        country_code: ISO country code

    Raises:
        ValidationError if invalid
    """
    if not value:
        return

    if country_code == "SA":
        # Saudi postal code format: 5 digits
        if not re.match(r"^\d{5}$", value):
            raise ValidationError(
                _("Saudi postal codes must be 5 digits"), code="invalid_postal_code"
            )
    else:
        # Generic validation
        if not re.match(r"^[\w\d\s-]{3,10}$", value):
            raise ValidationError(_("Invalid postal code format"), code="invalid_postal_code")


def validate_address_format(value):
    """
    Validate that an address has a reasonable format

    Args:
        value: Address to validate

    Raises:
        ValidationError if invalid
    """
    if not value:
        return

    # Basic validation - ensure reasonable length and no suspicious characters
    if len(value) < 5:
        raise ValidationError(_("Address is too short"), code="address_too_short")

    if len(value) > 255:
        raise ValidationError(_("Address is too long"), code="address_too_long")

    # Check for suspicious patterns (e.g., SQL injection attempts)
    suspicious_patterns = [
        r"<script",
        r"SELECT\s+.*\s+FROM",
        r";\s*DROP",
        r"--",
        r"\/\*",
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValidationError(
                _("Address contains suspicious characters"), code="suspicious_address"
            )
