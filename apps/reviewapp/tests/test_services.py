import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.reviewapp.models import ServiceReview, ShopReview, SpecialistReview
from apps.reviewapp.services.rating_service import RatingService
from apps.reviewapp.services.review_service import ReviewService
from apps.reviewapp.services.review_validator import ReviewValidator
from apps.reviewapp.services.sentiment_analyzer import SentimentAnalyzer
from apps.reviewapp.services.weighted_rating import WeightedRatingCalculator
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


class ReviewServicesTestCase(TestCase):
    """Test case for review services"""

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

        # Create some reviews
        self.shop_review = ShopReview.objects.create(
            shop=self.shop,
            user=self.user,
            title="Great Shop",
            rating=5,
            content="This shop is amazing!",
            city="Riyadh",
        )

        self.specialist_review = SpecialistReview.objects.create(
            specialist=self.specialist,
            user=self.user,
            title="Great Specialist",
            rating=4,
            content="This specialist is very professional!",
            city="Riyadh",
        )

        self.service_review = ServiceReview.objects.create(
            service=self.service,
            user=self.user,
            title="Excellent Service",
            rating=5,
            content="This service exceeded my expectations!",
            city="Riyadh",
        )

    def test_rating_service_update_metrics(self):
        """Test updating review metrics"""
        # Update metrics for shop
        metrics = RatingService.update_entity_metrics("shopapp.Shop", self.shop.id)

        # Check that metrics were created
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.review_count, 1)
        self.assertEqual(metrics.avg_rating, 5.0)

        # Create another review with different rating
        ShopReview.objects.create(
            shop=self.shop,
            user=User.objects.create(phone_number="9999999999"),
            title="Good Shop",
            rating=3,
            content="This shop is good but could be better",
            city="Riyadh",
        )

        # Update metrics again
        metrics = RatingService.update_entity_metrics("shopapp.Shop", self.shop.id)

        # Check that metrics were updated
        self.assertEqual(metrics.review_count, 2)
        self.assertEqual(metrics.avg_rating, 4.0)  # (5 + 3) / 2 = 4.0

    def test_weighted_rating_calculator(self):
        """Test weighted rating algorithms"""
        # Create multiple reviews with different ratings
        user2 = User.objects.create(phone_number="9999999999")
        user3 = User.objects.create(phone_number="8888888888")

        ShopReview.objects.create(
            shop=self.shop,
            user=user2,
            title="Good Shop",
            rating=3,
            content="This shop is good but could be better",
            city="Riyadh",
        )

        ShopReview.objects.create(
            shop=self.shop,
            user=user3,
            title="Ok Shop",
            rating=2,
            content="This shop was below average",
            city="Riyadh",
        )

        # Get all reviews
        reviews = ShopReview.objects.filter(shop=self.shop)

        # Test Bayesian average
        bayesian_avg = WeightedRatingCalculator.calculate_bayesian_average(reviews)

        # With 3 reviews (5, 3, 2) and prior of 3.5 with weight 5, expect:
        # (5 + 3 + 2 + 3.5*5) / (3 + 5) = 3.31
        self.assertAlmostEqual(bayesian_avg, 3.31, places=2)

        # Test IMDb weighted rating
        imdb_weighted = WeightedRatingCalculator.calculate_imdb_weighted_rating(reviews)

        # With 3 reviews (5, 3, 2) = avg 3.33, count 3, min_votes 10, global_avg 3.5:
        # (3 / (3 + 10)) * 3.33 + (10 / (3 + 10)) * 3.5 = 3.46
        self.assertAlmostEqual(imdb_weighted, 3.46, places=2)

        # Test recency weighted rating (can't test exact value due to time dependency)
        recency_weighted = WeightedRatingCalculator.calculate_recency_weighted_rating(
            reviews
        )

        # Should be between min and max rating
        self.assertGreaterEqual(recency_weighted, 2.0)
        self.assertLessEqual(recency_weighted, 5.0)

    def test_sentiment_analyzer(self):
        """Test sentiment analysis"""
        # Positive text
        positive_text = "This shop is amazing! The service was excellent and I had a great experience."
        positive_score = SentimentAnalyzer.analyze_text(positive_text)

        # Should be positive (above 0)
        self.assertGreater(positive_score, 0)

        # Negative text
        negative_text = "Terrible experience. The service was poor and I would not recommend this place."
        negative_score = SentimentAnalyzer.analyze_text(negative_text)

        # Should be negative (below 0)
        self.assertLess(negative_score, 0)

        # Neutral text
        neutral_text = "I visited the shop yesterday. They offer various services."
        neutral_score = SentimentAnalyzer.analyze_text(neutral_text)

        # Should be close to neutral
        self.assertAlmostEqual(neutral_score, 0, delta=0.3)

    def test_review_validator(self):
        """Test review validation"""
        # Valid review data
        valid_data = {
            "title": "Great Experience",
            "rating": 5,
            "content": "I had an amazing time at this shop. Highly recommended!",
        }

        # Should not raise exception
        try:
            ReviewValidator.validate_review_data(valid_data)
            validation_passed = True
        except Exception:
            validation_passed = False

        self.assertTrue(validation_passed)

        # Invalid data - missing title
        invalid_data = {"rating": 5, "content": "Great experience"}

        with self.assertRaises(Exception):
            ReviewValidator.validate_review_data(invalid_data)

        # Invalid data - rating out of range
        invalid_data = {"title": "Test", "rating": 6, "content": "Great experience"}

        with self.assertRaises(Exception):
            ReviewValidator.validate_review_data(invalid_data)

        # Test spam detection
        spam_text = "BUY NOW!!! AMAZING DEAL!!! CLICK HERE!!! http://example.com http://spam.com"
        self.assertTrue(ReviewValidator.is_potential_spam(spam_text))

        normal_text = (
            "I had a good experience at the shop yesterday. The service was nice."
        )
        self.assertFalse(ReviewValidator.is_potential_spam(normal_text))

    def test_review_service(self):
        """Test review service"""
        # Create a test image
        image = SimpleUploadedFile(
            "test_image.jpg", b"file_content", content_type="image/jpeg"
        )

        # Test moderating a review
        moderator = User.objects.create(phone_number="7777777777")

        updated_review = ReviewService.moderate_review(
            self.shop_review,
            status="rejected",
            moderator=moderator,
            comment="Contains inappropriate content",
        )

        self.assertEqual(updated_review.status, "rejected")
        self.assertEqual(updated_review.moderated_by, moderator)
        self.assertEqual(
            updated_review.moderation_comment, "Contains inappropriate content"
        )

        # Test marking review as helpful
        helper = User.objects.create(phone_number="6666666666")

        helpfulness = ReviewService.mark_review_helpful(
            self.service_review, user=helper, is_helpful=True
        )

        self.assertTrue(helpfulness.is_helpful)
        self.assertEqual(helpfulness.user, helper)

        # Test reporting a review
        reporter = User.objects.create(phone_number="5555555555")

        report = ReviewService.report_review(
            self.specialist_review,
            user=reporter,
            reason="inappropriate",
            details="This review is inappropriate",
        )

        self.assertEqual(report.reason, "inappropriate")
        self.assertEqual(report.reporter, reporter)
        self.assertEqual(report.status, "pending")
