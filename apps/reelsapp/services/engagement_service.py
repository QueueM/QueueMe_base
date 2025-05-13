import logging

from django.db.models import F

from apps.notificationsapp.services.notification_service import NotificationService

from ..models import ReelView

logger = logging.getLogger(__name__)


class EngagementService:
    """Service for tracking and managing reel engagement metrics"""

    @staticmethod
    def record_view(
        reel_id,
        user_id=None,
        device_id=None,
        watch_duration=0,
        watched_full=False,
        ip_address=None,
    ):
        """
        Record a view on a reel

        Args:
            reel_id: UUID of the reel
            user_id: UUID of the user viewing the reel (optional)
            device_id: Device identifier for anonymous users (optional)
            watch_duration: Duration of watch in seconds (optional)
            watched_full: Whether the user watched the full reel (optional)
            ip_address: IP address of the viewer (optional)

        Returns:
            ReelView instance
        """
        try:
            # Create view record
            view = ReelView.objects.create(
                reel_id=reel_id,
                user_id=user_id,
                device_id=device_id or "",
                watch_duration=watch_duration,
                watched_full=watched_full,
                ip_address=ip_address,
            )

            return view
        except Exception as e:
            logger.error(f"Error recording reel view: {str(e)}")
            # Continue without raising - viewing should not be disrupted by tracking errors
            return None

    @staticmethod
    def update_engagement_metrics(reel):
        """
        Update calculated engagement metrics for a reel

        Args:
            reel: Reel instance

        Returns:
            Updated Reel instance
        """
        try:
            # Calculate engagement metrics
            likes_count = reel.likes.count()
            comments_count = reel.comments.count()
            shares_count = reel.shares.count()
            views_count = reel.views.count()

            # Calculate engagement rate (likes + comments * 2 + shares * 3) / views
            if views_count > 0:
                engagement_rate = (
                    likes_count + (comments_count * 2) + (shares_count * 3)
                ) / views_count
            else:
                engagement_rate = 0

            # Store metrics in the reel object
            reel.engagement_rate = engagement_rate

            # We could store more metrics here if needed

            return reel
        except Exception as e:
            logger.error(f"Error updating engagement metrics: {str(e)}")
            return reel

    @staticmethod
    def process_engagement_event(reel, user, event_type):
        """
        Process a user engagement event (like, comment, share)

        Args:
            reel: Reel instance being engaged with
            user: User instance performing the engagement
            event_type: Type of engagement ('like', 'comment', 'share')

        Returns:
            None
        """
        # Update user's engagement history/preferences
        try:
            from apps.customersapp.models import CustomerPreference
            from apps.customersapp.services.preference_extractor import PreferenceExtractor

            # Extract categories and add to user preferences
            if hasattr(user, "customer"):
                category_ids = reel.categories.values_list("id", flat=True)
                for category_id in category_ids:
                    # Increment preference weight or create new preference
                    preference, created = CustomerPreference.objects.get_or_create(
                        customer=user.customer,
                        preference_type="category",
                        category_id=category_id,
                        defaults={"weight": 1.0},
                    )

                    if not created:
                        # Increment existing preference
                        preference.weight = F("weight") + 1.0
                        preference.save(update_fields=["weight"])

                # Recalculate normalized preferences
                PreferenceExtractor.normalize_preferences(user.customer)
        except Exception as e:
            logger.error(f"Error updating user preferences: {str(e)}")
            # Continue anyway - this is not critical

        # Check for engagement milestones
        try:
            # Only check milestones for certain event types
            if event_type in ["like", "share"]:
                if event_type == "like":
                    count = reel.likes.count()
                    milestones = [1, 5, 10, 50, 100, 500, 1000]
                else:  # share
                    count = reel.shares.count()
                    milestones = [1, 5, 10, 25, 50, 100]

                # Check if we've reached a milestone
                if count in milestones:
                    # Notify shop owner
                    if reel.shop.manager:
                        NotificationService.send_notification(
                            user_id=reel.shop.manager.id,
                            notification_type="reel_engagement_milestone",
                            data={
                                "reel_title": reel.title,
                                "reel_id": str(reel.id),
                                "metric": event_type,
                                "count": count,
                            },
                            channels=["in_app"],
                        )
        except Exception as e:
            logger.error(f"Error processing engagement milestone: {str(e)}")
            # Continue anyway - notifications are not critical
