"""
Dynamic Slot Allocation Algorithm

This module provides an advanced algorithm for dynamically allocating time slots
that optimizes for both business efficiency and customer satisfaction:

1. Prioritizes high-demand time slots for premium services
2. Implements load balancing across specialists
3. Adapts to historical booking patterns
4. Optimizes for service transitions (minimizing specialist downtime)
5. Uses cached pre-computation for better performance
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.db.models import Avg, Count
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import SpecialistService

logger = logging.getLogger(__name__)


class DynamicSlotAllocator:
    """
    Intelligent slot allocation system that optimizes time slot availability
    based on multiple factors to maximize business efficiency.
    """

    # Cache settings
    CACHE_PREFIX = "dynamic_slots:"
    CACHE_TTL = 60 * 5  # 5 minutes

    # Weight configuration
    DEFAULT_WEIGHTS = {
        "popularity": 0.3,  # Time slot's historical popularity
        "transition_time": 0.2,  # Minimize specialist transition time
        "load_balance": 0.15,  # Balance workload across specialists
        "service_priority": 0.15,  # Prioritize high-value services
        "specialist_rating": 0.1,  # Prefer higher-rated specialists
        "customer_history": 0.1,  # Consider customer booking history
    }

    def __init__(self, weights=None):
        """
        Initialize the dynamic slot allocator with custom weights if provided

        Args:
            weights: Dictionary of weight factors (optional)
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self._normalize_weights()

    def _normalize_weights(self):
        """Ensure weights sum to 1.0"""
        total = sum(self.weights.values())
        if total != 1.0:
            for key in self.weights:
                self.weights[key] = self.weights[key] / total

    def allocate_slots(
        self,
        shop_id: str,
        service_id: str,
        target_date: date,
        customer_id: Optional[str] = None,
        specialist_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Allocate optimized time slots for a service on a specific date

        Args:
            shop_id: ID of the shop
            service_id: ID of the service
            target_date: Date to generate slots for
            customer_id: Optional customer ID for personalization
            specialist_id: Optional specialist ID if specific specialist requested
            use_cache: Whether to use cached results

        Returns:
            List of optimized time slots with metadata
        """
        # Generate cache key
        cache_key = (
            f"{self.CACHE_PREFIX}{shop_id}:{service_id}:{target_date.isoformat()}"
        )
        if specialist_id:
            cache_key += f":{specialist_id}"

        # Try to get from cache
        if use_cache:
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for dynamic slots: {cache_key}")

                # If customer-specific, apply personalization on cached base results
                if customer_id:
                    return self._personalize_slots(cached_result, customer_id)
                return cached_result

        # Get basic data
        try:
            service = Service.objects.get(id=service_id)
            # shop = Shop.objects.get(id=shop_id)
        except (Service.DoesNotExist, Shop.DoesNotExist) as e:
            logger.error(f"Error retrieving service or shop: {e}")
            return []

        # Get all available time blocks (ignoring optimization factors)
        base_slots = self._get_base_availability(
            shop_id, service_id, target_date, specialist_id
        )

        if not base_slots:
            return []

        # Get specialists who can provide this service
        specialists = self._get_service_specialists(service_id, specialist_id)
        if not specialists:
            return []

        # Get popularity data (which time slots are most requested)
        popularity_data = self._get_time_popularity(shop_id, service_id, target_date)

        # Get specialist workload for load balancing
        workload_data = self._get_specialist_workload(specialists, target_date)

        # Get specialist ratings
        rating_data = self._get_specialist_ratings(specialists)

        # Get service priority values
        service_priority = self._get_service_priority(service_id)

        # Optimize slot allocation
        optimized_slots = self._optimize_slot_allocation(
            base_slots,
            specialists,
            popularity_data,
            workload_data,
            rating_data,
            service_priority,
            service,
        )

        # Cache the results for future requests
        if use_cache:
            cache.set(cache_key, optimized_slots, self.CACHE_TTL)

        # Apply customer-specific personalization if needed
        if customer_id:
            return self._personalize_slots(optimized_slots, customer_id)

        return optimized_slots

    def _get_base_availability(
        self,
        shop_id: str,
        service_id: str,
        target_date: date,
        specialist_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get basic availability slots without optimization

        Args:
            shop_id: Shop ID
            service_id: Service ID
            target_date: Date to check
            specialist_id: Optional specialist ID

        Returns:
            List of basic availability slots
        """
        # This would use the existing availability service
        from apps.bookingapp.services.availability_service import AvailabilityService

        # Get all slots from the basic availability service
        base_slots = AvailabilityService.get_service_availability(
            service_id, target_date
        )

        # If specialist_id is provided, filter for that specialist
        if specialist_id and base_slots:
            base_slots = [
                slot
                for slot in base_slots
                if slot.get("specialist_id") == str(specialist_id)
            ]

        return base_slots

    def _get_service_specialists(
        self, service_id: str, specialist_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get specialists who can provide this service

        Args:
            service_id: Service ID
            specialist_id: Optional specialist ID to filter for

        Returns:
            List of specialists with their metadata
        """
        # Query for specialists who provide this service
        specialist_services = SpecialistService.objects.filter(
            service_id=service_id
        ).select_related("specialist")

        if specialist_id:
            specialist_services = specialist_services.filter(
                specialist_id=specialist_id
            )

        # Extract specialist data
        specialists = []
        for ss in specialist_services:
            specialists.append(
                {
                    "id": str(ss.specialist.id),
                    "name": ss.specialist.name,
                    "experience_level": ss.experience_level or "standard",
                    "is_preferred": ss.is_preferred,
                    "service_time_multiplier": ss.service_time_multiplier or 1.0,
                }
            )

        return specialists

    def _get_time_popularity(
        self, shop_id: str, service_id: str, target_date: date
    ) -> Dict[str, float]:
        """
        Get popularity scores for different time slots based on historical data

        Args:
            shop_id: Shop ID
            service_id: Service ID
            target_date: Date to check

        Returns:
            Dictionary mapping time slots to popularity scores (0-1)
        """
        # Get day of week for the target date
        day_of_week = target_date.weekday()

        # Look at historical bookings for the same service and day of week
        # for the past 3 months
        three_months_ago = timezone.now() - timedelta(days=90)

        historical_bookings = (
            Appointment.objects.filter(
                service_id=service_id,
                shop_id=shop_id,
                start_time__gte=three_months_ago,
                start_time__time__isnull=False,
            )
            .extra(select={"day_of_week": "EXTRACT(DOW FROM start_time)"})
            .filter(day_of_week=day_of_week)
        )

        # Count bookings by hour of day
        bookings_by_hour = defaultdict(int)
        total_bookings = 0

        for booking in historical_bookings:
            hour_key = booking.start_time.strftime("%H:00")
            bookings_by_hour[hour_key] += 1
            total_bookings += 1

            # Also add half-hour slots
            if booking.start_time.minute >= 30:
                hour_key = booking.start_time.strftime("%H:30")
            else:
                hour_key = f"{booking.start_time.hour:02d}:30"
            bookings_by_hour[
                hour_key
            ] += 0.5  # Give half weight to half-hour approximations

        # Convert to popularity scores (0-1)
        popularity_scores = {}
        if total_bookings > 0:
            max_bookings = max(bookings_by_hour.values()) if bookings_by_hour else 1
            for time_key, count in bookings_by_hour.items():
                popularity_scores[time_key] = count / max_bookings

        # Fill in missing hours with baseline values
        for hour in range(7, 22):  # Assuming 7 AM to 10 PM business hours
            for minute in [0, 30]:
                time_key = f"{hour:02d}:{minute:02d}"
                if time_key not in popularity_scores:
                    # Assign baseline popularity based on time of day
                    if 11 <= hour <= 14:  # Lunch time
                        popularity_scores[time_key] = 0.7
                    elif 17 <= hour <= 19:  # After work
                        popularity_scores[time_key] = 0.8
                    elif 9 <= hour <= 16:  # Business hours
                        popularity_scores[time_key] = 0.5
                    else:  # Early morning or evening
                        popularity_scores[time_key] = 0.3

        return popularity_scores

    def _get_specialist_workload(
        self, specialists: List[Dict[str, Any]], target_date: date
    ) -> Dict[str, float]:
        """
        Get workload for each specialist to enable load balancing

        Args:
            specialists: List of specialists
            target_date: Date to check

        Returns:
            Dictionary mapping specialist IDs to workload scores (0-1)
        """
        specialist_ids = [s["id"] for s in specialists]

        # Get appointment counts for the target date
        appointment_counts = (
            Appointment.objects.filter(
                specialist_id__in=specialist_ids, start_time__date=target_date
            )
            .values("specialist_id")
            .annotate(count=Count("id"))
        )

        # Create workload dictionary
        workload = {s["id"]: 0 for s in specialists}

        # Update with actual counts
        max_count = 1  # Avoid division by zero
        for item in appointment_counts:
            specialist_id = str(item["specialist_id"])
            count = item["count"]
            workload[specialist_id] = count
            max_count = max(max_count, count)

        # Normalize workload scores (higher value = higher workload)
        for specialist_id in workload:
            workload[specialist_id] = workload[specialist_id] / max_count

        return workload

    def _get_specialist_ratings(
        self, specialists: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Get ratings for specialists

        Args:
            specialists: List of specialists

        Returns:
            Dictionary mapping specialist IDs to rating scores (0-1)
        """
        # Simple implementation - in reality, would pull from a rating system
        # Default values based on experience level
        ratings = {}
        for specialist in specialists:
            specialist_id = specialist["id"]
            experience_level = specialist.get("experience_level", "standard")

            if experience_level == "expert":
                base_rating = 0.9
            elif experience_level == "senior":
                base_rating = 0.75
            elif experience_level == "standard":
                base_rating = 0.6
            else:
                base_rating = 0.5

            # Adjust slightly for randomness
            import random

            rating = min(1.0, max(0.1, base_rating + random.uniform(-0.1, 0.1)))
            ratings[specialist_id] = rating

        return ratings

    def _get_service_priority(self, service_id: str) -> float:
        """
        Get priority value for a service (based on price, popularity, etc.)

        Args:
            service_id: Service ID

        Returns:
            Priority score (0-1) with higher being more priority
        """
        try:
            service = Service.objects.get(id=service_id)

            # Basic priority based on price - higher price = higher priority
            # More sophisticated logic would include profit margin, etc.
            price = service.price or 0

            # Get average price for normalization
            avg_price = (
                Service.objects.filter(shop=service.shop).aggregate(avg=Avg("price"))[
                    "avg"
                ]
                or 1
            )

            # Calculate normalized priority (0-1)
            priority = min(1.0, price / (avg_price * 2))  # Cap at 1.0

            return priority

        except Service.DoesNotExist:
            return 0.5  # Default mid-priority

    def _optimize_slot_allocation(
        self,
        base_slots: List[Dict[str, Any]],
        specialists: List[Dict[str, Any]],
        popularity_data: Dict[str, float],
        workload_data: Dict[str, float],
        rating_data: Dict[str, float],
        service_priority: float,
        service: Service,
    ) -> List[Dict[str, Any]]:
        """
        Apply optimization algorithm to allocate specialists to time slots

        Args:
            base_slots: Basic availability slots
            specialists: List of specialists
            popularity_data: Time slot popularity scores
            workload_data: Specialist workload scores
            rating_data: Specialist rating scores
            service_priority: Service priority score
            service: Service object

        Returns:
            List of optimized time slots with best specialist allocation
        """
        # Group base slots by time
        slots_by_time = defaultdict(list)
        for slot in base_slots:
            start_time = slot["start"]
            slots_by_time[start_time].append(slot)

        # Create optimized slots
        optimized_slots = []

        for start_time, time_slots in slots_by_time.items():
            # Get all specialists available for this time slot
            available_specialists = []
            for slot in time_slots:
                if "specialist_id" in slot:
                    specialist_id = slot["specialist_id"]
                    # Find specialist info
                    for s in specialists:
                        if s["id"] == specialist_id:
                            available_specialists.append(s)
                            break

            if not available_specialists:
                continue

            # Calculate optimization score for each specialist for this time slot
            ranked_specialists = []

            # Get popularity score for this time slot
            hour_minute = start_time.split(":")
            hour_key = f"{hour_minute[0]}:00"
            popularity = popularity_data.get(hour_key, 0.5)

            # Combined time slot value (higher = more valuable)
            time_value = popularity * self.weights["popularity"]
            time_value += service_priority * self.weights["service_priority"]

            for specialist in available_specialists:
                specialist_id = specialist["id"]

                # Get specialist-specific scores
                workload = workload_data.get(specialist_id, 0.5)
                rating = rating_data.get(specialist_id, 0.5)

                # Calculate transition score (more complex in reality)
                # For now, use a placeholder approach
                transition_score = 0.5

                # Combined specialist score
                specialist_score = (
                    (1 - workload)
                    * self.weights["load_balance"]  # Invert workload - lower is better
                    + rating * self.weights["specialist_rating"]
                    + transition_score * self.weights["transition_time"]
                )

                # Overall score combines time value and specialist score
                overall_score = time_value + specialist_score

                # Add to ranked list
                ranked_specialists.append(
                    {
                        "specialist": specialist,
                        "score": overall_score,
                        "is_preferred": specialist.get("is_preferred", False),
                    }
                )

            # Sort by score, with preferred specialists first if scores are close
            def sort_key(item):
                score = item["score"]
                if item["is_preferred"]:
                    score += 0.05  # Give preferred specialists a small boost
                return score

            ranked_specialists.sort(key=sort_key, reverse=True)

            # Take the best specialist
            if ranked_specialists:
                best_match = ranked_specialists[0]

                # Create slot with optimized specialist
                original_slot = time_slots[0]  # Take first slot's base data
                optimized_slot = original_slot.copy()

                # Set the best specialist
                optimized_slot["specialist_id"] = best_match["specialist"]["id"]
                optimized_slot["specialist_name"] = best_match["specialist"]["name"]
                optimized_slot["optimization_score"] = best_match["score"]

                # Add popularity/demand data for frontend highlighting
                optimized_slot["popularity"] = popularity

                # Add metadata about alternatives
                if len(ranked_specialists) > 1:
                    alternatives = [
                        r["specialist"]["id"] for r in ranked_specialists[1:3]
                    ]  # Top 2 alternatives
                    optimized_slot["alternative_specialists"] = alternatives

                optimized_slots.append(optimized_slot)

        # Sort by start time
        optimized_slots.sort(key=lambda x: x["start"])

        return optimized_slots

    def _personalize_slots(
        self, slots: List[Dict[str, Any]], customer_id: str
    ) -> List[Dict[str, Any]]:
        """
        Personalize slot rankings based on customer's history and preferences

        Args:
            slots: List of optimized slots
            customer_id: Customer ID for personalization

        Returns:
            List of slots with personalized rankings
        """
        # In a full implementation, analyze customer's:
        # - Preferred booking times
        # - Preferred specialists
        # - Cancellation history
        # - Service history

        # For now, use a simple boosting mechanism for demonstration
        try:
            from apps.bookingapp.models import Appointment

            # Get customer's previous appointments
            previous_appointments = Appointment.objects.filter(
                customer_id=customer_id
            ).order_by("-start_time")[:10]

            # Extract patterns
            preferred_specialists = defaultdict(int)
            preferred_hours = defaultdict(int)

            for appointment in previous_appointments:
                # Track specialist preference
                if appointment.specialist_id:
                    preferred_specialists[str(appointment.specialist_id)] += 1

                # Track hour preference
                hour = appointment.start_time.hour
                preferred_hours[hour] += 1

            # Normalize specialist preferences
            total_specialist_bookings = sum(preferred_specialists.values()) or 1
            for specialist_id in preferred_specialists:
                preferred_specialists[specialist_id] /= total_specialist_bookings

            # Normalize hour preferences
            total_hour_bookings = sum(preferred_hours.values()) or 1
            for hour in preferred_hours:
                preferred_hours[hour] /= total_hour_bookings

            # Apply personalization boosts
            personalized_slots = []

            for slot in slots:
                # Copy the slot
                personalized_slot = slot.copy()

                # Get base score
                base_score = personalized_slot.get("optimization_score", 0.5)

                # Apply specialist boost if customer has history with this specialist
                specialist_id = personalized_slot.get("specialist_id")
                if specialist_id and specialist_id in preferred_specialists:
                    specialist_boost = (
                        preferred_specialists[specialist_id] * 0.1
                    )  # Up to 10% boost
                    base_score += specialist_boost

                # Apply time of day boost
                hour = int(personalized_slot["start"].split(":")[0])
                if hour in preferred_hours:
                    time_boost = preferred_hours[hour] * 0.1  # Up to 10% boost
                    base_score += time_boost

                # Update score
                personalized_slot["optimization_score"] = min(1.0, base_score)
                personalized_slot["personalized"] = True

                personalized_slots.append(personalized_slot)

            # Re-sort based on personalized scores
            personalized_slots.sort(
                key=lambda x: (-x.get("optimization_score", 0), x["start"])
            )

            return personalized_slots

        except Exception as e:
            logger.error(f"Error in slot personalization: {e}")
            return slots

    def invalidate_cache(self, shop_id=None, service_id=None, date_str=None):
        """
        Invalidate cache for dynamic slot allocation

        Args:
            shop_id: Optional shop ID to invalidate
            service_id: Optional service ID to invalidate
            date_str: Optional date string to invalidate
        """
        patterns = []

        if shop_id and service_id and date_str:
            patterns.append(f"{self.CACHE_PREFIX}{shop_id}:{service_id}:{date_str}*")
        elif shop_id and service_id:
            patterns.append(f"{self.CACHE_PREFIX}{shop_id}:{service_id}:*")
        elif shop_id and date_str:
            patterns.append(f"{self.CACHE_PREFIX}{shop_id}:*:{date_str}*")
        elif service_id and date_str:
            patterns.append(f"{self.CACHE_PREFIX}*:{service_id}:{date_str}*")
        elif shop_id:
            patterns.append(f"{self.CACHE_PREFIX}{shop_id}:*")
        elif service_id:
            patterns.append(f"{self.CACHE_PREFIX}*:{service_id}:*")
        elif date_str:
            patterns.append(f"{self.CACHE_PREFIX}*:*:{date_str}*")
        else:
            patterns.append(f"{self.CACHE_PREFIX}*")

        # Delete matching cache entries
        for pattern in patterns:
            cache.delete_pattern(pattern)
