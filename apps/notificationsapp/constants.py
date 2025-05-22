"""
Constants for the notifications app.
"""

import os

from django.conf import settings

# Default maximum notifications to keep per user (for cleanup task)
DEFAULT_MAX_NOTIFICATIONS = 100

# Webhook secret key from settings or environment variable
DEFAULT_WEBHOOK_SECRET = getattr(
    settings,
    "NOTIFICATION_WEBHOOK_SECRET",
    os.environ.get("NOTIFICATION_WEBHOOK_SECRET", ""),
)

# If no secret is provided in settings or env vars, raise a warning
if not DEFAULT_WEBHOOK_SECRET:
    import warnings

    warnings.warn(
        "No NOTIFICATION_WEBHOOK_SECRET provided in settings or environment variables. "
        "This is insecure and should be fixed before deployment.",
        UserWarning,
    )

# Default Firebase service account file path
DEFAULT_FIREBASE_CREDENTIALS = getattr(
    settings, "FIREBASE_CREDENTIALS_PATH", "credentials/firebase-service-account.json"
)

# Default APNs certificate path
DEFAULT_APNS_CERT_PATH = getattr(
    settings, "APNS_CERT_PATH", "credentials/apns-cert.pem"
)

# Default VAPID keys for Web Push
DEFAULT_VAPID_PUBLIC_KEY = getattr(settings, "VAPID_PUBLIC_KEY", None)
DEFAULT_VAPID_PRIVATE_KEY = getattr(settings, "VAPID_PRIVATE_KEY", None)
DEFAULT_VAPID_CLAIM_EMAIL = getattr(settings, "VAPID_CLAIM_EMAIL", "admin@queueme.net")

# Notification scheduler settings
DEFAULT_BATCH_SIZE = getattr(settings, "NOTIFICATION_BATCH_SIZE", 100)
DEFAULT_RATE_LIMIT = getattr(
    settings, "NOTIFICATION_RATE_LIMIT", 60
)  # notifications per minute

# Channel priorities (higher is more important)
CHANNEL_PRIORITIES = {"push": 3, "sms": 4, "in_app": 2, "email": 1}
