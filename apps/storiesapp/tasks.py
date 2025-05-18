from celery import shared_task
from django.utils import timezone

from apps.storiesapp.services.expiry_manager import StoryExpiryManager


@shared_task
def deactivate_expired_stories_task():
    """
    Celery task to deactivate all expired stories
    """
    count = StoryExpiryManager.deactivate_expired_stories()
    return f"Deactivated {count} expired stories"


@shared_task
def deactivate_story_task(story_id):
    """
    Celery task to deactivate a specific story
    """
    result = StoryExpiryManager.check_expiry_status(story_id)
    return f"Story {story_id} expired status: {result}"


@shared_task
def schedule_pending_expirations_task():
    """
    Celery task to schedule expiry tasks for all pending stories
    """
    count = StoryExpiryManager.schedule_all_pending_expirations()
    return f"Scheduled expiry for {count} stories"


@shared_task
def cleanup_old_stories_task(days=7):
    """
    Celery task to permanently delete very old stories (default: 7 days)
    """
    cutoff_date = timezone.now() - timezone.timedelta(days=days)

    from apps.storiesapp.models import Story

    # Only delete stories that are already inactive and expired
    result = Story.objects.filter(is_active=False, expires_at__lt=cutoff_date).delete()

    count = result[0] if isinstance(result, tuple) and len(result) > 0 else 0
    return f"Deleted {count} old stories"
