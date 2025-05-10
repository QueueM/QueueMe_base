import logging

from django.utils import timezone

from apps.authapp.models import User
from apps.notificationsapp.models import DeviceToken, Notification

logger = logging.getLogger(__name__)


class ChannelSelector:
    """
    Advanced algorithm for selecting optimal notification channels
    based on user preferences, engagement history, and notification type.
    """

    # Weights for different factors in channel selection
    PREFERENCE_WEIGHT = 5.0  # User preference is most important
    ENGAGEMENT_WEIGHT = 3.0  # Past engagement is very important
    COST_WEIGHT = 1.0  # Cost is a factor but less important
    URGENCY_WEIGHT = 4.0  # Urgency is important for time-sensitive notifications
    TIME_WEIGHT = 2.0  # Time of day appropriateness

    # Urgency levels for different notification types
    NOTIFICATION_URGENCY = {
        "verification_code": "critical",
        "appointment_reminder": "high",
        "queue_called": "critical",
        "queue_status_update": "high",
        "new_message": "medium",
        "appointment_confirmation": "medium",
        "appointment_cancellation": "high",
        "appointment_reschedule": "high",
        "queue_join_confirmation": "medium",
        "payment_confirmation": "medium",
        "service_feedback": "low",
        "welcome": "low",
        "password_reset": "high",
    }

    # Channel cost factors (higher is more expensive)
    CHANNEL_COSTS = {
        "sms": 1.0,  # Most expensive
        "push": 0.1,  # Very low cost
        "email": 0.3,  # Low cost
        "in_app": 0.0,  # Free
    }

    @staticmethod
    def select_optimal_channels(user_id, notification_type, data=None):
        """
        Select the optimal channels for a notification based on multiple factors.

        Returns: list of channel names in priority order
        """
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"Cannot select channels: User {user_id} does not exist")
            return ["in_app", "push"]  # Default fallback

        # Get user preferences if any
        preferences = ChannelSelector._get_user_preferences(user)

        # Get engagement history for this user across channels
        engagement = ChannelSelector._get_user_engagement(user)

        # Get urgency level for this notification type
        urgency = ChannelSelector.NOTIFICATION_URGENCY.get(notification_type, "medium")

        # Calculate scores for each channel
        channel_scores = {}

        for channel in ["push", "sms", "email", "in_app"]:
            # Check channel availability
            if not ChannelSelector._is_channel_available(user, channel):
                continue

            score = 0

            # User preference factor (highest weight)
            if channel in preferences:
                score += ChannelSelector.PREFERENCE_WEIGHT * 1.0

            # Engagement history factor
            engagement_rate = engagement.get(
                channel, 0.5
            )  # Default to middle if no history
            score += ChannelSelector.ENGAGEMENT_WEIGHT * engagement_rate

            # Cost factor (lower cost is better)
            cost_factor = 1.0 - (ChannelSelector.CHANNEL_COSTS.get(channel, 0.5) / 1.0)
            score += ChannelSelector.COST_WEIGHT * cost_factor

            # Urgency factor
            urgency_score = ChannelSelector._calculate_urgency_score(channel, urgency)
            score += ChannelSelector.URGENCY_WEIGHT * urgency_score

            # Time of day appropriateness (uses user's timezone)
            time_score = ChannelSelector._calculate_time_appropriateness(channel, user)
            score += ChannelSelector.TIME_WEIGHT * time_score

            channel_scores[channel] = score

        # If no scores (no available channels), return default
        if not channel_scores:
            if ChannelSelector._is_channel_available(user, "push"):
                return ["push", "in_app"]
            else:
                return ["in_app"]

        # Sort channels by score descending
        sorted_channels = sorted(
            channel_scores.keys(), key=lambda c: channel_scores[c], reverse=True
        )

        # Get critical notifications on all available high-priority channels
        if urgency == "critical":
            critical_channels = []
            if "push" in sorted_channels:
                critical_channels.append("push")
            if "sms" in sorted_channels:
                critical_channels.append("sms")
            if not critical_channels:
                critical_channels = sorted_channels[:1]  # At least one channel

            return critical_channels

        # For non-critical, return top channels (up to 2 for high urgency, 1 for others)
        if urgency == "high":
            return sorted_channels[: min(2, len(sorted_channels))]
        else:
            return sorted_channels[:1]  # Just the best channel

    @staticmethod
    def _get_user_preferences(user):
        """Get user's notification preferences"""
        # This would be based on user preference settings
        # For now, using a simple default based on available channels

        preferences = []

        # Check if user has device tokens (for push)
        has_device = DeviceToken.objects.filter(user=user, is_active=True).exists()
        if has_device:
            preferences.append("push")

        # Always include in-app
        preferences.append("in_app")

        # Include email if user has email
        if user.email:
            preferences.append("email")

        # Include SMS if user has phone (always the case)
        preferences.append("sms")

        return preferences

    @staticmethod
    def _get_user_engagement(user):
        """
        Get user's engagement rates with different notification channels
        Returns dict of channel -> engagement rate (0.0 to 1.0)
        """
        # Calculate read rate for different channels
        engagement = {}

        for channel in ["push", "sms", "email", "in_app"]:
            # Get notifications for this channel in last 30 days
            channel_notifications = Notification.objects.filter(
                user=user,
                channel=channel,
                created_at__gte=timezone.now() - timezone.timedelta(days=30),
            )

            # Skip if no notifications on this channel
            if not channel_notifications.exists():
                continue

            # Calculate percentage that were read
            total = channel_notifications.count()
            read = channel_notifications.filter(status="read").count()

            if total > 0:
                engagement[channel] = read / total
            else:
                engagement[channel] = 0.5  # Default to middle

        return engagement

    @staticmethod
    def _is_channel_available(user, channel):
        """Check if a channel is available for this user"""
        if channel == "push":
            # Need device token for push
            return DeviceToken.objects.filter(user=user, is_active=True).exists()
        elif channel == "email":
            # Need email for email notifications
            return bool(user.email)
        elif channel == "sms":
            # Need phone for SMS (always true for our system)
            return bool(user.phone_number)
        elif channel == "in_app":
            # In-app is always available
            return True

        return False

    @staticmethod
    def _calculate_urgency_score(channel, urgency):
        """Calculate how appropriate a channel is for given urgency level"""
        # Channel effectiveness by urgency
        channel_urgency_map = {
            "push": {"critical": 1.0, "high": 0.9, "medium": 0.7, "low": 0.5},
            "sms": {"critical": 1.0, "high": 0.9, "medium": 0.6, "low": 0.3},
            "email": {"critical": 0.3, "high": 0.5, "medium": 0.8, "low": 1.0},
            "in_app": {"critical": 0.7, "high": 0.8, "medium": 0.9, "low": 1.0},
        }

        # Get score from map, default to 0.5
        return channel_urgency_map.get(channel, {}).get(urgency, 0.5)

    @staticmethod
    def _calculate_time_appropriateness(channel, user):
        """Calculate how appropriate a channel is at current time of day"""
        # Get user's local time (if timezone set, otherwise use default)
        user_timezone = getattr(user, "timezone", timezone.get_current_timezone())
        current_time = timezone.now().astimezone(user_timezone)
        hour = current_time.hour

        # Channel effectiveness by hour (24h format)
        # These are simplified rules, could be more sophisticated
        if channel == "push":
            # Push is good for waking hours, not late night
            if 8 <= hour <= 22:
                return 1.0
            elif 7 <= hour < 8 or 22 < hour <= 23:
                return 0.7
            else:
                return 0.3  # Late night

        elif channel == "sms":
            # SMS should be restricted to business hours mostly
            if 9 <= hour <= 20:
                return 1.0
            elif 8 <= hour < 9 or 20 < hour <= 21:
                return 0.7
            else:
                return 0.2  # Not appropriate late night or early morning

        elif channel == "email":
            # Email is fine any time, best in morning
            if 7 <= hour <= 12:
                return 1.0  # Morning is best
            else:
                return 0.8  # Still fine other times

        elif channel == "in_app":
            # In-app depends on typical usage patterns
            if 9 <= hour <= 23:
                return 1.0  # Waking hours
            else:
                return 0.5  # Night time less likely to be seen

        return 0.5  # Default middle value
