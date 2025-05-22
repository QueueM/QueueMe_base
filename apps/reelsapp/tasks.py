from datetime import timedelta

from celery import shared_task
from django.db.models import Count, F, Q
from django.utils import timezone

from .models import Reel, ReelView

# Import removed from here to prevent circular import


@shared_task
def process_reel_video(reel_id):
    """
    Process a reel's video to extract duration, generate thumbnail,
    and optimize for streaming.
    """
    # Import inside function to avoid circular imports
    from .models import Reel
    from .services.reel_service import ReelService

    try:
        reel = Reel.objects.get(id=reel_id)
        ReelService.process_reel_video(reel)
    except Reel.DoesNotExist:
        # Log error
        pass
    except Exception:  # Removed unused variable 'e' - fix for F841
        # Log error
        pass


@shared_task
def update_trending_reels():
    """
    Identify trending reels based on engagement metrics
    and update the 'is_featured' flag.
    """
    # Get the most engaged reels in the last 3 days
    three_days_ago = timezone.now() - timedelta(days=3)

    # Calculate engagement score for recent reels
    recent_reels = (
        Reel.objects.filter(status="published", created_at__gte=three_days_ago)
        .annotate(
            recent_views=Count(
                "views", filter=Q(views__created_at__gte=three_days_ago)
            ),
            recent_likes=Count(
                "likes", filter=Q(likes__created_at__gte=three_days_ago)
            ),
            recent_comments=Count(
                "comments", filter=Q(comments__created_at__gte=three_days_ago)
            ),
            recent_shares=Count(
                "shares", filter=Q(shares__created_at__gte=three_days_ago)
            ),
            engagement_score=(
                F("recent_views") * 1
                + F("recent_likes") * 2
                + F("recent_comments") * 3
                + F("recent_shares") * 4
            ),
        )
        .order_by("-engagement_score")
    )

    # Get top 5% or at least 10 trending reels
    num_trending = max(int(Reel.objects.filter(status="published").count() * 0.05), 10)
    trending_reels = recent_reels[:num_trending]

    # Reset all featured flags
    Reel.objects.filter(is_featured=True).update(is_featured=False)

    # Set featured flag for trending reels
    trending_ids = trending_reels.values_list("id", flat=True)
    Reel.objects.filter(id__in=trending_ids).update(is_featured=True)


@shared_task
def clean_view_records():
    """
    Aggregate and clean up old view records.
    This preserves the analytics data while reducing database size.
    """
    # Get date threshold (views older than 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)

    # Get old views grouped by reel and date
    old_views = ReelView.objects.filter(created_at__lt=thirty_days_ago)

    # For each reel, count views and delete individual records
    from django.db import connection

    with connection.cursor() as cursor:
        # This is a simplified approach - in production would need more sophisticated aggregation
        cursor.execute(
            """
            INSERT INTO reelsapp_daily_view_aggregate (reel_id, view_date, view_count)
            SELECT reel_id, DATE(created_at), COUNT(*)
            FROM reelsapp_reelview
            WHERE created_at < %s
            GROUP BY reel_id, DATE(created_at)
        """,
            [thirty_days_ago],
        )

    # Delete the old individual view records
    old_views.delete()


@shared_task
def remove_old_draft_reels():
    """
    Remove draft reels that are older than 30 days and have not been published.
    """
    thirty_days_ago = timezone.now() - timedelta(days=30)

    # Find old draft reels
    old_drafts = Reel.objects.filter(status="draft", created_at__lt=thirty_days_ago)

    # Delete them (which will cascade to related objects)
    old_drafts.delete()
