from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from apps.notificationsapp.services.notification_service import NotificationService
from apps.shopapp.models import Shop
from apps.storiesapp.models import Story, StoryView


class StoryService:
    """
    Service for managing stories, including creation, deletion, and expiry.
    """

    @staticmethod
    @transaction.atomic
    def create_story(shop_id, story_type, media_url, thumbnail_url=None):
        """
        Create a new story with associated media

        Args:
            shop_id (uuid): ID of the shop creating the story
            story_type (str): Type of story ('image' or 'video')
            media_url (str): URL to the story media
            thumbnail_url (str, optional): URL to the thumbnail image

        Returns:
            Story: The created story object
        """
        # Create the story
        story = Story.objects.create(
            shop_id=shop_id,
            story_type=story_type,
            media_url=media_url,
            thumbnail_url=thumbnail_url,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        # Send notifications to followers
        StoryService._notify_followers(story)

        # Send WebSocket notification for real-time updates
        StoryService._send_story_websocket_notification(story, "created")

        return story

    @staticmethod
    @transaction.atomic
    def delete_story(story_id):
        """
        Delete a story

        Args:
            story_id (uuid): ID of the story to delete

        Returns:
            bool: True if story was deleted, False otherwise
        """
        try:
            story = Story.objects.get(id=story_id)

            # Send WebSocket notification about deletion
            StoryService._send_story_websocket_notification(story, "deleted")

            # Delete the story
            story.delete()
            return True
        except Story.DoesNotExist:
            return False

    @staticmethod
    @transaction.atomic
    def mark_viewed(story_id, customer_id):
        """
        Mark a story as viewed by a customer

        Args:
            story_id (uuid): ID of the story
            customer_id (uuid): ID of the customer viewing the story

        Returns:
            StoryView: The created view record or None if already exists
        """
        story_view, created = StoryView.objects.get_or_create(
            story_id=story_id, customer_id=customer_id
        )

        if created:
            # If this is a new view, increment analytics counters (if any)
            pass

        return story_view if created else None

    @staticmethod
    def get_expired_stories():
        """
        Get all stories that have expired but are still marked as active

        Returns:
            QuerySet: QuerySet of expired stories
        """
        return Story.objects.filter(expires_at__lte=timezone.now(), is_active=True)

    @staticmethod
    @transaction.atomic
    def deactivate_expired_stories():
        """
        Deactivate all stories that have expired

        Returns:
            int: Number of stories deactivated
        """
        expired_stories = StoryService.get_expired_stories()

        # Send WebSocket notifications for each expired story
        for story in expired_stories:
            StoryService._send_story_expiry_notification(story)

        # Update all expired stories to inactive
        count = expired_stories.update(is_active=False)

        return count

    @staticmethod
    def get_stories_by_shop(shop_id, active_only=True, include_expired=False):
        """
        Get all stories for a specific shop

        Args:
            shop_id (uuid): ID of the shop
            active_only (bool): Only include active stories
            include_expired (bool): Include expired stories

        Returns:
            QuerySet: QuerySet of stories
        """
        queryset = Story.objects.filter(shop_id=shop_id)

        if active_only:
            queryset = queryset.filter(is_active=True)

        if not include_expired:
            queryset = queryset.filter(expires_at__gt=timezone.now())

        return queryset.order_by("-created_at")

    @staticmethod
    def get_stories_by_customer(customer_id, followed_only=False):
        """
        Get stories visible to a specific customer (same city or followed shops)

        Args:
            customer_id (uuid): ID of the customer
            followed_only (bool): Only include stories from followed shops

        Returns:
            QuerySet: QuerySet of stories
        """
        from apps.customersapp.models import CustomerProfile
        from apps.followapp.models import Follow

        # Get active, non-expired stories
        queryset = Story.objects.filter(is_active=True, expires_at__gt=timezone.now())

        if followed_only:
            # Get shops followed by customer
            shop_content_type = ContentType.objects.get_for_model(Shop)
            followed_shops = Follow.objects.filter(
                follower_id=customer_id, content_type=shop_content_type
            ).values_list("object_id", flat=True)

            # Filter to only followed shops
            queryset = queryset.filter(shop_id__in=followed_shops)
        else:
            # Get customer's city
            try:
                profile = CustomerProfile.objects.get(user_id=customer_id)
                if profile.city:
                    # Filter to shops in same city
                    queryset = queryset.filter(shop__location__city=profile.city)
            except CustomerProfile.DoesNotExist:
                pass

        return queryset.order_by("-created_at")

    @staticmethod
    def _notify_followers(story):
        """
        Send notifications to followers when a new story is created

        Args:
            story (Story): The story object
        """
        # Get content type for Shop model
        shop_content_type = ContentType.objects.get_for_model(Shop)

        # Get followers of this shop
        from apps.followapp.models import Follow

        followers = Follow.objects.filter(content_type=shop_content_type, object_id=story.shop_id)

        # Send notification to each follower
        for follow in followers:
            NotificationService.send_notification(
                user_id=follow.follower_id,
                notification_type="new_story",
                data={
                    "shop_name": story.shop.name,
                    "shop_id": str(story.shop_id),
                    "story_id": str(story.id),
                    "story_type": story.story_type,
                },
                channels=["push", "in_app"],
            )

    @staticmethod
    def _send_story_websocket_notification(story, action):
        """
        Send WebSocket notification about a story update

        Args:
            story (Story): The story object
            action (str): The action performed ('created', 'deleted')
        """
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        # Send to shop's group
        shop_group = f"stories_shop_{story.shop_id}"
        async_to_sync(channel_layer.group_send)(
            shop_group,
            {
                "type": "story_update",
                "story_id": str(story.id),
                "shop_id": str(story.shop_id),
                "shop_name": story.shop.name,
                "action": action,
                "story_type": story.story_type,
                "timestamp": timezone.now().isoformat(),
            },
        )

        # Also send to followed_shops groups
        from apps.followapp.models import Follow

        shop_content_type = ContentType.objects.get_for_model(Shop)
        followers = Follow.objects.filter(content_type=shop_content_type, object_id=story.shop_id)

        for follow in followers:
            followed_group = f"stories_followed_{follow.follower_id}"
            async_to_sync(channel_layer.group_send)(
                followed_group,
                {
                    "type": "story_update",
                    "story_id": str(story.id),
                    "shop_id": str(story.shop_id),
                    "shop_name": story.shop.name,
                    "action": action,
                    "story_type": story.story_type,
                    "timestamp": timezone.now().isoformat(),
                },
            )

    @staticmethod
    def _send_story_expiry_notification(story):
        """
        Send WebSocket notification about a story expiring

        Args:
            story (Story): The expiring story
        """
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        # Send to shop's group
        shop_group = f"stories_shop_{story.shop_id}"
        async_to_sync(channel_layer.group_send)(
            shop_group,
            {
                "type": "story_expiry",
                "story_id": str(story.id),
                "shop_id": str(story.shop_id),
            },
        )
