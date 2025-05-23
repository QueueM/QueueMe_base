"""
Security Service Module for QueueMe Backend

This module provides comprehensive security features for user authentication,
account protection, and system integrity. It handles rate limiting, account locking,
password history, token management, and security event tracking.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from apps.authapp.constants import (
    ACCOUNT_LOCK_DURATION,
    MAX_FAILED_LOGIN_ATTEMPTS,
    PASSWORD_HISTORY_COUNT,
    RATE_LIMIT_PERIODS,
)
from apps.authapp.models import AuthToken, LoginAttempt

# Configure logging
logger = logging.getLogger(__name__)

# User model
User = get_user_model()


class SecurityService:
    """
    Service for security-related functionality.

    This service handles:
    - Rate limiting for various actions (login, OTP, API calls)
    - Account locking after failed login attempts
    - Login attempt tracking and analysis
    - Password history management and enforcement
    - Security token management
    - Security event monitoring and alerting

    All methods use appropriate caching and database operations to ensure
    security measures are applied consistently and efficiently.
    """

    @classmethod
    def is_rate_limited(cls, key: str, action_type: str) -> bool:
        """
        Check if an action is rate limited.

        This method implements a sliding window rate limiting algorithm
        to prevent abuse of sensitive operations.

        Args:
            key: Identifier for the rate limit (username, phone, IP)
            action_type: Type of action being rate limited (login, otp, api)

        Returns:
            bool: True if rate limited, False otherwise

        Raises:
            ValueError: If action_type is not supported
        """
        if action_type not in RATE_LIMIT_PERIODS:
            raise ValueError(f"Unsupported rate limit action type: {action_type}")

        # Get rate limit configuration
        limit_config = RATE_LIMIT_PERIODS[action_type]
        max_attempts = limit_config["max_attempts"]
        window_seconds = limit_config["window_seconds"]

        # Create cache key
        cache_key = f"rate_limit:{action_type}:{key.lower()}"

        # Get current timestamp
        now = time.time()

        # Get existing timestamps from cache
        timestamps = cache.get(cache_key, [])

        # Filter out timestamps outside the window
        valid_timestamps = [ts for ts in timestamps if now - ts < window_seconds]

        # Check if rate limited
        is_limited = len(valid_timestamps) >= max_attempts

        # Add current timestamp and update cache
        valid_timestamps.append(now)
        cache.set(cache_key, valid_timestamps, window_seconds * 2)

        if is_limited:
            logger.warning(f"Rate limit exceeded for {action_type}: {key}")

        return is_limited

    @classmethod
    def is_account_locked(cls, username: str) -> bool:
        """
        Check if an account is locked due to failed login attempts.

        Args:
            username: Username or email to check

        Returns:
            bool: True if account is locked, False otherwise
        """
        lock_key = f"account_lock:{username.lower()}"
        return bool(cache.get(lock_key))

    @classmethod
    def lock_account(
        cls, username: str, duration_minutes: int = ACCOUNT_LOCK_DURATION
    ) -> None:
        """
        Lock an account for a specified duration.

        This method is typically called after multiple failed login attempts
        to prevent brute force attacks.

        Args:
            username: Username or email to lock
            duration_minutes: Duration of lock in minutes
        """
        lock_key = f"account_lock:{username.lower()}"
        cache.set(lock_key, True, duration_minutes * 60)

        # Try to update user's locked_until field if user exists
        User = get_user_model()
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email__iexact=username)
            except User.DoesNotExist:
                user = None

        if user:
            user.locked_until = timezone.now() + timedelta(minutes=duration_minutes)
            user.save(update_fields=["locked_until"])

            # Create security event record
            cls.record_security_event(
                user_id=user.id,
                event_type="account_locked",
                details={
                    "reason": "failed_login_attempts",
                    "duration_minutes": duration_minutes,
                },
            )

        logger.warning(f"Account locked for {duration_minutes} minutes: {username}")

    @classmethod
    def unlock_account(cls, username: str) -> bool:
        """
        Manually unlock an account.

        This method is typically used by administrators to unlock
        accounts that were automatically locked due to security measures.

        Args:
            username: Username or email to unlock

        Returns:
            bool: True if account was unlocked, False if it wasn't locked
        """
        lock_key = f"account_lock:{username.lower()}"
        was_locked = bool(cache.get(lock_key))

        if was_locked:
            cache.delete(lock_key)

            # Try to update user's locked_until field if user exists
            User = get_user_model()
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                try:
                    user = User.objects.get(email__iexact=username)
                except User.DoesNotExist:
                    user = None

            if user:
                user.locked_until = None
                user.save(update_fields=["locked_until"])

                # Create security event record
                cls.record_security_event(
                    user_id=user.id,
                    event_type="account_unlocked",
                    details={"reason": "manual_unlock"},
                )

            logger.info(f"Account manually unlocked: {username}")

        return was_locked

    @classmethod
    def record_login_failure(
        cls,
        username: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Record a failed login attempt.

        This method tracks failed login attempts for security monitoring
        and triggers account locking when thresholds are exceeded.

        Args:
            username: Username or email that failed
            ip_address: IP address of the client
            user_agent: User agent string
        """
        # Convert username to lowercase for consistency
        username = username.lower()

        # Increment failed login counter in cache
        counter_key = f"failed_logins:{username}"
        count = cache.get(counter_key, 0)
        new_count = count + 1
        cache.set(counter_key, new_count, 12 * 3600)  # Store for 12 hours

        # Try to create a login attempt record if we can find the user
        User = get_user_model()
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email__iexact=username)
            except User.DoesNotExist:
                user = None

        if user:
            LoginAttempt.objects.create(
                user=user, success=False, ip_address=ip_address, user_agent=user_agent
            )

            # Create security event record
            cls.record_security_event(
                user_id=user.id,
                event_type="login_failure",
                details={"ip_address": ip_address, "attempt_number": new_count},
            )

        # Check if we should lock the account
        if new_count >= MAX_FAILED_LOGIN_ATTEMPTS:
            cls.lock_account(username)

    @classmethod
    def record_login_success(
        cls,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Record a successful login.

        This method tracks successful logins for security monitoring
        and clears failed login counters.

        Args:
            user_id: ID of the user who logged in
            ip_address: IP address of the client
            user_agent: User agent string
        """
        user = User.objects.get(id=user_id)

        # Create login attempt record
        LoginAttempt.objects.create(
            user=user, success=True, ip_address=ip_address, user_agent=user_agent
        )

        # Clear failed login counter
        cls.clear_failed_login_attempts(user.username)
        cls.clear_failed_login_attempts(user.email)

        # Create security event record
        cls.record_security_event(
            user_id=user_id,
            event_type="login_success",
            details={"ip_address": ip_address},
        )

    @classmethod
    def get_failed_login_count(cls, username: str) -> int:
        """
        Get the number of failed login attempts for a username.

        Args:
            username: Username or email to check

        Returns:
            int: Number of failed login attempts
        """
        counter_key = f"failed_logins:{username.lower()}"
        return cache.get(counter_key, 0)

    @classmethod
    def clear_failed_login_attempts(cls, username: str) -> None:
        """
        Clear failed login attempts for a username.

        This method is typically called after a successful login
        to reset the failed attempt counter.

        Args:
            username: Username or email to clear
        """
        if not username:
            return

        counter_key = f"failed_logins:{username.lower()}"
        cache.delete(counter_key)

    @classmethod
    def track_successful_verification(cls, identifier: str) -> None:
        """
        Track successful verification events.

        This method is used to monitor successful verifications
        for security analysis and pattern detection.

        Args:
            identifier: Identifier that was verified (phone, email)
        """
        # Create cache key
        cache_key = f"verification_success:{identifier.lower()}"

        # Get current timestamp
        now = time.time()

        # Get existing timestamps from cache
        timestamps = cache.get(cache_key, [])

        # Add current timestamp and update cache (keep last 10)
        timestamps.append(now)
        timestamps = timestamps[-10:]
        cache.set(cache_key, timestamps, 24 * 3600)  # Store for 24 hours

    # Password history methods
    @classmethod
    def add_password_to_history(cls, user) -> None:
        """
        Add the user's current password to their password history.

        This method is used to prevent password reuse by tracking
        previously used passwords.

        Args:
            user: User object whose password should be added to history
        """
        # Get current password history
        password_history = user.password_history or []

        # Add current password with timestamp
        current_password = {
            "password": user.password,
            "set_at": timezone.now().isoformat(),
        }

        # Add to history and keep only the last PASSWORD_HISTORY_COUNT entries
        password_history.insert(0, current_password)
        password_history = password_history[:PASSWORD_HISTORY_COUNT]

        # Update user
        user.password_history = password_history
        user.save(update_fields=["password_history"])

        # Create security event record
        cls.record_security_event(
            user_id=user.id, event_type="password_changed", details={}
        )

    @classmethod
    def is_password_in_history(cls, user, new_password: str) -> bool:
        """
        Check if a password exists in the user's password history.

        This method prevents users from reusing recent passwords,
        which is an important security best practice.

        Args:
            user: User object
            new_password: Password to check against history

        Returns:
            bool: True if password is in history, False otherwise
        """
        if not user.password_history:
            return False

        # Check current password first
        if user.check_password(new_password):
            return True

        # Check against password history
        for entry in user.password_history:
            # The stored passwords are already hashed, so we need to use constant-time comparison
            stored_password = entry.get("password")
            if stored_password and stored_password.startswith(
                ("pbkdf2_sha256$", "bcrypt$", "argon2")
            ):
                # This is a proper Django password hash
                # We need to create a temporary user with this password to check it
                temp_user = User(password=stored_password)
                if temp_user.check_password(new_password):
                    return True

        return False

    # Token management methods
    @classmethod
    def invalidate_user_tokens(cls, user_id: str, reason: Optional[str] = None) -> int:
        """
        Invalidate all tokens for a user.

        This method is used when a user's security status changes,
        such as during password changes, suspicious activity, or logout.

        Args:
            user_id: ID of the user
            reason: Optional reason for invalidation

        Returns:
            int: Number of tokens invalidated
        """
        tokens = AuthToken.objects.filter(user_id=user_id, is_active=True)
        count = tokens.count()

        tokens.update(
            is_active=False,
            revoked_at=timezone.now(),
            revocation_reason=reason or "admin_revoked",
        )

        if count > 0:
            # Create security event record
            cls.record_security_event(
                user_id=user_id,
                event_type="tokens_invalidated",
                details={"count": count, "reason": reason or "admin_revoked"},
            )

            logger.info(f"Invalidated {count} tokens for user {user_id}")

        return count

    @classmethod
    def invalidate_specific_token(
        cls, token_id: str, reason: Optional[str] = None
    ) -> bool:
        """
        Invalidate a specific token.

        This method is used for targeted token revocation, such as
        when a user logs out from a specific device.

        Args:
            token_id: ID of the token to invalidate
            reason: Optional reason for invalidation

        Returns:
            bool: True if token was invalidated, False if not found
        """
        try:
            token = AuthToken.objects.get(id=token_id, is_active=True)
            token.is_active = False
            token.revoked_at = timezone.now()
            token.revocation_reason = reason or "user_revoked"
            token.save(update_fields=["is_active", "revoked_at", "revocation_reason"])

            # Create security event record
            cls.record_security_event(
                user_id=token.user_id,
                event_type="token_invalidated",
                details={"token_id": token_id, "reason": reason or "user_revoked"},
            )

            logger.info(f"Invalidated token {token_id} for user {token.user_id}")
            return True
        except AuthToken.DoesNotExist:
            return False

    @classmethod
    def record_security_event(
        cls, user_id: str, event_type: str, details: Dict[str, Any]
    ) -> None:
        """
        Record a security event for monitoring and auditing.

        This method creates a record of security-related events
        that can be used for security analysis and compliance reporting.

        Args:
            user_id: ID of the user associated with the event
            event_type: Type of security event
            details: Additional details about the event
        """
        # In a production system, this would write to a security event log
        # For now, we'll just log it
        logger.info(f"Security event: {event_type} for user {user_id} - {details}")

        # In a real implementation, we would store this in a database
        # SecurityEvent.objects.create(
        #     user_id=user_id,
        #     event_type=event_type,
        #     details=details,
        #     timestamp=timezone.now()
        # )

    @classmethod
    def get_user_security_status(cls, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive security status for a user.

        This method aggregates security information about a user
        for administrative and monitoring purposes.

        Args:
            user_id: ID of the user

        Returns:
            dict: Security status information
        """
        try:
            user = User.objects.get(id=user_id)

            # Get login attempts
            recent_attempts = LoginAttempt.objects.filter(user=user).order_by(
                "-timestamp"
            )[:10]

            # Get active tokens
            active_tokens = AuthToken.objects.filter(
                user_id=user_id, is_active=True
            ).count()

            # Calculate days since last password change
            last_password_change = None
            if user.password_history and len(user.password_history) > 0:
                try:
                    last_set_at = user.password_history[0].get("set_at")
                    if last_set_at:
                        last_password_change = (
                            timezone.now() - datetime.fromisoformat(last_set_at)
                        ).days
                except (ValueError, TypeError):
                    pass

            return {
                "is_locked": cls.is_account_locked(user.username),
                "locked_until": user.locked_until,
                "failed_login_count": cls.get_failed_login_count(user.username),
                "recent_login_attempts": [
                    {
                        "timestamp": attempt.timestamp,
                        "success": attempt.success,
                        "ip_address": attempt.ip_address,
                    }
                    for attempt in recent_attempts
                ],
                "active_tokens": active_tokens,
                "last_login": user.last_login,
                "days_since_password_change": last_password_change,
                "password_history_count": len(user.password_history or []),
                "is_verified": user.is_verified,
                "two_factor_enabled": getattr(user, "two_factor_enabled", False),
            }
        except User.DoesNotExist:
            return {"error": "User not found"}
