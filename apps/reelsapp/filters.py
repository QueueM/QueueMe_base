import django_filters
from django.db.models import Count, F, Q

from .models import Reel


class ReelFilter(django_filters.FilterSet):
    """Filter for Reels"""

    title = django_filters.CharFilter(lookup_expr="icontains")
    caption = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=Reel.STATUS_CHOICES)
    category = django_filters.UUIDFilter(field_name="categories__id")
    service = django_filters.UUIDFilter(field_name="services__id")
    package = django_filters.UUIDFilter(field_name="packages__id")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    min_views = django_filters.NumberFilter(field_name="view_count", lookup_expr="gte")
    max_views = django_filters.NumberFilter(field_name="view_count", lookup_expr="lte")

    # Advanced filters
    is_trending = django_filters.BooleanFilter(method="filter_trending")
    min_engagement = django_filters.NumberFilter(method="filter_min_engagement")
    max_duration = django_filters.NumberFilter(field_name="duration", lookup_expr="lte")

    class Meta:
        model = Reel
        fields = ["shop", "title", "caption", "status", "created_at", "view_count"]

    def filter_trending(self, queryset, name, value):
        """
        Filter for trending reels based on recent engagement.
        A trending reel has above-average engagement in the last 7 days.
        """
        if not value:
            return queryset

        # Calculate engagement score (likes + comments*2 + shares*3)
        from datetime import timedelta

        from django.utils import timezone

        recent_date = timezone.now() - timedelta(days=7)

        return queryset.annotate(
            recent_likes=Count("likes", filter=Q(likes__created_at__gte=recent_date)),
            recent_comments=Count("comments", filter=Q(comments__created_at__gte=recent_date)),
            recent_shares=Count("shares", filter=Q(shares__created_at__gte=recent_date)),
            engagement_score=F("recent_likes")
            + (F("recent_comments") * 2)
            + (F("recent_shares") * 3),
        ).filter(
            engagement_score__gte=5
        )  # Threshold for 'trending'

    def filter_min_engagement(self, queryset, name, value):
        """
        Filter reels with a minimum engagement score.
        Engagement score = likes + comments*2 + shares*3
        """
        return queryset.annotate(
            total_likes=Count("likes"),
            total_comments=Count("comments"),
            total_shares=Count("shares"),
            engagement_score=F("total_likes") + (F("total_comments") * 2) + (F("total_shares") * 3),
        ).filter(engagement_score__gte=value)
