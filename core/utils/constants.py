# Queue Me platform constants

# General constants
DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ["en", "ar"]
DEFAULT_TIMEZONE = "Asia/Riyadh"
DEFAULT_CURRENCY = "SAR"

# Authentication constants
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 3
OTP_RESEND_COOLDOWN_MINUTES = 2

# Phone number formats
SAUDI_PHONE_REGEX = r"^(05|\+9665)\d{8}$"
INTERNATIONAL_PHONE_REGEX = r"^\+\d{7,15}$"

# Time formats
TIME_FORMAT_12H = "%I:%M %p"  # Example: 02:30 PM
DATE_FORMAT = "%d %b, %Y"  # Example: 05 Apr, 2025

# Business constants
MIN_SLOT_DURATION = 5  # minutes
MAX_SLOT_DURATION = 480  # minutes (8 hours)
DEFAULT_BUFFER_TIME = 0  # minutes
DEFAULT_SLOT_GRANULARITY = 30  # minutes

# Payment constants
HALALAS_PER_RIYAL = 100

# Default working hours
DEFAULT_OPENING_HOUR = "09:00:00"
DEFAULT_CLOSING_HOUR = "18:00:00"
DEFAULT_CLOSED_DAYS = [5]  # Friday (index 5)

# File size limits
MAX_IMAGE_SIZE_MB = 5
MAX_VIDEO_SIZE_MB = 50

# Queue constants
DEFAULT_QUEUE_CAPACITY = 50
