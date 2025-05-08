import logging

from django.core.cache import cache

from apps.authapp.constants import MAX_OTP_REQUESTS_PER_HOUR

logger = logging.getLogger(__name__)


class SecurityService:
    """
    Service for security-related functionality like rate limiting.
    """

    @staticmethod
    def is_rate_limited(identifier, action_type):
        """
        Check if a given identifier (e.g., phone number, IP) is rate limited for an action.

        Args:
            identifier: The identifier to check (e.g., phone number)
            action_type: The type of action (e.g., 'otp', 'login')

        Returns:
            bool: True if rate limited, False otherwise
        """
        cache_key = f"rate_limit:{action_type}:{identifier}"

        # Get the current count
        count = cache.get(cache_key, 0)

        # Determine limits based on action type
        if action_type == "otp":
            max_attempts = MAX_OTP_REQUESTS_PER_HOUR
            ttl = 3600  # 1 hour in seconds
        elif action_type == "login":
            max_attempts = 10  # Example: 10 login attempts per hour
            ttl = 3600  # 1 hour in seconds
        elif action_type == "verification":
            max_attempts = 15  # Example: 15 verification attempts per hour
            ttl = 3600  # 1 hour in seconds
        else:
            # Default rate limit for unknown actions
            max_attempts = 30
            ttl = 3600  # 1 hour in seconds

        # Check if rate limited
        if count >= max_attempts:
            logger.warning(
                f"Rate limit exceeded for {action_type} by {identifier}: {count} attempts"
            )
            return True

        # Increment the counter
        new_count = count + 1

        # Only set the cache if it doesn't exist or update the count
        # Use add() for first time, incr() for subsequent times to avoid race conditions
        if count == 0:
            # Set expiration for first time
            cache.add(cache_key, 1, ttl)
        else:
            cache.incr(cache_key)

        logger.debug(
            f"Rate limit check for {action_type} by {identifier}: {new_count}/{max_attempts}"
        )
        return False

    @staticmethod
    def record_security_event(user_id, event_type, details, severity="info"):
        """
        Record a security-related event for auditing purposes.

        Args:
            user_id: ID of the affected user
            event_type: Type of security event (e.g., 'login_success', 'login_failure')
            details: Additional details about the event
            severity: Severity level (e.g., 'info', 'warning', 'critical')
        """
        # In a full implementation, this would likely log to a database table
        # For now, we'll just log to the standard logger
        log_message = f"SECURITY EVENT [{severity.upper()}] {event_type} User: {user_id} - {details}"

        if severity == "critical":
            logger.critical(log_message)
        elif severity == "warning":
            logger.warning(log_message)
        else:
            logger.info(log_message)

    @staticmethod
    def clear_rate_limit(identifier, action_type):
        """
        Clear rate limit for a specific identifier and action type.
        Useful for testing or manual intervention.

        Args:
            identifier: The identifier to clear (e.g., phone number)
            action_type: The type of action (e.g., 'otp', 'login')
        """
        cache_key = f"rate_limit:{action_type}:{identifier}"
        cache.delete(cache_key)
        logger.info(f"Rate limit cleared for {action_type} by {identifier}")
