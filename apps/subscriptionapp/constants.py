# apps/subscriptionapp/constants.py
from datetime import timedelta

from django.utils.translation import gettext_lazy as _

# Subscription statuses
STATUS_INITIATED = "initiated"
STATUS_ACTIVE = "active"
STATUS_PAST_DUE = "past_due"
STATUS_CANCELED = "canceled"
STATUS_EXPIRED = "expired"
STATUS_TRIAL = "trial"

SUBSCRIPTION_STATUS_CHOICES = (
    (STATUS_INITIATED, _("Initiated")),
    (STATUS_ACTIVE, _("Active")),
    (STATUS_PAST_DUE, _("Past Due")),
    (STATUS_CANCELED, _("Canceled")),
    (STATUS_EXPIRED, _("Expired")),
    (STATUS_TRIAL, _("Trial")),
)

# Subscription periods
PERIOD_MONTHLY = "monthly"
PERIOD_QUARTERLY = "quarterly"
PERIOD_SEMI_ANNUAL = "semi_annual"
PERIOD_ANNUAL = "annual"

SUBSCRIPTION_PERIOD_CHOICES = (
    (PERIOD_MONTHLY, _("Monthly")),
    (PERIOD_QUARTERLY, _("Quarterly")),
    (PERIOD_SEMI_ANNUAL, _("Semi-Annual")),
    (PERIOD_ANNUAL, _("Annual")),
)

# Period to days mapping
PERIOD_DAYS = {
    PERIOD_MONTHLY: 30,
    PERIOD_QUARTERLY: 90,
    PERIOD_SEMI_ANNUAL: 180,
    PERIOD_ANNUAL: 365,
}

# Period to timedelta mapping
PERIOD_TIMEDELTA = {
    PERIOD_MONTHLY: timedelta(days=30),
    PERIOD_QUARTERLY: timedelta(days=90),
    PERIOD_SEMI_ANNUAL: timedelta(days=180),
    PERIOD_ANNUAL: timedelta(days=365),
}

# Period to discount percentage (annual plans are cheaper)
PERIOD_DISCOUNT = {
    PERIOD_MONTHLY: 0,  # No discount
    PERIOD_QUARTERLY: 5,  # 5% discount
    PERIOD_SEMI_ANNUAL: 10,  # 10% discount
    PERIOD_ANNUAL: 15,  # 15% discount
}

# Feature categories
FEATURE_CATEGORY_SHOPS = "shops"
FEATURE_CATEGORY_SERVICES = "services"
FEATURE_CATEGORY_SPECIALISTS = "specialists"
FEATURE_CATEGORY_CONTENT = "content"
FEATURE_CATEGORY_ANALYTICS = "analytics"
FEATURE_CATEGORY_SUPPORT = "support"

FEATURE_CATEGORY_CHOICES = (
    (FEATURE_CATEGORY_SHOPS, _("Shops/Branches")),
    (FEATURE_CATEGORY_SERVICES, _("Services")),
    (FEATURE_CATEGORY_SPECIALISTS, _("Specialists")),
    (FEATURE_CATEGORY_CONTENT, _("Content Management")),
    (FEATURE_CATEGORY_ANALYTICS, _("Analytics")),
    (FEATURE_CATEGORY_SUPPORT, _("Support")),
)

# Renewal reminder intervals (days before expiry)
RENEWAL_REMINDER_DAYS = [30, 15, 7, 3, 1]

# Maximum retry attempts for failed payments
MAX_PAYMENT_RETRY_ATTEMPTS = 3

# Grace period for past due subscriptions (days)
PAST_DUE_GRACE_PERIOD_DAYS = 5

# Feature tiers
FEATURE_TIER_BASIC = "basic"
FEATURE_TIER_STANDARD = "standard"
FEATURE_TIER_PREMIUM = "premium"
FEATURE_TIER_UNLIMITED = "unlimited"

FEATURE_TIER_CHOICES = (
    (FEATURE_TIER_BASIC, _("Basic")),
    (FEATURE_TIER_STANDARD, _("Standard")),
    (FEATURE_TIER_PREMIUM, _("Premium")),
    (FEATURE_TIER_UNLIMITED, _("Unlimited")),
)

# Moyasar specific constants
MOYASAR_SOURCE_TYPE = "credit_card"

# Webhook event types
EVENT_PAYMENT_SUCCEEDED = "payment.succeeded"
EVENT_PAYMENT_FAILED = "payment.failed"
EVENT_SUBSCRIPTION_CREATED = "subscription.created"
EVENT_SUBSCRIPTION_UPDATED = "subscription.updated"
EVENT_SUBSCRIPTION_CANCELED = "subscription.canceled"
