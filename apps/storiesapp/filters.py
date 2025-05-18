import django_filters
from django.utils import timezone

from apps.storiesapp.models import Story


class StoryFilter(django_filters.FilterSet):
    """
    Filter for Story model that includes additional filtering by:
    - shop_id: Filter by specific shop
    - expired: Filter to include/exclude expired stories
    - active_only: Filter to only include active stories
    - type: Filter by story type (image/video)
    - followed_by: Filter to only include stories from shops followed by the specified user
    """

    shop_id = django_filters.UUIDFilter(field_name="shop__id")
    expired = django_filters.BooleanFilter(method="filter_expired")
    active_only = django_filters.BooleanFilter(field_name="is_active")
    type = django_filters.CharFilter(field_name="story_type")
    followed_by = django_filters.UUIDFilter(method="filter_followed_by")

    class Meta:
        model = Story
        fields = ["shop_id", "expired", "active_only", "type"]

    def filter_expired(self, queryset, name, value):
        """Filter to include or exclude expired stories"""
        now = timezone.now()
        if value:  # Include expired
            return queryset.filter(expires_at__lte=now)
        else:  # Exclude expired
            return queryset.filter(expires_at__gt=now)

    def filter_followed_by(self, queryset, name, value):
        """Filter to only include stories from shops followed by the specified user"""
        from apps.followapp.models import Follow

        # Get shops followed by user
        followed_shops = Follow.objects.filter(
            follower_id=value, content_type__model="shop"
        ).values_list("object_id", flat=True)

        # Filter stories to only those from followed shops
        return queryset.filter(shop_id__in=followed_shops)
