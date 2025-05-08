from datetime import date

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_discount_price(original_price, discounted_price):
    """
    Validates that the discounted price is less than the original price.

    Args:
        original_price: The original total price of all services
        discounted_price: The discounted package price

    Raises:
        ValidationError: If discounted price is not less than original price
    """
    if discounted_price >= original_price:
        raise ValidationError(
            _(
                "Discounted price (%(discounted)s) must be less than original price (%(original)s)"
            ),
            params={"discounted": discounted_price, "original": original_price},
        )


def validate_date_range(start_date, end_date):
    """
    Validates that the end date is after the start date.

    Args:
        start_date: The package start date
        end_date: The package end date

    Raises:
        ValidationError: If end date is not after start date
    """
    if start_date and end_date and end_date <= start_date:
        raise ValidationError(_("End date must be after start date"))


def validate_future_date(value):
    """
    Validates that a date is in the future.

    Args:
        value: The date to validate

    Raises:
        ValidationError: If date is not in the future
    """
    if value and value < date.today():
        raise ValidationError(_("Date must be in the future"))


def validate_services_compatibility(services):
    """
    Validates that all services in a package are compatible
    (e.g., all from the same shop, no conflicting requirements).

    Args:
        services: List of service IDs to include in package

    Raises:
        ValidationError: If services are incompatible
    """
    if not services or len(services) < 2:
        raise ValidationError(_("A package must contain at least two services"))

    # Extract services data
    from apps.serviceapp.models import Service

    service_objs = Service.objects.filter(id__in=services)

    # Check if all services exist
    if len(service_objs) != len(services):
        raise ValidationError(_("One or more services do not exist"))

    # Check if all services belong to the same shop
    shops = {service.shop_id for service in service_objs}
    if len(shops) > 1:
        raise ValidationError(_("All services must belong to the same shop"))

    # Check service locations compatibility
    locations = {service.service_location for service in service_objs}
    if "in_shop" in locations and "in_home" in locations:
        # If we have both in-shop and in-home services, we need a 'both' option
        if "both" not in locations:
            raise ValidationError(
                _(
                    "Package contains both in-shop and in-home services, but not all services support both locations"
                )
            )
