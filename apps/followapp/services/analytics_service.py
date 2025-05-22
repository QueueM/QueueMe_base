from datetime import timedelta
from typing import Any, Dict, List

from django.db.models import Count
from django.utils import timezone

from apps.shopapp.models import Shop

from ..models import Follow, FollowEvent, FollowStats


class FollowAnalyticsService:
    """
    Service for generating analytics and insights about follow relationships.
    Provides data for shop owners to understand their follower growth and patterns.
    """

    @staticmethod
    def get_follower_trends(shop) -> Dict[str, Any]:
        """
        Generate follower trend data for a shop.
        Shows daily follower growth for the last 30 days.

        Args:
            shop: The shop object

        Returns:
            Dict containing follower trend data
        """
        # Get dates for the analysis
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)

        # Get follow events for this shop in the last 30 days
        events = FollowEvent.objects.filter(
            shop=shop, timestamp__date__gte=start_date, timestamp__date__lte=end_date
        ).order_by("timestamp")

        # Prepare data structures for analysis
        daily_follows = {}
        daily_unfollows = {}

        # Initialize all dates with zero
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.isoformat()
            daily_follows[date_str] = 0
            daily_unfollows[date_str] = 0
            current_date += timedelta(days=1)

        # Process events and group by date
        for event in events:
            date_str = event.timestamp.date().isoformat()
            if event.event_type == "follow":
                daily_follows[date_str] = daily_follows.get(date_str, 0) + 1
            else:  # unfollow
                daily_unfollows[date_str] = daily_unfollows.get(date_str, 0) + 1

        # Calculate net growth
        daily_net = {}
        for date in daily_follows.keys():
            daily_net[date] = daily_follows[date] - daily_unfollows[date]

        # Return the trend data
        return {
            "dates": list(daily_follows.keys()),
            "follows": list(daily_follows.values()),
            "unfollows": list(daily_unfollows.values()),
            "net_growth": list(daily_net.values()),
        }

    @staticmethod
    def refresh_follow_stats(shop=None):
        """
        Refresh the pre-calculated follow statistics.
        Can be run for one shop or all shops.

        Args:
            shop: Optional shop object to refresh stats for
        """
        current_time = timezone.now()

        if shop:
            shops = [shop]
        else:
            # Get all shops
            shops = Shop.objects.all()

        for shop in shops:
            # Get current follower count
            follower_count = Follow.objects.filter(shop=shop).count()

            # Get weekly growth (new follows - unfollows in the last 7 days)
            week_ago = current_time - timedelta(days=7)

            weekly_follows = FollowEvent.objects.filter(
                shop=shop, event_type="follow", timestamp__gte=week_ago
            ).count()

            weekly_unfollows = FollowEvent.objects.filter(
                shop=shop, event_type="unfollow", timestamp__gte=week_ago
            ).count()

            weekly_growth = weekly_follows - weekly_unfollows

            # Get monthly growth
            month_ago = current_time - timedelta(days=30)

            monthly_follows = FollowEvent.objects.filter(
                shop=shop, event_type="follow", timestamp__gte=month_ago
            ).count()

            monthly_unfollows = FollowEvent.objects.filter(
                shop=shop, event_type="unfollow", timestamp__gte=month_ago
            ).count()

            monthly_growth = monthly_follows - monthly_unfollows

            # Update the stats
            FollowStats.objects.update_or_create(
                shop=shop,
                defaults={
                    "follower_count": follower_count,
                    "weekly_growth": weekly_growth,
                    "monthly_growth": monthly_growth,
                    "last_calculated": current_time,
                },
            )

    @staticmethod
    def get_most_followed_shops(limit: int = 10) -> List[Shop]:
        """
        Get the most followed shops across the platform.

        Args:
            limit: Maximum number of shops to return

        Returns:
            List of shop objects with highest follower counts
        """
        # Get shops ordered by follower count
        return (
            Shop.objects.filter(is_active=True)
            .select_related("follow_stats")
            .order_by("-follow_stats__follower_count")[:limit]
        )

    @staticmethod
    def get_follow_source_breakdown(shop) -> Dict[str, int]:
        """
        Get breakdown of where followers are coming from for a shop.

        Args:
            shop: The shop object

        Returns:
            Dict with source names and counts
        """
        # Look at the last 90 days for relevant data
        start_date = timezone.now() - timedelta(days=90)

        # Get follow events with source information
        follow_sources = (
            FollowEvent.objects.filter(
                shop=shop, event_type="follow", timestamp__gte=start_date
            )
            .exclude(source__isnull=True)
            .values("source")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Convert to a simple dictionary
        result = {}
        for source in follow_sources:
            result[source["source"]] = source["count"]

        return result

    @staticmethod
    def calculate_retention_rate(shop) -> Dict[str, float]:
        """
        Calculate follow retention rates (7d, 30d, 90d) for the shop.

        Returns:
            Dict containing retention rates and total followers count
        """
        # Get all follow events for the shop
        from ..models import FollowEvent

        events = FollowEvent.objects.filter(shop=shop)

        # Organize events by customer
        customer_events = {}
        # Commented out unused variable - fix for F841
        # shop_follow_state = {}  # Track current follow state for each shop

        for event in events:
            if event.customer_id not in customer_events:
                customer_events[event.customer_id] = []
            customer_events[event.customer_id].append(event)

        # Calculate retention statistics
        total_followers = 0
        retained_7d = 0
        retained_30d = 0
        retained_90d = 0

        current_time = timezone.now()

        for customer_id, events in customer_events.items():
            # Sort events by timestamp
            sorted_events = sorted(events, key=lambda x: x.timestamp)

            # Check the current state (after all events)
            # Commented out unused variable - fix for F841
            # current_state = "unfollowed"
            if sorted_events and sorted_events[-1].event_type == "follow":
                # This is a current follower, check for how long
                follow_time = sorted_events[-1].timestamp
                follow_duration = current_time - follow_time

                total_followers += 1

                # Check retention periods
                if follow_duration.days >= 90:
                    retained_90d += 1
                    retained_30d += 1
                    retained_7d += 1
                elif follow_duration.days >= 30:
                    retained_30d += 1
                    retained_7d += 1
                elif follow_duration.days >= 7:
                    retained_7d += 1

        # Calculate rates
        retention_7d = (retained_7d / total_followers) if total_followers > 0 else 0
        retention_30d = (retained_30d / total_followers) if total_followers > 0 else 0
        retention_90d = (retained_90d / total_followers) if total_followers > 0 else 0

        return {
            "7d_retention": round(retention_7d * 100, 2),
            "30d_retention": round(retention_30d * 100, 2),
            "90d_retention": round(retention_90d * 100, 2),
            "total_followers": total_followers,
        }
