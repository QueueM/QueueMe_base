from decimal import Decimal

from django.utils.translation import gettext_lazy as _

# Payment types
PAYMENT_TYPE_CARD = "card"
PAYMENT_TYPE_STCPAY = "stcpay"
PAYMENT_TYPE_MADA = "mada"
PAYMENT_TYPE_APPLE_PAY = "apple_pay"

PAYMENT_TYPES = (
    (PAYMENT_TYPE_CARD, _("Credit/Debit Card")),
    (PAYMENT_TYPE_STCPAY, _("STC Pay")),
    (PAYMENT_TYPE_MADA, _("Mada")),
    (PAYMENT_TYPE_APPLE_PAY, _("Apple Pay")),
)

# Transaction types
TRANSACTION_TYPE_BOOKING = "booking"
TRANSACTION_TYPE_SUBSCRIPTION = "subscription"
TRANSACTION_TYPE_AD = "ad"

TRANSACTION_TYPES = (
    (TRANSACTION_TYPE_BOOKING, _("Booking Payment")),
    (TRANSACTION_TYPE_SUBSCRIPTION, _("Subscription Payment")),
    (TRANSACTION_TYPE_AD, _("Advertisement Payment")),
)

# Transaction statuses
TRANSACTION_STATUS_INITIATED = "initiated"
TRANSACTION_STATUS_PROCESSING = "processing"
TRANSACTION_STATUS_SUCCEEDED = "succeeded"
TRANSACTION_STATUS_FAILED = "failed"
TRANSACTION_STATUS_REFUNDED = "refunded"
TRANSACTION_STATUS_PARTIALLY_REFUNDED = "partially_refunded"

TRANSACTION_STATUSES = (
    (TRANSACTION_STATUS_INITIATED, _("Initiated")),
    (TRANSACTION_STATUS_PROCESSING, _("Processing")),
    (TRANSACTION_STATUS_SUCCEEDED, _("Succeeded")),
    (TRANSACTION_STATUS_FAILED, _("Failed")),
    (TRANSACTION_STATUS_REFUNDED, _("Refunded")),
    (TRANSACTION_STATUS_PARTIALLY_REFUNDED, _("Partially Refunded")),
)

# Refund statuses
REFUND_STATUS_INITIATED = "initiated"
REFUND_STATUS_PROCESSING = "processing"
REFUND_STATUS_SUCCEEDED = "succeeded"
REFUND_STATUS_FAILED = "failed"

REFUND_STATUSES = (
    (REFUND_STATUS_INITIATED, _("Initiated")),
    (REFUND_STATUS_PROCESSING, _("Processing")),
    (REFUND_STATUS_SUCCEEDED, _("Succeeded")),
    (REFUND_STATUS_FAILED, _("Failed")),
)

# Rate limits
MAX_PAYMENT_ATTEMPTS_PER_HOUR = 5
MAX_PAYMENT_ATTEMPTS_PER_DAY = 20
MAX_CARD_SAVE_ATTEMPTS_PER_DAY = 10

# Risk thresholds
LARGE_AMOUNT_THRESHOLD = Decimal("5000.00")  # SAR
UNUSUAL_TRANSACTION_THRESHOLD = Decimal("10000.00")  # SAR
VELOCITY_THRESHOLD = 10  # transactions per hour
NEW_PAYMENT_METHOD_RISK_SCORE = 0.3
LARGE_AMOUNT_RISK_SCORE = 0.4
VELOCITY_RISK_SCORE = 0.5
HIGH_RISK_THRESHOLD = 0.7

# Performance metrics
DEFAULT_PAYMENT_METHOD_BONUS = 5.0
USAGE_WEIGHT = 3.0
SUCCESS_RATE_WEIGHT = 4.0
RECENTLY_ADDED_BONUS = 2.0
GENERIC_METHOD_SCORE = 1.0

# Moyasar configuration
MOYASAR_BASE_URL = "https://api.moyasar.com/v1"
MOYASAR_WEBHOOK_EVENTS = [
    "payment.created",
    "payment.paid",
    "payment.failed",
    "payment.refunded",
]
