from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.storiesapp.models import Story
from apps.storiesapp.services.expiry_manager import StoryExpiryManager


@receiver(post_save, sender=Story)
def story_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for Story post-save
    - Schedule expiry task for new stories
    - Notify followers when a new story is created
    """
    if created:
        # Schedule expiry task
        StoryExpiryManager.schedule_expiry_task(instance)


@receiver(pre_save, sender=Story)
def story_pre_save(sender, instance, **kwargs):
    """
    Signal handler for Story pre-save
    - Ensure expires_at is set for new stories
    """
    if not instance.pk and not instance.expires_at:
        # New story without expires_at set
        instance.expires_at = timezone.now() + timezone.timedelta(hours=24)


@receiver(post_delete, sender=Story)
def story_post_delete(sender, instance, **kwargs):
    """
    Signal handler for Story post-delete
    - Handle cleanup of associated resources
    """
    # Clean up media files if needed
    from core.storage.s3_storage import S3Storage

    s3_storage = S3Storage()

    # Delete main media file
    if instance.media_url:
        s3_storage.delete_file(instance.media_url)

    # Delete thumbnail if exists
    if instance.thumbnail_url:
        s3_storage.delete_file(instance.thumbnail_url)
