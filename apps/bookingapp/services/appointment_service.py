"""
Appointment service for handling booking-related operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

from django.core.cache import cache
from django.db.models import Count, F, Q, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.serviceapp.models import Service
from apps.specialistsapp.models import Specialist

logger = logging.getLogger(__name__)

# Cache keys and timeouts
SPECIALIST_APPOINTMENTS_CACHE_KEY = (
    "specialist_appointments_{specialist_id}_{start_date}_{end_date}"
)
CUSTOMER_APPOINTMENTS_CACHE_KEY = "customer_appointments_{customer_id}_{start_date}_{end_date}"
SERVICE_APPOINTMENTS_CACHE_KEY = "service_appointments_{service_id}_{start_date}_{end_date}"
SHOP_APPOINTMENTS_CACHE_KEY = "shop_appointments_{shop_id}_{start_date}_{end_date}"

# Cache timeouts (in seconds)
APPOINTMENTS_CACHE_TIMEOUT = 60 * 5  # 5 minutes
RECENTLY_BOOKED_CACHE_TIMEOUT = 60 * 30  # 30 minutes


class AppointmentService:
    """
    Service for appointment-related operations.
    Implements caching for expensive queries to improve performance.
    """

    @classmethod
    def get_specialist_appointments(
        cls,
        specialist_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
        status: str = None,
        use_cache: bool = True,
    ) -> List[Appointment]:
        """
        Get appointments for a specialist with caching.

        Args:
            specialist_id: ID of the specialist
            start_date: Optional start date filter
            end_date: Optional end date filter
            status: Optional status filter
            use_cache: Whether to use cached results

        Returns:
            List of appointments
        """
        # Set default date range if not provided
        if not start_date:
            start_date = timezone.now().replace(hour=0, minute=0, second=0)
        if not end_date:
            end_date = start_date + timedelta(days=7)

        # Generate cache key
        cache_key = SPECIALIST_APPOINTMENTS_CACHE_KEY.format(
            specialist_id=specialist_id,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )

        # If status is provided, add to cache key
        if status:
            cache_key += f"_{status}"

        # Try to get from cache if enabled
        if use_cache:
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for specialist appointments: {cache_key}")
                return cached_result

        # Build query
        query = Appointment.objects.filter(
            specialist_id=specialist_id,
            appointment_date__gte=start_date,
            appointment_date__lte=end_date,
        )

        # Apply status filter if provided
        if status:
            query = query.filter(status=status)

        # Execute query
        appointments = list(
            query.select_related("service", "customer", "shop").order_by(
                "appointment_date", "start_time"
            )
        )

        # Cache the result
        if use_cache:
            cache.set(cache_key, appointments, APPOINTMENTS_CACHE_TIMEOUT)
            logger.debug(f"Cached specialist appointments: {cache_key}")

        return appointments

    @classmethod
    def get_customer_appointments(
        cls,
        customer_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
        status: str = None,
        use_cache: bool = True,
    ) -> List[Appointment]:
        """
        Get appointments for a customer with caching.

        Args:
            customer_id: ID of the customer
            start_date: Optional start date filter
            end_date: Optional end date filter
            status: Optional status filter
            use_cache: Whether to use cached results

        Returns:
            List of appointments
        """
        # Set default date range if not provided
        if not start_date:
            start_date = timezone.now().replace(hour=0, minute=0, second=0)
        if not end_date:
            end_date = start_date + timedelta(days=30)  # Longer period for customers

        # Generate cache key
        cache_key = CUSTOMER_APPOINTMENTS_CACHE_KEY.format(
            customer_id=customer_id,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )

        # If status is provided, add to cache key
        if status:
            cache_key += f"_{status}"

        # Try to get from cache if enabled
        if use_cache:
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for customer appointments: {cache_key}")
                return cached_result

        # Build query
        query = Appointment.objects.filter(
            customer_id=customer_id,
            appointment_date__gte=start_date,
            appointment_date__lte=end_date,
        )

        # Apply status filter if provided
        if status:
            query = query.filter(status=status)

        # Execute query
        appointments = list(
            query.select_related("service", "specialist", "shop").order_by(
                "-appointment_date", "-start_time"
            )
        )

        # Cache the result
        if use_cache:
            cache.set(cache_key, appointments, APPOINTMENTS_CACHE_TIMEOUT)
            logger.debug(f"Cached customer appointments: {cache_key}")

        return appointments

    @classmethod
    def invalidate_appointment_caches(cls, appointment: Appointment):
        """
        Invalidate all caches related to an appointment.
        Call this whenever an appointment is created, updated, or deleted.

        Args:
            appointment: The appointment that changed
        """
        # Create date range
        start_date = appointment.appointment_date
        end_date = appointment.appointment_date

        # Delete specialist cache
        if appointment.specialist_id:
            specialist_key = SPECIALIST_APPOINTMENTS_CACHE_KEY.format(
                specialist_id=appointment.specialist_id,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            cache.delete(specialist_key)
            # Also delete with status suffix
            cache.delete(f"{specialist_key}_{appointment.status}")

        # Delete customer cache
        if appointment.customer_id:
            customer_key = CUSTOMER_APPOINTMENTS_CACHE_KEY.format(
                customer_id=appointment.customer_id,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            cache.delete(customer_key)
            # Also delete with status suffix
            cache.delete(f"{customer_key}_{appointment.status}")

        # Delete service cache
        if appointment.service_id:
            service_key = SERVICE_APPOINTMENTS_CACHE_KEY.format(
                service_id=appointment.service_id,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            cache.delete(service_key)

        # Delete shop cache
        if appointment.shop_id:
            shop_key = SHOP_APPOINTMENTS_CACHE_KEY.format(
                shop_id=appointment.shop_id,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            cache.delete(shop_key)

        logger.debug(f"Invalidated caches for appointment {appointment.id}")
