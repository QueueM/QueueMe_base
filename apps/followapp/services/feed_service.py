import datetime
from typing import Any, Dict, List

from ..models import Follow
from .follow_service import FollowService


class FeedService:
    """
    Service for generating content feeds based on follow relationships.
    Manages what content appears in a user's "Following" feed.
    """

    @staticmethod
    def get_following_stories_feed(customer) -> List[Dict[str, Any]]:
        """
        Get stories from shops the customer follows for the home feed.
        Stories are grouped by shop and only includes active stories (< 24h old).

        Args:
            customer: The customer user object

        Returns:
            List of shop objects with their active stories
        """
        # Get shops the customer follows
        following_shop_ids = FollowService.get_following_shop_ids(customer)

        if not following_shop_ids:
            return []

        # Get active stories from followed shops
        expiry_threshold = datetime.datetime.now() - datetime.timedelta(hours=24)

        # Import here to avoid circular imports
        from apps.storiesapp.services.story_service import StoryService

        # Get stories grouped by shop
        return StoryService.get_stories_by_shops(
            shop_ids=following_shop_ids, since=expiry_threshold
        )

    @staticmethod
    def get_following_reels_feed(customer, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """
        Get reels from shops the customer follows.
        Ordered by recency with pagination.

        Args:
            customer: The customer user object
            page: Page number (1-indexed)
            page_size: Number of reels per page

        Returns:
            Dict with reels data and pagination info
        """
        # Get shops the customer follows
        following_shop_ids = FollowService.get_following_shop_ids(customer)

        if not following_shop_ids:
            return {"results": [], "page": page, "total_pages": 0, "total_count": 0}

        # Import here to avoid circular imports
        from apps.reelsapp.services.reel_service import ReelService

        # Get reels from followed shops
        return ReelService.get_reels_feed(
            filter_type="following",
            customer=customer,
            shop_ids=following_shop_ids,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def should_show_shop_updates(customer, shop) -> bool:
        """
        Check if a customer should see updates from a specific shop.
        Based on follow relationship and notification preferences.

        Args:
            customer: The customer user object
            shop: The shop object

        Returns:
            Boolean indicating if updates should be shown
        """
        # Check if the customer follows the shop
        follow = Follow.objects.filter(customer=customer, shop=shop).first()

        if not follow:
            return False

        # Check notification preferences
        return follow.notification_preference
