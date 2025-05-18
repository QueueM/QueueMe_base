# apps/bookingapp/utils/date_utils.py
import calendar
from datetime import datetime, timedelta

from django.utils import timezone


def get_week_dates(date=None):
    """
    Get list of dates for the week containing the given date

    Args:
        date: Date to get week for (defaults to today)

    Returns:
        List of 7 dates for the week (Sunday to Saturday)
    """
    if date is None:
        date = timezone.now().date()

    # Get the day of the week (0 = Monday, 6 = Sunday)
    day_of_week = date.weekday()

    # Calculate the date for Sunday (start of week)
    sunday = date - timedelta(days=(day_of_week + 1) % 7)

    # Generate list of dates for the week
    return [sunday + timedelta(days=i) for i in range(7)]


def get_month_dates(year, month):
    """
    Get list of all dates in the specified month

    Args:
        year: Year
        month: Month (1-12)

    Returns:
        List of all dates in the month
    """
    # Get first day of the month
    first_day = datetime(year, month, 1).date()

    # Get number of days in the month
    _, num_days = calendar.monthrange(year, month)

    # Generate list of dates
    return [first_day + timedelta(days=i) for i in range(num_days)]


def get_date_range(start_date, end_date):
    """
    Get list of all dates in the specified range (inclusive)

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        List of all dates in the range
    """
    delta = end_date - start_date
    return [start_date + timedelta(days=i) for i in range(delta.days + 1)]


def format_date_display(date, include_day=True):
    """
    Format date for display (localization-ready)

    Args:
        date: Date to format
        include_day: Whether to include day of week

    Returns:
        Formatted date string
    """
    if include_day:
        return date.strftime("%a, %b %d, %Y")  # Mon, Jan 01, 2025
    return date.strftime("%b %d, %Y")  # Jan 01, 2025


def format_time_display(time, use_12h=True):
    """
    Format time for display (localization-ready)

    Args:
        time: Time to format
        use_12h: Whether to use 12-hour format

    Returns:
        Formatted time string
    """
    if use_12h:
        return time.strftime("%I:%M %p")  # 01:30 PM
    return time.strftime("%H:%M")  # 13:30


def format_datetime_display(dt, use_12h=True):
    """
    Format datetime for display (localization-ready)

    Args:
        dt: Datetime to format
        use_12h: Whether to use 12-hour format

    Returns:
        Formatted datetime string
    """
    date_str = format_date_display(dt.date(), include_day=True)
    time_str = format_time_display(dt.time(), use_12h=use_12h)
    return f"{time_str} - {date_str}"  # 01:30 PM - Mon, Jan 01, 2025
