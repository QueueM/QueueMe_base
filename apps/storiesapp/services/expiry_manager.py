from django.db import transaction
from django.utils import timezone

from apps.storiesapp.models import Story
from apps.storiesapp.services.story_service import StoryService


class StoryExpiryManager:
    """
    Service for managing the expiry of stories.
    Stories expire after 24 hours and need to be deactivated.
    """

    @staticmethod
    @transaction.atomic
    def deactivate_expired_stories():
        """
        Deactivate all stories that have expired

        Returns:
            int: Number of stories deactivated
        """
        return StoryService.deactivate_expired_stories()

    @staticmethod
    @transaction.atomic
    def schedule_expiry_task(story):
        """
        Schedule a task to deactivate a story when it expires

        Args:
            story (Story): The story to schedule expiry for
        """
        from apps.storiesapp.tasks import deactivate_story_task

        # Calculate seconds until expiry
        now = timezone.now()
        seconds_until_expiry = max(0, (story.expires_at - now).total_seconds())

        # Schedule task to run at expiry time
        deactivate_story_task.apply_async(args=[str(story.id)], countdown=seconds_until_expiry)

    @staticmethod
    def schedule_all_pending_expirations():
        """
        Schedule expiry tasks for all active stories that haven't expired yet

        Returns:
            int: Number of stories scheduled
        """
        count = 0
        stories = Story.objects.filter(is_active=True, expires_at__gt=timezone.now())

        for story in stories:
            StoryExpiryManager.schedule_expiry_task(story)
            count += 1

        return count

    @staticmethod
    def check_expiry_status(story_id):
        """
        Check if a story has expired and update status if needed

        Args:
            story_id (uuid): ID of the story to check

        Returns:
            bool: True if story expired and was deactivated, False otherwise
        """
        try:
            story = Story.objects.get(id=story_id)

            if story.is_active and story.is_expired:
                # Story has expired, deactivate it
                story.is_active = False
                story.save(update_fields=["is_active"])

                # Send notification about expiry
                StoryService._send_story_expiry_notification(story)

                return True

            return False
        except Story.DoesNotExist:
            return False
