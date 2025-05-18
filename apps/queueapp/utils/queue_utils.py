import random
import string

from django.utils import timezone


def generate_random_alphanumeric(length=6):
    """
    Generate a random alphanumeric string of the specified length.
    Used for ticket IDs and other references.
    """
    characters = string.ascii_uppercase + string.digits
    return "".join(random.choice(characters) for _ in range(length))


def format_time_interval(minutes):
    """
    Format a time interval in minutes into a human-readable string.
    For example, 65 minutes becomes "1 hour 5 minutes".
    """
    if minutes < 1:
        return "less than a minute"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours == 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif remaining_minutes == 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        return f"{hours} hour{'s' if hours != 1 else ''} {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"


def calculate_time_difference(start_time, end_time=None):
    """
    Calculate the time difference between two timestamps in minutes.
    If end_time is not provided, current time is used.
    """
    if end_time is None:
        end_time = timezone.now()

    diff = end_time - start_time
    return int(diff.total_seconds() / 60)


def format_am_pm_time(time_obj):
    """
    Format a time object to AM/PM format, as preferred in Saudi Arabia.
    For example, 14:30:00 becomes "02:30 PM".
    """
    return time_obj.strftime("%I:%M %p")


def format_queue_position(position):
    """
    Format a queue position with appropriate suffix (1st, 2nd, 3rd, etc.)
    """
    if 10 <= position % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(position % 10, "th")

    return f"{position}{suffix}"
