"""
Notification System Enumerations

This module defines the enumerations used in the notification system
for consistency across the application.
"""

from enum import Enum


class NotificationType(str, Enum):
    """Types of notifications that can be sent to users"""

    BOOKING_CREATED = "booking_created"
    BOOKING_UPDATED = "booking_updated"
    BOOKING_CANCELLED = "booking_cancelled"
    BOOKING_REMINDER = "booking_reminder"
    BOOKING_COMPLETED = "booking_completed"
    QUEUE_UPDATE = "queue_update"
    QUEUE_CALL = "queue_call"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    NEW_MESSAGE = "new_message"
    SYSTEM_UPDATE = "system_update"
    MARKETING = "marketing"
    DISCOUNT_OFFER = "discount_offer"
    NEW_REEL = "new_reel"
    NEW_STORY = "new_story"
    REVIEW_REQUEST = "review_request"
    NEW_REVIEW = "new_review"
    NEW_FOLLOWER = "new_follower"


class NotificationDeliveryStatus(str, Enum):
    """Status of a notification delivery attempt"""

    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"
    READ = "read"


class DeliveryChannel(str, Enum):
    """Channels through which notifications can be delivered"""

    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"
    WEBSOCKET = "websocket"


class NotificationPriority(str, Enum):
    """Priority levels for notifications"""

    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
