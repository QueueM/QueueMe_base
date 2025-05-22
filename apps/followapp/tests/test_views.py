from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.companiesapp.models import Company
from apps.followapp.models import Follow, FollowStats
from apps.shopapp.models import Shop

User = get_user_model()


class FollowViewSetTestCase(APITestCase):
    def setUp(self):
        # Create test users
        self.customer = User.objects.create(
            phone_number="1234567890", user_type="customer"
        )

        self.company_owner = User.objects.create(
            phone_number="9876543210", user_type="admin"
        )

        # Create test company and shop
        self.company = Company.objects.create(
            name="Test Company", owner=self.company_owner, contact_phone="9876543210"
        )

        self.shop = Shop.objects.create(
            company=self.company,
            name="Test Shop",
            phone_number="9876543210",
            username="testshop",
        )

        # Create follow stats for the shop
        self.follow_stats = FollowStats.objects.get(shop=self.shop)
        self.follow_stats.follower_count = 10
        self.follow_stats.save()

        # Authenticate the customer
        self.client.force_authenticate(user=self.customer)

    def test_follow_shop(self):
        """Test following a shop"""
        url = reverse("followapp:follow-list")
        data = {"shop": self.shop.id}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Follow.objects.count(), 1)

        follow = Follow.objects.first()
        self.assertEqual(follow.customer, self.customer)
        self.assertEqual(follow.shop, self.shop)

    def test_list_following(self):
        """Test listing shops the user follows"""
        # Create a follow relationship
        # unused_unused_follow = Follow.objects.create(customer=self.customer, shop=self.shop)

        url = reverse("followapp:follow-following")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["shop"], str(self.shop.id))

    def test_toggle_follow(self):
        """Test toggling follow status"""
        url = reverse("followapp:follow-toggle")
        data = {"shop_id": self.shop.id}

        # Test following
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_following"])
        self.assertEqual(Follow.objects.count(), 1)

        # Test unfollowing
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_following"])
        self.assertEqual(Follow.objects.count(), 0)

    def test_check_follow_status(self):
        """Test checking follow status for a shop"""
        url = reverse("followapp:follow-status")

        # Test without following
        response = self.client.get(f"{url}?shop_id={self.shop.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_following"])
        self.assertEqual(response.data["follower_count"], 10)

        # Create a follow relationship
        Follow.objects.create(customer=self.customer, shop=self.shop)

        # Test with following
        response = self.client.get(f"{url}?shop_id={self.shop.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_following"])
        self.assertEqual(response.data["follower_count"], 10)

    def test_get_most_followed_shops(self):
        """Test getting most followed shops"""
        url = reverse(
            "followapp:shop-followers-most-followed", kwargs={"shop_id": self.shop.id}
        )

        # Create another shop with more followers
        shop2 = Shop.objects.create(
            company=self.company,
            name="More Popular Shop",
            phone_number="5555555555",
            username="popularshop",
        )

        # Update follow stats
        stats2 = FollowStats.objects.get(shop=shop2)
        stats2.follower_count = 20
        stats2.save()

        # Authenticate as shop owner to access the endpoint
        self.client.force_authenticate(user=self.company_owner)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)

        # First shop should be the more popular one
        self.assertEqual(response.data[0]["name"], "More Popular Shop")
        self.assertEqual(response.data[0]["follower_count"], 20)
