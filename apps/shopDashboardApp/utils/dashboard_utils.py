"""
Utility functions for the dashboard.
These helpers are used across the dashboard module.
"""

from datetime import datetime, timedelta

from django.utils import timezone

from apps.shopDashboardApp.constants import (
    TIME_PERIOD_CUSTOM,
    TIME_PERIOD_MONTH,
    TIME_PERIOD_QUARTER,
    TIME_PERIOD_TODAY,
    TIME_PERIOD_WEEK,
    TIME_PERIOD_YEAR,
    TIME_PERIOD_YESTERDAY,
)
from apps.shopDashboardApp.exceptions import InvalidDateRangeException


def calculate_date_range(time_period, start_date=None, end_date=None):
    """
    Calculate start and end dates based on time period.
    This is a utility version of the method in DashboardService.
    """
    today = timezone.now().date()

    if time_period == TIME_PERIOD_TODAY:
        return {"start_date": today, "end_date": today}

    elif time_period == TIME_PERIOD_YESTERDAY:
        yesterday = today - timedelta(days=1)
        return {"start_date": yesterday, "end_date": yesterday}

    elif time_period == TIME_PERIOD_WEEK:
        # Current week (Sunday to today)
        # Get the most recent Sunday
        start_of_week = today - timedelta(days=today.weekday() + 1)
        if start_of_week > today:  # If today is Sunday
            start_of_week = today

        return {"start_date": start_of_week, "end_date": today}

    elif time_period == TIME_PERIOD_MONTH:
        # Current month (1st to today)
        start_of_month = today.replace(day=1)

        return {"start_date": start_of_month, "end_date": today}

    elif time_period == TIME_PERIOD_QUARTER:
        # Current quarter
        current_month = today.month
        quarter_start_month = ((current_month - 1) // 3) * 3 + 1
        start_of_quarter = today.replace(month=quarter_start_month, day=1)

        return {"start_date": start_of_quarter, "end_date": today}

    elif time_period == TIME_PERIOD_YEAR:
        # Current year (Jan 1st to today)
        start_of_year = today.replace(month=1, day=1)

        return {"start_date": start_of_year, "end_date": today}

    elif time_period == TIME_PERIOD_CUSTOM:
        # Custom date range - validate input
        if not start_date or not end_date:
            raise InvalidDateRangeException(
                "Start date and end date are required for custom range."
            )

        # Parse dates
        try:
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            # Validate date range
            if start_date > end_date:
                raise InvalidDateRangeException("Start date cannot be after end date.")

            return {"start_date": start_date, "end_date": end_date}
        except ValueError:
            raise InvalidDateRangeException("Invalid date format. Use YYYY-MM-DD.")

    else:
        raise InvalidDateRangeException(f"Unknown time period: {time_period}")


def format_duration(minutes):
    """Format minutes as hours and minutes"""
    if minutes is None:
        return "0m"

    hours = minutes // 60
    mins = minutes % 60

    if hours > 0:
        return f"{hours}h {mins}m"
    else:
        return f"{mins}m"


def format_percentage(value, decimal_places=1):
    """Format a decimal as a percentage with specified decimal places"""
    if value is None:
        return "0%"

    return f"{value:.{decimal_places}f}%"


def format_currency(amount, currency="SAR"):
    """Format an amount as currency"""
    if amount is None:
        return f"0 {currency}"

    return f"{float(amount):.2f} {currency}"


def date_to_fiscal_quarter(date):
    """Convert date to fiscal quarter string (e.g., 'Q1 2023')"""
    quarter = (date.month - 1) // 3 + 1
    return f"Q{quarter} {date.year}"


def get_change_indicator(change_percentage):
    """Return indicator for change (up, down, neutral)"""
    if change_percentage > 5:
        return "up"
    elif change_percentage < -5:
        return "down"
    else:
        return "neutral"


def sanitize_string_for_id(text):
    """Convert a string to a valid ID for DOM elements"""
    if not text:
        return ""

    # Remove non-alphanumeric characters and replace spaces with underscores
    return "".join(c if c.isalnum() else "_" for c in text).lower()
