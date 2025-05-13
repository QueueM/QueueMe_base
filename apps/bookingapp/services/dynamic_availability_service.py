"""
Dynamic Availability Service

This service provides an interface to the advanced dynamic slot allocation algorithm
that optimizes scheduling based on various factors:
- Time slot popularity/demand
- Specialist workload balance
- Specialist-service match quality
- Customer preferences
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from django.utils import timezone

from algorithms.availability.dynamic_slot_allocator import DynamicSlotAllocator
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop

logger = logging.getLogger(__name__)


class DynamicAvailabilityService:
    """
    Service for accessing the dynamic slot allocation algorithm
    with business logic integration
    """

    @staticmethod
    def get_optimized_availability(
        service_id: str,
        target_date: date,
        customer_id: Optional[str] = None,
        specialist_id: Optional[str] = None,
        personalize: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get optimized availability slots for a service on a specific date

        Args:
            service_id: UUID of the service
            target_date: Date to generate slots for
            customer_id: Optional customer ID for personalization
            specialist_id: Optional specialist ID if required
            personalize: Whether to apply customer personalization (if customer_id provided)

        Returns:
            List of optimized time slots with metadata
        """
        try:
            # Get service details
            service = Service.objects.get(id=service_id)
            shop_id = str(service.shop_id)

            # Check if date is in the future
            if target_date < timezone.now().date():
                # Can't book in the past
                return []

            # Initialize the dynamic slot allocator
            allocator = DynamicSlotAllocator()

            # Get optimized slots
            slots = allocator.allocate_slots(
                shop_id=shop_id,
                service_id=service_id,
                target_date=target_date,
                customer_id=customer_id if personalize else None,
                specialist_id=specialist_id,
            )

            # Apply any additional business logic or filters
            # For example, enforcing minimum notice period
            minimum_notice = service.min_booking_notice or 0
            if minimum_notice > 0:
                min_notice_time = timezone.now() + timezone.timedelta(minutes=minimum_notice)

                # Filter out slots that don't meet notice requirement
                filtered_slots = []
                for slot in slots:
                    slot_time_str = f"{target_date.isoformat()} {slot['start']}"
                    slot_time = datetime.fromisoformat(slot_time_str)

                    # Make timezone aware
                    if timezone.is_naive(slot_time):
                        slot_time = timezone.make_aware(slot_time)

                    if slot_time >= min_notice_time:
                        filtered_slots.append(slot)

                slots = filtered_slots

            return slots

        except Exception as e:
            logger.error(f"Error in dynamic availability service: {e}")
            # Fall back to standard availability service
            from apps.bookingapp.services.availability_service import AvailabilityService

            return AvailabilityService.get_service_availability(service_id, target_date)

    @staticmethod
    def invalidate_cache_for_booking(
        appointment_id: str, service_id: str, shop_id: str, date_str: str
    ) -> None:
        """
        Invalidate the dynamic slot cache when bookings change

        Args:
            appointment_id: ID of the modified appointment
            service_id: Service ID
            shop_id: Shop ID
            date_str: Date string in ISO format (YYYY-MM-DD)
        """
        try:
            allocator = DynamicSlotAllocator()
            allocator.invalidate_cache(shop_id=shop_id, service_id=service_id, date_str=date_str)
            logger.debug(f"Invalidated dynamic slot cache for appointment {appointment_id}")
        except Exception as e:
            logger.error(f"Error invalidating dynamic slot cache: {e}")

    @staticmethod
    def get_popular_slots(
        service_id: str, target_date: date, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get the most popular time slots for a service

        Args:
            service_id: Service ID
            target_date: Target date
            limit: Maximum number of slots to return

        Returns:
            List of popular time slots with popularity scores
        """
        try:
            # Get service details
            service = Service.objects.get(id=service_id)
            shop_id = str(service.shop_id)

            # Initialize allocator
            allocator = DynamicSlotAllocator()

            # Get all slots
            all_slots = allocator.allocate_slots(
                shop_id=shop_id, service_id=service_id, target_date=target_date
            )

            # Sort by popularity
            popular_slots = sorted(all_slots, key=lambda x: x.get("popularity", 0), reverse=True)[
                :limit
            ]

            return popular_slots

        except Exception as e:
            logger.error(f"Error getting popular slots: {e}")
            return []

    @staticmethod
    def get_quiet_slots(service_id: str, target_date: date, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Get the least busy time slots for a service

        Args:
            service_id: Service ID
            target_date: Target date
            limit: Maximum number of slots to return

        Returns:
            List of quiet time slots
        """
        try:
            # Get service details
            service = Service.objects.get(id=service_id)
            shop_id = str(service.shop_id)

            # Initialize allocator
            allocator = DynamicSlotAllocator()

            # Get all slots
            all_slots = allocator.allocate_slots(
                shop_id=shop_id, service_id=service_id, target_date=target_date
            )

            # Sort by popularity (ascending)
            quiet_slots = sorted(all_slots, key=lambda x: x.get("popularity", 1))[:limit]

            return quiet_slots

        except Exception as e:
            logger.error(f"Error getting quiet slots: {e}")
            return []

    @staticmethod
    def get_best_specialist_for_slot(
        service_id: str, target_date: date, time_slot: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the best specialist for a specific time slot

        Args:
            service_id: Service ID
            target_date: Target date
            time_slot: Time slot string in format "HH:MM"

        Returns:
            Best specialist details or None if not available
        """
        try:
            # Get service details
            service = Service.objects.get(id=service_id)
            shop_id = str(service.shop_id)

            # Initialize allocator
            allocator = DynamicSlotAllocator()

            # Get all slots
            all_slots = allocator.allocate_slots(
                shop_id=shop_id, service_id=service_id, target_date=target_date
            )

            # Find the specific time slot
            for slot in all_slots:
                if slot["start"] == time_slot:
                    return {
                        "specialist_id": slot.get("specialist_id"),
                        "specialist_name": slot.get("specialist_name"),
                        "optimization_score": slot.get("optimization_score", 0.5),
                        "alternative_specialists": slot.get("alternative_specialists", []),
                    }

            return None

        except Exception as e:
            logger.error(f"Error finding best specialist for slot: {e}")
            return None
