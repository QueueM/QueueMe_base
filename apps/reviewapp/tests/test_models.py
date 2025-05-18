import uuid

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.reviewapp.models import (
    PlatformReview,
    ReviewHelpfulness,
    ReviewMedia,
    ReviewMetric,
    ReviewReport,
    ServiceReview,
    ShopReview,
    SpecialistReview,
)
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


class ReviewModelsTestCase(TestCase):
    """Test case for review models"""

    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        # Create company
        self.company = Company.objects.create(
            name="Test Company", contact_phone="9876543210", owner=self.user
        )

        # Create shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            company=self.company,
            phone_number="9876543210",
            username="testshop",
        )

        # Mock specialist (without full dependency chain)
        self.specialist = Specialist.objects.create(id=uuid.uuid4())

        # Mock service (without full dependency chain)
        self.service = Service.objects.create(
            id=uuid.uuid4(),
            name="Test Service",
            shop=self.shop,
            price=100.00,
            duration=60,
        )

    def test_shop_review_creation(self):
        """Test creating a shop review"""
        review = ShopReview.objects.create(
            shop=self.shop,
            user=self.user,
            title="Great Shop",
            rating=5,
            content="This shop is amazing!",
            city="Riyadh",
        )

        self.assertEqual(review.rating, 5)
        self.assertEqual(review.title, "Great Shop")
        self.assertEqual(review.shop, self.shop)
        self.assertEqual(review.user, self.user)
        self.assertEqual(review.status, "approved")  # Default

    def test_specialist_review_creation(self):
        """Test creating a specialist review"""
        review = SpecialistReview.objects.create(
            specialist=self.specialist,
            user=self.user,
            title="Great Specialist",
            rating=4,
            content="This specialist is very professional!",
            city="Riyadh",
        )

        self.assertEqual(review.rating, 4)
        self.assertEqual(review.title, "Great Specialist")
        self.assertEqual(review.specialist, self.specialist)
        self.assertEqual(review.user, self.user)

    def test_service_review_creation(self):
        """Test creating a service review"""
        review = ServiceReview.objects.create(
            service=self.service,
            user=self.user,
            title="Excellent Service",
            rating=5,
            content="This service exceeded my expectations!",
            city="Riyadh",
        )

        self.assertEqual(review.rating, 5)
        self.assertEqual(review.title, "Excellent Service")
        self.assertEqual(review.service, self.service)
        self.assertEqual(review.user, self.user)

    def test_platform_review_creation(self):
        """Test creating a platform review"""
        review = PlatformReview.objects.create(
            company=self.company,
            user=self.user,
            title="Great Platform",
            rating=4,
            content="The Queue Me platform is easy to use!",
            category="usability",
        )

        self.assertEqual(review.rating, 4)
        self.assertEqual(review.title, "Great Platform")
        self.assertEqual(review.company, self.company)
        self.assertEqual(review.user, self.user)
        self.assertEqual(review.category, "usability")

    def test_review_media_creation(self):
        """Test creating review media attachments"""
        # Create a review first
        review = ShopReview.objects.create(
            shop=self.shop,
            user=self.user,
            title="Great Shop",
            rating=5,
            content="This shop is amazing!",
        )

        # Get content type
        content_type = ContentType.objects.get_for_model(review)

        # Create media attachment
        media = ReviewMedia.objects.create(
            content_type=content_type,
            object_id=review.id,
            media_type="image",
            media_file="reviews/media/test.jpg",
        )

        self.assertEqual(media.media_type, "image")
        self.assertEqual(media.content_type, content_type)
        self.assertEqual(str(media.object_id), str(review.id))

    def test_review_helpfulness(self):
        """Test marking a review as helpful"""
        # Create a review first
        review = ShopReview.objects.create(
            shop=self.shop,
            user=self.user,
            title="Great Shop",
            rating=5,
            content="This shop is amazing!",
        )

        # Create another user
        other_user = User.objects.create(phone_number="5555555555", user_type="customer")

        # Get content type
        content_type = ContentType.objects.get_for_model(review)

        # Mark as helpful
        helpfulness = ReviewHelpfulness.objects.create(
            content_type=content_type,
            object_id=review.id,
            user=other_user,
            is_helpful=True,
        )

        self.assertTrue(helpfulness.is_helpful)
        self.assertEqual(helpfulness.user, other_user)
        self.assertEqual(helpfulness.content_type, content_type)
        self.assertEqual(str(helpfulness.object_id), str(review.id))

    def test_review_report(self):
        """Test reporting a review"""
        # Create a review first
        review = ShopReview.objects.create(
            shop=self.shop,
            user=self.user,
            title="Great Shop",
            rating=5,
            content="This shop is amazing!",
        )

        # Create another user
        reporter = User.objects.create(phone_number="5555555555", user_type="customer")

        # Get content type
        content_type = ContentType.objects.get_for_model(review)

        # Report the review
        report = ReviewReport.objects.create(
            content_type=content_type,
            object_id=review.id,
            reporter=reporter,
            reason="inappropriate",
            details="This review contains inappropriate content",
        )

        self.assertEqual(report.reason, "inappropriate")
        self.assertEqual(report.reporter, reporter)
        self.assertEqual(report.status, "pending")  # Default
        self.assertEqual(report.content_type, content_type)
        self.assertEqual(str(report.object_id), str(review.id))

    def test_review_metric(self):
        """Test review metrics"""
        # Get content type for shop
        content_type = ContentType.objects.get_for_model(self.shop)

        # Create metrics
        metrics = ReviewMetric.objects.create(
            content_type=content_type,
            object_id=self.shop.id,
            avg_rating=4.5,
            weighted_rating=4.2,
            review_count=10,
            rating_distribution={"1": 0, "2": 1, "3": 2, "4": 3, "5": 4},
            last_reviewed_at=timezone.now(),
        )

        self.assertEqual(metrics.avg_rating, 4.5)
        self.assertEqual(metrics.weighted_rating, 4.2)
        self.assertEqual(metrics.review_count, 10)
        self.assertEqual(metrics.rating_distribution, {"1": 0, "2": 1, "3": 2, "4": 3, "5": 4})
        self.assertEqual(metrics.content_type, content_type)
        self.assertEqual(str(metrics.object_id), str(self.shop.id))
