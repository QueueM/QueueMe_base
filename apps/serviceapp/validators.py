from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_time_range(from_hour, to_hour):
    """Validate that from_hour is before to_hour"""
    if from_hour >= to_hour:
        raise ValidationError(_("From hour must be before to hour"))


def validate_duration(duration):
    """Validate service duration (between 1 minute and 24 hours)"""
    if duration < 1 or duration > 1440:
        raise ValidationError(_("Duration must be between 1 minute and 24 hours"))


def validate_slot_granularity(granularity, duration):
    """Validate slot granularity is compatible with duration"""
    if granularity < 1 or granularity > 120:
        raise ValidationError(_("Slot granularity must be between 1 and 120 minutes"))

    if duration % granularity != 0:
        raise ValidationError(_("Duration must be divisible by slot granularity"))


def validate_working_hours(hours):
    """Validate service working hours"""
    weekdays = set()

    for hour in hours:
        # Check for duplicate weekdays
        if hour["weekday"] in weekdays:
            raise ValidationError(_("Duplicate weekday in service hours"))
        weekdays.add(hour["weekday"])

        # Check time range if not closed
        if not hour.get("is_closed", False):
            if not hour.get("from_hour") or not hour.get("to_hour"):
                raise ValidationError(_("From hour and to hour are required when not closed"))

            validate_time_range(hour["from_hour"], hour["to_hour"])

    # Ensure all weekdays are covered
    if len(weekdays) < 7:
        raise ValidationError(_("All weekdays must be defined in service hours"))
