import uuid

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.reviewapp.models import ReviewHelpfulness, ReviewReport, ShopReview, SpecialistReview
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop
from apps.specialistsapp.models import Specialist


class ReviewViewsTestCase(TestCase):
    """Test case for review API views"""

    def setUp(self):
        """Set up test data"""
        # Create API client
        self.client = APIClient()

        # Create users
        self.user = User.objects.create(phone_number="1234567890", user_type="customer")

        self.admin_user = User.objects.create(
            phone_number="9999999999", user_type="admin", is_staff=True
        )

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

        # Create reviews
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

        # Mock authentication mechanism
        # This is simplified - in a real app, you'd use proper auth tokens
        self.client.force_authenticate(user=self.user)

    def test_list_shop_reviews(self):
        """Test listing shop reviews"""
        url = reverse("shopreview-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

    def test_create_shop_review(self):
        """Test creating a shop review"""
        url = reverse("shopreview-list")

        # Create another user
        user2 = User.objects.create(phone_number="5555555555", user_type="customer")

        # Force authenticate as this user
        self.client.force_authenticate(user=user2)

        data = {
            "shop_id": str(self.shop.id),
            "title": "Good Experience",
            "rating": 4,
            "content": "I had a good experience at this shop.",
            "city": "Jeddah",
        }

        # Note: In a real app, this would fail without a booking
        # We're bypassing the eligibility check for testing
        from apps.reviewapp.services.review_validator import ReviewValidator

        original_has_used_entity = ReviewValidator.has_used_entity

        # Mock the has_used_entity method to always return True for testing
        ReviewValidator.has_used_entity = lambda *args, **kwargs: True

        response = self.client.post(url, data, format="json")

        # Restore original method
        ReviewValidator.has_used_entity = original_has_used_entity

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Good Experience")
        self.assertEqual(response.data["rating"], 4)

    def test_get_shop_review_detail(self):
        """Test getting shop review detail"""
        url = reverse("shopreview-detail", args=[self.shop_review.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Great Shop")
        self.assertEqual(response.data["rating"], 5)

    def test_mark_review_helpful(self):
        """Test marking a review as helpful"""
        # Create another user
        user2 = User.objects.create(phone_number="5555555555", user_type="customer")

        # Force authenticate as this user
        self.client.force_authenticate(user=user2)

        url = reverse("shopreview-helpful", args=[self.shop_review.id])
        response = self.client.post(url, {"is_helpful": True}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

        # Check that helpfulness record was created
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(ShopReview)

        helpfulness = ReviewHelpfulness.objects.filter(
            content_type=content_type, object_id=self.shop_review.id, user=user2
        ).first()

        self.assertIsNotNone(helpfulness)
        self.assertTrue(helpfulness.is_helpful)

    def test_report_review(self):
        """Test reporting a review"""
        # Create another user
        user2 = User.objects.create(phone_number="5555555555", user_type="customer")

        # Force authenticate as this user
        self.client.force_authenticate(user=user2)

        url = reverse("shopreview-report", args=[self.shop_review.id])
        data = {
            "reason": "inappropriate",
            "details": "This review contains inappropriate content",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "report submitted")

        # Check that report record was created
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(ShopReview)

        report = ReviewReport.objects.filter(
            content_type=content_type, object_id=self.shop_review.id, reporter=user2
        ).first()

        self.assertIsNotNone(report)
        self.assertEqual(report.reason, "inappropriate")

    def test_moderate_review(self):
        """Test moderating a review"""
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # First mock the permission check
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        original_has_permission = PermissionResolver.has_permission

        # Mock to always return True for admin
        PermissionResolver.has_permission = lambda *args, **kwargs: True

        url = reverse("shopreview-moderate", args=[self.shop_review.id])
        data = {"status": "rejected", "comment": "Contains inappropriate content"}

        response = self.client.post(url, data, format="json")

        # Restore original method
        PermissionResolver.has_permission = original_has_permission

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "review moderated")

        # Check that review was updated
        updated_review = ShopReview.objects.get(id=self.shop_review.id)
        self.assertEqual(updated_review.status, "rejected")
        self.assertEqual(updated_review.moderation_comment, "Contains inappropriate content")

    def test_get_entity_metrics(self):
        """Test getting metrics for an entity"""
        # First create metrics
        from apps.reviewapp.services.rating_service import RatingService

        RatingService.update_entity_metrics("shopapp.Shop", self.shop.id)

        url = reverse("reviewmetric-entity")
        response = self.client.get(
            url, {"entity_type": "shopapp.shop", "entity_id": str(self.shop.id)}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["review_count"], 1)
        self.assertEqual(float(response.data["avg_rating"]), 5.0)
