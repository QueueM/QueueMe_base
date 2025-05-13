# apps/subscriptionapp/tests/test_views.py
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.subscriptionapp.constants import PERIOD_MONTHLY, STATUS_ACTIVE
from apps.subscriptionapp.models import Plan, PlanFeature, Subscription, SubscriptionInvoice


class PlanViewSetTest(TestCase):
    """Test cases for the PlanViewSet"""

    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(phone_number="1234567890", password="password123")

        # Create admin user
        self.admin = User.objects.create_superuser(phone_number="9876543210", password="admin123")

        # Create test plans
        self.basic_plan = Plan.objects.create(
            name="Basic Plan",
            description="Basic plan for testing",
            monthly_price=99.99,
            max_shops=1,
            max_services_per_shop=10,
            max_specialists_per_shop=5,
            position=1,
        )

        self.premium_plan = Plan.objects.create(
            name="Premium Plan",
            description="Premium plan for testing",
            monthly_price=199.99,
            max_shops=3,
            max_services_per_shop=30,
            max_specialists_per_shop=15,
            position=2,
            is_featured=True,
        )

        # Create test features
        PlanFeature.objects.create(
            plan=self.basic_plan,
            name="Shops",
            category="shops",
            tier="basic",
            value="1",
            is_available=True,
        )

        PlanFeature.objects.create(
            plan=self.premium_plan,
            name="Shops",
            category="shops",
            tier="premium",
            value="3",
            is_available=True,
        )

        # Setup API client
        self.client = APIClient()

    def test_list_plans(self):
        """Test listing plans"""
        # Authenticate
        self.client.force_authenticate(user=self.user)

        # Make request
        url = reverse("plan-list")
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return 2 plans
        self.assertEqual(len(response.data["results"]), 2)

        # Check order
        self.assertEqual(response.data["results"][0]["name"], "Basic Plan")
        self.assertEqual(response.data["results"][1]["name"], "Premium Plan")

    def test_retrieve_plan(self):
        """Test retrieving a single plan"""
        # Authenticate
        self.client.force_authenticate(user=self.user)

        # Make request
        url = reverse("plan-detail", args=[self.basic_plan.id])
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check plan data
        self.assertEqual(response.data["name"], "Basic Plan")
        self.assertEqual(response.data["monthly_price"], "99.99")
        self.assertEqual(response.data["max_shops"], 1)

        # Check features are included
        self.assertEqual(len(response.data["features"]), 1)

    def test_create_plan_admin_only(self):
        """Test that only admins can create plans"""
        # Authenticate as regular user
        self.client.force_authenticate(user=self.user)

        # Prepare data
        plan_data = {
            "name": "New Plan",
            "description": "New plan for testing",
            "monthly_price": 149.99,
            "max_shops": 2,
            "max_services_per_shop": 20,
            "max_specialists_per_shop": 10,
        }

        # Make request
        url = reverse("plan-list")
        response = self.client.post(url, plan_data, format="json")

        # Should be forbidden for regular user
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin)

        # Make request again
        response = self.client.post(url, plan_data, format="json")

        # Should be successful for admin
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check plan was created
        self.assertEqual(response.data["name"], "New Plan")
        self.assertEqual(response.data["monthly_price"], "149.99")

    def test_update_plan_admin_only(self):
        """Test that only admins can update plans"""
        # Authenticate as regular user
        self.client.force_authenticate(user=self.user)

        # Prepare data
        update_data = {"monthly_price": 89.99}

        # Make request
        url = reverse("plan-detail", args=[self.basic_plan.id])
        response = self.client.patch(url, update_data, format="json")

        # Should be forbidden for regular user
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin)

        # Make request again
        response = self.client.patch(url, update_data, format="json")

        # Should be successful for admin
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check plan was updated
        self.assertEqual(response.data["monthly_price"], "89.99")

    def test_compare_plans(self):
        """Test comparing plans"""
        # Authenticate
        self.client.force_authenticate(user=self.user)

        # Make request
        url = reverse("plan-compare")
        params = {"plan_ids": [str(self.basic_plan.id), str(self.premium_plan.id)]}
        response = self.client.get(url, params)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check comparison data
        self.assertIn("plans", response.data)
        self.assertIn("features", response.data)

        # Check plans data
        self.assertEqual(len(response.data["plans"]), 2)

        # Check features data
        self.assertIn("shops", response.data["features"])


