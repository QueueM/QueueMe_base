import ipaddress
import logging
import secrets
import string
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from apps.authapp.constants import (
    MAX_OTP_REQUESTS_PER_DAY,
    MAX_OTP_REQUESTS_PER_HOUR,
    MAX_OTP_REQUESTS_PER_WEEK,
)
from apps.authapp.models import AuthToken, LoginAttempt, PasswordResetToken, SecurityEvent, User
from apps.notificationsapp.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Security constants
MAX_LOGIN_ATTEMPTS = getattr(settings, "MAX_LOGIN_ATTEMPTS", 5)
ACCOUNT_LOCKOUT_MINUTES = getattr(settings, "ACCOUNT_LOCKOUT_MINUTES", 30)
PASSWORD_RESET_EXPIRY_MINUTES = getattr(settings, "PASSWORD_RESET_EXPIRY_MINUTES", 30)
REQUIRE_PASSWORD_HISTORY = getattr(settings, "REQUIRE_PASSWORD_HISTORY", True)
PASSWORD_HISTORY_COUNT = getattr(settings, "PASSWORD_HISTORY_COUNT", 5)


class SecurityService:
    """
    Enhanced security service with Redis-based rate limiting and persistent logging.
    """

    # Rate limit windows
    WINDOWS = {
        "hour": 3600,  # 1 hour in seconds
        "day": 86400,  # 24 hours in seconds
        "week": 604800,  # 7 days in seconds
    }

    # Rate limits by action type and window
    RATE_LIMITS = {
        "otp": {
            "hour": MAX_OTP_REQUESTS_PER_HOUR,
            "day": MAX_OTP_REQUESTS_PER_DAY,
            "week": MAX_OTP_REQUESTS_PER_WEEK,
        },
        "login": {"hour": 10, "day": 50, "week": 200},
        "verification": {"hour": 15, "day": 75, "week": 300},
        "password_reset": {"hour": 5, "day": 10, "week": 20},
    }

    # Suspicious IP ranges (example)
    SUSPICIOUS_IP_RANGES = [
        "185.156.73.0/24",  # Known for abuse
        "193.32.161.0/24",  # Known for abuse
        "91.132.0.0/16",  # High volume of attacks
    ]

    # Brute force detection thresholds
    BRUTE_FORCE_THRESHOLDS = {
        "login": {"count": 5, "timeframe": 300},  # 5 failed attempts in 5 minutes
        "otp": {"count": 4, "timeframe": 600},  # 4 failed attempts in 10 minutes
        "api": {"count": 15, "timeframe": 60},  # 15 failed attempts in 1 minute
    }

    @staticmethod
    def is_rate_limited(identifier: str, action_type: str) -> bool:
        """
        Check if a given identifier is rate limited using Redis-based tracking.
        Fixed to check limit before incrementing counter.

        Args:
            identifier: The identifier to check (e.g., phone number, IP)
            action_type: The type of action (e.g., 'otp', 'login')

        Returns:
            bool: True if rate limited, False otherwise
        """
        if action_type not in SecurityService.RATE_LIMITS:
            logger.warning(f"Unknown action type: {action_type}")
            return False

        # Check all time windows
        for window, ttl in SecurityService.WINDOWS.items():
            if window not in SecurityService.RATE_LIMITS[action_type]:
                continue

            cache_key = f"rate_limit:{action_type}:{window}:{identifier}"
            max_attempts = SecurityService.RATE_LIMITS[action_type][window]

            # Get current count WITHOUT incrementing first
            current_count = cache.get(cache_key, 0)

            # Check if already over limit
            if current_count >= max_attempts:
                logger.warning(
                    f"Rate limit already exceeded for {action_type} by {identifier} "
                    f"in {window} window: {current_count}/{max_attempts} attempts"
                )
                return True

            # Increment only if not already limited
            count = cache.incr(cache_key)

            # Set expiration if this is the first request
            if count == 1:
                cache.expire(cache_key, ttl)

            if count > max_attempts:
                logger.warning(
                    f"Rate limit exceeded for {action_type} by {identifier} "
                    f"in {window} window: {count}/{max_attempts} attempts"
                )
                return True

        return False

    @staticmethod
    def is_brute_force_attempt(identifier: str, action_type: str, success: bool = False) -> bool:
        """
        Check if the current activity appears to be a brute force attempt.

        Args:
            identifier: The identifier (IP or user ID)
            action_type: The action type being performed
            success: Whether the action was successful

        Returns:
            bool: True if detected as brute force, False otherwise
        """
        if action_type not in SecurityService.BRUTE_FORCE_THRESHOLDS:
            return False

        threshold = SecurityService.BRUTE_FORCE_THRESHOLDS[action_type]
        cache_key = f"brute_force:{action_type}:{identifier}"

        # Get the list of attempts with timestamps
        attempts = cache.get(cache_key, [])

        # Current time
        now = datetime.now().timestamp()

        # Add current attempt
        if not success:
            attempts.append(now)

            # Only keep attempts within the timeframe
            valid_attempts = [t for t in attempts if now - t <= threshold["timeframe"]]

            # Update the cache
            cache.set(cache_key, valid_attempts, threshold["timeframe"])

            # Check if we exceed the threshold
            if len(valid_attempts) >= threshold["count"]:
                # Record security event for brute force
                SecurityService.record_security_event(
                    user_id=None,
                    event_type="brute_force_detected",
                    details={
                        "identifier": identifier,
                        "action_type": action_type,
                        "attempts": len(valid_attempts),
                    },
                    severity="critical",
                    ip_address=identifier if "." in identifier else None,
                )
                return True
        elif success and attempts:
            # Clear attempts on successful action
            cache.delete(cache_key)

        return False

    @staticmethod
    def is_suspicious_ip(ip_address: str) -> bool:
        """
        Check if an IP address matches known suspicious ranges.

        Args:
            ip_address: IP address to check

        Returns:
            bool: True if suspicious, False otherwise
        """
        try:
            ip_obj = ipaddress.ip_address(ip_address)

            for ip_range in SecurityService.SUSPICIOUS_IP_RANGES:
                if ip_obj in ipaddress.ip_network(ip_range):
                    return True

            return False
        except ValueError:
            logger.warning(f"Invalid IP address format: {ip_address}")
            return False

    @staticmethod
    def record_security_event(
        user_id: Optional[str],
        event_type: str,
        details: Dict[str, Any],
        severity: str = "info",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Record a security event with persistent storage and logging.

        Args:
            user_id: ID of the affected user
            event_type: Type of security event
            details: Additional event details
            severity: Severity level
            ip_address: IP address of the request
            user_agent: User agent of the request
        """
        try:
            with transaction.atomic():
                # Create security event record
                SecurityEvent.objects.create(
                    user_id=user_id,
                    event_type=event_type,
                    details=details,
                    severity=severity,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

            # Log to standard logger
            log_message = (
                f"SECURITY EVENT [{severity.upper()}] {event_type} " f"User: {user_id} - {details}"
            )

            if severity == "critical":
                logger.critical(log_message)
            elif severity == "warning":
                logger.warning(log_message)
            else:
                logger.info(log_message)

        except Exception as e:
            logger.error(f"Failed to record security event: {str(e)}")

    @staticmethod
    def clear_rate_limit(identifier: str, action_type: str) -> None:
        """
        Clear rate limits for a specific identifier and action type.

        Args:
            identifier: The identifier to clear
            action_type: The type of action
        """
        try:
            # Clear all time windows
            for window in SecurityService.WINDOWS:
                cache_key = f"rate_limit:{action_type}:{window}:{identifier}"
                cache.delete(cache_key)

            logger.info(f"Rate limits cleared for {action_type} by {identifier}")
        except Exception as e:
            logger.error(f"Failed to clear rate limits: {str(e)}")

    @staticmethod
    def get_rate_limit_status(identifier: str, action_type: str) -> Dict[str, Any]:
        """
        Get current rate limit status for an identifier.

        Args:
            identifier: The identifier to check
            action_type: The type of action

        Returns:
            Dict containing rate limit status for each window
        """
        status = {}

        for window, ttl in SecurityService.WINDOWS.items():
            if window not in SecurityService.RATE_LIMITS[action_type]:
                continue

            cache_key = f"rate_limit:{action_type}:{window}:{identifier}"
            count = cache.get(cache_key, 0)
            max_attempts = SecurityService.RATE_LIMITS[action_type][window]

            status[window] = {
                "count": count,
                "max_attempts": max_attempts,
                "remaining": max(0, max_attempts - count),
                "reset_in": cache.ttl(cache_key) if count > 0 else 0,
            }

        return status

    @staticmethod
    def analyze_access_patterns(user_id: str, ip_address: str, action_type: str) -> Dict[str, Any]:
        """
        Analyze access patterns to detect unusual activity.

        Args:
            user_id: User identifier
            ip_address: IP address
            action_type: Type of action

        Returns:
            Analysis result with risk score
        """
        # Get user's common IPs
        cache_key = f"user_ips:{user_id}"
        user_ips = cache.get(cache_key, [])

        # New location detection
        is_new_location = ip_address not in [ip for ip, _ in user_ips]

        # Calculate risk score
        risk_score = 0
        risk_factors = []

        # Check if IP is suspicious
        if SecurityService.is_suspicious_ip(ip_address):
            risk_score += 50
            risk_factors.append("suspicious_ip")

        # Check if it's a new location
        if is_new_location and user_ips:
            risk_score += 30
            risk_factors.append("new_location")

        # Add current IP to history
        now = datetime.now().timestamp()
        user_ips.append((ip_address, now))

        # Keep only recent history (last 30 days)
        user_ips = [(ip, ts) for ip, ts in user_ips if now - ts <= 30 * 86400]

        # Update cache
        cache.set(cache_key, user_ips, 30 * 86400)  # 30 days TTL

        return {
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "is_new_location": is_new_location,
            "known_locations": len(set(ip for ip, _ in user_ips)),
        }

    @classmethod
    def login_user(
        cls,
        username: str,
        password: str,
        request: HttpRequest = None,
        ip_address: str = None,
        user_agent: str = None,
    ) -> Dict[str, Any]:
        """
        Authenticate a user with username and password.

        Args:
            username: The username or email
            password: The password
            request: Optional HTTP request for Django session auth
            ip_address: IP address of the client
            user_agent: User agent string

        Returns:
            Dictionary with user info and token on success
        """
        try:
            # Normalize username to lowercase
            username = username.lower()

            # Check if account is locked
            if cls.is_account_locked(username):
                return {
                    "success": False,
                    "error": "account_locked",
                    "message": "Account is temporarily locked due to too many failed login attempts",
                    "remaining_time_minutes": cls.get_lockout_remaining_time(username),
                }

            # Try to authenticate
            user = authenticate(username=username, password=password)

            if not user:
                # Log failed attempt
                cls.record_login_failure(username, ip_address, user_agent)

                # Check if account should be locked
                attempts_left = MAX_LOGIN_ATTEMPTS - cls.get_failed_login_count(username)
                if attempts_left <= 0:
                    cls.lock_account(username)
                    return {
                        "success": False,
                        "error": "account_locked",
                        "message": "Account has been locked due to too many failed login attempts",
                        "remaining_time_minutes": ACCOUNT_LOCKOUT_MINUTES,
                    }

                return {
                    "success": False,
                    "error": "invalid_credentials",
                    "message": "Invalid username or password",
                    "attempts_left": attempts_left,
                }

            # Check if user is active
            if not user.is_active:
                return {
                    "success": False,
                    "error": "account_inactive",
                    "message": "Account is inactive",
                }

            # Authentication successful
            # Clear any failed login attempts
            cls.clear_failed_login_attempts(username)

            # Record successful login
            LoginAttempt.objects.create(
                user=user, success=True, ip_address=ip_address, user_agent=user_agent
            )

            # Create auth token
            token = cls.create_auth_token(user.id)

            # If request is provided, use Django's session-based auth too
            if request:
                login(request, user)

            return {
                "success": True,
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
                "token": token,
                "message": "Login successful",
            }

        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return {
                "success": False,
                "error": "server_error",
                "message": "An error occurred during login",
            }

    @classmethod
    def logout_user(
        cls, user_id: str, token: str = None, request: HttpRequest = None
    ) -> Dict[str, bool]:
        """
        Log out a user by invalidating their token.

        Args:
            user_id: ID of the user to log out
            token: Optional token to invalidate (if None, invalidates all tokens)
            request: Optional HTTP request for Django session auth

        Returns:
            Dictionary with logout status
        """
        try:
            # Invalidate token(s)
            if token:
                # Invalidate specific token
                try:
                    auth_token = AuthToken.objects.get(token=token, user_id=user_id)
                    auth_token.is_active = False
                    auth_token.revoked_at = timezone.now()
                    auth_token.save()
                except AuthToken.DoesNotExist:
                    pass
            else:
                # Invalidate all tokens for user
                AuthToken.objects.filter(user_id=user_id, is_active=True).update(
                    is_active=False, revoked_at=timezone.now()
                )

            # If request is provided, use Django's session-based logout too
            if request:
                logout(request)

            return {"success": True, "message": "Logged out successfully"}

        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return {"success": False, "message": "An error occurred during logout"}

    @classmethod
    def validate_token(cls, token: str) -> Tuple[bool, Optional[str]]:
        """
        Validate an authentication token.

        Args:
            token: The token to validate

        Returns:
            Tuple of (is_valid, user_id)
        """
        try:
            # Try to find token in database
            token_obj = AuthToken.objects.get(token=token, is_active=True)

            # Check if token has expired
            if token_obj.expires_at and token_obj.expires_at < timezone.now():
                token_obj.is_active = False
                token_obj.save()
                return False, None

            # Update last used timestamp
            token_obj.last_used_at = timezone.now()
            token_obj.save(update_fields=["last_used_at"])

            return True, str(token_obj.user_id)

        except AuthToken.DoesNotExist:
            return False, None
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return False, None

    @classmethod
    def create_auth_token(
        cls, user_id: str, expires_in_days: int = 30, device_info: Dict[str, Any] = None
    ) -> str:
        """
        Create a new authentication token for a user.

        Args:
            user_id: ID of the user
            expires_in_days: Number of days until token expires
            device_info: Optional information about the device

        Returns:
            The generated token string
        """
        # Generate secure token
        token = secrets.token_urlsafe(40)

        # Set expiration date
        expires_at = timezone.now() + timedelta(days=expires_in_days)

        # Create token record
        AuthToken.objects.create(
            user_id=user_id,
            token=token,
            is_active=True,
            device_info=device_info or {},
            expires_at=expires_at,
        )

        return token

    @classmethod
    def change_password(
        cls,
        user_id: str,
        current_password: str,
        new_password: str,
        invalidate_sessions: bool = True,
    ) -> Dict[str, Any]:
        """
        Change a user's password with security checks.

        Args:
            user_id: ID of the user
            current_password: Current password for verification
            new_password: New password to set
            invalidate_sessions: Whether to invalidate all existing sessions

        Returns:
            Dictionary with password change result
        """
        try:
            # Get user
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return {
                    "success": False,
                    "error": "user_not_found",
                    "message": "User not found",
                }

            # Verify current password
            if not user.check_password(current_password):
                return {
                    "success": False,
                    "error": "invalid_password",
                    "message": "Current password is incorrect",
                }

            # Check password history if enabled
            if REQUIRE_PASSWORD_HISTORY:
                if cls.is_password_in_history(user, new_password):
                    return {
                        "success": False,
                        "error": "password_in_history",
                        "message": f"Cannot reuse one of your last {PASSWORD_HISTORY_COUNT} passwords",
                    }

            # Change password
            with transaction.atomic():
                # Store current password in history before changing
                if REQUIRE_PASSWORD_HISTORY:
                    cls.add_password_to_history(user)

                # Update password
                user.set_password(new_password)
                user.password_changed_at = timezone.now()
                user.save(update_fields=["password", "password_changed_at"])

                # Invalidate all sessions if requested
                if invalidate_sessions:
                    # Invalidate all tokens
                    AuthToken.objects.filter(user=user, is_active=True).update(
                        is_active=False, revoked_at=timezone.now()
                    )

            # Send notification
            NotificationService.send_notification(
                recipient_id=str(user.id),
                notification_type="password_changed",
                title="Password Changed",
                message="Your password was successfully changed. If you did not make this change, please contact support immediately.",
                channels=["email", "in_app"],
            )

            return {"success": True, "message": "Password changed successfully"}

        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            return {
                "success": False,
                "error": "server_error",
                "message": "An error occurred while changing password",
            }

    @classmethod
    def request_password_reset(cls, email: str, request_ip: str = None) -> Dict[str, Any]:
        """
        Request a password reset for a user's account.

        Args:
            email: Email address of the user
            request_ip: IP address of the requester

        Returns:
            Dictionary with request result
        """
        try:
            # Normalize email to lowercase
            email = email.lower()

            # Get user by email
            User = get_user_model()
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Still return success to prevent email enumeration
                logger.info(f"Password reset requested for non-existent email: {email}")
                return {
                    "success": True,
                    "message": "If your email is in our system, you will receive a password reset link",
                }

            # Check if user is active
            if not user.is_active:
                # Still return success to prevent account enumeration
                logger.info(f"Password reset requested for inactive user: {email}")
                return {
                    "success": True,
                    "message": "If your email is in our system, you will receive a password reset link",
                }

            # Check for rate limiting
            rate_limit_key = f"pwd_reset_rate_limit:{email}"
            request_count = cache.get(rate_limit_key, 0)

            if request_count >= 3:  # Max 3 requests per hour
                logger.warning(f"Password reset rate limit exceeded for email: {email}")
                return {
                    "success": True,  # Still return success to prevent enumeration
                    "message": "If your email is in our system, you will receive a password reset link",
                }

            # Increment rate limit counter
            cache.set(rate_limit_key, request_count + 1, 3600)  # 1 hour expiry

            # Generate secure token
            token = secrets.token_urlsafe(40)

            # Set expiration time
            expires_at = timezone.now() + timedelta(minutes=PASSWORD_RESET_EXPIRY_MINUTES)

            # Save token
            reset_token = PasswordResetToken.objects.create(
                user=user,
                token=token,
                expires_at=expires_at,
                is_used=False,
                request_ip=request_ip,
            )

            # Send notification with reset link
            reset_link = f"{settings.WEBSITE_URL}/reset-password/?token={token}"

            NotificationService.send_notification(
                recipient_id=str(user.id),
                notification_type="password_reset",
                title="Password Reset Request",
                message="You requested a password reset. Click the link below to reset your password.",
                channels=["email"],
                data={
                    "reset_link": reset_link,
                    "expiry_minutes": PASSWORD_RESET_EXPIRY_MINUTES,
                    "user_name": user.get_full_name() or user.username,
                },
                priority="high",
                rate_limit_bypass=True,  # Bypass rate limiting for security-critical notifications
            )

            return {
                "success": True,
                "message": "If your email is in our system, you will receive a password reset link",
            }

        except Exception as e:
            logger.error(f"Password reset request error: {str(e)}")
            return {
                "success": False,
                "error": "server_error",
                "message": "An error occurred while processing your request",
            }

    @classmethod
    def validate_reset_token(cls, token: str) -> Dict[str, Any]:
        """
        Validate a password reset token.

        Args:
            token: The reset token to validate

        Returns:
            Dictionary with validation result and user information
        """
        try:
            try:
                reset_token = PasswordResetToken.objects.get(token=token, is_used=False)
            except PasswordResetToken.DoesNotExist:
                return {
                    "success": False,
                    "error": "invalid_token",
                    "message": "The reset token is invalid or has already been used",
                }

            # Check if token has expired
            if reset_token.expires_at < timezone.now():
                reset_token.is_used = True
                reset_token.save()
                return {
                    "success": False,
                    "error": "token_expired",
                    "message": "The reset token has expired",
                }

            # Token is valid
            return {
                "success": True,
                "user_id": str(reset_token.user.id),
                "email": reset_token.user.email,
                "expires_at": reset_token.expires_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Reset token validation error: {str(e)}")
            return {
                "success": False,
                "error": "server_error",
                "message": "An error occurred while validating the token",
            }

    @classmethod
    def reset_password(cls, token: str, new_password: str, user_ip: str = None) -> Dict[str, Any]:
        """
        Reset password using a valid reset token.

        Args:
            token: The reset token
            new_password: New password to set
            user_ip: IP address of the user

        Returns:
            Dictionary with reset result
        """
        try:
            # First validate the token
            validation = cls.validate_reset_token(token)
            if not validation.get("success"):
                return validation

            user_id = validation.get("user_id")

            # Get user
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return {
                    "success": False,
                    "error": "user_not_found",
                    "message": "User not found",
                }

            # Get token object
            reset_token = PasswordResetToken.objects.get(token=token, is_used=False)

            # Password history check
            if REQUIRE_PASSWORD_HISTORY:
                if cls.is_password_in_history(user, new_password):
                    return {
                        "success": False,
                        "error": "password_in_history",
                        "message": f"Cannot reuse one of your last {PASSWORD_HISTORY_COUNT} passwords",
                    }

            # Reset password
            with transaction.atomic():
                # Store current password in history before changing
                if REQUIRE_PASSWORD_HISTORY:
                    cls.add_password_to_history(user)

                # Update password
                user.set_password(new_password)
                user.password_changed_at = timezone.now()
                user.save()

                # Mark token as used
                reset_token.is_used = True
                reset_token.used_at = timezone.now()
                reset_token.used_ip = user_ip
                reset_token.save()

                # Invalidate all existing sessions for security
                AuthToken.objects.filter(user=user, is_active=True).update(
                    is_active=False, revoked_at=timezone.now()
                )

            # Send notification
            NotificationService.send_notification(
                recipient_id=str(user.id),
                notification_type="password_reset_complete",
                title="Password Reset Complete",
                message="Your password has been reset successfully. If you did not make this change, please contact support immediately.",
                channels=["email", "in_app"],
                priority="high",
                rate_limit_bypass=True,  # Bypass rate limiting for security-critical notifications
            )

            return {"success": True, "message": "Password reset successful"}

        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return {
                "success": False,
                "error": "server_error",
                "message": "An error occurred while resetting password",
            }

    # Account lockout methods

    @classmethod
    def is_account_locked(cls, username: str) -> bool:
        """
        Check if an account is locked due to too many failed login attempts.

        Args:
            username: Username or email to check

        Returns:
            Boolean indicating if account is locked
        """
        lock_key = f"account_lock:{username.lower()}"
        return bool(cache.get(lock_key))

    @classmethod
    def lock_account(cls, username: str, minutes: int = None) -> None:
        """
        Lock an account for a specified period due to too many failed login attempts.

        Args:
            username: Username or email to lock
            minutes: Lock duration in minutes (defaults to ACCOUNT_LOCKOUT_MINUTES)
        """
        if minutes is None:
            minutes = ACCOUNT_LOCKOUT_MINUTES

        lock_key = f"account_lock:{username.lower()}"
        cache.set(lock_key, True, minutes * 60)  # Convert to seconds

        logger.warning(f"Account locked for {minutes} minutes: {username}")

        # Try to notify user if we can find them
        User = get_user_model()
        try:
            user = User.objects.get(username__iexact=username)

            NotificationService.send_notification(
                recipient_id=str(user.id),
                notification_type="account_locked",
                title="Account Temporarily Locked",
                message=f"Your account has been temporarily locked for {minutes} minutes due to too many failed login attempts.",
                channels=["email", "in_app"],
                priority="high",
                rate_limit_bypass=True,  # Bypass rate limiting for security-critical notifications
            )
        except User.DoesNotExist:
            # Try with email
            try:
                user = User.objects.get(email__iexact=username)

                NotificationService.send_notification(
                    recipient_id=str(user.id),
                    notification_type="account_locked",
                    title="Account Temporarily Locked",
                    message=f"Your account has been temporarily locked for {minutes} minutes due to too many failed login attempts.",
                    channels=["email", "in_app"],
                    priority="high",
                    rate_limit_bypass=True,  # Bypass rate limiting for security-critical notifications
                )
            except User.DoesNotExist:
                # Can't find user, just log it
                pass

    @classmethod
    def get_lockout_remaining_time(cls, username: str) -> int:
        """
        Get remaining lockout time in minutes.

        Args:
            username: Username or email to check

        Returns:
            Remaining lockout time in minutes, or 0 if not locked
        """
        lock_key = f"account_lock:{username.lower()}"
        remaining = cache.ttl(lock_key)

        if remaining is None or remaining <= 0:
            return 0

        return int(remaining / 60) + 1  # Convert to minutes, round up

    @classmethod
    def unlock_account(cls, username: str) -> bool:
        """
        Manually unlock an account.

        Args:
            username: Username or email to unlock

        Returns:
            Boolean indicating if unlock was successful
        """
        lock_key = f"account_lock:{username.lower()}"
        was_locked = bool(cache.get(lock_key))

        if was_locked:
            cache.delete(lock_key)
            logger.info(f"Account manually unlocked: {username}")

        return was_locked

    @classmethod
    def record_login_failure(
        cls, username: str, ip_address: str = None, user_agent: str = None
    ) -> None:
        """
        Record a failed login attempt.

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
        cache.set(counter_key, count + 1, 12 * 3600)  # Store for 12 hours

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

    @classmethod
    def get_failed_login_count(cls, username: str) -> int:
        """
        Get the number of failed login attempts for a username.

        Args:
            username: Username or email to check

        Returns:
            Number of failed login attempts
        """
        counter_key = f"failed_logins:{username.lower()}"
        return cache.get(counter_key, 0)

    @classmethod
    def clear_failed_login_attempts(cls, username: str) -> None:
        """
        Clear failed login attempts for a username.

        Args:
            username: Username or email to clear
        """
        counter_key = f"failed_logins:{username.lower()}"
        cache.delete(counter_key)

    # Password history methods

    @classmethod
    def add_password_to_history(cls, user) -> None:
        """
        Add the user's current password to their password history.

        Args:
            user: User object
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

    @classmethod
    def is_password_in_history(cls, user, new_password: str) -> bool:
        """
        Check if a password exists in the user's password history.

        Args:
            user: User object
            new_password: Password to check

        Returns:
            Boolean indicating if password is in history
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
    def invalidate_user_tokens(cls, user_id: str, reason: str = None) -> int:
        """
        Invalidate all tokens for a user.

        Args:
            user_id: ID of the user
            reason: Optional reason for invalidation

        Returns:
            Number of tokens invalidated
        """
        tokens = AuthToken.objects.filter(user_id=user_id, is_active=True)
        count = tokens.count()

        tokens.update(
            is_active=False,
            revoked_at=timezone.now(),
            revocation_reason=reason or "admin_revoked",
        )

        return count
