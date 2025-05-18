from django.db import models
from django.utils.translation import gettext_lazy as _


class ServiceLocationType(models.TextChoices):
    """Service location types"""

    IN_SHOP = "in_shop", _("In Shop")
    IN_HOME = "in_home", _("In Home")
    BOTH = "both", _("Both")


class DayOfWeek(models.IntegerChoices):
    """Day of week (0=Sunday, 6=Saturday)"""

    SUNDAY = 0, _("Sunday")
    MONDAY = 1, _("Monday")
    TUESDAY = 2, _("Tuesday")
    WEDNESDAY = 3, _("Wednesday")
    THURSDAY = 4, _("Thursday")
    FRIDAY = 5, _("Friday")
    SATURDAY = 6, _("Saturday")


class ServiceStatus(models.TextChoices):
    """Service status"""

    ACTIVE = "active", _("Active")
    INACTIVE = "inactive", _("Inactive")
    DRAFT = "draft", _("Draft")
    ARCHIVED = "archived", _("Archived")
