"""
API Rate Limiting Configuration for QueueMe

This module defines various throttling classes to limit API request rates.
"""

from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle


class AnonBasicRateThrottle(AnonRateThrottle):
    """
    Throttling for anonymous users - basic rate limits
    """

    rate = "30/minute"


class AnonStrictRateThrottle(AnonRateThrottle):
    """
    Throttling for anonymous users - stricter for sensitive endpoints
    """

    rate = "10/minute"


class UserBasicRateThrottle(UserRateThrottle):
    """
    Throttling for authenticated users - basic rate limits
    """

    rate = "100/minute"


class UserStrictRateThrottle(UserRateThrottle):
    """
    Throttling for authenticated users - stricter for sensitive endpoints
    """

    rate = "20/minute"


class AuthenticationRateThrottle(ScopedRateThrottle):
    """
    Throttling for authentication endpoints
    """

    scope = "authentication"
    rate = "5/minute"


class PaymentRateThrottle(ScopedRateThrottle):
    """
    Throttling for payment-related endpoints
    """

    scope = "payment"
    rate = "10/minute"


class SearchRateThrottle(ScopedRateThrottle):
    """
    Throttling for search endpoints
    """

    scope = "search"
    rate = "30/minute"


class BookingRateThrottle(ScopedRateThrottle):
    """
    Throttling for booking-related endpoints
    """

    scope = "booking"
    rate = "20/minute"


class BurstRateThrottle(UserRateThrottle):
    """
    Throttling for burst requests (allows short bursts of requests)
    """

    scope = "burst"
    rate = "60/minute"


class SustainedRateThrottle(UserRateThrottle):
    """
    Throttling for sustained requests over a longer period
    """

    scope = "sustained"
    rate = "1000/day"
