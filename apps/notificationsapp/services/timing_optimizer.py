import logging

from django.utils import timezone

from apps.authapp.models import User
from apps.notificationsapp.models import Notification

logger = logging.getLogger(__name__)


class TimingOptimizer:
    """
    Sophisticated algorithm to determine optimal notification delivery time
    based on user activity patterns, response rates, and notification type.
    """

    # Maximum delay for different notification types (in hours)
    MAX_DELAY = {
        "appointment_confirmation": 1,  # Quick but not immediate
        "appointment_reminder": 2,  # Some flexibility
        "appointment_cancellation": 0.5,  # Relatively urgent
        "appointment_reschedule": 0.5,  # Relatively urgent
        "queue_status_update": 0.5,  # Relatively urgent
        "queue_join_confirmation": 0,  # Immediate
        "queue_called": 0,  # Immediate
        "new_message": 0.1,  # Almost immediate
        "payment_confirmation": 0.5,  # Relatively urgent
        "service_feedback": 12,  # Very flexible
        "welcome": 0,  # Immediate
        "verification_code": 0,  # Immediate
        "password_reset": 0,  # Immediate
    }

    # Weights for different factors
    ACTIVITY_WEIGHT = 0.7
    EFFECTIVENESS_WEIGHT = 0.3

    @staticmethod
    def determine_optimal_send_time(user_id, notification_type):
        """
        Determine the optimal time to send a notification.
        For urgent notifications, returns None (send immediately).
        For non-urgent, may return a future timestamp.
        """
        # Get max delay for this notification type
        max_delay_hours = TimingOptimizer.MAX_DELAY.get(notification_type, 0)

        # If max delay is 0, send immediately
        if max_delay_hours <= 0:
            return None

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"Cannot optimize timing: User {user_id} does not exist")
            return None

        # Get current time in user's timezone
        user_timezone = getattr(user, "timezone", timezone.get_current_timezone())
        current_time = timezone.now().astimezone(user_timezone)

        # Get user's activity pattern
        activity_pattern = TimingOptimizer._get_user_activity_pattern(user)

        # Get notification effectiveness by hour
        hourly_effectiveness = TimingOptimizer._get_notification_effectiveness(
            notification_type=notification_type
        )

        # Combine activity pattern with effectiveness
        hourly_scores = {}
        for hour in range(24):
            activity_score = activity_pattern.get(hour, 0)
            effectiveness_score = hourly_effectiveness.get(hour, 0.5)

            hourly_scores[hour] = (activity_score * TimingOptimizer.ACTIVITY_WEIGHT) + (
                effectiveness_score * TimingOptimizer.EFFECTIVENESS_WEIGHT
            )

        # Find best hour in the near future (within max delay)
        current_hour = current_time.hour
        max_delay_hours = int(max_delay_hours)

        best_hour = TimingOptimizer._find_best_hour_in_range(
            hourly_scores=hourly_scores,
            current_hour=current_hour,
            max_delay_hours=max_delay_hours,
        )

        # If best hour is current hour, send immediately
        if best_hour == current_hour:
            return None

        # Calculate exact send time
        if best_hour < current_hour:
            # Best hour is tomorrow
            target_day = current_time.date() + timezone.timedelta(days=1)
        else:
            # Best hour is today
            target_day = current_time.date()

        target_time = timezone.datetime(
            year=target_day.year,
            month=target_day.month,
            day=target_day.day,
            hour=best_hour,
            minute=0,
            second=0,
            tzinfo=user_timezone,
        )

        # Ensure it's within max delay
        max_delay_timestamp = current_time + timezone.timedelta(hours=max_delay_hours)
        if target_time > max_delay_timestamp:
            # If optimal time is too far in future, use max delay
            return max_delay_timestamp

        return target_time

    @staticmethod
    def _get_user_activity_pattern(user):
        """
        Analyze user's activity pattern by hour of day.
        Returns dict of hour (0-23) -> activity score (0.0-1.0)
        """
        # Look at when user reads notifications
        read_notifications = Notification.objects.filter(
            user=user, status="read", read_at__isnull=False
        ).order_by("-read_at")[
            :100
        ]  # Look at recent 100 read notifications

        # Compile hourly activity
        hourly_counts = {hour: 0 for hour in range(24)}

        for notification in read_notifications:
            # Convert to user's timezone
            user_timezone = getattr(user, "timezone", timezone.get_current_timezone())
            read_time = notification.read_at.astimezone(user_timezone)
            hour = read_time.hour
            hourly_counts[hour] += 1

        # Convert to scores (0.0-1.0)
        total = sum(hourly_counts.values())
        if total == 0:
            # No data, use default activity pattern
            return TimingOptimizer._get_default_activity_pattern()

        hourly_scores = {}
        for hour, count in hourly_counts.items():
            hourly_scores[hour] = count / total

        return hourly_scores

    @staticmethod
    def _get_notification_effectiveness(notification_type):
        """
        Get historical effectiveness of notifications by hour of day.
        Effectiveness = likelihood of being read/acted upon.

        Returns dict of hour (0-23) -> effectiveness score (0.0-1.0)
        """
        # Ideally, this would analyze historical data for each notification type
        # For simplicity, we'll use reasonable defaults based on type

        # General effectiveness by hour (higher is better)
        general_effectiveness = {
            0: 0.2,  # Midnight
            1: 0.1,
            2: 0.1,
            3: 0.1,
            4: 0.1,
            5: 0.2,
            6: 0.4,
            7: 0.6,
            8: 0.8,
            9: 0.9,  # Morning
            10: 0.9,
            11: 0.9,
            12: 0.8,  # Noon
            13: 0.7,
            14: 0.7,
            15: 0.7,
            16: 0.8,
            17: 0.9,  # End of workday
            18: 0.9,
            19: 0.8,
            20: 0.7,
            21: 0.6,
            22: 0.4,
            23: 0.3,  # Late evening
        }

        # Adjust for specific notification types
        if notification_type in ["appointment_reminder", "appointment_confirmation"]:
            # Reminders are best in evening or morning
            for hour in range(24):
                if 18 <= hour <= 21:  # Evening
                    general_effectiveness[hour] = max(general_effectiveness[hour], 0.9)
                elif 7 <= hour <= 9:  # Morning
                    general_effectiveness[hour] = max(general_effectiveness[hour], 0.9)

        elif notification_type in ["service_feedback"]:
            # Feedback requests best in evening when people have time
            for hour in range(24):
                if 19 <= hour <= 21:  # Evening
                    general_effectiveness[hour] = max(general_effectiveness[hour], 0.9)

        return general_effectiveness

    @staticmethod
    def _get_default_activity_pattern():
        """Default activity pattern for users with no data"""
        return {
            0: 0.01,  # Midnight
            1: 0.01,
            2: 0.01,
            3: 0.01,
            4: 0.01,
            5: 0.02,
            6: 0.05,
            7: 0.08,
            8: 0.10,  # Morning
            9: 0.10,
            10: 0.07,
            11: 0.05,
            12: 0.05,  # Noon
            13: 0.05,
            14: 0.04,
            15: 0.04,
            16: 0.05,
            17: 0.07,  # End of workday
            18: 0.07,
            19: 0.08,
            20: 0.05,
            21: 0.05,
            22: 0.03,
            23: 0.02,  # Late evening
        }

    @staticmethod
    def _find_best_hour_in_range(hourly_scores, current_hour, max_delay_hours):
        """
        Find the hour with the highest score within allowed delay range.
        Handles wraparound to next day.
        """
        # Generate list of hours in the allowed range
        allowed_hours = []
        for offset in range(max_delay_hours + 1):
            hour = (current_hour + offset) % 24
            allowed_hours.append(hour)

        # Find hour with highest score
        best_hour = current_hour
        best_score = hourly_scores.get(current_hour, 0)

        for hour in allowed_hours:
            score = hourly_scores.get(hour, 0)
            if score > best_score:
                best_score = score
                best_hour = hour

        return best_hour
