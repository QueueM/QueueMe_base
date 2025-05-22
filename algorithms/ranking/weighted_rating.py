import logging
import math
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class WeightedRating:
    """
    Advanced algorithm for calculating weighted ratings that account for
    rating count, recency, content, and reviewer credibility.

    This algorithm improves rating accuracy by:
    1. Considering the number of ratings (statistical confidence)
    2. Weighting recent ratings more heavily
    3. Analyzing review content for sentiment and helpfulness
    4. Adjusting for reviewer credibility and bias
    5. Incorporating business responses to reviews
    """

    def __init__(
        self,
        confidence_factor: float = 5.0,
        recency_half_life: int = 180,  # days
        min_ratings_for_full_confidence: int = 20,
        verified_purchase_weight: float = 1.2,
        content_weight: float = 0.3,
        bias_correction_factor: float = 0.2,
    ):
        """
        Initialize the weighted rating calculator with configurable parameters.

        Args:
            confidence_factor: Bayesian prior weight (higher = more conservative)
            recency_half_life: Days after which a rating's weight is halved
            min_ratings_for_full_confidence: Ratings needed for full confidence
            verified_purchase_weight: Extra weight for verified purchase reviews
            content_weight: Weight given to review content analysis
            bias_correction_factor: Strength of bias correction
        """
        self.confidence_factor = confidence_factor
        self.recency_half_life = recency_half_life
        self.min_ratings_for_full_confidence = min_ratings_for_full_confidence
        self.verified_purchase_weight = verified_purchase_weight
        self.content_weight = content_weight
        self.bias_correction_factor = bias_correction_factor

    def calculate_weighted_rating(
        self,
        reviews: List[Dict],
        entity_type: str = "shop",
        prior_mean: float = 3.0,
        include_details: bool = False,
    ) -> Dict:
        """
        Calculate weighted rating for an entity based on its reviews.

        Args:
            reviews: List of review objects with fields:
                - id: Unique identifier
                - rating: Numeric rating (typically 1-5)
                - created_at: Datetime when review was created
                - content: Review text content
                - is_verified: Whether the review is from a verified purchase
                - reviewer_id: ID of the reviewer
                - helpfulness_votes: Optional count of helpfulness votes
                - review_response: Optional response to the review
            entity_type: Type of entity being rated ('shop', 'specialist', 'service')
            prior_mean: Prior belief about average rating
            include_details: Whether to include detailed calculations

        Returns:
            A dictionary containing:
            - weighted_rating: The calculated weighted rating
            - raw_rating: Simple average rating
            - rating_count: Number of reviews
            - confidence_score: Confidence in the rating
            - details: Optional detailed breakdown of calculations
        """
        # Initialize result
        result = {
            "weighted_rating": 0.0,
            "raw_rating": 0.0,
            "rating_count": len(reviews),
            "confidence_score": 0.0,
        }

        # If no reviews, return default rating
        if not reviews:
            result["weighted_rating"] = prior_mean
            return result

        # Calculate simple average (raw rating)
        raw_rating_sum = sum(review.get("rating", 0) for review in reviews)
        raw_rating = raw_rating_sum / len(reviews)
        result["raw_rating"] = raw_rating

        # Initialize variables for weighted calculation
        weighted_sum = 0.0
        weight_sum = 0.0

        # Details for each review if requested
        review_details = {}

        # Current time for recency calculation
        current_time = datetime.now()

        # Step 1: Calculate individual weights and sums
        for review in reviews:
            review_id = review.get("id", "unknown")
            rating = review.get("rating", 0)

            # Skip invalid ratings
            if rating <= 0:
                continue

            # Calculate base weight (1.0)
            weight = 1.0

            # Adjust for recency
            recency_weight = self._calculate_recency_weight(review, current_time)
            weight *= recency_weight

            # Adjust for verified purchase
            verified_weight = 1.0
            if review.get("is_verified", False):
                verified_weight = self.verified_purchase_weight
            weight *= verified_weight

            # Adjust for content quality
            content_quality_weight = self._calculate_content_weight(review)
            weight *= 1.0 + (content_quality_weight * self.content_weight)

            # Adjust for reviewer credibility
            credibility_weight = self._calculate_reviewer_credibility(review)
            weight *= credibility_weight

            # Adjust for review response (if business responded)
            response_weight = self._calculate_response_weight(review)
            weight *= response_weight

            # Apply bias correction
            bias_corrected_rating = self._apply_bias_correction(review, raw_rating)

            # Add to sums
            weighted_sum += bias_corrected_rating * weight
            weight_sum += weight

            # Store details if requested
            if include_details:
                review_details[review_id] = {
                    "rating": rating,
                    "recency_weight": recency_weight,
                    "verified_weight": verified_weight,
                    "content_weight": content_quality_weight,
                    "credibility_weight": credibility_weight,
                    "response_weight": response_weight,
                    "bias_correction": bias_corrected_rating - rating,
                    "final_weight": weight,
                    "weighted_contribution": bias_corrected_rating * weight,
                }

        # Step 2: Apply Bayesian adjustment based on review count
        # This pulls the rating toward the prior mean when there are few reviews
        confidence = min(1.0, len(reviews) / self.min_ratings_for_full_confidence)
        result["confidence_score"] = confidence

        # Calculate final rating
        if weight_sum > 0:
            # Calculate weighted average of reviews
            review_average = weighted_sum / weight_sum

            # Apply Bayesian adjustment
            final_rating = (confidence * review_average) + (
                (1 - confidence) * prior_mean
            )

            # Round to one decimal place
            result["weighted_rating"] = round(final_rating * 10) / 10
        else:
            # Fallback to prior mean if no valid weights
            result["weighted_rating"] = prior_mean

        # Include details if requested
        if include_details:
            result["details"] = {
                "review_weights": review_details,
                "bayesian_prior": prior_mean,
                "confidence_factor": self.confidence_factor,
                "weighted_average": (
                    weighted_sum / weight_sum if weight_sum > 0 else 0.0
                ),
                "confidence_adjustment": confidence,
            }

        return result

    def _calculate_recency_weight(self, review: Dict, current_time: datetime) -> float:
        """
        Calculate weight adjustment based on review recency.
        Recent reviews get higher weight, using an exponential decay function.
        """
        # Get review creation time
        created_at = review.get("created_at")
        if not created_at:
            return 1.0  # Default if no date

        # Convert to datetime if it's a string
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return 1.0  # Default if parsing fails

        # Calculate age in days
        if isinstance(created_at, datetime):
            age_days = (current_time - created_at).days

            # Apply exponential decay: weight = 2^(-age/half_life)
            recency_weight = 2.0 ** (-age_days / self.recency_half_life)

            # Ensure minimum weight (old reviews still have some value)
            return max(0.2, recency_weight)

        return 1.0  # Default if not a datetime

    def _calculate_content_weight(self, review: Dict) -> float:
        """
        Calculate weight adjustment based on review content.

        In a real implementation, this would use NLP to analyze:
        - Content length and detail
        - Sentiment consistency with numeric rating
        - Helpfulness to other users (votes)
        - Specific details vs. generic comments

        For this simplified version, we'll use basic signals.
        """
        content = review.get("content", "")
        helpfulness_votes = review.get("helpfulness_votes", 0)

        # Base weight
        content_weight = 0.0

        # Factor 1: Content length (longer reviews might be more detailed)
        if content:
            # Normalize length (cap at 500 chars for max score)
            length_score = min(1.0, len(content) / 500.0)
            content_weight += length_score * 0.4  # 40% contribution

        # Factor 2: Helpfulness votes
        if helpfulness_votes > 0:
            # Normalize votes (diminishing returns for many votes)
            vote_score = min(1.0, math.log10(helpfulness_votes + 1) / math.log10(21))
            content_weight += vote_score * 0.6  # 60% contribution

        # In a real implementation, would also consider:
        # - Sentiment analysis consistency
        # - Specific mention of features/services
        # - Photo/video attachments

        return content_weight

    def _calculate_reviewer_credibility(self, review: Dict) -> float:
        """
        Calculate weight adjustment based on reviewer credibility.

        In a real implementation, this would consider:
        - Reviewer's history (number of reviews, consistency)
        - Reviewer's status (regular customer, new user, etc.)
        - Pattern of ratings (all 5s or 1s vs. varied ratings)

        For this simplified version, we'll assume all reviewers are equally credible.
        """
        # In a real implementation, would query reviewer history
        return 1.0

    def _calculate_response_weight(self, review: Dict) -> float:
        """
        Calculate weight adjustment based on business response.

        Reviews that received a response from the business might be
        weighted differently (either higher because they were addressed,
        or lower if the response exposed issues with the review).
        """
        # Check if review has a response
        has_response = "review_response" in review and review["review_response"]

        # In a real implementation, might:
        # - Analyze response content
        # - Consider response timing
        # - Check if reviewer updated rating after response

        # For now, simply give a small boost to reviews with responses
        return 1.05 if has_response else 1.0

    def _apply_bias_correction(self, review: Dict, average_rating: float) -> float:
        """
        Apply bias correction to individual rating.

        This adjusts for common biases like:
        - Extreme rating bias (tendency to give 1s or 5s)
        - Cultural biases (some cultures tend to rate higher/lower)
        - Review source bias (mobile vs web, etc.)

        The correction pulls extreme ratings slightly toward the mean.
        """
        rating = review.get("rating", 0)

        # Skip invalid ratings
        if rating <= 0:
            return rating

        # Calculate deviation from average
        deviation = rating - average_rating

        # Apply a mild correction (pulling toward the average)
        # stronger for extreme ratings
        correction_strength = (
            abs(deviation) / 4.0
        )  # 4.0 = max possible deviation on 1-5 scale
        correction = deviation * self.bias_correction_factor * correction_strength

        # Apply correction (subtract because we want to pull toward mean)
        corrected_rating = rating - correction

        return corrected_rating
