# apps/discountapp/constants.py
from django.utils.translation import gettext_lazy as _

# Discount Status Constants
STATUS_ACTIVE = "active"
STATUS_SCHEDULED = "scheduled"
STATUS_EXPIRED = "expired"
STATUS_PAUSED = "paused"
STATUS_CANCELLED = "cancelled"

# Discount Type Constants
TYPE_PERCENTAGE = "percentage"
TYPE_FIXED = "fixed"

# Campaign Type Constants
CAMPAIGN_HOLIDAY = "holiday"
CAMPAIGN_SEASONAL = "seasonal"
CAMPAIGN_FLASH_SALE = "flash_sale"
CAMPAIGN_PRODUCT_LAUNCH = "product_launch"
CAMPAIGN_LOYALTY = "loyalty"
CAMPAIGN_REFERRAL = "referral"

# Error Messages
ERROR_CODE_INVALID = _("Invalid coupon code.")
ERROR_CODE_EXPIRED = _("This coupon code has expired.")
ERROR_CODE_USAGE_LIMIT = _("This coupon has reached its usage limit.")
ERROR_CODE_DATE_RANGE = _("This coupon is not valid for the current date.")
ERROR_CODE_MIN_AMOUNT = _("The purchase amount does not meet the minimum required.")
ERROR_CODE_ALREADY_USED = _("You have already used this coupon.")
ERROR_CODE_NOT_ELIGIBLE = _("This coupon cannot be applied to the selected services.")
ERROR_CODE_AUTHENTICATION = _("You must be logged in to use this coupon.")

# Success Messages
SUCCESS_DISCOUNT_APPLIED = _("Discount has been successfully applied.")
SUCCESS_COUPON_APPLIED = _("Coupon code has been successfully applied.")
SUCCESS_COUPON_CREATED = _("Coupon has been successfully created.")
SUCCESS_COUPON_REMOVED = _("Coupon has been successfully removed.")

# Validation Constants
MAX_COUPON_CODE_LENGTH = 20
MIN_COUPON_CODE_LENGTH = 4
MAX_DISCOUNT_PERCENT = 100
MIN_DISCOUNT_PERCENT = 0

# System Constants
COUPON_BATCH_SIZE = 100
DEFAULT_COUPON_PREFIX = "QM"
DEFAULT_COUPON_LENGTH = 8
DEFAULT_REFERRAL_DISCOUNT = 10  # Percentage
DEFAULT_PRIORITY = 5  # Medium priority
