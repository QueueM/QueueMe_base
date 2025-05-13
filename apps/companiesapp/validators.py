# apps/companiesapp/validators.py
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_company_name(value):
    """Validate company name doesn't contain restricted words"""
    restricted_words = ["admin", "queue me", "system"]

    for word in restricted_words:
        if word.lower() in value.lower():
            raise ValidationError(
                _('Company name cannot contain the word "%(word)s".'),
                params={"word": word},
            )


def validate_registration_number(value):
    """Validate Saudi company registration number"""
    if value and not re.match(r"^\d{10}$", value):
        raise ValidationError(_("Registration number must be a 10-digit number."))


def validate_company_logo(image):
    """Validate company logo dimensions and size"""
    # Check file size (max 2MB)
    if image.size > 2 * 1024 * 1024:
        raise ValidationError(_("Image file too large. Maximum size is 2MB."))

    # Check dimensions
    if hasattr(image, "width") and hasattr(image, "height"):
        if image.width < 100 or image.height < 100:
            raise ValidationError(_("Image dimensions too small. Minimum size is 100x100 pixels."))

        if image.width > 2000 or image.height > 2000:
            raise ValidationError(
                _("Image dimensions too large. Maximum size is 2000x2000 pixels.")
            )
