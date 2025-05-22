"""
Rating Aggregation Service

Advanced rating calculation and aggregation system for shops and specialists,
with weighted algorithms, trend analysis, and fraud detection.
"""

import logging
import math
import statistics
from datetime import timedelta
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Q
from django.utils import timezone

from apps.bookingapp.models import Appointment
from apps.reviewapp.models import Rating, Review
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist

logger = logging.getLogger(__name__)


class RatingAggregator:
    """
    Advanced rating aggregation service that calculates accurate ratings
    for shops and specialists using sophisticated algorithms.
    """

    # Configuration settings
    RECENT_PERIOD_DAYS = 30
    OLD_PERIOD_DAYS = 90
    RECENT_WEIGHT = 0.7  # Weight for recent ratings
    OLD_WEIGHT = 0.3  # Weight for older ratings
    MIN_RATINGS_FOR_CONFIDENCE = 5  # Minimum ratings for confidence calculation
    SUSPICIOUS_THRESHOLD = 4.8  # High ratings that may require verification
    BAYESIAN_PRIOR_COUNT = 3  # Number of prior ratings to include in Bayesian average
    BAYESIAN_PRIOR_MEAN = 3.0  # Prior mean rating for Bayesian average

    @classmethod
    def calculate_shop_rating(
        cls, shop_id: str, recalculate_all: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate the aggregate rating for a shop

        Args:
            shop_id: The shop ID
            recalculate_all: Whether to force recalculation of all metrics

        Returns:
            Dictionary with rating metrics
        """
        try:
            shop = Shop.objects.get(id=shop_id)

            # Get all ratings for this shop
            ratings = Rating.objects.filter(shop_id=shop_id)

            # Skip if no ratings and not forcing recalculation
            if not ratings.exists() and not recalculate_all:
                return {
                    "shop_id": shop_id,
                    "rating": shop.rating or 0,
                    "rating_count": 0,
                    "calculated_at": timezone.now(),
                }

            # Calculate different metrics
            simple_average = cls._calculate_simple_average(ratings)
            weighted_average = cls._calculate_weighted_average(ratings)
            bayesian_average = cls._calculate_bayesian_average(ratings)
            wilson_score = cls._calculate_wilson_score(ratings)

            # Get category metrics for comparison
            category_metrics = cls._get_category_metrics(shop.category_id)

            # Calculate the rating relative to category average
            category_relative_score = 0
            if category_metrics["average"] > 0:
                category_relative_score = (
                    bayesian_average / category_metrics["average"]
                ) - 1

            # Perform fraud detection
            fraud_check = cls._detect_rating_fraud(shop_id, "shop")

            # Calculate final rating (using Bayesian average as the base)
            final_rating = bayesian_average

            # Adjust if fraud suspected
            if fraud_check["suspected_fraud"]:
                # Apply penalty to the rating
                final_rating = min(final_rating, fraud_check["adjusted_rating"])
                logger.warning(
                    f"Applied fraud adjustment to shop {shop_id}: {fraud_check}"
                )

            # Calculate rating components by dimension
            dimensions = cls._calculate_dimension_ratings(ratings)

            # Update shop rating in database
            with transaction.atomic():
                shop.rating = final_rating
                shop.rating_count = ratings.count()
                shop.last_rating_update = timezone.now()
                shop.save(
                    update_fields=["rating", "rating_count", "last_rating_update"]
                )

            # Return the calculated metrics
            return {
                "shop_id": shop_id,
                "rating": final_rating,
                "rating_count": ratings.count(),
                "confidence": cls._calculate_confidence_score(ratings.count()),
                "simple_average": simple_average,
                "weighted_average": weighted_average,
                "bayesian_average": bayesian_average,
                "wilson_score": wilson_score,
                "category_relative": category_relative_score,
                "dimensions": dimensions,
                "fraud_check": fraud_check,
                "calculated_at": timezone.now(),
            }

        except Exception as e:
            logger.exception(f"Error calculating shop rating: {e}")
            return {
                "shop_id": shop_id,
                "error": str(e),
                "calculated_at": timezone.now(),
            }

    @classmethod
    def calculate_specialist_rating(cls, specialist_id: str) -> Dict[str, Any]:
        """
        Calculate the aggregate rating for a specialist

        Args:
            specialist_id: The specialist ID

        Returns:
            Dictionary with rating metrics
        """
        try:
            specialist = Specialist.objects.get(id=specialist_id)

            # Get ratings for this specialist
            ratings = Rating.objects.filter(specialist_id=specialist_id)

            if not ratings.exists():
                return {
                    "specialist_id": specialist_id,
                    "rating": specialist.rating or 0,
                    "rating_count": 0,
                    "calculated_at": timezone.now(),
                }

            # Calculate metrics using the same methods as for shops
            simple_average = cls._calculate_simple_average(ratings)
            weighted_average = cls._calculate_weighted_average(ratings)
            bayesian_average = cls._calculate_bayesian_average(ratings)

            # Get service-specific ratings
            service_ratings = cls._calculate_service_ratings(specialist_id)

            # Get shop average for comparison
            shop_average = 0
            if specialist.shop_id:
                shop = Shop.objects.get(id=specialist.shop_id)
                shop_average = shop.rating or 0

            # Calculate final rating (using Bayesian average as the base)
            final_rating = bayesian_average

            # Update specialist rating in database
            with transaction.atomic():
                specialist.rating = final_rating
                specialist.rating_count = ratings.count()
                specialist.save(update_fields=["rating", "rating_count"])

            return {
                "specialist_id": specialist_id,
                "rating": final_rating,
                "rating_count": ratings.count(),
                "confidence": cls._calculate_confidence_score(ratings.count()),
                "simple_average": simple_average,
                "weighted_average": weighted_average,
                "bayesian_average": bayesian_average,
                "shop_relative": (
                    (final_rating / shop_average - 1) if shop_average > 0 else 0
                ),
                "service_ratings": service_ratings,
                "calculated_at": timezone.now(),
            }

        except Exception as e:
            logger.exception(f"Error calculating specialist rating: {e}")
            return {
                "specialist_id": specialist_id,
                "error": str(e),
                "calculated_at": timezone.now(),
            }

    @classmethod
    def update_all_ratings(cls) -> Dict[str, Any]:
        """
        Update ratings for all shops and specialists

        Returns:
            Dictionary with update statistics
        """
        start_time = timezone.now()
        shops_updated = 0
        specialists_updated = 0
        errors = 0

        try:
            # Update all shops
            shops = Shop.objects.filter(is_active=True)
            for shop in shops:
                try:
                    cls.calculate_shop_rating(shop.id)
                    shops_updated += 1
                except Exception as e:
                    logger.error(f"Error updating shop {shop.id} rating: {e}")
                    errors += 1

            # Update all specialists
            specialists = Specialist.objects.filter(is_active=True)
            for specialist in specialists:
                try:
                    cls.calculate_specialist_rating(specialist.id)
                    specialists_updated += 1
                except Exception as e:
                    logger.error(
                        f"Error updating specialist {specialist.id} rating: {e}"
                    )
                    errors += 1

            duration = (timezone.now() - start_time).total_seconds()

            return {
                "shops_updated": shops_updated,
                "specialists_updated": specialists_updated,
                "errors": errors,
                "duration_seconds": duration,
                "completed_at": timezone.now(),
            }

        except Exception as e:
            logger.exception(f"Error in bulk rating update: {e}")
            return {
                "error": str(e),
                "shops_updated": shops_updated,
                "specialists_updated": specialists_updated,
                "errors": errors + 1,
                "completed_at": timezone.now(),
            }

    @classmethod
    def process_new_review(cls, review_id: str) -> Dict[str, Any]:
        """
        Process a new review and update associated ratings

        Args:
            review_id: The review ID

        Returns:
            Dictionary with processing result
        """
        try:
            review = Review.objects.get(id=review_id)

            # Check if this review seems suspicious
            is_suspicious = cls._check_review_suspicious(review)

            if is_suspicious:
                logger.warning(f"Suspicious review detected: {review_id}")
                review.flagged_suspicious = True
                review.save(update_fields=["flagged_suspicious"])

                # If automatic moderation is enabled, hide the review
                if getattr(settings, "AUTO_MODERATE_SUSPICIOUS_REVIEWS", False):
                    review.is_visible = False
                    review.save(update_fields=["is_visible"])

            # Update shop rating if review includes shop rating
            shop_results = None
            if review.shop_id and hasattr(review, "rating") and review.rating:
                shop_results = cls.calculate_shop_rating(review.shop_id)

            # Update specialist rating if review includes specialist rating
            specialist_results = None
            if (
                review.specialist_id
                and hasattr(review, "specialist_rating")
                and review.specialist_rating
            ):
                specialist_results = cls.calculate_specialist_rating(
                    review.specialist_id
                )

            return {
                "review_id": review_id,
                "is_suspicious": is_suspicious,
                "shop_results": shop_results,
                "specialist_results": specialist_results,
                "processed_at": timezone.now(),
            }

        except Exception as e:
            logger.exception(f"Error processing review {review_id}: {e}")
            return {
                "review_id": review_id,
                "error": str(e),
                "processed_at": timezone.now(),
            }

    @classmethod
    def _calculate_simple_average(cls, ratings) -> float:
        """Calculate simple average rating"""
        if not ratings.exists():
            return 0

        avg = ratings.aggregate(avg=Avg("rating"))["avg"] or 0
        return round(avg, 2)

    @classmethod
    def _calculate_weighted_average(cls, ratings) -> float:
        """
        Calculate time-weighted average rating
        Recent ratings carry more weight than older ones
        """
        if not ratings.exists():
            return 0

        today = timezone.now().date()
        recent_cutoff = today - timedelta(days=cls.RECENT_PERIOD_DAYS)
        old_cutoff = today - timedelta(days=cls.OLD_PERIOD_DAYS)

        # Get recent and older ratings
        recent_ratings = ratings.filter(created_at__gte=recent_cutoff)
        older_ratings = ratings.filter(
            created_at__lt=recent_cutoff, created_at__gte=old_cutoff
        )

        # Calculate averages for each time period
        recent_avg = recent_ratings.aggregate(avg=Avg("rating"))["avg"] or 0
        older_avg = older_ratings.aggregate(avg=Avg("rating"))["avg"] or 0

        # If we don't have ratings for a period, use the other period's average
        if recent_ratings.count() == 0 and older_ratings.count() > 0:
            return older_avg
        elif older_ratings.count() == 0 and recent_ratings.count() > 0:
            return recent_avg
        elif recent_ratings.count() == 0 and older_ratings.count() == 0:
            return 0

        # Calculate weighted average
        weighted_avg = recent_avg * cls.RECENT_WEIGHT + older_avg * cls.OLD_WEIGHT

        return round(weighted_avg, 2)

    @classmethod
    def _calculate_bayesian_average(cls, ratings) -> float:
        """
        Calculate Bayesian average rating
        This factors in the overall confidence based on number of ratings
        """
        if not ratings.exists():
            return 0

        # Get rating count and average
        count = ratings.count()
        avg = ratings.aggregate(avg=Avg("rating"))["avg"] or 0

        # Apply Bayesian average formula: (C × m + R × v) / (C + R)
        # where C is the prior count, m is the prior mean,
        # R is the number of ratings, and v is the average rating
        bayesian_avg = (
            cls.BAYESIAN_PRIOR_COUNT * cls.BAYESIAN_PRIOR_MEAN + count * avg
        ) / (cls.BAYESIAN_PRIOR_COUNT + count)

        return round(bayesian_avg, 2)

    @classmethod
    def _calculate_wilson_score(cls, ratings) -> float:
        """
        Calculate Wilson score lower bound
        This provides a conservative estimate of the "true" rating
        """
        if not ratings.exists():
            return 0

        # Count ratings in each bucket (1-5 stars)
        # Convert to positive/negative for Wilson score calculation
        total = ratings.count()
        positive = ratings.filter(rating__gte=4).count()  # 4-5 stars are positive
        total - positive

        if total == 0:
            return 0

        # Wilson score calculation
        z = 1.96  # 95% confidence
        phat = positive / total

        wilson_score = (
            phat
            + z * z / (2 * total)
            - z * math.sqrt((phat * (1 - phat) + z * z / (4 * total)) / total)
        ) / (1 + z * z / total)

        # Convert from 0-1 range to 1-5 rating scale
        wilson_rating = 1 + wilson_score * 4

        return round(wilson_rating, 2)

    @classmethod
    def _calculate_confidence_score(cls, rating_count: int) -> float:
        """
        Calculate confidence score based on number of ratings

        Args:
            rating_count: Number of ratings

        Returns:
            Confidence score from 0-1
        """
        # Confidence increases with more ratings but plateaus
        if rating_count >= cls.MIN_RATINGS_FOR_CONFIDENCE * 10:
            return 1.0
        elif rating_count == 0:
            return 0.0

        # Logarithmic scale provides increasing confidence that tapers off
        confidence = math.log10(rating_count + 1) / math.log10(
            cls.MIN_RATINGS_FOR_CONFIDENCE * 10 + 1
        )
        return round(min(1.0, confidence), 2)

    @classmethod
    def _get_category_metrics(cls, category_id: Optional[str]) -> Dict[str, Any]:
        """
        Get rating metrics for a category

        Args:
            category_id: Category ID or None

        Returns:
            Dictionary with category metrics
        """
        if not category_id:
            return {"average": 0, "median": 0, "count": 0}

        # Get shops in this category
        shops = Shop.objects.filter(category_id=category_id, is_active=True).exclude(
            rating__isnull=True
        )

        if not shops.exists():
            return {"average": 0, "median": 0, "count": 0}

        # Calculate metrics
        avg = shops.aggregate(avg=Avg("rating"))["avg"] or 0

        # Calculate median (this requires evaluating the queryset)
        ratings = list(shops.values_list("rating", flat=True))
        median = statistics.median(ratings) if ratings else 0

        return {
            "average": round(avg, 2),
            "median": round(median, 2),
            "count": len(ratings),
        }

    @classmethod
    def _calculate_dimension_ratings(cls, ratings) -> Dict[str, float]:
        """
        Calculate ratings by dimension (cleanliness, service, value, etc.)

        Args:
            ratings: QuerySet of ratings

        Returns:
            Dictionary mapping dimensions to their average scores
        """
        dimensions = {}

        # Add dimensions that are tracked in your system
        # This example assumes Rating model has fields like cleanliness, service_quality, etc.
        dimension_fields = [
            "cleanliness",
            "service_quality",
            "value",
            "location",
            "staff",
            "communication",
            "wait_time",
        ]

        for field in dimension_fields:
            if hasattr(Rating, field):
                avg = ratings.aggregate(avg=Avg(field))["avg"]
                if avg is not None:
                    dimensions[field] = round(avg, 2)

        return dimensions

    @classmethod
    def _calculate_service_ratings(cls, specialist_id: str) -> Dict[str, Any]:
        """
        Calculate ratings by service for a specialist

        Args:
            specialist_id: Specialist ID

        Returns:
            Dictionary with service-specific ratings
        """
        # Get appointments with ratings
        appointments = Appointment.objects.filter(
            specialist_id=specialist_id, has_review=True
        ).select_related("service", "review")

        if not appointments.exists():
            return {}

        # Group by service
        service_ratings = {}

        for appointment in appointments:
            if (
                not appointment.service_id
                or not hasattr(appointment, "review")
                or not appointment.review
            ):
                continue

            service_id = appointment.service_id
            service_name = (
                appointment.service.name if appointment.service else "Unknown Service"
            )
            rating = getattr(appointment.review, "rating", 0)

            if service_id not in service_ratings:
                service_ratings[service_id] = {
                    "service_name": service_name,
                    "ratings": [],
                    "average": 0,
                    "count": 0,
                }

            service_ratings[service_id]["ratings"].append(rating)

        # Calculate averages
        for service_id, data in service_ratings.items():
            ratings = data["ratings"]
            data["count"] = len(ratings)
            data["average"] = round(sum(ratings) / len(ratings), 2) if ratings else 0
            data.pop("ratings")  # Remove individual ratings from result

        return service_ratings

    @classmethod
    def _detect_rating_fraud(cls, entity_id: str, entity_type: str) -> Dict[str, Any]:
        """
        Detect potentially fraudulent ratings

        Args:
            entity_id: ID of shop or specialist
            entity_type: "shop" or "specialist"

        Returns:
            Dictionary with fraud detection results
        """
        filter_kwargs = {f"{entity_type}_id": entity_id}
        ratings = Rating.objects.filter(**filter_kwargs)

        if ratings.count() < cls.MIN_RATINGS_FOR_CONFIDENCE:
            return {
                "suspected_fraud": False,
                "confidence": 0,
                "flags": [],
                "adjusted_rating": 0,
            }

        # Get rating distribution
        distribution = {}
        for i in range(1, 6):
            distribution[i] = ratings.filter(rating=i).count()

        # Calculate suspicious patterns
        flags = []

        # Check for unusual distribution (too many 5-star ratings)
        five_star_ratio = (
            distribution.get(5, 0) / ratings.count() if ratings.count() > 0 else 0
        )
        if five_star_ratio > 0.9 and ratings.count() >= 10:
            flags.append(
                {
                    "type": "high_five_star",
                    "description": f"Unusually high percentage of 5-star ratings ({five_star_ratio:.0%})",
                }
            )

        # Check for rating burst (many ratings in short time)
        recent_cutoff = timezone.now() - timedelta(days=7)
        recent_count = ratings.filter(created_at__gte=recent_cutoff).count()

        if recent_count > 10 and recent_count > ratings.count() * 0.5:
            flags.append(
                {
                    "type": "rating_burst",
                    "description": f"Unusual spike in ratings: {recent_count} in the last week",
                }
            )

        # Check for ratings with no review text
        empty_reviews = ratings.filter(
            Q(review_text="") | Q(review_text__isnull=True)
        ).count()
        empty_ratio = empty_reviews / ratings.count() if ratings.count() > 0 else 0

        if empty_ratio > 0.8 and ratings.count() >= 10:
            flags.append(
                {
                    "type": "empty_reviews",
                    "description": f"High percentage ({empty_ratio:.0%}) of ratings without review text",
                }
            )

        # Determine if fraud is suspected and confidence
        suspected_fraud = len(flags) >= 2
        confidence = min(1.0, len(flags) * 0.3)

        # Calculate adjusted rating
        adjusted_rating = cls._calculate_simple_average(ratings)

        if suspected_fraud:
            # Apply a penalty to the rating
            original = adjusted_rating
            penalty = confidence * 0.5  # Max penalty is 0.5 stars
            adjusted_rating = max(1.0, adjusted_rating - penalty)

            flags.append(
                {
                    "type": "rating_adjusted",
                    "description": f"Rating adjusted from {original} to {adjusted_rating}",
                }
            )

        return {
            "suspected_fraud": suspected_fraud,
            "confidence": round(confidence, 2),
            "flags": flags,
            "adjusted_rating": round(adjusted_rating, 2),
        }

    @classmethod
    def _check_review_suspicious(cls, review) -> bool:
        """
        Check if a specific review appears suspicious

        Args:
            review: Review object

        Returns:
            Boolean indicating if review is suspicious
        """
        flags = 0

        # Check if high rating with no text
        if getattr(review, "rating", 0) >= cls.SUSPICIOUS_THRESHOLD and (
            not getattr(review, "review_text", None) or len(review.review_text) < 10
        ):
            flags += 1

        # Check if created very soon after appointment
        if hasattr(review, "appointment") and review.appointment:
            appointment_time = review.appointment.appointment_time
            if (
                review.created_at - appointment_time
            ).total_seconds() < 60 * 5:  # 5 minutes
                flags += 1

        # Check for suspicious words/patterns in text
        suspicious_phrases = [
            "best ever",
            "amazing service",
            "incredible",
            "best in town",
            "perfect",
            "flawless",
        ]
        if hasattr(review, "review_text") and review.review_text:
            text = review.review_text.lower()
            if any(phrase in text for phrase in suspicious_phrases) and len(text) < 30:
                flags += 1

        # Check if reviewer has left multiple similar ratings
        if hasattr(review, "customer") and review.customer:
            recent_cutoff = timezone.now() - timedelta(days=30)
            recent_reviews = Review.objects.filter(
                customer=review.customer, created_at__gte=recent_cutoff
            ).exclude(id=review.id)

            if recent_reviews.count() > 5:  # User left many reviews recently
                flags += 1

        # Review is suspicious if it has 2+ flags
        return flags >= 2


# Convenience function for direct access
get_shop_rating = RatingAggregator.calculate_shop_rating
get_specialist_rating = RatingAggregator.calculate_specialist_rating
process_new_review = RatingAggregator.process_new_review
