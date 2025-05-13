import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from ..utils.payment_utils import format_amount, mask_card_number

register = template.Library()


@register.filter
def currency_format(amount, currency="SAR"):
    """Format amount with currency symbol"""
    return format_amount(amount, currency)


@register.filter
def card_mask(number):
    """Mask credit card number"""
    return mask_card_number(number)


# Function to sanitize a string for use in HTML attributes
def sanitize_for_html_attribute(value):
    """Sanitize a string for use in HTML attributes"""
    # Allow only alphanumeric, hyphen, and underscore
    if not value or not isinstance(value, str):
        return "default"
    sanitized = re.sub(r"[^a-zA-Z0-9\-_]", "", value)
    return sanitized or "default"


@register.filter
def status_badge(status):
    """Display a colored badge for a status value"""
    if not status or not isinstance(status, str):
        status = "unknown"

    status_map = {
        "paid": ("success", "Paid"),
        "refunded": ("warning", "Refunded"),
        "failed": ("danger", "Failed"),
        "pending": ("info", "Pending"),
        "cancelled": ("secondary", "Cancelled"),
    }

    color, label = status_map.get(status.lower(), ("gray", escape(status)))
    # Sanitize color to prevent XSS
    color = sanitize_for_html_attribute(color)

    # Use Django's HTML templating system rather than f-strings
    template = '<span class="badge badge-{color}">{label}</span>'
    return mark_safe(template.format(color=color, label=escape(label)))


@register.filter
def payment_icon(payment_type):
    """Display a Font Awesome icon for payment type"""
    if not payment_type or not isinstance(payment_type, str):
        payment_type = "unknown"

    icon_map = {
        "credit_card": "credit-card",
        "credit": "credit-card",
        "card": "credit-card",
        "bank": "university",
        "cash": "money-bill",
        "online": "globe",
        "paypal": "paypal",
        "wallet": "wallet",
    }

    icon = icon_map.get(payment_type.lower(), "money")
    # Sanitize icon to prevent XSS
    icon = sanitize_for_html_attribute(icon)

    # Use Django's HTML templating system rather than f-strings
    template = '<i class="fa fa-{icon}"></i>'
    return mark_safe(template.format(icon=icon))


@register.filter
def card_icon(brand):
    """Display a Font Awesome icon for card brand"""
    if not brand or not isinstance(brand, str):
        brand = "unknown"

    brand_map = {
        "visa": "fa-cc-visa",
        "mastercard": "fa-cc-mastercard",
        "amex": "fa-cc-amex",
        "american express": "fa-cc-amex",
        "discover": "fa-cc-discover",
        "diners": "fa-cc-diners-club",
        "diners club": "fa-cc-diners-club",
        "jcb": "fa-cc-jcb",
    }

    icon_class = brand_map.get(brand.lower(), "fa-credit-card")
    # Sanitize icon_class to prevent XSS
    icon_class = sanitize_for_html_attribute(icon_class)

    # Use Django's HTML templating system rather than f-strings
    template = '<i class="fa {icon_class}"></i>'
    return mark_safe(template.format(icon_class=icon_class))
