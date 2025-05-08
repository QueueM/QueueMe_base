from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.geoapp.models import Location
from apps.shopapp.models import Shop
from apps.storiesapp.models import Story, StoryView
from apps.storiesapp.services.expiry_manager import StoryExpiryManager
from apps.storiesapp.services.story_feed_generator import StoryFeedGenerator
from apps.storiesapp.services.story_service import StoryService


class StoryServiceTest(TestCase):
    """Test case for StoryService"""

    def setUp(self):
        """Set up test data"""
        # Create company
        self.company = Company.objects.create(
            name="Test Company",
            contact_phone="1234567890",
        )

        # Create location
        self.location = Location.objects.create(
            city="Test City", latitude=0.0, longitude=0.0
        )

        # Create shop
        self.shop = Shop.objects.create(
            company=self.company,
            name="Test Shop",
            phone_number="1234567890",
            location=self.location,
            username="testshop",
        )

        # Create test customer
        self.customer = User.objects.create(
            phone_number="9876543210", user_type="customer"
        )

    @patch("apps.storiesapp.services.story_service.StoryService._notify_followers")
    @patch(
        "apps.storiesapp.services.story_service.StoryService._send_story_websocket_notification"
    )
    def test_create_story(self, mock_send_notification, mock_notify_followers):
        """Test creating a story"""
        # Create a story using the service
        story = StoryService.create_story(
            shop_id=self.shop.id,
            story_type="image",
            media_url="https://example.com/test.jpg",
        )

        # Verify story was created
        self.assertEqual(Story.objects.count(), 1)
        self.assertEqual(story.shop, self.shop)
        self.assertEqual(story.story_type, "image")
        self.assertEqual(story.media_url, "https://example.com/test.jpg")

        # Verify expiry date is set
        self.assertIsNotNone(story.expires_at)
        time_diff = story.expires_at - timezone.now()
        self.assertAlmostEqual(
            time_diff.total_seconds(), 24 * 3600, delta=120
        )  # Allow 2 min difference

        # Verify notification methods were called
        mock_notify_followers.assert_called_once_with(story)
        mock_send_notification.assert_called_once_with(story, "created")

    def test_delete_story(self):
        """Test deleting a story"""
        # Create a story first
        story = Story.objects.create(
            shop=self.shop, story_type="image", media_url="https://example.com/test.jpg"
        )

        # Verify story exists
        self.assertEqual(Story.objects.count(), 1)

        # Mock websocket notification
        with patch(
            "apps.storiesapp.services.story_service.StoryService._send_story_websocket_notification"
        ) as mock:
            # Delete the story
            result = StoryService.delete_story(story.id)

            # Verify story was deleted
            self.assertTrue(result)
            self.assertEqual(Story.objects.count(), 0)

            # Verify notification was called
            mock.assert_called_once_with(story, "deleted")

    def test_mark_viewed(self):
        """Test marking a story as viewed"""
        # Create a story
        story = Story.objects.create(
            shop=self.shop, story_type="image", media_url="https://example.com/test.jpg"
        )

        # No views initially
        self.assertEqual(StoryView.objects.count(), 0)

        # Mark as viewed
        view = StoryService.mark_viewed(story.id, self.customer.id)

        # Verify view was created
        self.assertEqual(StoryView.objects.count(), 1)
        self.assertEqual(view.story, story)
        self.assertEqual(view.customer, self.customer)

        # Marking again should not create a new view
        result = StoryService.mark_viewed(story.id, self.customer.id)
        self.assertIsNone(result)
        self.assertEqual(StoryView.objects.count(), 1)

    def test_get_expired_stories(self):
        """Test getting expired stories"""
        # Create an expired story
        expired_story = Story.objects.create(
            shop=self.shop,
            story_type="image",
            media_url="https://example.com/expired.jpg",
            expires_at=timezone.now() - timedelta(hours=1),
        )

        # Create a non-expired story
        active_story = Story.objects.create(
            shop=self.shop,
            story_type="image",
            media_url="https://example.com/active.jpg",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Get expired stories
        expired_stories = StoryService.get_expired_stories()

        # Verify only expired story is returned
        self.assertEqual(expired_stories.count(), 1)
        self.assertEqual(expired_stories.first(), expired_story)

    @patch(
        "apps.storiesapp.services.story_service.StoryService._send_story_expiry_notification"
    )
    def test_deactivate_expired_stories(self, mock_send_notification):
        """Test deactivating expired stories"""
        # Create expired stories
        expired_story1 = Story.objects.create(
            shop=self.shop,
            story_type="image",
            media_url="https://example.com/expired1.jpg",
            expires_at=timezone.now() - timedelta(hours=1),
        )

        expired_story2 = Story.objects.create(
            shop=self.shop,
            story_type="image",
            media_url="https://example.com/expired2.jpg",
            expires_at=timezone.now() - timedelta(minutes=30),
        )

        # Create a non-expired story
        active_story = Story.objects.create(
            shop=self.shop,
            story_type="image",
            media_url="https://example.com/active.jpg",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Deactivate expired stories
        count = StoryService.deactivate_expired_stories()

        # Verify correct count and stories deactivated
        self.assertEqual(count, 2)
        self.assertEqual(mock_send_notification.call_count, 2)

        # Refresh from DB
        expired_story1.refresh_from_db()
        expired_story2.refresh_from_db()
        active_story.refresh_from_db()

        # Verify status
        self.assertFalse(expired_story1.is_active)
        self.assertFalse(expired_story2.is_active)
        self.assertTrue(active_story.is_active)


class StoryExpiryManagerTest(TestCase):
    """Test case for StoryExpiryManager"""

    def setUp(self):
        """Set up test data"""
        # Create company
        self.company = Company.objects.create(
            name="Test Company",
            contact_phone="1234567890",
        )

        # Create location
        self.location = Location.objects.create(
            city="Test City", latitude=0.0, longitude=0.0
        )

        # Create shop
        self.shop = Shop.objects.create(
            company=self.company,
            name="Test Shop",
            phone_number="1234567890",
            location=self.location,
            username="testshop",
        )

    @patch(
        "apps.storiesapp.services.story_service.StoryService.deactivate_expired_stories"
    )
    def test_deactivate_expired_stories(self, mock_deactivate):
        """Test deactivate_expired_stories delegating to StoryService"""
        mock_deactivate.return_value = 5

        # Call the method
        result = StoryExpiryManager.deactivate_expired_stories()

        # Verify delegation
        mock_deactivate.assert_called_once()
        self.assertEqual(result, 5)

    @patch("apps.storiesapp.tasks.deactivate_story_task.apply_async")
    def test_schedule_expiry_task(self, mock_apply_async):
        """Test scheduling an expiry task"""
        # Create a story
        story = Story.objects.create(
            shop=self.shop,
            story_type="image",
            media_url="https://example.com/test.jpg",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Schedule expiry task
        StoryExpiryManager.schedule_expiry_task(story)

        # Verify task was scheduled
        mock_apply_async.assert_called_once()
        args, kwargs = mock_apply_async.call_args

        # Verify task arguments
        self.assertEqual(kwargs["args"], [str(story.id)])

        # Verify countdown is roughly 1 hour (3600 seconds)
        self.assertLess(abs(kwargs["countdown"] - 3600), 60)  # Allow 1 min difference

    def test_check_expiry_status(self):
        """Test checking expiry status of a story"""
        # Create an expired story
        expired_story = Story.objects.create(
            shop=self.shop,
            story_type="image",
            media_url="https://example.com/expired.jpg",
            expires_at=timezone.now() - timedelta(hours=1),
            is_active=True,
        )

        # Mock the notification function
        with patch(
            "apps.storiesapp.services.story_service.StoryService._send_story_expiry_notification"
        ) as mock:
            # Check expiry status
            result = StoryExpiryManager.check_expiry_status(expired_story.id)

            # Verify story was deactivated
            self.assertTrue(result)

            # Refresh from DB
            expired_story.refresh_from_db()
            self.assertFalse(expired_story.is_active)

            # Verify notification was sent
            mock.assert_called_once_with(expired_story)


class StoryFeedGeneratorTest(TestCase):
    """Test case for StoryFeedGenerator"""

    def setUp(self):
        """Set up test data"""
        # Create company
        self.company = Company.objects.create(
            name="Test Company",
            contact_phone="1234567890",
        )

        # Create location
        self.location = Location.objects.create(
            city="Test City", latitude=0.0, longitude=0.0
        )

        # Create shops
        self.shop1 = Shop.objects.create(
            company=self.company,
            name="Shop 1",
            phone_number="1111111111",
            location=self.location,
            username="shop1",
        )

        self.shop2 = Shop.objects.create(
            company=self.company,
            name="Shop 2",
            phone_number="2222222222",
            location=self.location,
            username="shop2",
        )

        # Create test customer
        self.customer = User.objects.create(
            phone_number="9876543210", user_type="customer"
        )

        # Create stories
        self.story1 = Story.objects.create(
            shop=self.shop1,
            story_type="image",
            media_url="https://example.com/story1.jpg",
        )

        self.story2 = Story.objects.create(
            shop=self.shop2,
            story_type="image",
            media_url="https://example.com/story2.jpg",
        )

        # Mock Follow relationship
        self.patcher = patch(
            "apps.storiesapp.services.story_feed_generator.Follow.objects.filter"
        )
        self.mock_follow_filter = self.patcher.start()

        # Setup mock to return shop1 as followed
        self.mock_follow_filter.return_value.values_list.return_value = [self.shop1.id]

    def tearDown(self):
        self.patcher.stop()

    def test_generate_home_feed(self):
        """Test generating home feed"""
        generator = StoryFeedGenerator()

        # Mock _optimize_feed to return a simple filtered queryset
        with patch.object(
            generator,
            "_optimize_feed",
            return_value=Story.objects.filter(shop=self.shop1),
        ):
            # Generate home feed
            feed = generator.generate_home_feed(self.customer.id)

            # Verify feed contains only story1
            self.assertEqual(feed.count(), 1)
            self.assertEqual(feed.first(), self.story1)

    def test_generate_shop_feed(self):
        """Test generating shop feed"""
        generator = StoryFeedGenerator()

        # Create another story for shop1
        story3 = Story.objects.create(
            shop=self.shop1,
            story_type="video",
            media_url="https://example.com/story3.mp4",
        )

        # Generate shop feed for shop1
        feed = generator.generate_shop_feed(self.shop1.id)

        # Verify feed contains both stories from shop1, ordered by created_at descending
        self.assertEqual(feed.count(), 2)
        self.assertEqual(feed[0], story3)  # Most recent first
        self.assertEqual(feed[1], self.story1)
