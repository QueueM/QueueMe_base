"""
Constants for the notifications app.
"""

# Default maximum notifications to keep per user (for cleanup task)
DEFAULT_MAX_NOTIFICATIONS = 100

# Default webhook secret key (should be overridden in settings)
DEFAULT_WEBHOOK_SECRET = "change-me-in-production"

# Default Firebase service account file path
DEFAULT_FIREBASE_CREDENTIALS = "credentials/firebase-service-account.json"

# Default APNs certificate path
DEFAULT_APNS_CERT_PATH = "credentials/apns-cert.pem"

# Default VAPID keys for Web Push
DEFAULT_VAPID_PUBLIC_KEY = None
DEFAULT_VAPID_PRIVATE_KEY = None
DEFAULT_VAPID_CLAIM_EMAIL = "admin@queueme.net"

# Notification scheduler settings
DEFAULT_BATCH_SIZE = 100
DEFAULT_RATE_LIMIT = 60  # notifications per minute

# Channel priorities (higher is more important)
CHANNEL_PRIORITIES = {"push": 3, "sms": 4, "in_app": 2, "email": 1}
