import logging
import math

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from apps.reviewapp.models import (
    ReviewMetric,
    ServiceReview,
    ShopReview,
    SpecialistReview,
)

logger = logging.getLogger(__name__)


class RatingService:
    """Service for calculating and managing ratings"""

    @staticmethod
    def update_entity_metrics(entity_model_name, entity_id):
        """Update review metrics for an entity

        This calculates various metrics including:
        - Average rating
        - Weighted rating (based on recency, helpfulness, etc.)
        - Review count
        - Rating distribution

        Args:
            entity_model_name (str): Model name including app label (e.g., 'shopapp.Shop')
            entity_id (uuid): ID of the entity

        Returns:
            ReviewMetric: The updated metrics
        """
        try:
            # Get content type for the entity
            app_label, model = entity_model_name.lower().split(".")
            content_type = ContentType.objects.get(app_label=app_label, model=model)

            # Get all approved reviews for the entity
            reviews = None
            if model == "shop":
                reviews = ShopReview.objects.filter(
                    shop_id=entity_id, status="approved"
                )
            elif model == "specialist":
                reviews = SpecialistReview.objects.filter(
                    specialist_id=entity_id, status="approved"
                )
            elif model == "service":
                reviews = ServiceReview.objects.filter(
                    service_id=entity_id, status="approved"
                )
            else:
                logger.error(f"Unsupported entity model: {entity_model_name}")
                return None

            # Calculate metrics
            review_count = reviews.count()

            # Handle case with no reviews
            if review_count == 0:
                # Get or create metrics with default values
                metrics, created = ReviewMetric.objects.update_or_create(
                    content_type=content_type,
                    object_id=entity_id,
                    defaults={
                        "avg_rating": 0,
                        "weighted_rating": 0,
                        "review_count": 0,
                        "rating_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
                        "last_reviewed_at": None,
                    },
                )
                return metrics

            # Calculate average rating
            avg_rating = reviews.aggregate(avg=models.Avg("rating"))["avg"]

            # Calculate rating distribution
            distribution = {
                "1": reviews.filter(rating=1).count(),
                "2": reviews.filter(rating=2).count(),
                "3": reviews.filter(rating=3).count(),
                "4": reviews.filter(rating=4).count(),
                "5": reviews.filter(rating=5).count(),
            }

            # Calculate weighted rating using our sophisticated algorithm
            weighted_rating = RatingService.calculate_weighted_rating(reviews)

            # Get last review date
            last_reviewed_at = reviews.order_by("-created_at").first().created_at

            # Update or create metrics
            metrics, created = ReviewMetric.objects.update_or_create(
                content_type=content_type,
                object_id=entity_id,
                defaults={
                    "avg_rating": avg_rating,
                    "weighted_rating": weighted_rating,
                    "review_count": review_count,
                    "rating_distribution": distribution,
                    "last_reviewed_at": last_reviewed_at,
                },
            )

            return metrics

        except Exception as e:
            logger.error(
                f"Error updating metrics for {entity_model_name} {entity_id}: {str(e)}"
            )
            return None

    @staticmethod
    def calculate_weighted_rating(reviews):
        """Calculate weighted rating that considers multiple factors

        Factors:
        - Recency (newer reviews count more)
        - Verified purchase status
        - Review quality (length, detail)
        - Helpfulness votes
        - Statistical confidence (Bayesian average)

        Args:
            reviews (QuerySet): Reviews to calculate from

        Returns:
            float: Weighted rating (1.0-5.0)
        """
        if not reviews.exists():
            return 0.0

        # Constants for weighting
        RECENCY_WEIGHT = 0.3  # How much recency matters
        VERIFIED_WEIGHT = 0.2  # How much verified purchases matter
        HELPFULNESS_WEIGHT = 0.2  # How much helpfulness votes matter
        QUALITY_WEIGHT = 0.1  # How much review quality matters
        # unused_unused_BAYESIAN_PRIOR_WEIGHT = 0.2  # How much statistical confidence matters

        # Bayesian prior (overall average, tends to 3.5 for new items)
        PRIOR_MEAN = 3.5
        PRIOR_COUNT = 5  # Equivalent to 5 reviews at 3.5

        # Initialize weighted sum and total weight
        weighted_sum = 0
        total_weight = 0

        # Current time for recency calculation
        now = timezone.now()

        # For each review, calculate its weight and contribution
        for review in reviews:
            # Start with base weight
            weight = 1.0

            # Recency factor (exponential decay)
            days_old = (now - review.created_at).days
            recency_factor = math.exp(-days_old / 180)  # Half-life of ~180 days
            weight *= 1 + (recency_factor - 0.5) * RECENCY_WEIGHT

            # Verified purchase factor
            if review.is_verified_purchase:
                weight *= 1 + VERIFIED_WEIGHT

            # Review quality factor (content length as proxy)
            content_length = len(review.content) if review.content else 0
            quality_factor = min(1.0, content_length / 500)  # Normalize to max 1.0
            weight *= 1 + quality_factor * QUALITY_WEIGHT

            # Helpfulness factor
            try:
                from django.contrib.contenttypes.models import ContentType

                from apps.reviewapp.models import ReviewHelpfulness

                content_type = ContentType.objects.get_for_model(review)
                helpful_count = ReviewHelpfulness.objects.filter(
                    content_type=content_type, object_id=review.id, is_helpful=True
                ).count()

                unhelpful_count = ReviewHelpfulness.objects.filter(
                    content_type=content_type, object_id=review.id, is_helpful=False
                ).count()

                total_votes = helpful_count + unhelpful_count
                if total_votes > 0:
                    helpfulness_ratio = helpful_count / total_votes
                    # Adjust weight based on helpfulness ratio
                    weight *= 1 + (helpfulness_ratio - 0.5) * 2 * HELPFULNESS_WEIGHT
            except Exception:
                # If any error in helpfulness calculation, skip this factor
                pass

            # Add to weighted sum
            weighted_sum += review.rating * weight
            total_weight += weight

        # Bayesian adjustment
        adjusted_rating = (weighted_sum + PRIOR_MEAN * PRIOR_COUNT) / (
            total_weight + PRIOR_COUNT
        )

        # Ensure the result is in the valid range
        return max(1.0, min(5.0, adjusted_rating))

    @staticmethod
    def recalculate_all_metrics():
        """Recalculate metrics for all entities

        This is useful for maintenance or after algorithm changes
        """
        # Update shop metrics
        from apps.shopapp.models import Shop

        shops = Shop.objects.all()

        for shop in shops:
            RatingService.update_entity_metrics("shopapp.Shop", shop.id)

        # Update specialist metrics
        from apps.specialistsapp.models import Specialist

        specialists = Specialist.objects.all()

        for specialist in specialists:
            RatingService.update_entity_metrics(
                "specialistsapp.Specialist", specialist.id
            )

        # Update service metrics
        from apps.serviceapp.models import Service

        services = Service.objects.all()

        for service in services:
            RatingService.update_entity_metrics("serviceapp.Service", service.id)

    @staticmethod
    def get_top_rated_entities(entity_model_name, limit=10, min_reviews=5):
        """Get top rated entities based on weighted rating

        Args:
            entity_model_name (str): Model name including app label
            limit (int): Number of entities to return
            min_reviews (int): Minimum number of reviews required

        Returns:
            list: List of entity IDs with metrics
        """
        try:
            # Get content type for the entity
            app_label, model = entity_model_name.lower().split(".")
            content_type = ContentType.objects.get(app_label=app_label, model=model)

            # Get metrics with minimum number of reviews
            metrics = ReviewMetric.objects.filter(
                content_type=content_type, review_count__gte=min_reviews
            ).order_by("-weighted_rating")[:limit]

            # Return entity IDs with metrics
            return [
                {
                    "entity_id": metric.object_id,
                    "avg_rating": metric.avg_rating,
                    "weighted_rating": metric.weighted_rating,
                    "review_count": metric.review_count,
                }
                for metric in metrics
            ]

        except Exception as e:
            logger.error(
                f"Error getting top rated entities for {entity_model_name}: {str(e)}"
            )
            return []
