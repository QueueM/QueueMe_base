from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.geoapp.models import Location
from apps.shopapp.models import Shop
from apps.storiesapp.models import Story, StoryView


class StoryModelTest(TestCase):
    """Test case for Story model"""

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

        # Create test story
        self.story = Story.objects.create(
            shop=self.shop, story_type="image", media_url="https://example.com/test.jpg"
        )

    def test_story_creation(self):
        """Test story creation"""
        self.assertEqual(Story.objects.count(), 1)
        self.assertEqual(self.story.shop, self.shop)
        self.assertEqual(self.story.story_type, "image")
        self.assertEqual(self.story.media_url, "https://example.com/test.jpg")
        self.assertTrue(self.story.is_active)

        # Test expires_at is set to 24 hours from creation
        time_diff = self.story.expires_at - self.story.created_at
        self.assertAlmostEqual(
            time_diff.total_seconds(), 24 * 3600, delta=60
        )  # Allow 1 min difference

    def test_is_expired_property(self):
        """Test is_expired property"""
        # Not expired initially
        self.assertFalse(self.story.is_expired)

        # Set expires_at to past time
        self.story.expires_at = timezone.now() - timedelta(hours=1)
        self.story.save()

        # Now should be expired
        self.assertTrue(self.story.is_expired)

    def test_time_left_property(self):
        """Test time_left property"""
        # Set expires_at to 1 hour from now
        self.story.expires_at = timezone.now() + timedelta(hours=1)
        self.story.save()

        # Should be approximately 1 hour
        self.assertAlmostEqual(
            self.story.time_left, 3600, delta=60
        )  # Allow 1 min difference


class StoryViewModelTest(TestCase):
    """Test case for StoryView model"""

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

        # Create test story
        self.story = Story.objects.create(
            shop=self.shop, story_type="image", media_url="https://example.com/test.jpg"
        )

        # Create test customer
        self.customer = User.objects.create(
            phone_number="9876543210", user_type="customer"
        )

        # Create story view
        self.story_view = StoryView.objects.create(
            story=self.story, customer=self.customer
        )

    def test_story_view_creation(self):
        """Test story view creation"""
        self.assertEqual(StoryView.objects.count(), 1)
        self.assertEqual(self.story_view.story, self.story)
        self.assertEqual(self.story_view.customer, self.customer)
        self.assertIsNotNone(self.story_view.viewed_at)

    def test_story_view_count(self):
        """Test story view_count property"""
        self.assertEqual(self.story.view_count, 1)

        # Create another customer and view
        another_customer = User.objects.create(
            phone_number="5555555555", user_type="customer"
        )

        StoryView.objects.create(story=self.story, customer=another_customer)

        # View count should now be 2
        self.assertEqual(self.story.view_count, 2)

    def test_unique_constraint(self):
        """Test unique constraint of story and customer"""
        # Trying to create a duplicate view should raise an error
        with self.assertRaises(Exception):
            StoryView.objects.create(story=self.story, customer=self.customer)