class SubscriptionViewSetTest(TestCase):
    """Test cases for the SubscriptionViewSet"""

    def setUp(self):
        # Create test users
        self.user = User.objects.create_user(phone_number="1234567890", password="password123")

        self.admin = User.objects.create_superuser(phone_number="9876543210", password="admin123")

        # Create test company
        self.company = Company.objects.create(
            name="Test Company", contact_phone="1234567890", owner=self.user
        )

        # Create test plan
        self.plan = Plan.objects.create(
            name="Basic Plan",
            description="Basic plan for testing",
            monthly_price=99.99,
            max_shops=1,
            max_services_per_shop=10,
            max_specialists_per_shop=5,
        )

        # Create test subscription
        now = timezone.now()
        self.subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            status=STATUS_ACTIVE,
            period=PERIOD_MONTHLY,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            plan_name=self.plan.name,
            max_shops=self.plan.max_shops,
            max_services_per_shop=self.plan.max_services_per_shop,
            max_specialists_per_shop=self.plan.max_specialists_per_shop,
        )

        # Create test invoice
        self.invoice = SubscriptionInvoice.objects.create(
            subscription=self.subscription,
            invoice_number="INV-20230101-123456",
            amount=99.99,
            status="paid",
            period_start=now,
            period_end=now + timedelta(days=30),
            due_date=now + timedelta(days=7),
            paid_date=now,
        )

        # Setup API client
        self.client = APIClient()

        # Set up permissions for test user
        # In a real implementation, this would be done using the PermissionResolver

        # Mock permission resolver
        patch(
            "apps.rolesapp.services.permission_resolver.PermissionResolver.has_permission",
            return_value=True,
        ).start()

    def test_list_subscriptions_admin_only(self):
        """Test listing subscriptions (admin only)"""
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin)

        # Make request
        url = reverse("subscription-list")
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return 1 subscription
        self.assertEqual(len(response.data["results"]), 1)

        # Check subscription data
        self.assertEqual(response.data["results"][0]["company"], str(self.company.id))
        self.assertEqual(response.data["results"][0]["status"], STATUS_ACTIVE)

    def test_retrieve_subscription(self):
        """Test retrieving a single subscription"""
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin)

        # Make request
        url = reverse("subscription-detail", args=[self.subscription.id])
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check subscription data
        self.assertEqual(response.data["company"], str(self.company.id))
        self.assertEqual(response.data["plan"], str(self.plan.id))
        self.assertEqual(response.data["status"], STATUS_ACTIVE)
        self.assertEqual(response.data["period"], PERIOD_MONTHLY)

    @patch("apps.subscriptionapp.views.SubscriptionService.create_subscription")
    def test_create_subscription(self, mock_create):
        """Test creating a subscription"""
        # Mock create subscription
        mock_create.return_value = self.subscription

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin)

        # Prepare data
        subscription_data = {
            "company": str(self.company.id),
            "plan": str(self.plan.id),
            "period": PERIOD_MONTHLY,
            "auto_renew": True,
        }

        # Make request
        url = reverse("subscription-list")
        response = self.client.post(url, subscription_data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that service was called
        mock_create.assert_called_once_with(
            company_id=str(self.company.id),
            plan_id=str(self.plan.id),
            period=PERIOD_MONTHLY,
            auto_renew=True,
        )

    @patch("apps.subscriptionapp.views.SubscriptionService.cancel_subscription")
    def test_cancel_subscription(self, mock_cancel):
        """Test canceling a subscription"""
        # Mock cancel subscription
        mock_cancel.return_value = True

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin)

        # Prepare data
        cancel_data = {"reason": "Testing cancellation"}

        # Make request
        url = reverse("subscription-cancel", args=[self.subscription.id])
        response = self.client.post(url, cancel_data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that service was called
        mock_cancel.assert_called_once_with(
            subscription_id=self.subscription.id,
            performed_by=self.admin,
            reason="Testing cancellation",
        )

    def test_get_subscription_invoices(self):
        """Test getting invoices for a subscription"""
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin)

        # Make request
        url = reverse("subscription-invoices", args=[self.subscription.id])
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should return 1 invoice
        self.assertEqual(len(response.data["results"]), 1)

        # Check invoice data
        self.assertEqual(response.data["results"][0]["invoice_number"], "INV-20230101-123456")
        self.assertEqual(response.data["results"][0]["status"], "paid")
