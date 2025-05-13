from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.notificationsapp.services.notification_service import NotificationService

from .models import Reel, ReelComment, ReelLike, ReelShare
from .services.engagement_service import EngagementService


@receiver(post_save, sender=Reel)
def handle_reel_published(sender, instance, created, **kwargs):
    """
    Signal handler for when a reel is published.
    Sends notification to followers.
    """
    # Skip if not a newly published reel
    if not created and instance.status == "published" and instance.published_at:
        # Check if publication happened in the last minute
        one_minute_ago = timezone.now() - timezone.timedelta(minutes=1)
        if instance.published_at >= one_minute_ago:
            # Send notification to followers
            shop = instance.shop

            # Get followers of this shop
            from apps.followapp.models import Follow

            follower_ids = Follow.objects.filter(shop=shop, is_active=True).values_list(
                "user_id", flat=True
            )

            # Send notifications
            for follower_id in follower_ids:
                NotificationService.send_notification(
                    user_id=follower_id,
                    notification_type="new_reel",
                    data={
                        "shop_name": shop.name,
                        "reel_title": instance.title,
                        "reel_id": str(instance.id),
                    },
                    channels=["push", "in_app"],
                )


@receiver(post_save, sender=ReelLike)
def handle_reel_like(sender, instance, created, **kwargs):
    """
    Signal handler for when a reel is liked.
    Updates engagement metrics and sends notification to shop.
    """
    if created:
        # Update engagement metrics
        EngagementService.update_engagement_metrics(instance.reel)

        # Notify shop about the like if it crosses threshold
        like_count = instance.reel.likes.count()
        if like_count in [5, 10, 50, 100, 500, 1000]:  # Milestone thresholds
            shop = instance.reel.shop

            # Get shop manager
            if shop.manager:
                NotificationService.send_notification(
                    user_id=shop.manager.id,
                    notification_type="reel_engagement_milestone",
                    data={
                        "reel_title": instance.reel.title,
                        "reel_id": str(instance.reel.id),
                        "metric": "likes",
                        "count": like_count,
                    },
                    channels=["in_app"],
                )


@receiver(post_save, sender=ReelComment)
def handle_reel_comment(sender, instance, created, **kwargs):
    """
    Signal handler for when a reel receives a comment.
    Updates engagement metrics and sends notification to shop and reel owner.
    """
    if created:
        # Update engagement metrics
        EngagementService.update_engagement_metrics(instance.reel)

        # Notify shop about the comment
        shop = instance.reel.shop

        # Get shop manager
        if shop.manager:
            NotificationService.send_notification(
                user_id=shop.manager.id,
                notification_type="new_reel_comment",
                data={
                    "reel_title": instance.reel.title,
                    "reel_id": str(instance.reel.id),
                    "comment_preview": instance.content[:50]
                    + ("..." if len(instance.content) > 50 else ""),
                    "user_name": instance.user.phone_number,  # Use name if available
                },
                channels=["in_app"],
            )


@receiver(post_save, sender=ReelShare)
def handle_reel_share(sender, instance, created, **kwargs):
    """
    Signal handler for when a reel is shared.
    Updates engagement metrics.
    """
    if created:
        # Update engagement metrics
        EngagementService.update_engagement_metrics(instance.reel)

        # Milestone notifications (similar to likes)
        share_count = instance.reel.shares.count()
        if share_count in [5, 10, 50, 100]:  # Milestone thresholds
            shop = instance.reel.shop

            # Get shop manager
            if shop.manager:
                NotificationService.send_notification(
                    user_id=shop.manager.id,
                    notification_type="reel_engagement_milestone",
                    data={
                        "reel_title": instance.reel.title,
                        "reel_id": str(instance.reel.id),
                        "metric": "shares",
                        "count": share_count,
                    },
                    channels=["in_app"],
                )
