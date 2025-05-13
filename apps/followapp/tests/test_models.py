from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.companiesapp.models import Company
from apps.followapp.models import Follow, FollowEvent, FollowStats
from apps.shopapp.models import Shop

User = get_user_model()


class FollowModelTestCase(TestCase):
    def setUp(self):
        # Create test users
        self.customer = User.objects.create(phone_number="1234567890", user_type="customer")

        self.company_owner = User.objects.create(phone_number="9876543210", user_type="admin")

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

    def test_follow_creation(self):
        """Test creating a follow relationship"""
        follow = Follow.objects.create(customer=self.customer, shop=self.shop)

        self.assertEqual(follow.customer, self.customer)
        self.assertEqual(follow.shop, self.shop)
        self.assertTrue(follow.notification_preference)

        # Test string representation
        self.assertEqual(str(follow), f"{self.customer.phone_number} → {self.shop.name}")

    def test_unique_constraint(self):
        """Test that a customer can't follow the same shop twice"""
        Follow.objects.create(customer=self.customer, shop=self.shop)

        # Attempting to create a duplicate follow should raise an error
        with self.assertRaises(Exception):
            Follow.objects.create(customer=self.customer, shop=self.shop)

    def test_follow_stats_creation(self):
        """Test creating follow statistics"""
        stats = FollowStats.objects.create(
            shop=self.shop, follower_count=100, weekly_growth=10, monthly_growth=25
        )

        self.assertEqual(stats.shop, self.shop)
        self.assertEqual(stats.follower_count, 100)
        self.assertEqual(stats.weekly_growth, 10)
        self.assertEqual(stats.monthly_growth, 25)

        # Test string representation
        self.assertEqual(str(stats), f"Stats for {self.shop.name} - 100 followers")

    def test_follow_event_creation(self):
        """Test creating follow events"""
        # Test follow event
        follow_event = FollowEvent.objects.create(
            customer=self.customer,
            shop=self.shop,
            event_type="follow",
            source="profile",
        )

        self.assertEqual(follow_event.customer, self.customer)
        self.assertEqual(follow_event.shop, self.shop)
        self.assertEqual(follow_event.event_type, "follow")
        self.assertEqual(follow_event.source, "profile")

        # Test string representation
        self.assertEqual(
            str(follow_event),
            f"Follow: {self.customer.phone_number} - {self.shop.name}",
        )

        # Test unfollow event
        unfollow_event = FollowEvent.objects.create(
            customer=self.customer,
            shop=self.shop,
            event_type="unfollow",
            source="profile",
        )

        self.assertEqual(unfollow_event.event_type, "unfollow")

        # Test string representation
        self.assertEqual(
            str(unfollow_event),
            f"Unfollow: {self.customer.phone_number} - {self.shop.name}",
        )
