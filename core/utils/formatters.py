"""
Data formatting utilities for the Queue Me platform.

This module provides utility functions for formatting data in various ways.
"""

import decimal
import json
import re
from datetime import date, datetime, time

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _


def format_currency(amount, currency="SAR", decimal_places=2):
    """
    Format a currency amount.

    Args:
        amount: Amount to format
        currency (str): Currency code (default: SAR)
        decimal_places (int): Number of decimal places

    Returns:
        str: Formatted currency amount
    """
    # Convert to decimal for consistent handling
    if not isinstance(amount, decimal.Decimal):
        amount = decimal.Decimal(str(amount))

    # Round to specified decimal places
    amount = round(amount, decimal_places)

    # Format with thousand separators
    formatted = "{:,.{prec}f}".format(amount, prec=decimal_places)

    # Add currency symbol based on locale
    current_language = getattr(settings, "LANGUAGE_CODE", "en")

    if current_language == "ar":
        if currency == "SAR":
            return f"{formatted} ر.س"
        else:
            return f"{formatted} {currency}"
    else:
        if currency == "SAR":
            return f"SAR {formatted}"
        else:
            return f"{currency} {formatted}"


def format_date(date_obj, format_str=None, include_time=False, language=None):
    """
    Format a date according to the specified format and language.

    Args:
        date_obj: Date to format (date, datetime, or string)
        format_str (str): Date format string
        include_time (bool): Whether to include time
        language (str): Language code (default: current language)

    Returns:
        str: Formatted date
    """
    # Set default language to current language
    if language is None:
        language = getattr(settings, "LANGUAGE_CODE", "en")

    # Set default format based on language
    if format_str is None:
        if language == "ar":
            format_str = "d MMM, yyyy" if not include_time else "d MMM, yyyy h:mm a"
        else:
            format_str = "%d %b, %Y" if not include_time else "%d %b, %Y %I:%M %p"

    # Convert string to date/datetime if needed
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.fromisoformat(date_obj.replace("Z", "+00:00"))
        except ValueError:
            try:
                date_obj = datetime.strptime(date_obj, "%Y-%m-%d")
            except ValueError:
                return date_obj  # Return original string if parsing fails

    # Convert datetime to current timezone if timezone-aware
    if isinstance(date_obj, datetime) and timezone.is_aware(date_obj):
        date_obj = timezone.localtime(date_obj)

    # Format date
    if isinstance(date_obj, datetime):
        formatted = date_obj.strftime(format_str)
    elif isinstance(date_obj, date):
        if include_time:
            # Convert to datetime with midnight time
            date_obj = datetime.combine(date_obj, time.min)
            formatted = date_obj.strftime(format_str)
        else:
            formatted = date_obj.strftime(format_str)
    else:
        return str(date_obj)  # Return string representation for other types

    # Handle Arabic formatting
    if language == "ar":
        # Replace English month names with Arabic month names
        arabic_months = {
            "Jan": "يناير",
            "Feb": "فبراير",
            "Mar": "مارس",
            "Apr": "أبريل",
            "May": "مايو",
            "Jun": "يونيو",
            "Jul": "يوليو",
            "Aug": "أغسطس",
            "Sep": "سبتمبر",
            "Oct": "أكتوبر",
            "Nov": "نوفمبر",
            "Dec": "ديسمبر",
        }

        for en_month, ar_month in arabic_months.items():
            formatted = formatted.replace(en_month, ar_month)

        # Replace AM/PM with Arabic equivalent
        formatted = formatted.replace("AM", "ص").replace("PM", "م")

        # Note: For production, we would also replace English numerals with Arabic numerals here
        # That's handled separately in the view rendering for proper RTL support

    return formatted


def format_phone_number(phone_number, country_code="+966"):
    """
    Format a phone number.

    Args:
        phone_number (str): Phone number to format
        country_code (str): Country code (default: +966 for Saudi Arabia)

    Returns:
        str: Formatted phone number
    """
    # Remove non-numeric characters
    digits = re.sub(r"\D", "", phone_number)

    # Handle Saudi phone numbers (example: +966 5X XXX XXXX)
    if digits.startswith("966"):
        # Format with Saudi country code
        return f"+{digits[:3]} {digits[3:4]} {digits[4:7]} {digits[7:]}"
    elif len(digits) == 9 and digits.startswith("5"):
        # Add Saudi country code
        return f"{country_code} {digits[:1]} {digits[1:4]} {digits[4:]}"
    else:
        # Generic formatting
        if digits.startswith("00"):
            # Convert 00 to +
            digits = digits[2:]
            return f"+{digits}"
        elif not digits.startswith("+"):
            # Add + if missing
            return f"+{digits}"
        else:
            return phone_number


