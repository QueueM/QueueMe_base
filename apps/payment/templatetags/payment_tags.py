from django import template
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


@register.simple_tag
def payment_status_badge(status):
    """Render a colored status badge for payment status"""
    status_map = {
        "initiated": ("gray", _("Initiated")),
        "processing": ("blue", _("Processing")),
        "succeeded": ("green", _("Succeeded")),
        "failed": ("red", _("Failed")),
        "refunded": ("purple", _("Refunded")),
        "partially_refunded": ("orange", _("Partially Refunded")),
    }

    color, label = status_map.get(status, ("gray", status))
    return mark_safe(f'<span class="badge badge-{color}">{label}</span>')


@register.simple_tag
def payment_type_icon(payment_type):
    """Render an icon for the payment type"""
    icon_map = {
        "card": "credit-card",
        "stcpay": "mobile",
        "mada": "credit-card",
        "apple_pay": "apple",
    }

    icon = icon_map.get(payment_type, "money")
    return mark_safe(f'<i class="fa fa-{icon}"></i>')


@register.filter
def card_brand_icon(brand):
    """Return icon class for card brand"""
    brand_map = {
        "visa": "fa-cc-visa",
        "mastercard": "fa-cc-mastercard",
        "amex": "fa-cc-amex",
        "discover": "fa-cc-discover",
        "mada": "fa-credit-card",
    }

    icon_class = brand_map.get(brand.lower(), "fa-credit-card")
    return mark_safe(f'<i class="fa {icon_class}"></i>')
