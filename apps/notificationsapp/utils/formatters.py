"""
Utilities for formatting notification messages.
"""

import re

from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def format_phone_number(phone_number):
    """
    Format a phone number for display.

    Args:
        phone_number: Raw phone number

    Returns:
        Formatted phone number
    """
    if not phone_number:
        return ""

    # Remove any non-digit characters
    digits = re.sub(r"\D", "", phone_number)

    # If it starts with country code (e.g., +966), format accordingly
    if phone_number.startswith("+"):
        if len(digits) > 10:
            country_code = digits[:-10]
            main_number = digits[-10:]
            return f"+{country_code} {main_number[:3]} {main_number[3:6]} {main_number[6:]}"
        else:
            return phone_number

    # Otherwise use simple spacing for standard number
    if len(digits) >= 10:
        return f"{digits[:-7]} {digits[-7:-4]} {digits[-4:]}"

    return phone_number


def format_date_for_sms(date):
    """
    Format a date for SMS display (keeping it short).

    Args:
        date: Date or datetime object

    Returns:
        Formatted date string
    """
    if not date:
        return ""

    # For today or tomorrow, use those words
    today = timezone.now().date()

    if hasattr(date, "date"):
        date_part = date.date()
    else:
        date_part = date

    if date_part == today:
        return _("today")
    elif date_part == today + timezone.timedelta(days=1):
        return _("tomorrow")

    # Otherwise use short date
    if hasattr(date, "strftime"):
        return date.strftime("%d/%m")

    return str(date)


def format_time_for_sms(time):
    """
    Format a time for SMS display.

    Args:
        time: Time or datetime object

    Returns:
        Formatted time string
    """
    if not time:
        return ""

    if hasattr(time, "strftime"):
        return time.strftime("%I:%M %p")

    return str(time)


def truncate_text(text, max_length=50, suffix="..."):
    """
    Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def format_wait_time(minutes):
    """
    Format wait time in minutes to a human-readable string.

    Args:
        minutes: Wait time in minutes

    Returns:
        Formatted wait time string
    """
    if minutes is None:
        return _("unknown")

    if minutes < 1:
        return _("less than a minute")

    if minutes == 1:
        return _("1 minute")

    if minutes < 60:
        return _("{} minutes").format(minutes)

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours == 1:
        if remaining_minutes == 0:
            return _("1 hour")
        elif remaining_minutes == 1:
            return _("1 hour and 1 minute")
        else:
            return _("1 hour and {} minutes").format(remaining_minutes)

    if remaining_minutes == 0:
        return _("{} hours").format(hours)
    elif remaining_minutes == 1:
        return _("{} hours and 1 minute").format(hours)
    else:
        return _("{} hours and {} minutes").format(hours, remaining_minutes)
