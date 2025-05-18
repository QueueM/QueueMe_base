import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class ContentRanker:
    """
    Advanced algorithm for ranking content (reels, stories, etc.)
    in the customer feed based on relevance, engagement, and personalization.

    This algorithm optimizes content discovery by:
    1. Personalizing content based on user preferences
    2. Considering engagement metrics (likes, comments, shares)
    3. Incorporating recency and location relevance
    4. Balancing exploration and exploitation
    5. Applying business rules and boosting factors
    """

    def __init__(
        self,
        recency_weight: float = 1.0,
        relevance_weight: float = 1.5,
        engagement_weight: float = 1.2,
        location_weight: float = 1.0,
        following_boost: float = 1.3,
        verified_boost: float = 1.1,
        sponsored_boost: float = 1.5,
        exploration_factor: float = 0.2,
    ):
        """
        Initialize the content ranker with configurable weights.

        Args:
            recency_weight: Weight for content recency factor
            relevance_weight: Weight for content relevance to user interests
            engagement_weight: Weight for engagement metrics
            location_weight: Weight for location relevance
            following_boost: Boost factor for content from followed shops
            verified_boost: Boost factor for content from verified shops/specialists
            sponsored_boost: Boost factor for sponsored/ad content
            exploration_factor: Factor for showing new content types (exploration vs. exploitation)
        """
        self.recency_weight = recency_weight
        self.relevance_weight = relevance_weight
        self.engagement_weight = engagement_weight
        self.location_weight = location_weight
        self.following_boost = following_boost
        self.verified_boost = verified_boost
        self.sponsored_boost = sponsored_boost
        self.exploration_factor = exploration_factor

    def rank_feed_content(
        self,
        content_items: List[Dict],
        user_data: Dict,
        feed_type: str = "for_you",
        page_size: int = 20,
        page: int = 1,
        exclude_seen_content: bool = True,
    ) -> Dict:
        """
        Rank content items for a specific feed type based on user data.

        Args:
            content_items: List of content items (reels, stories, etc.) to rank
            user_data: Dict containing user information:
                - id: User ID
                - location: Dict with latitude and longitude
                - city: User's current city
                - interests: List of interest categories/topics
                - followed_shops: List of shop IDs the user follows
                - viewed_content: List of content IDs the user has viewed
                - engagement_history: Dict with user's previous engagements
            feed_type: Type of feed to generate ('for_you', 'nearby', 'following')
            page_size: Number of items per page
            page: Page number (1-based)
            exclude_seen_content: Whether to exclude content the user has already seen

        Returns:
            A dictionary containing:
            - ranked_content: List of ranked content items
            - total_items: Total number of matching items
            - page: Current page number
            - total_pages: Total number of pages
            - next_page: Next page number (or None if last page)
            - ranking_explanation: Optional details about ranking factors
        """
        # Initialize result
        result = {
            "ranked_content": [],
            "total_items": 0,
            "page": page,
            "total_pages": 0,
            "next_page": None,
            "ranking_explanation": {},
        }

        # Apply basic filtering based on feed type
        filtered_items = self._filter_by_feed_type(content_items, user_data, feed_type)

        # Exclude content the user has already seen if requested
        if exclude_seen_content and user_data.get("viewed_content"):
            viewed_ids = set(user_data["viewed_content"])
            filtered_items = [item for item in filtered_items if item["id"] not in viewed_ids]

        # If no items after filtering, return empty result
        if not filtered_items:
            return result

        # Calculate base scores for all filtered items
        scored_items = self._calculate_content_scores(filtered_items, user_data, feed_type)

        # Apply diversification to ensure variety in feed
        diversified_items = self._apply_diversification(scored_items, user_data)

        # Sort by score (highest first)
        ranked_items = sorted(diversified_items, key=lambda x: x["_ranking_score"], reverse=True)

        # Implement pagination
        total_items = len(ranked_items)
        total_pages = (total_items + page_size - 1) // page_size

        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_items)

        # Get items for current page
        page_items = ranked_items[start_idx:end_idx]

        # Prepare items for return (remove internal ranking metadata)
        cleaned_items = []
        ranking_details = {}

        for item in page_items:
            # Store ranking details if present
            if "_ranking_details" in item:
                ranking_details[item["id"]] = item["_ranking_details"]

            # Remove internal ranking fields
            clean_item = {k: v for k, v in item.items() if not k.startswith("_ranking")}

            cleaned_items.append(clean_item)

        # Set result fields
        result["ranked_content"] = cleaned_items
        result["total_items"] = total_items
        result["total_pages"] = total_pages
        result["next_page"] = page + 1 if page < total_pages else None

        # Include ranking explanation if any details were collected
        if ranking_details:
            result["ranking_explanation"] = ranking_details

        return result

    def _filter_by_feed_type(
        self, content_items: List[Dict], user_data: Dict, feed_type: str
    ) -> List[Dict]:
        """
        Apply initial filtering based on feed type.
        """
        if feed_type == "nearby":
            # Filter to content in user's city
            user_city = user_data.get("city", "").lower()
            return [
                item for item in content_items if item.get("shop_city", "").lower() == user_city
            ]

        elif feed_type == "following":
            # Filter to content from shops the user follows
            followed_shops = set(user_data.get("followed_shops", []))
            return [item for item in content_items if item.get("shop_id") in followed_shops]

        elif feed_type == "for_you":
            # For personalized feed, apply less strict filtering
            # (scoring will handle relevance)
            return content_items

        # Default: no specific filtering
        return content_items

    def _calculate_content_scores(
        self, content_items: List[Dict], user_data: Dict, feed_type: str
    ) -> List[Dict]:
        """
        Calculate ranking scores for content items based on multiple factors.
        """
        scored_items = []

        # Get user location for distance calculation
        user_location = user_data.get("location", {})
        user_lat = user_location.get("latitude")
        user_lng = user_location.get("longitude")

        # Get user interests for relevance calculation
        user_interests = set(user_data.get("interests", []))

        # Get followed shops for relationship calculation
        followed_shops = set(user_data.get("followed_shops", []))

        # Get current time for recency calculation
        current_time = datetime.now()

        # Calculate scores for each item
        for item in content_items:
            # Create a copy of the item to avoid modifying original
            scored_item = item.copy()

            # Initialize factors dict to track scoring components
            ranking_factors = {}

            # 1. Base score starts at 1.0
            base_score = 1.0
            ranking_factors["base"] = base_score

            # 2. Recency factor
            recency_score = self._calculate_recency_score(item, current_time)
            ranking_factors["recency"] = recency_score * self.recency_weight

            # 3. Relevance/interest match factor
            relevance_score = self._calculate_relevance_score(item, user_interests)
            ranking_factors["relevance"] = relevance_score * self.relevance_weight

            # 4. Engagement factor
            engagement_score = self._calculate_engagement_score(item)
            ranking_factors["engagement"] = engagement_score * self.engagement_weight

            # 5. Location/proximity factor (especially important for 'nearby' feed)
            location_score = 0
            if feed_type == "nearby" and user_lat and user_lng:
                location_score = self._calculate_location_score(item, user_lat, user_lng)
            ranking_factors["location"] = location_score * self.location_weight

            # 6. Apply boost factors

            # Following boost: Content from shops the user follows
            if item.get("shop_id") in followed_shops:
                following_boost = self.following_boost
            else:
                following_boost = 1.0
            ranking_factors["following_boost"] = following_boost

            # Verified boost: Content from verified shops
            if item.get("is_verified", False):
                verified_boost = self.verified_boost
            else:
                verified_boost = 1.0
            ranking_factors["verified_boost"] = verified_boost

            # Sponsored content boost
            if item.get("is_sponsored", False):
                sponsored_boost = self.sponsored_boost
            else:
                sponsored_boost = 1.0
            ranking_factors["sponsored_boost"] = sponsored_boost

            # 7. Calculate final score
            final_score = (
                base_score
                + (recency_score * self.recency_weight)
                + (relevance_score * self.relevance_weight)
                + (engagement_score * self.engagement_weight)
                + (location_score * self.location_weight)
            )

            # Apply boosts
            final_score *= following_boost * verified_boost * sponsored_boost

            # 8. Add exploration factor
            # This adds randomness to prevent echo chambers and bubble effects
            if self.exploration_factor > 0:
                import random

                exploration_boost = 1.0 + (random.random() * self.exploration_factor)
                final_score *= exploration_boost
                ranking_factors["exploration"] = exploration_boost

            # Store the final score and factors in the item
            scored_item["_ranking_score"] = final_score
            scored_item["_ranking_details"] = ranking_factors

            scored_items.append(scored_item)

        return scored_items

    def _calculate_recency_score(self, item: Dict, current_time: datetime) -> float:
        """
        Calculate recency score based on content age.
        Newer content gets higher scores, with a decay over time.
        """
        # Get content creation time
        created_at = item.get("created_at")
        if not created_at:
            return 0.5  # Default if time is missing

        # Convert to datetime if it's a string
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return 0.5  # Default if parsing fails

        # Calculate age in hours
        if isinstance(created_at, datetime):
            age_hours = (current_time - created_at).total_seconds() / 3600

            # Exponential decay: score = exp(-age_hours/halflife)
            # Half-life of 24 hours means content loses half its value each day
            halflife = 24.0  # Adjust based on desired decay rate
            recency_score = 2.0 * (0.5 ** (age_hours / halflife))

            # Cap between 0.0 and 1.0
            return max(0.0, min(1.0, recency_score))

        return 0.5  # Default if type is not datetime

    def _calculate_relevance_score(self, item: Dict, user_interests: set) -> float:
        """
        Calculate relevance score based on match with user interests.
        """
        # Get content categories/tags
        content_categories = set(item.get("categories", []))
        content_tags = set(item.get("tags", []))

        # If no categories/tags or no user interests, use medium relevance
        if not (content_categories or content_tags) or not user_interests:
            return 0.5

        # Calculate overlap between user interests and content categories/tags
        combined_content_topics = content_categories.union(content_tags)
        overlap = len(user_interests.intersection(combined_content_topics))

        # Normalize by minimum of the two set sizes to get overlap ratio
        min_size = min(len(user_interests), len(combined_content_topics))

        if min_size == 0:
            return 0.5

        overlap_ratio = overlap / min_size

        # Scale to 0.0-1.0 range with bias toward some relevance
        # Even 0 overlap should get a small score for exploration
        return 0.2 + (0.8 * overlap_ratio)

    def _calculate_engagement_score(self, item: Dict) -> float:
        """
        Calculate engagement score based on likes, comments, shares.
        Uses a logarithmic scale to prevent very popular content from dominating.
        """
        # Get engagement metrics
        likes = item.get("likes_count", 0)
        comments = item.get("comments_count", 0)
        shares = item.get("shares_count", 0)

        # Calculate weighted engagement (comments and shares worth more than likes)
        weighted_engagement = likes + (comments * 3) + (shares * 5)

        # Apply logarithmic scaling to dampen the effect of viral content
        # log(1+x) ensures the value is always positive and log(1) = 0
        import math

        log_engagement = math.log1p(weighted_engagement)

        # Normalize to 0-1 range
        # Assuming log_engagement of 10 (which corresponds to thousands of engagements)
        # deserves max score
        max_log_engagement = 10.0

        # Cap between 0.0 and 1.0
        return min(1.0, log_engagement / max_log_engagement)

    def _calculate_location_score(self, item: Dict, user_lat: float, user_lng: float) -> float:
        """
        Calculate location relevance score based on distance.
        Closer content gets higher scores.
        """
        # Get content location
        shop_lat = item.get("shop_latitude")
        shop_lng = item.get("shop_longitude")

        # If location is missing, use medium relevance
        if shop_lat is None or shop_lng is None:
            return 0.5

        # Calculate distance using Haversine formula
        distance_km = self._calculate_distance(user_lat, user_lng, shop_lat, shop_lng)

        # Calculate score: 1.0 for very close (< 1km), decreasing with distance
        # Using an exponential decay function
        proximity_score = 1.0 * (0.5 ** (distance_km / 5.0))  # Half-value at 5km

        # Cap between 0.0 and 1.0
        return max(0.0, min(1.0, proximity_score))

    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.
        """
        from math import atan2, cos, radians, sin, sqrt

        # Convert latitude and longitude from degrees to radians
        lat1_rad = radians(lat1)
        lng1_rad = radians(lng1)
        lat2_rad = radians(lat2)
        lng2_rad = radians(lng2)

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

    def _apply_diversification(self, scored_items: List[Dict], user_data: Dict) -> List[Dict]:
        """
        Apply diversification to ensure variety in the feed.
        Prevents the feed from being dominated by a single shop or content type.
        """
        # Group items by shop
        shops_items = {}
        for item in scored_items:
            shop_id = item.get("shop_id")
            if shop_id not in shops_items:
                shops_items[shop_id] = []
            shops_items[shop_id].append(item)

        # Group items by content type (e.g., video, image)
        type_items = {}
        for item in scored_items:
            content_type = item.get("content_type", "unknown")
            if content_type not in type_items:
                type_items[content_type] = []
            type_items[content_type].append(item)

        # Detect shops with many items
        shops_with_many = [
            shop_id
            for shop_id, items in shops_items.items()
            if len(items) > 3  # Arbitrary threshold
        ]

        # Apply penalty to items from shops that already have many items
        # This ensures diversity in the feed
        for item in scored_items:
            shop_id = item.get("shop_id")

            # Skip if shop_id is missing or if shop doesn't have many items
            if not shop_id or shop_id not in shops_with_many:
                continue

            # Get all items from this shop
            shop_items = shops_items[shop_id]

            # Skip first few items (allow some presence)
            item_index = shop_items.index(item)
            if item_index < 2:  # Allow first 2 items without penalty
                continue

            # Apply progressive penalty based on position
            # Later items get larger penalty
            diversity_penalty = 0.9 ** (item_index - 1)  # 10% reduction per item

            item["_ranking_score"] *= diversity_penalty

            # Track penalty in ranking details
            if "_ranking_details" in item:
                item["_ranking_details"]["diversity_penalty"] = diversity_penalty

        return scored_items
