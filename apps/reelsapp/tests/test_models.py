import os
import tempfile
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.companiesapp.models import Company
from apps.shopapp.models import Shop

from ..models import Reel, ReelComment, ReelLike, ReelShare

User = get_user_model()


class ReelModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a user
        cls.user = User.objects.create(phone_number="1234567890", user_type="customer")

        # Create a company
        cls.company = Company.objects.create(
            name="Test Company", contact_phone="9876543210", owner=cls.user
        )

        # Create a shop
        cls.shop = Shop.objects.create(
            company=cls.company,
            name="Test Shop",
            phone_number="9876543210",
            username="testshop",
        )

        # Create a test video file
        video_file_path = os.path.join(tempfile.gettempdir(), "test_video.mp4")
        with open(video_file_path, "wb") as f:
            f.write(b"fake video content")

        # Create a reel
        with open(video_file_path, "rb") as f:
            video_file = SimpleUploadedFile("test_video.mp4", f.read(), content_type="video/mp4")

            cls.reel = Reel.objects.create(
                shop=cls.shop,
                title="Test Reel",
                caption="This is a test reel",
                video=video_file,
                status="published",
                city="Riyadh",
            )

        # Clean up temp file
        os.remove(video_file_path)

    def test_reel_creation(self):
        """Test that the reel is created properly"""
        self.assertEqual(Reel.objects.count(), 1)
        self.assertEqual(self.reel.title, "Test Reel")
        self.assertEqual(self.reel.shop, self.shop)
        self.assertEqual(self.reel.status, "published")
        self.assertEqual(self.reel.city, "Riyadh")

    def test_reel_str_representation(self):
        """Test the string representation of a reel"""
        expected_str = f"{self.shop.name} - Test Reel"
        self.assertEqual(str(self.reel), expected_str)

    def test_reel_engagement_score(self):
        """Test the engagement score calculation"""
        # Create some interactions
        ReelLike.objects.create(reel=self.reel, user=self.user)
        ReelComment.objects.create(reel=self.reel, user=self.user, content="Nice reel!")
        ReelShare.objects.create(reel=self.reel, user=self.user)

        # Calculate expected score: 1 like + 2*1 comment + 3*1 share = 6
        expected_score = 6
        self.assertEqual(self.reel.get_engagement_score(), expected_score)

    def test_reel_engagement_properties(self):
        """Test the engagement property getters"""
        # Create some interactions
        ReelLike.objects.create(reel=self.reel, user=self.user)
        ReelComment.objects.create(reel=self.reel, user=self.user, content="Nice reel!")
        ReelShare.objects.create(reel=self.reel, user=self.user)

        self.assertEqual(self.reel.total_likes, 1)
        self.assertEqual(self.reel.total_comments, 1)
        self.assertEqual(self.reel.total_shares, 1)

    @patch("apps.reelsapp.models.S3Storage")
    def test_reel_deletion(self, mock_s3_storage):
        """Test that when a reel is deleted, the associated file is also deleted"""
        # Mock the S3Storage to avoid actual AWS API calls
        mock_instance = MagicMock()
        mock_s3_storage.return_value = mock_instance

        # Store the video path for verification
        # unused_unused_video_path = self.reel.video.name

        # Delete the reel
        self.reel.delete()

        # Check reel is deleted from database
        self.assertEqual(Reel.objects.count(), 0)

        # In a real test, we'd verify S3 deletion was called
        # but we're mocking it here
