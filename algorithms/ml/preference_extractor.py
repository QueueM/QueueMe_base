"""
Customer preference extraction algorithm.

This module contains algorithms for extracting and modeling customer preferences
based on their behavior, bookings, content interactions, and explicit preferences.
These preferences are used to power personalized recommendations and experiences.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)


class PreferenceExtractor:
    """
    Customer preference extraction engine.

    This class analyzes various customer behaviors to extract their preferences
    for categories, services, specialists, shops, and time slots. These preferences
    are normalized and weighted to produce a comprehensive preference profile.
    """

    # Weight factors for different preference signals
    BOOKING_WEIGHT = 4.0
    EXPLICIT_PREFERENCE_WEIGHT = 5.0
    CONTENT_INTERACTION_WEIGHT = 2.0
    SHOP_VISIT_WEIGHT = 3.0
    SEARCH_WEIGHT = 1.5

    # Recency weights for temporal relevance
    RECENT_MULTIPLIER = 2.0  # Last 7 days
    MEDIUM_MULTIPLIER = 1.5  # Last 30 days
    STANDARD_MULTIPLIER = 1.0  # Older

    # Maximum values to normalize preference scores
    MAX_PREFERENCES_PER_TYPE = 20

    def __init__(self, customer_id: str = None):
        """
        Initialize preference extractor.

        Args:
            customer_id: The ID of the customer to extract preferences for
        """
        self.customer_id = customer_id

    def extract_preferences(self, force_update: bool = False) -> Dict:
        """
        Extract comprehensive customer preference profile.

        Args:
            force_update: Force recalculation even if cached preferences exist

        Returns:
            Dictionary with preference categories and scores
        """
        try:
            if not self.customer_id:
                return {}

            # Check for cached preferences unless forced update
            if not force_update:
                cached_preferences = self._get_cached_preferences()
                if cached_preferences:
                    return cached_preferences

            # Extract preferences from different signals
            booking_preferences = self._extract_booking_preferences()
            explicit_preferences = self._extract_explicit_preferences()
            content_preferences = self._extract_content_interaction_preferences()
            shop_preferences = self._extract_shop_visit_preferences()
            search_preferences = self._extract_search_preferences()

            # Combine preferences with weights
            preferences = self._combine_preferences(
                [
                    (booking_preferences, self.BOOKING_WEIGHT),
                    (explicit_preferences, self.EXPLICIT_PREFERENCE_WEIGHT),
                    (content_preferences, self.CONTENT_INTERACTION_WEIGHT),
                    (shop_preferences, self.SHOP_VISIT_WEIGHT),
                    (search_preferences, self.SEARCH_WEIGHT),
                ]
            )

            # Add temporal preferences (time of day, day of week)
            preferences["time_preferences"] = self._extract_time_preferences()

            # Add location if available
            location_preferences = self._extract_location_preferences()
            if location_preferences:
                preferences["location"] = location_preferences

            # Cache the calculated preferences
            self._cache_preferences(preferences)

            return preferences

        except Exception as e:
            logger.exception(f"Error extracting customer preferences: {str(e)}")
            return {}

    def _extract_booking_preferences(self) -> Dict:
        """
        Extract preferences from booking history.

        Returns:
            Dictionary with preferences from bookings
        """
        try:
            # Import here to avoid circular imports
            from apps.bookingapp.models import Appointment

            # Initialize preference containers
            category_preferences = defaultdict(float)
            service_preferences = defaultdict(float)
            specialist_preferences = defaultdict(float)
            shop_preferences = defaultdict(float)

            # Get completed bookings from the last 6 months
            six_months_ago = timezone.now() - timedelta(days=180)
            bookings = Appointment.objects.filter(
                customer_id=self.customer_id,
                status__in=["completed", "cancelled", "no_show"],
                created_at__gte=six_months_ago,
            ).select_related("service", "specialist", "shop")

            # Process each booking
            for booking in bookings:
                # Calculate recency weight
                recency_weight = self._calculate_recency_weight(booking.created_at)

                # Add service category preference if available
                if booking.service and hasattr(booking.service, "category_id"):
                    category_id = booking.service.category_id
                    if category_id:
                        category_preferences[category_id] += 1.0 * recency_weight

                        # Also add parent category if exists
                        if (
                            hasattr(booking.service.category, "parent_id")
                            and booking.service.category.parent_id
                        ):
                            parent_id = booking.service.category.parent_id
                            category_preferences[parent_id] += (
                                0.5 * recency_weight
                            )  # Lower weight for parent

                # Add service preference
                if booking.service_id:
                    service_preferences[booking.service_id] += 1.0 * recency_weight

                # Add specialist preference
                if booking.specialist_id:
                    specialist_preferences[booking.specialist_id] += (
                        1.0 * recency_weight
                    )

                # Add shop preference
                if booking.shop_id:
                    shop_preferences[booking.shop_id] += 1.0 * recency_weight

                    # Add extra preference weight for repeat visits
                    repeat_visits = Appointment.objects.filter(
                        customer_id=self.customer_id,
                        shop_id=booking.shop_id,
                        status="completed",
                    ).count()

                    if repeat_visits > 1:
                        # Logarithmic scaling for repeat visits (diminishing returns)
                        shop_preferences[booking.shop_id] += (
                            np.log2(repeat_visits) * 0.5 * recency_weight
                        )

            # Normalize preferences
            return {
                "categories": self._normalize_preferences(category_preferences),
                "services": self._normalize_preferences(service_preferences),
                "specialists": self._normalize_preferences(specialist_preferences),
                "shops": self._normalize_preferences(shop_preferences),
            }

        except Exception as e:
            logger.debug(f"Error extracting booking preferences: {str(e)}")
            return {}

    def _extract_explicit_preferences(self) -> Dict:
        """
        Extract explicitly stated preferences.

        Returns:
            Dictionary with explicit preferences
        """
        try:
            # Import here to avoid circular imports
            from apps.customersapp.models import Customer, CustomerPreference

            # Initialize preference containers
            category_preferences = defaultdict(float)
            service_preferences = defaultdict(float)
            specialist_preferences = defaultdict(float)
            shop_preferences = defaultdict(float)

            # Get explicit preferences if they exist
            try:
                customer = Customer.objects.get(user_id=self.customer_id)
                explicit_prefs = CustomerPreference.objects.filter(customer=customer)

                for pref in explicit_prefs:
                    if pref.preference_type == "category" and pref.category_id:
                        category_preferences[pref.category_id] = pref.strength
                    elif pref.preference_type == "service" and pref.service_id:
                        service_preferences[pref.service_id] = pref.strength
                    elif pref.preference_type == "specialist" and pref.specialist_id:
                        specialist_preferences[pref.specialist_id] = pref.strength
                    elif pref.preference_type == "shop" and pref.shop_id:
                        shop_preferences[pref.shop_id] = pref.strength
            except Customer.DoesNotExist:
                # Customer profile may not exist yet
                pass

            # Check favorites (treated as explicit preferences)
            from apps.customersapp.models import Favorite

            favorites = Favorite.objects.filter(customer_id=self.customer_id)

            for fav in favorites:
                if fav.content_type.model == "category":
                    category_preferences[fav.object_id] = 5.0  # Maximum strength
                elif fav.content_type.model == "service":
                    service_preferences[fav.object_id] = 5.0
                elif fav.content_type.model == "specialist":
                    specialist_preferences[fav.object_id] = 5.0
                elif fav.content_type.model == "shop":
                    shop_preferences[fav.object_id] = 5.0

            # No need to normalize explicit preferences as they are already on a defined scale
            return {
                "categories": dict(category_preferences),
                "services": dict(service_preferences),
                "specialists": dict(specialist_preferences),
                "shops": dict(shop_preferences),
            }

        except Exception as e:
            logger.debug(f"Error extracting explicit preferences: {str(e)}")
            return {}

    def _extract_content_interaction_preferences(self) -> Dict:
        """
        Extract preferences from content interactions (reels, stories, etc.).

        Returns:
            Dictionary with preferences from content interactions
        """
        try:
            # Import here to avoid circular imports
            from apps.reelsapp.models import ReelEngagement
            from apps.storiesapp.models import StoryView

            # Initialize preference containers
            category_preferences = defaultdict(float)
            shop_preferences = defaultdict(float)

            # Process reel engagements (comments, likes, shares)
            three_months_ago = timezone.now() - timedelta(days=90)
            engagements = ReelEngagement.objects.filter(
                user_id=self.customer_id, created_at__gte=three_months_ago
            ).select_related("reel")

            for engagement in engagements:
                # Calculate recency weight
                recency_weight = self._calculate_recency_weight(engagement.created_at)

                # Calculate engagement weight based on type
                engagement_weight = 1.0  # Default
                if engagement.engagement_type == "like":
                    engagement_weight = 1.0
                elif engagement.engagement_type == "comment":
                    engagement_weight = 2.0  # Comments show more interest
                elif engagement.engagement_type == "share":
                    engagement_weight = 3.0  # Shares show highest interest

                # Add shop preference
                if engagement.reel and engagement.reel.shop_id:
                    shop_preferences[engagement.reel.shop_id] += (
                        engagement_weight * recency_weight
                    )

                # Add category preference if available
                if (
                    engagement.reel
                    and hasattr(engagement.reel, "service")
                    and engagement.reel.service
                    and hasattr(engagement.reel.service, "category_id")
                ):
                    category_id = engagement.reel.service.category_id
                    if category_id:
                        category_preferences[category_id] += (
                            engagement_weight * recency_weight
                        )

            # Process story views
            story_views = StoryView.objects.filter(
                viewer_id=self.customer_id, viewed_at__gte=three_months_ago
            ).select_related("story")

            for view in story_views:
                # Calculate recency weight
                recency_weight = self._calculate_recency_weight(view.viewed_at)

                # Calculate view weight based on completion
                view_weight = 0.5  # Default for partial views
                if view.completed:
                    view_weight = 1.0  # Full views indicate more interest

                # Add shop preference
                if view.story and view.story.shop_id:
                    shop_preferences[view.story.shop_id] += view_weight * recency_weight

                # Add category preference if story has category context
                if (
                    view.story
                    and hasattr(view.story, "context_type")
                    and view.story.context_type == "category"
                    and view.story.context_id
                ):
                    category_preferences[view.story.context_id] += (
                        view_weight * recency_weight
                    )

            # Normalize preferences
            return {
                "categories": self._normalize_preferences(category_preferences),
                "shops": self._normalize_preferences(shop_preferences),
            }

        except Exception as e:
            logger.debug(f"Error extracting content interaction preferences: {str(e)}")
            return {}

    def _extract_shop_visit_preferences(self) -> Dict:
        """
        Extract preferences from shop page visits.

        Returns:
            Dictionary with preferences from shop visits
        """
        try:
            # Import here to avoid circular imports
            from apps.shopapp.models import ShopView

            # Initialize preference containers
            shop_preferences = defaultdict(float)
            category_preferences = defaultdict(float)

            # Get shop views from the last 3 months
            three_months_ago = timezone.now() - timedelta(days=90)
            shop_views = ShopView.objects.filter(
                viewer_id=self.customer_id, viewed_at__gte=three_months_ago
            ).select_related("shop")

            # Process each shop view
            for view in shop_views:
                # Calculate recency weight
                recency_weight = self._calculate_recency_weight(view.viewed_at)

                # Add shop preference
                shop_preferences[view.shop_id] += 1.0 * recency_weight

                # Add category preferences based on shop's primary categories
                if view.shop:
                    # Get shop's main service categories
                    from apps.serviceapp.models import Service

                    service_categories = (
                        Service.objects.filter(shop_id=view.shop_id)
                        .values("category_id")
                        .annotate(count=Count("id"))
                        .order_by("-count")[:3]
                    )  # Top 3 categories

                    for cat_entry in service_categories:
                        if cat_entry["category_id"]:
                            # Weight by service count within shop
                            category_preferences[cat_entry["category_id"]] += (
                                0.5
                                * recency_weight
                                * (
                                    cat_entry["count"]
                                    / max(
                                        1, sum(c["count"] for c in service_categories)
                                    )
                                )
                            )

            # Normalize preferences
            return {
                "shops": self._normalize_preferences(shop_preferences),
                "categories": self._normalize_preferences(category_preferences),
            }

        except Exception as e:
            logger.debug(f"Error extracting shop visit preferences: {str(e)}")
            return {}

    def _extract_search_preferences(self) -> Dict:
        """
        Extract preferences from search history.

        Returns:
            Dictionary with preferences from search queries
        """
        try:
            # Import here to avoid circular imports
            from apps.searchapp.models import SearchQuery, SearchResult

            # Initialize preference containers
            category_preferences = defaultdict(float)
            shop_preferences = defaultdict(float)
            service_preferences = defaultdict(float)

            # Get search queries from the last 3 months
            three_months_ago = timezone.now() - timedelta(days=90)
            search_queries = SearchQuery.objects.filter(
                user_id=self.customer_id, created_at__gte=three_months_ago
            )

            # Process each search query
            for query in search_queries:
                # Calculate recency weight
                recency_weight = self._calculate_recency_weight(query.created_at)

                # Get search results clicked by user for this query
                clicked_results = SearchResult.objects.filter(query=query, clicked=True)

                for result in clicked_results:
                    # Add preference based on result type
                    if result.result_type == "category" and result.result_id:
                        category_preferences[result.result_id] += 1.0 * recency_weight
                    elif result.result_type == "shop" and result.result_id:
                        shop_preferences[result.result_id] += 1.0 * recency_weight
                    elif result.result_type == "service" and result.result_id:
                        service_preferences[result.result_id] += 1.0 * recency_weight

                # If query has category context, add preference
                if query.category_id:
                    category_preferences[query.category_id] += 0.5 * recency_weight

            # Normalize preferences
            return {
                "categories": self._normalize_preferences(category_preferences),
                "shops": self._normalize_preferences(shop_preferences),
                "services": self._normalize_preferences(service_preferences),
            }

        except Exception as e:
            logger.debug(f"Error extracting search preferences: {str(e)}")
            return {}

    def _extract_time_preferences(self) -> Dict:
        """
        Extract temporal preferences (time of day, day of week).

        Returns:
            Dictionary with temporal preferences
        """
        try:
            # Import here to avoid circular imports
            from apps.bookingapp.models import Appointment

            # Initialize preference counters
            hour_counts = Counter()
            day_counts = Counter()

            # Get bookings from the last 6 months
            six_months_ago = timezone.now() - timedelta(days=180)
            bookings = Appointment.objects.filter(
                customer_id=self.customer_id,
                status__in=["completed", "scheduled", "confirmed"],
                created_at__gte=six_months_ago,
            )

            total_bookings = bookings.count()

            if total_bookings == 0:
                return {}

            # Count bookings by hour and day
            for booking in bookings:
                if booking.start_time:
                    hour = booking.start_time.hour
                    # Convert to 3-hour blocks for better generalization
                    hour_block = hour // 3
                    hour_counts[hour_block] += 1

                    # Convert weekday to our system (0 = Sunday, 6 = Saturday)
                    weekday = booking.start_time.weekday()
                    if weekday == 6:  # Sunday in Python is 6
                        adj_weekday = 0
                    else:
                        adj_weekday = weekday + 1

                    day_counts[adj_weekday] += 1

            # Normalize to get preferences
            hour_preferences = {}
            for hour, count in hour_counts.items():
                hour_preferences[hour] = count / total_bookings

            day_preferences = {}
            for day, count in day_counts.items():
                day_preferences[day] = count / total_bookings

            return {
                "hour_blocks": hour_preferences,  # 0-7 representing 3-hour blocks
                "days": day_preferences,  # 0-6 representing Sunday to Saturday
            }

        except Exception as e:
            logger.debug(f"Error extracting time preferences: {str(e)}")
            return {}

    def _extract_location_preferences(self) -> Tuple[float, float]:
        """
        Extract preferred location based on customer profile.

        Returns:
            Tuple of (latitude, longitude) or None
        """
        try:
            # Import here to avoid circular imports
            from apps.customersapp.models import Customer

            try:
                customer = Customer.objects.get(user_id=self.customer_id)
                if hasattr(customer, "location") and customer.location:
                    return (customer.location.latitude, customer.location.longitude)
            except Customer.DoesNotExist:
                # Customer profile may not exist yet
                pass

            # If no explicit location, try to infer from bookings
            from apps.bookingapp.models import Appointment

            # Get most frequent booking location
            recent_bookings = (
                Appointment.objects.filter(
                    customer_id=self.customer_id,
                    status__in=["completed", "scheduled", "confirmed"],
                )
                .select_related("shop__location")
                .order_by("-created_at")[:5]
            )

            if recent_bookings:
                # Collect locations from bookings
                locations = []
                for booking in recent_bookings:
                    if booking.shop and booking.shop.location:
                        locations.append(
                            (
                                booking.shop.location.latitude,
                                booking.shop.location.longitude,
                            )
                        )

                if locations:
                    # Calculate average location as an approximation
                    avg_lat = sum(loc[0] for loc in locations) / len(locations)
                    avg_lng = sum(loc[1] for loc in locations) / len(locations)
                    return (avg_lat, avg_lng)

            return None

        except Exception as e:
            logger.debug(f"Error extracting location preferences: {str(e)}")
            return None

    def _combine_preferences(
        self, weighted_preferences: List[Tuple[Dict, float]]
    ) -> Dict:
        """
        Combine multiple preference sources with weights.

        Args:
            weighted_preferences: List of (preferences_dict, weight) tuples

        Returns:
            Combined preference dictionary
        """
        combined = {
            "categories": defaultdict(float),
            "services": defaultdict(float),
            "specialists": defaultdict(float),
            "shops": defaultdict(float),
        }

        # Combine each preference source
        for prefs, weight in weighted_preferences:
            for category in ["categories", "services", "specialists", "shops"]:
                if category in prefs:
                    for item_id, score in prefs[category].items():
                        combined[category][item_id] += score * weight

        # Normalize the combined scores
        return {
            "categories": self._normalize_preferences(combined["categories"]),
            "services": self._normalize_preferences(combined["services"]),
            "specialists": self._normalize_preferences(combined["specialists"]),
            "shops": self._normalize_preferences(combined["shops"]),
        }

    def _normalize_preferences(self, preferences: Dict) -> Dict:
        """
        Normalize preference scores to 0-1 range.

        Args:
            preferences: Dictionary of preference scores

        Returns:
            Dictionary with normalized scores
        """
        # Return empty dict if no preferences
        if not preferences:
            return {}

        # Find maximum score for normalization
        max_score = max(preferences.values()) if preferences else 1.0

        # Normalize all scores to 0-1 range
        normalized = {}
        for item_id, score in preferences.items():
            normalized[item_id] = score / max_score if max_score > 0 else 0

        # Limit to top preferences to avoid noise
        if len(normalized) > self.MAX_PREFERENCES_PER_TYPE:
            sorted_prefs = sorted(normalized.items(), key=lambda x: x[1], reverse=True)
            normalized = dict(sorted_prefs[: self.MAX_PREFERENCES_PER_TYPE])

        return normalized

    def _calculate_recency_weight(self, timestamp: datetime) -> float:
        """
        Calculate recency weight for a timestamp.

        Args:
            timestamp: The datetime to evaluate

        Returns:
            Recency weight multiplier
        """
        now = timezone.now()
        days_ago = (now - timestamp).days

        if days_ago <= 7:
            return self.RECENT_MULTIPLIER
        elif days_ago <= 30:
            return self.MEDIUM_MULTIPLIER
        else:
            return self.STANDARD_MULTIPLIER

    def _get_cached_preferences(self) -> Optional[Dict]:
        """
        Get cached preferences if available and not stale.

        Returns:
            Cached preferences or None if not available/stale
        """
        try:
            # Import here to avoid circular imports
            from apps.customersapp.models import CustomerPreferenceCache

            # Check for recent cache (less than 24 hours old)
            one_day_ago = timezone.now() - timedelta(hours=24)
            cache = CustomerPreferenceCache.objects.filter(
                customer_id=self.customer_id, updated_at__gte=one_day_ago
            ).first()

            if cache and cache.preferences:
                return cache.preferences

            return None

        except Exception as e:
            logger.debug(f"Error retrieving cached preferences: {str(e)}")
            return None

    def _cache_preferences(self, preferences: Dict) -> None:
        """
        Cache calculated preferences for future use.

        Args:
            preferences: The preference dictionary to cache
        """
        try:
            # Import here to avoid circular imports
            from apps.customersapp.models import CustomerPreferenceCache

            # Update or create preference cache
            CustomerPreferenceCache.objects.update_or_create(
                customer_id=self.customer_id, defaults={"preferences": preferences}
            )

        except Exception as e:
            logger.debug(f"Error caching preferences: {str(e)}")
            # Non-critical failure, can be ignored
