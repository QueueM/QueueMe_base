"""
Global constants for the Queue Me platform.

This module defines constants used throughout the application, including
format strings, status values, error messages, and more.
"""

# Time and date formats
TIME_FORMATS = {
    "ar": "%I:%M %p",  # Arabic (12-hour with AM/PM)
    "en": "%I:%M %p",  # English (12-hour with AM/PM)
}

DATE_FORMATS = {
    "ar": "%d %b، %Y",  # Arabic date format
    "en": "%d %b, %Y",  # English date format
}

DATETIME_FORMATS = {
    "ar": "%d %b، %Y %I:%M %p",  # Arabic datetime format
    "en": "%d %b, %Y %I:%M %p",  # English datetime format
}

# Currency formats
CURRENCY_FORMATS = {
    "SAR": {
        "ar": "{value} ر.س",  # Arabic SAR format
        "en": "SAR {value}",  # English SAR format
    }
}

# Phone number formats
PHONE_FORMATS = {
    "SA": r"^\+?9665\d{8}$",  # Saudi Arabia format (5xxxxxxxx)
}

# Supported languages
LANGUAGES = (
    ("en", "English"),
    ("ar", "Arabic"),
)

# Payment and transaction statuses
PAYMENT_STATUS = {
    "pending": "pending",
    "processing": "processing",
    "succeeded": "succeeded",
    "failed": "failed",
    "refunded": "refunded",
    "partially_refunded": "partially_refunded",
}

TRANSACTION_TYPES = {
    "booking": "booking",
    "subscription": "subscription",
    "ad": "ad",
}

# API Rate limits (requests per minute)
REQUEST_LIMIT_RATES = {
    "default": "60/min",
    "auth": "10/min",
    "otp": "5/min",
    "geolocation": "30/min",
    "availability": "20/min",
    "booking": "30/min",
    "payment": "20/min",
}

# Error messages (for consistent error responses)
ERROR_MESSAGES = {
    "validation_error": {
        "ar": "خطأ في التحقق من البيانات",
        "en": "Validation error",
    },
    "authentication_error": {
        "ar": "خطأ في المصادقة",
        "en": "Authentication error",
    },
    "permission_denied": {
        "ar": "الإذن مرفوض",
        "en": "Permission denied",
    },
    "not_found": {
        "ar": "لم يتم العثور على المورد",
        "en": "Resource not found",
    },
    "service_unavailable": {
        "ar": "الخدمة غير متوفرة",
        "en": "Service unavailable",
    },
    "rate_limit_exceeded": {
        "ar": "تم تجاوز حد الطلبات",
        "en": "Rate limit exceeded",
    },
    "duplicate_resource": {
        "ar": "المورد موجود بالفعل",
        "en": "Resource already exists",
    },
    "booking_conflict": {
        "ar": "هناك تعارض في الحجز",
        "en": "Booking conflict detected",
    },
    "invalid_phone": {
        "ar": "رقم الهاتف غير صحيح",
        "en": "Invalid phone number",
    },
    "invalid_otp": {
        "ar": "رمز التحقق غير صحيح",
        "en": "Invalid OTP code",
    },
    "expired_otp": {
        "ar": "انتهت صلاحية رمز التحقق",
        "en": "OTP code has expired",
    },
    "payment_failed": {
        "ar": "فشلت عملية الدفع",
        "en": "Payment failed",
    },
    "unavailable_slot": {
        "ar": "الموعد غير متاح",
        "en": "Time slot unavailable",
    },
    "invalid_file": {
        "ar": "ملف غير صالح",
        "en": "Invalid file",
    },
}

# Content moderation
MAX_FILE_SIZE_MB = 10  # 10 MB max upload size
ALLOWED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
ALLOWED_VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi"]
ALLOWED_AUDIO_EXTENSIONS = [".mp3", ".wav", ".m4a"]

# Security constants
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
PHONE_VERIFICATION_ATTEMPTS = 5
JWT_EXPIRY_MINUTES = 60
REFRESH_TOKEN_EXPIRY_DAYS = 7

# Internationalization
DEFAULT_LANGUAGE = "ar"  # Default language for Saudi Arabian market
DEFAULT_TIMEZONE = "Asia/Riyadh"  # Default timezone for Saudi Arabian market
DEFAULT_COUNTRY = "SA"  # Default country code (Saudi Arabia)

# Pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
SMALL_PAGE_SIZE = 10
LARGE_PAGE_SIZE = 50

# Geolocation
DEFAULT_NEARBY_RADIUS_KM = 10
MAX_NEARBY_RADIUS_KM = 50
EARTH_RADIUS_KM = 6371  # Earth radius in kilometers for distance calculations

# Queue settings
DEFAULT_QUEUE_CAPACITY = 30
REMINDER_TIMES_MINUTES = [5, 15, 30, 60]  # Reminder times in minutes before appointment

# Cache timeout defaults (seconds)
CACHE_TIMEOUT_SHORT = 60  # 1 minute
CACHE_TIMEOUT_MEDIUM = 300  # 5 minutes
CACHE_TIMEOUT_LONG = 3600  # 1 hour
CACHE_TIMEOUT_EXTRA_LONG = 86400  # 24 hours

# Feature flags
FEATURE_FLAGS = {
    "enable_push_notifications": True,
    "enable_email_notifications": True,
    "enable_sms_notifications": True,
    "enable_chat": True,
    "enable_reels": True,
    "enable_stories": True,
    "enable_in_home_services": True,
    "enable_package_bookings": True,
    "enable_specialist_recommendations": True,
    "enable_ratings": True,
    "enable_analytics": True,
}

# Database schema migration strategy
DATABASE_MIGRATION_CHUNK_SIZE = 1000  # Number of records to process in each batch
