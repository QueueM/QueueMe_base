# apps/subscriptionapp/tests/test_models.py
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.subscriptionapp.constants import (
    FEATURE_CATEGORY_SHOPS,
    PERIOD_MONTHLY,
    STATUS_ACTIVE,
)
from apps.subscriptionapp.models import (
    FeatureUsage,
    Plan,
    PlanFeature,
    Subscription,
    SubscriptionInvoice,
)


class PlanModelTest(TestCase):
    """Test cases for the Plan model"""

    def setUp(self):
        # Create a test plan
        self.plan = Plan.objects.create(
            name="Basic Plan",
            description="Basic plan for testing",
            monthly_price=99.99,
            max_shops=1,
            max_services_per_shop=10,
            max_specialists_per_shop=5,
        )

        # Create a test feature
        self.feature = PlanFeature.objects.create(
            plan=self.plan,
            name="Feature 1",
            category="shops",
            tier="basic",
            value="1",
            is_available=True,
        )

    def test_plan_creation(self):
        """Test basic plan creation"""
        self.assertEqual(self.plan.name, "Basic Plan")
        self.assertEqual(self.plan.monthly_price, 99.99)
        self.assertEqual(self.plan.max_shops, 1)
        self.assertTrue(self.plan.is_active)

    def test_get_price_for_period(self):
        """Test price calculation for different periods"""
        # Monthly price
        monthly_price = self.plan.get_price_for_period("monthly")
        self.assertEqual(monthly_price, 99.99)

        # Quarterly price (3 months, 5% discount)
        quarterly_price = self.plan.get_price_for_period("quarterly")
        expected_quarterly = 99.99 * 3 * 0.95
        self.assertEqual(quarterly_price, round(expected_quarterly, 2))

        # Annual price (12 months, 15% discount)
        annual_price = self.plan.get_price_for_period("annual")
        expected_annual = 99.99 * 12 * 0.85
        self.assertEqual(annual_price, round(expected_annual, 2))

    def test_plan_feature_relation(self):
        """Test plan-feature relationship"""
        # Get features for plan
        features = self.plan.features.all()
        self.assertEqual(features.count(), 1)
        self.assertEqual(features.first(), self.feature)


class SubscriptionModelTest(TestCase):
    """Test cases for the Subscription model"""

    def setUp(self):
        # Create test user
        self.user = User.objects.create(phone_number="1234567890", user_type="employee")

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

        # Create test feature usage
        self.feature_usage = FeatureUsage.objects.create(
            subscription=self.subscription,
            feature_category=FEATURE_CATEGORY_SHOPS,
            limit=self.plan.max_shops,
            current_usage=0,
        )

    def test_subscription_creation(self):
        """Test basic subscription creation"""
        self.assertEqual(self.subscription.company, self.company)
        self.assertEqual(self.subscription.plan, self.plan)
        self.assertEqual(self.subscription.status, STATUS_ACTIVE)
        self.assertEqual(self.subscription.period, PERIOD_MONTHLY)

        # Test cached plan details
        self.assertEqual(self.subscription.plan_name, self.plan.name)
        self.assertEqual(self.subscription.max_shops, self.plan.max_shops)

    def test_is_active(self):
        """Test is_active method"""
        self.assertTrue(self.subscription.is_active())

        # Test with expired subscription
        self.subscription.current_period_end = timezone.now() - timedelta(days=1)
        self.subscription.save()
        self.assertFalse(self.subscription.is_active())

        # Test with inactive status
        self.subscription.current_period_end = timezone.now() + timedelta(days=30)
        self.subscription.status = "expired"
        self.subscription.save()
        self.assertFalse(self.subscription.is_active())

    def test_days_remaining(self):
        """Test days_remaining method"""
        # Set a fixed future date (30 days from now)
        now = timezone.now()
        future_date = now + timedelta(days=30)
        self.subscription.current_period_end = future_date
        self.subscription.save()

        # Should return approximately 30 days
        self.assertTrue(29 <= self.subscription.days_remaining() <= 30)

        # Test with past date (should return 0)
        self.subscription.current_period_end = now - timedelta(days=1)
        self.subscription.save()
        self.assertEqual(self.subscription.days_remaining(), 0)

    def test_is_in_trial(self):
        """Test is_in_trial method"""
        # Initially not in trial
        self.assertFalse(self.subscription.is_in_trial())

        # Set trial end date
        now = timezone.now()
        self.subscription.trial_end = now + timedelta(days=14)
        self.subscription.save()
        self.assertTrue(self.subscription.is_in_trial())

        # Test with expired trial
        self.subscription.trial_end = now - timedelta(days=1)
        self.subscription.save()
        self.assertFalse(self.subscription.is_in_trial())


class FeatureUsageModelTest(TestCase):
    """Test cases for the FeatureUsage model"""

    def setUp(self):
        # Create test user
        self.user = User.objects.create(phone_number="1234567890", user_type="employee")

        # Create test company
        self.company = Company.objects.create(
            name="Test Company", contact_phone="1234567890", owner=self.user
        )

        # Create test plan
        self.plan = Plan.objects.create(
            name="Basic Plan",
            description="Basic plan for testing",
            monthly_price=99.99,
            max_shops=3,
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

        # Create test feature usage
        self.feature_usage = FeatureUsage.objects.create(
            subscription=self.subscription,
            feature_category=FEATURE_CATEGORY_SHOPS,
            limit=self.plan.max_shops,
            current_usage=2,
        )

    def test_feature_usage_creation(self):
        """Test basic feature usage creation"""
        self.assertEqual(self.feature_usage.subscription, self.subscription)
        self.assertEqual(self.feature_usage.feature_category, FEATURE_CATEGORY_SHOPS)
        self.assertEqual(self.feature_usage.limit, 3)
        self.assertEqual(self.feature_usage.current_usage, 2)

    def test_is_limit_reached(self):
        """Test is_limit_reached method"""
        # Current usage (2) is less than limit (3)
        self.assertFalse(self.feature_usage.is_limit_reached())

        # Set usage equal to limit
        self.feature_usage.current_usage = 3
        self.feature_usage.save()
        self.assertTrue(self.feature_usage.is_limit_reached())

        # Set usage above limit
        self.feature_usage.current_usage = 4
        self.feature_usage.save()
        self.assertTrue(self.feature_usage.is_limit_reached())