def format_time_ago(timestamp):
    """
    Format a timestamp as a human-readable "time ago" string.

    Args:
        timestamp: Timestamp to format (datetime or string)

    Returns:
        str: Human-readable time ago
    """
    # Convert string to datetime if needed
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return timestamp  # Return original string if parsing fails

    # Get current time in same timezone
    now = timezone.now()
    if timezone.is_aware(timestamp):
        now = timezone.localtime(now)
        timestamp = timezone.localtime(timestamp)

    # Calculate difference
    diff = now - timestamp

    # Format based on difference
    if diff.days > 365:
        years = diff.days // 365
        return (
            _("%(years)d year ago") % {"years": years}
            if years == 1
            else _("%(years)d years ago") % {"years": years}
        )
    elif diff.days > 30:
        months = diff.days // 30
        return (
            _("%(months)d month ago") % {"months": months}
            if months == 1
            else _("%(months)d months ago") % {"months": months}
        )
    elif diff.days > 0:
        return (
            _("%(days)d day ago") % {"days": diff.days}
            if diff.days == 1
            else _("%(days)d days ago") % {"days": diff.days}
        )
    elif diff.seconds >= 3600:
        hours = diff.seconds // 3600
        return (
            _("%(hours)d hour ago") % {"hours": hours}
            if hours == 1
            else _("%(hours)d hours ago") % {"hours": hours}
        )
    elif diff.seconds >= 60:
        minutes = diff.seconds // 60
        return (
            _("%(minutes)d minute ago") % {"minutes": minutes}
            if minutes == 1
            else _("%(minutes)d minutes ago") % {"minutes": minutes}
        )
    else:
        return _("just now")


def format_file_size(size_bytes):
    """
    Format file size in human-readable format.

    Args:
        size_bytes (int): File size in bytes

    Returns:
        str: Formatted file size
    """
    # Handle edge cases
    if size_bytes < 0:
        return "0 B"

    # Define units and suffixes
    units = ["B", "KB", "MB", "GB", "TB", "PB"]

    # Calculate unit index
    unit_index = 0
    while size_bytes >= 1024 and unit_index < len(units) - 1:
        size_bytes /= 1024
        unit_index += 1

    # Format with appropriate precision
    if unit_index == 0:
        return f"{size_bytes:.0f} {units[unit_index]}"
    else:
        return f"{size_bytes:.1f} {units[unit_index]}"


def format_duration(seconds, detailed=False):
    """
    Format duration in human-readable format.

    Args:
        seconds (int): Duration in seconds
        detailed (bool): Whether to use detailed format

    Returns:
        str: Formatted duration
    """
    # Handle edge cases
    if seconds < 0:
        return "0s"

    # Calculate components
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    # Format based on largest non-zero component
    if detailed:
        # Detailed format (e.g., "2 days, 3 hours, 45 minutes, 30 seconds")
        components = []

        if days > 0:
            components.append(
                _("%(days)d day") % {"days": days}
                if days == 1
                else _("%(days)d days") % {"days": days}
            )

        if hours > 0:
            components.append(
                _("%(hours)d hour") % {"hours": hours}
                if hours == 1
                else _("%(hours)d hours") % {"hours": hours}
            )

        if minutes > 0:
            components.append(
                _("%(minutes)d minute") % {"minutes": minutes}
                if minutes == 1
                else _("%(minutes)d minutes") % {"minutes": minutes}
            )

        if seconds > 0 or not components:
            components.append(
                _("%(seconds)d second") % {"seconds": seconds}
                if seconds == 1
                else _("%(seconds)d seconds") % {"seconds": seconds}
            )

        return ", ".join(components)
    else:
        # Simple format (e.g., "2d 3h 45m 30s" or "3h 45m" or "45m 30s")
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"


def format_json(data, pretty=True, ensure_ascii=False):
    """
    Format data as JSON.

    Args:
        data: Data to format
        pretty (bool): Whether to use pretty formatting
        ensure_ascii (bool): Whether to ensure ASCII-only output

    Returns:
        str: Formatted JSON
    """

    class CustomJSONEncoder(json.JSONEncoder):
        """Custom JSON encoder for handling special types."""

        def default(self, obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            elif isinstance(obj, decimal.Decimal):
                return float(obj)
            return super().default(obj)

    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=ensure_ascii, cls=CustomJSONEncoder)
    else:
        return json.dumps(data, ensure_ascii=ensure_ascii, cls=CustomJSONEncoder)


def truncate_text(text, max_length=100, suffix="..."):
    """
    Truncate text to a specified length.

    Args:
        text (str): Text to truncate
        max_length (int): Maximum length
        suffix (str): Suffix to add when truncated

    Returns:
        str: Truncated text
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    # Truncate at maximum length
    truncated = text[: max_length - len(suffix)]

    # Try to truncate at word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_length * 0.7:  # Only truncate at word if we're keeping most of the text
        truncated = truncated[:last_space]

    return truncated + suffix
