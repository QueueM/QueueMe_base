import os
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.companiesapp.models import Company
from apps.rolesapp.models import Permission, Role, UserRole
from apps.shopapp.models import Shop

from ..models import Reel, ReelComment, ReelLike, ReelReport, ReelShare

User = get_user_model()


class ReelViewSetTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Create users
        cls.customer = User.objects.create_user(
            phone_number="1234567890", user_type="customer", password="testpassword"
        )

        cls.shop_manager = User.objects.create_user(
            phone_number="9876543210", user_type="employee", password="testpassword"
        )

        # Create a company
        cls.company = Company.objects.create(
            name="Test Company", contact_phone="5556667777", owner=cls.customer
        )

        # Create a shop
        cls.shop = Shop.objects.create(
            company=cls.company,
            name="Test Shop",
            phone_number="5556667777",
            username="testshop",
            manager=cls.shop_manager,
        )

        # Create permissions
        cls.view_permission = Permission.objects.create(resource="reel", action="view")

        cls.add_permission = Permission.objects.create(resource="reel", action="add")

        cls.edit_permission = Permission.objects.create(resource="reel", action="edit")

        cls.delete_permission = Permission.objects.create(resource="reel", action="delete")

        # Create role for shop manager
        cls.manager_role = Role.objects.create(
            name="Shop Manager", role_type="shop_manager", shop=cls.shop
        )

        # Add permissions to role
        cls.manager_role.permissions.add(
            cls.view_permission,
            cls.add_permission,
            cls.edit_permission,
            cls.delete_permission,
        )

        # Assign role to shop manager
        UserRole.objects.create(user=cls.shop_manager, role=cls.manager_role)

        # Create a reel
        cls.reel = Reel.objects.create(
            shop=cls.shop,
            title="Test Reel",
            caption="This is a test reel",
            status="published",
            city="Riyadh",
        )

    def setUp(self):
        self.client = APIClient()

    def test_shop_manager_can_view_reels(self):
        """Test that shop manager can view reels"""
        # Authenticate as shop manager
        self.client.force_authenticate(user=self.shop_manager)

        # Get reels list
        url = reverse("shop-reels-list", kwargs={"shop_id": self.shop.id})
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "Test Reel")

    @patch("apps.reelsapp.views.ReelService.process_reel_video")
    def test_shop_manager_can_create_reel(self, mock_process_video):
        """Test that shop manager can create a reel"""
        # Authenticate as shop manager
        self.client.force_authenticate(user=self.shop_manager)

        # Create a test video file
        video_file_path = os.path.join(tempfile.gettempdir(), "test_video.mp4")
        with open(video_file_path, "wb") as f:
            f.write(b"fake video content")

        # Prepare data
        with open(video_file_path, "rb") as f:
            data = {
                "title": "New Reel",
                "caption": "This is a new reel",
                "video": f,
                "status": "draft",
            }

            # Create reel
            url = reverse("shop-reels-list", kwargs={"shop_id": self.shop.id})
            response = self.client.post(url, data, format="multipart")

        # Clean up temp file
        os.remove(video_file_path)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "New Reel")

        # Check that video processing was called
        mock_process_video.assert_called_once()

    def test_shop_manager_can_update_reel(self):
        """Test that shop manager can update a reel"""
        # Authenticate as shop manager
        self.client.force_authenticate(user=self.shop_manager)

        # Update reel
        url = reverse("shop-reels-detail", kwargs={"shop_id": self.shop.id, "pk": self.reel.id})
        data = {"title": "Updated Reel", "caption": "This reel has been updated"}
        response = self.client.patch(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Reel")

        # Verify in database
        self.reel.refresh_from_db()
        self.assertEqual(self.reel.title, "Updated Reel")

    def test_shop_manager_can_publish_reel(self):
        """Test that shop manager can publish a reel"""
        # Create a draft reel with a linked service
        draft_reel = Reel.objects.create(
            shop=self.shop,
            title="Draft Reel",
            caption="This is a draft reel",
            status="draft",
        )

        # Add a service to the reel
        from apps.serviceapp.models import Service

        service = Service.objects.create(
            shop=self.shop, name="Test Service", price=100.00, duration=60
        )
        draft_reel.services.add(service)

        # Authenticate as shop manager
        self.client.force_authenticate(user=self.shop_manager)

        # Publish reel
        url = reverse("shop-reels-publish", kwargs={"shop_id": self.shop.id, "pk": draft_reel.id})
        response = self.client.post(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "published")

        # Verify in database
        draft_reel.refresh_from_db()
        self.assertEqual(draft_reel.status, "published")
        self.assertIsNotNone(draft_reel.published_at)

    def test_customer_can_view_feed(self):
        """Test that customer can view the reel feed"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Get feed
        url = reverse("customer-reels-feed")
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_customer_can_like_reel(self):
        """Test that customer can like a reel"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Like reel
        url = reverse("customer-reels-like", kwargs={"pk": self.reel.id})
        response = self.client.post(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify in database
        self.assertTrue(ReelLike.objects.filter(reel=self.reel, user=self.customer).exists())

    def test_customer_can_comment_on_reel(self):
        """Test that customer can comment on a reel"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Comment on reel
        url = reverse("customer-reels-comment", kwargs={"pk": self.reel.id})
        data = {"content": "Great reel!"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["content"], "Great reel!")

        # Verify in database
        self.assertTrue(
            ReelComment.objects.filter(
                reel=self.reel, user=self.customer, content="Great reel!"
            ).exists()
        )

    def test_customer_can_share_reel(self):
        """Test that customer can share a reel"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Share reel
        url = reverse("customer-reels-share", kwargs={"pk": self.reel.id})
        data = {"share_type": "whatsapp"}
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["share_type"], "whatsapp")

        # Verify in database
        self.assertTrue(
            ReelShare.objects.filter(
                reel=self.reel, user=self.customer, share_type="whatsapp"
            ).exists()
        )

    def test_customer_can_report_reel(self):
        """Test that customer can report a reel"""
        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Report reel
        url = reverse("customer-reels-report", kwargs={"pk": self.reel.id})
        data = {
            "reason": "inappropriate",
            "description": "This reel contains inappropriate content",
        }
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["reason"], "inappropriate")

        # Verify in database
        self.assertTrue(
            ReelReport.objects.filter(
                reel=self.reel, user=self.customer, reason="inappropriate"
            ).exists()
        )

    def test_city_based_visibility(self):
        """Test that reels are filtered by city"""
        # Create a reel in a different city
        other_reel = Reel.objects.create(
            shop=self.shop,
            title="Jeddah Reel",
            caption="This is a reel in Jeddah",
            status="published",
            city="Jeddah",
        )

        # Authenticate as customer
        self.client.force_authenticate(user=self.customer)

        # Get feed filtered by Riyadh
        url = reverse("customer-reels-feed")
        response = self.client.get(f"{url}?city=Riyadh")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should include Riyadh reel but not Jeddah reel
        reel_ids = [reel["id"] for reel in response.data["results"]]
        self.assertIn(str(self.reel.id), reel_ids)
        self.assertNotIn(str(other_reel.id), reel_ids)

        # Get feed filtered by Jeddah
        response = self.client.get(f"{url}?city=Jeddah")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should include Jeddah reel but not Riyadh reel
        reel_ids = [reel["id"] for reel in response.data["results"]]
        self.assertNotIn(str(self.reel.id), reel_ids)
        self.assertIn(str(other_reel.id), reel_ids)
