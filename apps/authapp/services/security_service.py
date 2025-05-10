import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

from django.core.cache import cache
from django.db import transaction
from django.conf import settings
import ipaddress

from apps.authapp.constants import (
    MAX_OTP_REQUESTS_PER_HOUR,
    MAX_OTP_REQUESTS_PER_DAY,
    MAX_OTP_REQUESTS_PER_WEEK
)
from apps.authapp.models import SecurityEvent

logger = logging.getLogger(__name__)


class SecurityService:
    """
    Enhanced security service with Redis-based rate limiting and persistent logging.
    """

    # Rate limit windows
    WINDOWS = {
        "hour": 3600,  # 1 hour in seconds
        "day": 86400,  # 24 hours in seconds
        "week": 604800  # 7 days in seconds
    }

    # Rate limits by action type and window
    RATE_LIMITS = {
        "otp": {
            "hour": MAX_OTP_REQUESTS_PER_HOUR,
            "day": MAX_OTP_REQUESTS_PER_DAY,
            "week": MAX_OTP_REQUESTS_PER_WEEK
        },
        "login": {
            "hour": 10,
            "day": 50,
            "week": 200
        },
        "verification": {
            "hour": 15,
            "day": 75,
            "week": 300
        },
        "password_reset": {
            "hour": 5,
            "day": 10,
            "week": 20
        }
    }
    
    # Suspicious IP ranges (example)
    SUSPICIOUS_IP_RANGES = [
        "185.156.73.0/24",  # Known for abuse
        "193.32.161.0/24",   # Known for abuse
        "91.132.0.0/16",     # High volume of attacks
    ]
    
    # Brute force detection thresholds
    BRUTE_FORCE_THRESHOLDS = {
        "login": {"count": 5, "timeframe": 300},  # 5 failed attempts in 5 minutes
        "otp": {"count": 4, "timeframe": 600},    # 4 failed attempts in 10 minutes
        "api": {"count": 15, "timeframe": 60}     # 15 failed attempts in 1 minute
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
                        "attempts": len(valid_attempts)
                    },
                    severity="critical",
                    ip_address=identifier if "." in identifier else None
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
        user_agent: Optional[str] = None
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
                    user_agent=user_agent
                )

            # Log to standard logger
            log_message = (
                f"SECURITY EVENT [{severity.upper()}] {event_type} "
                f"User: {user_id} - {details}"
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
                "reset_in": cache.ttl(cache_key) if count > 0 else 0
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
            "known_locations": len(set(ip for ip, _ in user_ips))
        }
