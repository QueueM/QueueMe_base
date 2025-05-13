# apps/bookingapp/utils/time_calculator.py
import math
from datetime import timedelta

from django.utils import timezone


def calculate_total_duration(appointments):
    """
    Calculate total duration from a list of appointments

    Args:
        appointments: List of Appointment objects

    Returns:
        Total duration in minutes
    """
    return sum(appointment.duration for appointment in appointments)


def calculate_appointment_end_time(start_time, duration):
    """
    Calculate end time based on start time and duration

    Args:
        start_time: Datetime for start
        duration: Duration in minutes

    Returns:
        Datetime for end
    """
    return start_time + timedelta(minutes=duration)


def calculate_total_appointment_time(duration, buffer_before, buffer_after):
    """
    Calculate total appointment time including buffers

    Args:
        duration: Service duration in minutes
        buffer_before: Buffer before in minutes
        buffer_after: Buffer after in minutes

    Returns:
        Total time in minutes
    """
    return duration + buffer_before + buffer_after


def round_time_to_slot(time, slot_minutes=15):
    """
    Round time to nearest slot

    Args:
        time: Time to round
        slot_minutes: Slot granularity in minutes

    Returns:
        Rounded time
    """
    minutes = time.hour * 60 + time.minute
    rounded_minutes = math.ceil(minutes / slot_minutes) * slot_minutes

    return (
        timezone.datetime.combine(timezone.datetime.min.date(), time)
        + timedelta(minutes=rounded_minutes - minutes)
    ).time()


def get_appointment_overlaps(appointment1, appointment2):
    """
    Calculate overlap time between two appointments

    Args:
        appointment1: First Appointment object
        appointment2: Second Appointment object

    Returns:
        Overlap duration in minutes or 0 if no overlap
    """
    # No overlap if one ends before the other starts
    if (
        appointment1.end_time <= appointment2.start_time
        or appointment2.end_time <= appointment1.start_time
    ):
        return 0

    # Calculate overlap
    overlap_start = max(appointment1.start_time, appointment2.start_time)
    overlap_end = min(appointment1.end_time, appointment2.end_time)

    overlap_duration = (overlap_end - overlap_start).total_seconds() / 60
    return max(0, overlap_duration)


def add_buffer_times(start_time, end_time, buffer_before, buffer_after):
    """
    Add buffer times to an appointment time range

    Args:
        start_time: Original start datetime
        end_time: Original end datetime
        buffer_before: Buffer before in minutes
        buffer_after: Buffer after in minutes

    Returns:
        Tuple of (new_start_time, new_end_time)
    """
    new_start = start_time - timedelta(minutes=buffer_before)
    new_end = end_time + timedelta(minutes=buffer_after)

    return (new_start, new_end)
