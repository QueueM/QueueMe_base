from django.utils.translation import gettext_lazy as _

# Experience levels
EXPERIENCE_LEVEL_CHOICES = (
    ("junior", _("Junior")),
    ("intermediate", _("Intermediate")),
    ("senior", _("Senior")),
    ("expert", _("Expert")),
)

# Availability statuses
AVAILABILITY_STATUS_CHOICES = (
    ("available", _("Available")),
    ("busy", _("Busy")),
    ("on_leave", _("On Leave")),
)

# Working day choices - for readability in code
SUNDAY = 0
MONDAY = 1
TUESDAY = 2
WEDNESDAY = 3
THURSDAY = 4
FRIDAY = 5
SATURDAY = 6

# Specialist cache keys
SPECIALIST_CACHE_KEY = "specialist_{id}"
SPECIALIST_SERVICES_CACHE_KEY = "specialist_{id}_services"
SPECIALIST_AVAILABILITY_CACHE_KEY = "specialist_{id}_availability_{date}"
SPECIALIST_TOP_RATED_CACHE_KEY = "top_specialists_{shop_id}_{limit}"
SPECIALIST_RECOMMENDATIONS_CACHE_KEY = (
    "specialist_recommendations_{customer_id}_{category_id}"
)

# Default buffer time (in minutes)
DEFAULT_BUFFER_BEFORE = 5
DEFAULT_BUFFER_AFTER = 5

# Default working hours
DEFAULT_START_HOUR = "09:00:00"
DEFAULT_END_HOUR = "17:00:00"

# Specialist ranking weights
RATING_WEIGHT = 0.45
BOOKING_COUNT_WEIGHT = 0.25
EXPERIENCE_WEIGHT = 0.15
PORTFOLIO_WEIGHT = 0.10
VERIFICATION_WEIGHT = 0.05

# Maximum portfolio items
MAX_PORTFOLIO_ITEMS = 20

# Notification types
NOTIFICATION_NEW_SPECIALIST = "new_specialist"
NOTIFICATION_SPECIALIST_VERIFIED = "specialist_verified"
