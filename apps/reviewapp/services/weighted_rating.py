import math

from django.db.models import Avg, Count
from django.utils import timezone


class WeightedRatingCalculator:
    """Advanced rating calculation algorithms"""

    @staticmethod
    def calculate_bayesian_average(reviews, prior_mean=3.5, prior_count=5):
        """Calculate Bayesian average rating

        This gives more statistical confidence by adding "prior" reviews
        at the average rating. Helps avoid extreme ratings with few reviews.

        Args:
            reviews (QuerySet): Reviews to calculate from
            prior_mean (float): Prior mean rating (default 3.5)
            prior_count (int): Weight of prior (equivalent to # of reviews)

        Returns:
            float: Bayesian average rating
        """
        if not reviews.exists():
            return prior_mean

        # Get count and average from database
        review_stats = reviews.aggregate(avg=Avg("rating"), count=Count("id"))

        avg_rating = review_stats["avg"] or 0
        review_count = review_stats["count"] or 0

        # Calculate Bayesian average
        bayesian_avg = (avg_rating * review_count + prior_mean * prior_count) / (
            review_count + prior_count
        )

        return bayesian_avg

    @staticmethod
    def calculate_imdb_weighted_rating(reviews, min_votes=10):
        """Calculate weighted rating using IMDb formula

        IMDb uses a weighted rating formula: WR = (v/(v+m)) × R + (m/(v+m)) × C
        Where:
        - WR is the weighted rating
        - R is the average rating
        - v is the number of votes (reviews)
        - m is the minimum votes required
        - C is the mean vote across the whole platform

        Args:
            reviews (QuerySet): Reviews to calculate from
            min_votes (int): Minimum votes required for full weight

        Returns:
            float: Weighted rating
        """
        if not reviews.exists():
            return 0.0

        # Get review stats
        review_stats = reviews.aggregate(avg=Avg("rating"), count=Count("id"))

        avg_rating = review_stats["avg"] or 0
        review_count = review_stats["count"] or 0

        # For C (global average), we should ideally get this from a global setting
        # For simplicity, we'll use 3.5 as an approximation
        global_avg = 3.5

        # Calculate IMDb weighted rating
        weighted_rating = (review_count / (review_count + min_votes) * avg_rating) + (
            min_votes / (review_count + min_votes) * global_avg
        )

        return weighted_rating

    @staticmethod
    def calculate_recency_weighted_rating(reviews, half_life_days=90):
        """Calculate rating weighted by recency

        More recent reviews get higher weight using exponential decay

        Args:
            reviews (QuerySet): Reviews to calculate from
            half_life_days (int): Days after which weight is halved

        Returns:
            float: Recency-weighted rating
        """
        if not reviews.exists():
            return 0.0

        now = timezone.now()
        weighted_sum = 0
        total_weight = 0

        for review in reviews:
            # Calculate days since review
            days_old = (now - review.created_at).days

            # Calculate weight using exponential decay
            weight = math.exp(-math.log(2) * days_old / half_life_days)

            weighted_sum += review.rating * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    @staticmethod
    def calculate_wilson_score(reviews):
        """Calculate Wilson score lower bound

        This gives a confidence interval for the true fraction of positive ratings
        It's useful for sorting items with few reviews.

        Args:
            reviews (QuerySet): Reviews to calculate from

        Returns:
            float: Wilson score (0.0-1.0)
        """
        if not reviews.exists():
            return 0.0

        # Count positive and total reviews
        # We'll consider 4-5 stars as positive
        positive_count = reviews.filter(rating__gte=4).count()
        total_count = reviews.count()

        if total_count == 0:
            return 0.0

        # Calculate Wilson score
        z = 1.96  # 95% confidence
        p = float(positive_count) / total_count

        # Wilson score formula
        numerator = (
            p
            + z * z / (2 * total_count)
            - z * math.sqrt((p * (1 - p) + z * z / (4 * total_count)) / total_count)
        )
        denominator = 1 + z * z / total_count

        return numerator / denominator

    @staticmethod
    def calculate_comprehensive_rating(entity_type, entity_id):
        """Calculate a comprehensive rating using multiple algorithms

        This combines multiple rating algorithms for the most balanced result

        Args:
            entity_type (str): Type of entity
            entity_id (uuid): ID of the entity

        Returns:
            dict: Complete rating metrics
        """
        # Get reviews for the entity
        reviews = None
        if entity_type == "shop":
            from apps.reviewapp.models import ShopReview

            reviews = ShopReview.objects.filter(shop_id=entity_id, status="approved")
        elif entity_type == "specialist":
            from apps.reviewapp.models import SpecialistReview

            reviews = SpecialistReview.objects.filter(
                specialist_id=entity_id, status="approved"
            )
        elif entity_type == "service":
            from apps.reviewapp.models import ServiceReview

            reviews = ServiceReview.objects.filter(
                service_id=entity_id, status="approved"
            )
        else:
            return {"error": f"Invalid entity type: {entity_type}"}

        if not reviews.exists():
            return {
                "avg_rating": 0,
                "review_count": 0,
                "bayesian_avg": 0,
                "imdb_weighted": 0,
                "recency_weighted": 0,
                "wilson_score": 0,
                "confidence": 0,
            }

        # Calculate various metrics
        review_stats = reviews.aggregate(avg=Avg("rating"), count=Count("id"))

        avg_rating = review_stats["avg"] or 0
        review_count = review_stats["count"] or 0

        # Calculate confidence based on review count
        # Reaches 100% confidence at 50+ reviews
        confidence = min(1.0, review_count / 50)

        # Calculate various weighted ratings
        bayesian_avg = WeightedRatingCalculator.calculate_bayesian_average(reviews)
        imdb_weighted = WeightedRatingCalculator.calculate_imdb_weighted_rating(reviews)
        recency_weighted = WeightedRatingCalculator.calculate_recency_weighted_rating(
            reviews
        )
        wilson_score = WeightedRatingCalculator.calculate_wilson_score(reviews)

        # Scale wilson score (0-1) to rating scale (1-5)
        wilson_rating = 1 + wilson_score * 4

        return {
            "avg_rating": avg_rating,
            "review_count": review_count,
            "bayesian_avg": bayesian_avg,
            "imdb_weighted": imdb_weighted,
            "recency_weighted": recency_weighted,
            "wilson_score_rating": wilson_rating,
            "confidence": confidence,
        }
