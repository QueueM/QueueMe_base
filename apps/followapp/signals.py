from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.shopapp.models import Shop

from .models import Follow, FollowEvent, FollowStats


@receiver(post_save, sender=Follow)
def create_follow_event(sender, instance, created, **kwargs):
    """
    Create a follow event when a Follow object is created.
    Used for analytics and trend calculations.
    """
    if created:
        # Create a follow event
        FollowEvent.objects.create(
            customer=instance.customer, shop=instance.shop, event_type="follow"
        )

        # Update or create shop follow stats
        with transaction.atomic():
            stats, created = FollowStats.objects.get_or_create(
                shop=instance.shop,
                defaults={
                    "follower_count": 1,
                    "weekly_growth": 1,
                    "monthly_growth": 1,
                    "last_calculated": timezone.now(),
                },
            )

            if not created:
                stats.follower_count = F("follower_count") + 1
                stats.weekly_growth = F("weekly_growth") + 1
                stats.monthly_growth = F("monthly_growth") + 1
                stats.last_calculated = timezone.now()
                stats.save()


@receiver(post_delete, sender=Follow)
def create_unfollow_event(sender, instance, **kwargs):
    """
    Create an unfollow event when a Follow object is deleted.
    Update shop follow stats when unfollowed.
    """
    # Create unfollow event
    FollowEvent.objects.create(
        customer=instance.customer, shop=instance.shop, event_type="unfollow"
    )

    # Update shop follow stats
    with transaction.atomic():
        stats = FollowStats.objects.filter(shop=instance.shop).first()
        if stats:
            stats.follower_count = F("follower_count") - 1
            stats.weekly_growth = F("weekly_growth") - 1
            stats.monthly_growth = F("monthly_growth") - 1
            stats.last_calculated = timezone.now()
            stats.save()


@receiver(post_save, sender=Shop)
def initialize_follow_stats(sender, instance, created, **kwargs):
    """
    Initialize follow stats for a new shop.
    """
    if created:
        FollowStats.objects.create(
            shop=instance,
            follower_count=0,
            weekly_growth=0,
            monthly_growth=0,
            last_calculated=timezone.now(),
        )
