from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction

from apps.notificationsapp.services.notification_service import NotificationService

from ..models import Follow, FollowEvent


class FollowService:
    """
    Service for handling follow relationships between customers and shops.
    Implements advanced logic for managing follows, syncing with notifications,
    and tracking follow events.
    """

    @staticmethod
    @transaction.atomic
    def toggle_follow(customer, shop) -> Tuple[bool, Optional[Follow]]:
        """
        Toggle the follow status between a customer and shop.

        Args:
            customer: The customer user object
            shop: The shop object

        Returns:
            Tuple containing (is_following after toggle, Follow object if created)
        """
        # Check if follow relationship exists
        existing_follow = Follow.objects.filter(customer=customer, shop=shop).first()

        if existing_follow:
            # Already following, so unfollow
            existing_follow.delete()
            # Record the event with unfollow source
            FollowEvent.objects.create(
                customer=customer, shop=shop, event_type="unfollow", source="toggle_api"
            )
            return False, None
        else:
            # Not following, so create follow
            follow = Follow.objects.create(
                customer=customer, shop=shop, notification_preference=True
            )
            # Record the event with follow source
            FollowEvent.objects.create(
                customer=customer, shop=shop, event_type="follow", source="toggle_api"
            )

            # Send follow notification to shop owner/manager
            if shop.manager:
                NotificationService.send_notification(
                    user_id=shop.manager.id,
                    notification_type="new_follower",
                    data={
                        "shop_name": shop.name,
                        "follower_phone": customer.phone_number,
                    },
                    channels=["push", "in_app"],
                )

            return True, follow

    @staticmethod
    def get_following_shop_ids(customer) -> List[str]:
        """
        Get all shop IDs that a customer follows.
        Used for efficient filtering in feed queries.

        Args:
            customer: The customer user object

        Returns:
            List of shop IDs the customer follows
        """
        return list(
            Follow.objects.filter(customer=customer).values_list("shop_id", flat=True)
        )

    @staticmethod
    def update_notification_preference(follow_id, preference: bool) -> bool:
        """
        Update the notification preference for a specific follow relationship.

        Args:
            follow_id: The follow relationship ID
            preference: Boolean indicating if notifications should be received

        Returns:
            Boolean indicating success
        """
        try:
            follow = Follow.objects.get(id=follow_id)
            follow.notification_preference = preference
            follow.save(update_fields=["notification_preference", "updated_at"])
            return True
        except Follow.DoesNotExist:
            return False

    @staticmethod
    def get_user_follow_counts(customer) -> Dict[str, int]:
        """
        Get basic follow statistics for a user.

        Args:
            customer: The customer user object

        Returns:
            Dict containing count information
        """
        follows_count = Follow.objects.filter(customer=customer).count()

        return {"follows_count": follows_count}

    @staticmethod
    def recommend_shops_to_follow(customer, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recommend shops to follow based on city, category preferences,
        and popular shops the user isn't following yet.

        Args:
            customer: The customer user object
            limit: Maximum number of recommendations to return

        Returns:
            List of recommended shop objects
        """
        # Get shops the user already follows
        following_shop_ids = FollowService.get_following_shop_ids(customer)

        # Start with shops in the same city that the customer doesn't follow yet
        recommended_shops = []

        if customer.city:
            # Get popular shops in customer's city that they don't follow
            from apps.shopapp.models import Shop

            city_shops = (
                Shop.objects.filter(location__city=customer.city, is_active=True)
                .exclude(id__in=following_shop_ids)
                .select_related("follow_stats")
            )

            # Order by verification and follower count
            if city_shops.exists():
                # First get verified shops ordered by follower count
                verified_shops = city_shops.filter(is_verified=True).order_by(
                    "-follow_stats__follower_count"
                )[:limit]

                recommended_shops.extend(verified_shops)

                # If we need more, get unverified shops
                if len(recommended_shops) < limit:
                    remaining = limit - len(recommended_shops)
                    unverified_shops = city_shops.filter(is_verified=False).order_by(
                        "-follow_stats__follower_count"
                    )[:remaining]

                    recommended_shops.extend(unverified_shops)

        # Return the recommendations
        return recommended_shops[:limit]
