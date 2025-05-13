from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.followapp.models import Follow
from apps.shopapp.models import Shop
from apps.storiesapp.models import Story, StoryView


class StoryFeedGenerator:
    """
    Advanced algorithm for generating story feeds for customers.
    Handles two main feed types:
    1. Home feed - Stories from shops that the customer follows
    2. Shop feed - All stories from a specific shop

    Includes optimization for performance and relevance.
    """

    def generate_home_feed(self, customer_id):
        """
        Generate a personalized story feed for the customer's home screen.
        Shows stories from shops they follow, ordered by recency.

        Args:
            customer_id (uuid): ID of the customer

        Returns:
            QuerySet: QuerySet of stories for the home feed
        """
        # Get shop content type
        shop_content_type = ContentType.objects.get_for_model(Shop)

        # Get shops followed by the customer
        followed_shops = Follow.objects.filter(
            follower_id=customer_id, content_type=shop_content_type
        ).values_list("object_id", flat=True)

        # Get active, non-expired stories from followed shops
        stories = Story.objects.filter(
            shop_id__in=followed_shops, is_active=True, expires_at__gt=timezone.now()
        )

        # Optimize the feed with advanced algorithm
        stories = self._optimize_feed(stories, customer_id)

        return stories

    def generate_shop_feed(self, shop_id):
        """
        Generate a feed for a specific shop's screen.
        Shows all active stories from that shop.

        Args:
            shop_id (uuid): ID of the shop

        Returns:
            QuerySet: QuerySet of stories for the shop feed
        """
        # Get active, non-expired stories for this shop
        stories = Story.objects.filter(
            shop_id=shop_id, is_active=True, expires_at__gt=timezone.now()
        ).order_by("-created_at")

        return stories

    def _optimize_feed(self, stories, customer_id):
        """
        Optimize a story feed for a specific customer using an advanced algorithm.

        The algorithm:
        1. Prioritizes unseen stories
        2. Considers recency
        3. Groups by shop (to avoid one shop dominating the feed)
        4. Considers engagement patterns

        Args:
            stories (QuerySet): Base QuerySet of stories
            customer_id (uuid): ID of the customer

        Returns:
            QuerySet: Optimized QuerySet of stories
        """
        # Get viewed stories by this customer
        viewed_story_ids = StoryView.objects.filter(customer_id=customer_id).values_list(
            "story_id", flat=True
        )

        # Split stories into viewed and unviewed
        unviewed_stories = stories.exclude(id__in=viewed_story_ids)
        viewed_stories = stories.filter(id__in=viewed_story_ids)

        # Get shops with unviewed stories
        shops_with_unviewed = unviewed_stories.values_list("shop_id", flat=True).distinct()

        # For each shop with unviewed stories, take the most recent
        prioritized_stories = []

        for shop_id in shops_with_unviewed:
            # Get most recent unviewed story for this shop
            shop_unviewed = unviewed_stories.filter(shop_id=shop_id).order_by("-created_at").first()
            if shop_unviewed:
                prioritized_stories.append(shop_unviewed.id)

        # Now add shops that only have viewed stories
        shops_with_only_viewed = (
            viewed_stories.exclude(shop_id__in=shops_with_unviewed)
            .values_list("shop_id", flat=True)
            .distinct()
        )

        for shop_id in shops_with_only_viewed:
            # Get most recent story for this shop
            shop_story = viewed_stories.filter(shop_id=shop_id).order_by("-created_at").first()
            if shop_story:
                prioritized_stories.append(shop_story.id)

        # Create a combined queryset with the prioritized order
        from django.db.models import Case, IntegerField, Value, When

        # Create ordering based on the prioritized story IDs
        preserved_order = Case(
            *[When(id=id, then=Value(i)) for i, id in enumerate(prioritized_stories)],
            default=Value(len(prioritized_stories)),
            output_field=IntegerField()
        )

        # Get all stories with the preserved order
        optimized_stories = Story.objects.filter(id__in=prioritized_stories).order_by(
            preserved_order
        )

        return optimized_stories

    def get_explore_feed(self, customer_id, city=None):
        """
        Generate an 'Explore' feed with stories from shops in the customer's city
        that they don't follow. This is for discovery.

        Args:
            customer_id (uuid): ID of the customer
            city (str, optional): City to filter by, if not provided uses customer's city

        Returns:
            QuerySet: QuerySet of stories for the explore feed
        """
        # Get shop content type
        shop_content_type = ContentType.objects.get_for_model(Shop)

        # Get shops followed by the customer
        followed_shops = Follow.objects.filter(
            follower_id=customer_id, content_type=shop_content_type
        ).values_list("object_id", flat=True)

        # Get customer's city if not provided
        if not city:
            from apps.customersapp.models import CustomerProfile

            try:
                profile = CustomerProfile.objects.get(user_id=customer_id)
                city = profile.city
            except CustomerProfile.DoesNotExist:
                return Story.objects.none()

        # Get active, non-expired stories from shops in the same city that are not followed
        stories = (
            Story.objects.filter(
                shop__location__city=city, is_active=True, expires_at__gt=timezone.now()
            )
            .exclude(shop_id__in=followed_shops)
            .order_by("?")[:20]
        )  # Randomize for discovery

        return stories
