import logging
import math
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SpecialistRanker:
    """
    Advanced algorithm for ranking and recommending specialists based
    on ratings, availability, expertise, and customer preferences.

    This algorithm improves specialist discovery by:
    1. Considering multiple ranking factors
    2. Personalizing recommendations for customers
    3. Balancing specialist quality with availability
    4. Accounting for experience and specialization
    5. Incorporating historical success rates
    """

    def __init__(
        self,
        rating_weight: float = 2.0,
        experience_weight: float = 1.5,
        availability_weight: float = 1.0,
        booking_count_weight: float = 0.8,
        portfolio_weight: float = 0.5,
        category_match_weight: float = 1.0,
        distance_weight: float = 0.3,
        verified_boost: float = 1.2,
    ):
        """
        Initialize the specialist ranker with configurable weights.

        Args:
            rating_weight: Weight for specialist ratings factor
            experience_weight: Weight for years of experience
            availability_weight: Weight for availability factor
            booking_count_weight: Weight for popularity (booking count)
            portfolio_weight: Weight for portfolio size and quality
            category_match_weight: Weight for category/skill matching
            distance_weight: Weight for proximity to customer (if relevant)
            verified_boost: Boost factor for verified specialists
        """
        self.rating_weight = rating_weight
        self.experience_weight = experience_weight
        self.availability_weight = availability_weight
        self.booking_count_weight = booking_count_weight
        self.portfolio_weight = portfolio_weight
        self.category_match_weight = category_match_weight
        self.distance_weight = distance_weight
        self.verified_boost = verified_boost

    def rank_specialists(
        self,
        specialists: List[Dict],
        customer_data: Optional[Dict] = None,
        service_id: Optional[str] = None,
        category_id: Optional[str] = None,
        location_data: Optional[Dict] = None,
        availability_date: Optional[datetime.date] = None,
        limit: int = 20,
    ) -> Dict:
        """
        Rank specialists based on multiple factors.

        Args:
            specialists: List of specialist objects with fields:
                - id: Unique identifier
                - employee_id: ID of the employee record
                - employee: Employee details (name, position, etc.)
                - ratings: Average rating score or None
                - ratings_count: Number of ratings
                - experience_years: Years of experience
                - booking_count: Number of successful bookings
                - portfolio_items: List of portfolio items or count
                - categories: List of categories/services they specialize in
                - location: Dict with latitude and longitude
                - is_verified: Whether specialist is verified
                - availability: Optional availability data
            customer_data: Optional dict with customer preferences:
                - id: Customer ID
                - previous_bookings: List of previous booking records
                - favorite_specialists: List of favorite specialist IDs
                - preferred_categories: List of preferred categories
                - location: Dict with latitude and longitude
            service_id: Optional specific service ID to match
            category_id: Optional category ID to match
            location_data: Optional location data (lat/long) for proximity calculation
            availability_date: Optional date to consider for availability
            limit: Maximum number of specialists to return

        Returns:
            A dictionary containing:
            - ranked_specialists: List of specialists with scores
            - ranking_factors: Explanation of how specialists were ranked
            - top_specialist: The highest-ranking specialist
            - personalized: Whether the ranking was personalized
        """
        # Initialize result
        result = {
            "ranked_specialists": [],
            "ranking_factors": {},
            "top_specialist": None,
            "personalized": customer_data is not None,
        }

        if not specialists:
            return result

        # Calculate scores for each specialist
        scored_specialists = []
        ranking_factors = {}

        for specialist in specialists:
            # Create a copy of specialist to avoid modifying original
            specialist_copy = specialist.copy()
            specialist_id = specialist["id"]

            # Initialize factors to track scoring components
            factors = {}

            # 1. Base score starts at 1.0
            base_score = 1.0
            factors["base"] = base_score

            # 2. Rating score (if available)
            rating_score = self._calculate_rating_score(specialist)
            factors["rating"] = rating_score * self.rating_weight

            # 3. Experience score
            experience_score = self._calculate_experience_score(specialist)
            factors["experience"] = experience_score * self.experience_weight

            # 4. Booking count / popularity score
            booking_score = self._calculate_booking_score(specialist)
            factors["booking_count"] = booking_score * self.booking_count_weight

            # 5. Portfolio score
            portfolio_score = self._calculate_portfolio_score(specialist)
            factors["portfolio"] = portfolio_score * self.portfolio_weight

            # 6. Availability score (if date provided)
            availability_score = 1.0
            if availability_date:
                availability_score = self._calculate_availability_score(
                    specialist, availability_date
                )
            factors["availability"] = availability_score * self.availability_weight

            # 7. Category/service match score
            category_match_score = self._calculate_category_match(
                specialist, service_id, category_id
            )
            factors["category_match"] = category_match_score * self.category_match_weight

            # 8. Location/distance score (if location provided)
            distance_score = 1.0
            if location_data:
                distance_score = self._calculate_distance_score(specialist, location_data)
            factors["distance"] = distance_score * self.distance_weight

            # 9. Verification boost
            verified_boost = self.verified_boost if specialist.get("is_verified", False) else 1.0
            factors["verified_boost"] = verified_boost

            # 10. Customer personalization (if customer data provided)
            personalization_score = 1.0
            if customer_data:
                personalization_score = self._calculate_personalization_score(
                    specialist, customer_data
                )
            factors["personalization"] = personalization_score

            # Calculate final score
            final_score = (
                base_score
                + (rating_score * self.rating_weight)
                + (experience_score * self.experience_weight)
                + (booking_score * self.booking_count_weight)
                + (portfolio_score * self.portfolio_weight)
                + (availability_score * self.availability_weight)
                + (category_match_score * self.category_match_weight)
                + (distance_score * self.distance_weight)
            )

            # Apply boosts
            final_score *= verified_boost * personalization_score

            # Store score and factors
            specialist_copy["_score"] = final_score
            ranking_factors[specialist_id] = factors

            scored_specialists.append(specialist_copy)

        # Sort by score (highest first)
        ranked_specialists = sorted(scored_specialists, key=lambda x: x["_score"], reverse=True)

        # Apply limit if provided
        if limit:
            ranked_specialists = ranked_specialists[:limit]

        # Cleanup - remove internal score
        for specialist in ranked_specialists:
            if "_score" in specialist:
                specialist.pop("_score")

        # Get top specialist (if any)
        top_specialist = ranked_specialists[0] if ranked_specialists else None

        # Set result fields
        result["ranked_specialists"] = ranked_specialists
        result["ranking_factors"] = ranking_factors
        result["top_specialist"] = top_specialist

        return result

    def _calculate_rating_score(self, specialist: Dict) -> float:
        """
        Calculate score based on ratings.
        Accounts for both rating value and number of ratings.
        """
        # Get rating value and count
        rating = specialist.get("ratings")
        ratings_count = specialist.get("ratings_count", 0)

        # If no ratings, return baseline score
        if rating is None or ratings_count == 0:
            return 0.5  # Neutral score for unrated specialists

        # Normalize rating to 0-1 scale (assuming 1-5 rating scale)
        normalized_rating = (rating - 1) / 4.0

        # Apply confidence adjustment based on number of ratings
        # This prevents a specialist with a single 5-star rating from outranking
        # a specialist with hundreds of 4.8-star ratings
        confidence = min(1.0, math.log10(ratings_count + 1) / 2.0)

        # Weighted score: blend of normalized rating and baseline 0.5
        # as confidence increases, we trust the rating more
        weighted_score = (normalized_rating * confidence) + (0.5 * (1 - confidence))

        return weighted_score

    def _calculate_experience_score(self, specialist: Dict) -> float:
        """
        Calculate score based on years of experience.
        """
        experience_years = specialist.get("experience_years", 0)

        # Normalize experience (cap at 10 years for max score)
        normalized_experience = min(1.0, experience_years / 10.0)

        return normalized_experience

    def _calculate_booking_score(self, specialist: Dict) -> float:
        """
        Calculate score based on number of successful bookings.
        """
        booking_count = specialist.get("booking_count", 0)

        # Use logarithmic scale to dampen effect of very high counts
        # log(101) ≈ 4.6, log(1001) ≈ 6.9, giving diminishing returns
        normalized_bookings = min(1.0, math.log10(booking_count + 1) / 6.0)

        return normalized_bookings

    def _calculate_portfolio_score(self, specialist: Dict) -> float:
        """
        Calculate score based on portfolio size and quality.
        """
        # Check if we have portfolio items list or just a count
        portfolio_items = specialist.get("portfolio_items", [])

        if isinstance(portfolio_items, list):
            portfolio_count = len(portfolio_items)
        else:
            # Assume it's a count
            portfolio_count = int(portfolio_items) if portfolio_items else 0

        # Normalize portfolio size (cap at 20 items for max score)
        normalized_portfolio = min(1.0, portfolio_count / 20.0)

        # In a real implementation, would also consider portfolio quality
        # based on customer feedback, views, etc.

        return normalized_portfolio

    def _calculate_availability_score(self, specialist: Dict, date: datetime.date) -> float:
        """
        Calculate score based on specialist availability on the given date.
        Higher score for more available slots.
        """
        # Get availability data if present
        availability = specialist.get("availability", {})

        # Format date as string for lookup
        date_str = date.isoformat()

        # If no availability data, return neutral score
        if not availability or date_str not in availability:
            return 0.5

        # Get available hours for the date
        available_hours = availability.get(date_str, 0)

        # If explicitly marked as unavailable, return low score
        if available_hours == 0:
            return 0.0

        # Normalize availability (assuming 8-hour workday as maximum)
        normalized_availability = min(1.0, available_hours / 8.0)

        return normalized_availability

    def _calculate_category_match(
        self, specialist: Dict, service_id: Optional[str], category_id: Optional[str]
    ) -> float:
        """
        Calculate score based on category/service match.
        """
        # If neither service nor category specified, return neutral score
        if not service_id and not category_id:
            return 0.5

        # Get specialist categories and services
        specialist_categories = specialist.get("categories", [])
        specialist_services = specialist.get("services", [])

        # Check for exact service match (highest priority)
        if service_id and service_id in specialist_services:
            # Check if it's a primary service
            if specialist.get("primary_services") and service_id in specialist.get(
                "primary_services", []
            ):
                return 1.0  # Perfect match with primary service
            else:
                return 0.9  # Service match but not primary

        # Check for category match
        if category_id and category_id in specialist_categories:
            # Check if it's a primary category
            if specialist.get("primary_categories") and category_id in specialist.get(
                "primary_categories", []
            ):
                return 0.8  # Category match with primary category
            else:
                return 0.7  # Category match but not primary

        # If service specified but not matched, check if specialist offers
        # any service in the same category (would need a service-to-category mapping)

        # If no match at all, return low score
        return 0.1

    def _calculate_distance_score(self, specialist: Dict, location_data: Dict) -> float:
        """
        Calculate score based on distance/proximity.
        """
        # Get location data
        customer_lat = location_data.get("latitude")
        customer_lng = location_data.get("longitude")

        specialist_location = specialist.get("location", {})
        specialist_lat = specialist_location.get("latitude")
        specialist_lng = specialist_location.get("longitude")

        # If either location is missing, return neutral score
        if not customer_lat or not customer_lng or not specialist_lat or not specialist_lng:
            return 0.5

        # Calculate distance in kilometers
        distance_km = self._calculate_distance(
            customer_lat, customer_lng, specialist_lat, specialist_lng
        )

        # Normalize distance (closer is better)
        # Using an exponential decay function
        # Distance of 0km = score 1.0, 10km = score 0.5, etc.
        normalized_distance = math.exp(-distance_km / 10.0)

        return normalized_distance

    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.
        """
        from math import atan2, cos, radians, sin, sqrt

        # Convert latitude and longitude from degrees to radians
        lat1_rad = radians(float(lat1))
        lng1_rad = radians(float(lng1))
        lat2_rad = radians(float(lat2))
        lng2_rad = radians(float(lng2))

        # Haversine formula
        dlng = lng2_rad - lng1_rad
        dlat = lat2_rad - lat1_rad

        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        # Earth radius in kilometers
        radius = 6371.0

        # Calculate distance
        distance = radius * c

        return distance

    def _calculate_personalization_score(self, specialist: Dict, customer_data: Dict) -> float:
        """
        Calculate personalization score based on customer history and preferences.
        """
        specialist_id = specialist["id"]

        # Initialize personalization boost at 1.0 (neutral)
        personalization_score = 1.0

        # Check if specialist is in customer's favorites
        favorite_specialists = customer_data.get("favorite_specialists", [])
        if specialist_id in favorite_specialists:
            personalization_score *= 1.5  # 50% boost for favorites

        # Check if customer has previous bookings with this specialist
        previous_bookings = customer_data.get("previous_bookings", [])
        specialist_bookings = [
            b for b in previous_bookings if b.get("specialist_id") == specialist_id
        ]

        if specialist_bookings:
            # Boost based on number of previous bookings (with cap)
            booking_boost = min(1.3, 1.0 + (len(specialist_bookings) * 0.05))
            personalization_score *= booking_boost

            # Check if previous experiences were positive
            positive_bookings = [b for b in specialist_bookings if b.get("rating", 0) >= 4.0]

            if positive_bookings:
                # Additional boost for positive experiences
                positive_ratio = len(positive_bookings) / len(specialist_bookings)
                positive_boost = 1.0 + (positive_ratio * 0.2)
                personalization_score *= positive_boost

        # Check if specialist categories match customer preferences
        specialist_categories = set(specialist.get("categories", []))
        preferred_categories = set(customer_data.get("preferred_categories", []))

        if specialist_categories and preferred_categories:
            # Calculate category overlap
            overlap = specialist_categories.intersection(preferred_categories)

            if overlap:
                # Boost based on category match ratio
                match_ratio = len(overlap) / len(preferred_categories)
                category_boost = 1.0 + (match_ratio * 0.2)
                personalization_score *= category_boost

        return personalization_score
