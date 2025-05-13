# apps/subscriptionapp/tests/test_services.py
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.subscriptionapp.constants import (
    FEATURE_CATEGORY_SHOPS,
    PERIOD_MONTHLY,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_INITIATED,
)
from apps.subscriptionapp.models import (
    FeatureUsage,
    Plan,
    PlanFeature,
    Subscription,
    SubscriptionInvoice,
    SubscriptionLog,
)
from apps.subscriptionapp.services.invoice_service import InvoiceService
from apps.subscriptionapp.services.plan_service import PlanService
from apps.subscriptionapp.services.subscription_service import SubscriptionService
from apps.subscriptionapp.services.usage_monitor import UsageMonitor


class SubscriptionServiceTest(TestCase):
    """Test cases for the SubscriptionService"""

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

    def test_create_subscription(self):
        """Test creating a new subscription"""
        subscription = SubscriptionService.create_subscription(
            company_id=self.company.id,
            plan_id=self.plan.id,
            period=PERIOD_MONTHLY,
            auto_renew=True,
        )

        # Check subscription was created
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.company, self.company)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, STATUS_INITIATED)
        self.assertEqual(subscription.period, PERIOD_MONTHLY)
        self.assertTrue(subscription.auto_renew)

        # Check cached plan details
        self.assertEqual(subscription.plan_name, self.plan.name)
        self.assertEqual(subscription.max_shops, self.plan.max_shops)

    def test_create_subscription_already_exists(self):
        """Test error when company already has an active subscription"""
        # Create an active subscription first
        Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            status=STATUS_ACTIVE,
            period=PERIOD_MONTHLY,
            start_date=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            plan_name=self.plan.name,
            max_shops=self.plan.max_shops,
            max_services_per_shop=self.plan.max_services_per_shop,
            max_specialists_per_shop=self.plan.max_specialists_per_shop,
        )

        # Should raise ValueError
        with self.assertRaises(ValueError):
            SubscriptionService.create_subscription(
                company_id=self.company.id, plan_id=self.plan.id
            )

    @patch("apps.subscriptionapp.services.subscription_service.requests.post")
    def test_initiate_subscription_payment(self, mock_post):
        """Test initiating payment for a subscription"""
        # Mock Moyasar API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "payment_123",
            "source": {"transaction_url": "https://api.moyasar.com/payment/123"},
        }
        mock_post.return_value = mock_response

        # Create ContentType for Transaction model
        from django.contrib.contenttypes.models import ContentType

        ContentType.objects.get_or_create(app_label="payment", model="transaction")

        # Call the service with test data
        result = SubscriptionService.initiate_subscription_payment(
            company_id=self.company.id,
            plan_id=self.plan.id,
            period=PERIOD_MONTHLY,
            return_url="https://queueme.net/callback",
        )

        # Check the result
        self.assertIn("subscription_id", result)
        self.assertIn("invoice_id", result)
        self.assertEqual(result["payment_id"], "payment_123")
        self.assertEqual(result["payment_url"], "https://api.moyasar.com/payment/123")
        self.assertEqual(result["amount"], Decimal("99.99"))

        # Check that a subscription was created
        subscription = Subscription.objects.get(id=result["subscription_id"])
        self.assertEqual(subscription.company, self.company)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, STATUS_INITIATED)

        # Check that an invoice was created
        invoice = SubscriptionInvoice.objects.get(id=result["invoice_id"])
        self.assertEqual(invoice.subscription, subscription)
        self.assertEqual(invoice.amount, Decimal("99.99"))
        self.assertEqual(invoice.status, "pending")

    @patch(
        "apps.subscriptionapp.services.subscription_service.SubscriptionService.send_confirmation_email"
    )
    def test_activate_subscription(self, mock_send_email):
        """Test activating a subscription after payment"""
        # Create an initiated subscription
        subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            status=STATUS_INITIATED,
            period=PERIOD_MONTHLY,
            plan_name=self.plan.name,
            max_shops=self.plan.max_shops,
            max_services_per_shop=self.plan.max_services_per_shop,
            max_specialists_per_shop=self.plan.max_specialists_per_shop,
        )

        # Activate the subscription
        result = SubscriptionService.activate_subscription(subscription.id)

        # Check result
        self.assertTrue(result)

        # Refresh subscription from database
        subscription.refresh_from_db()

        # Check that subscription was activated
        self.assertEqual(subscription.status, STATUS_ACTIVE)
        self.assertIsNotNone(subscription.start_date)
        self.assertIsNotNone(subscription.current_period_start)
        self.assertIsNotNone(subscription.current_period_end)

        # Check that log entry was created
        log = SubscriptionLog.objects.filter(
            subscription=subscription,
            action="status_change",
            status_before=STATUS_INITIATED,
            status_after=STATUS_ACTIVE,
        ).first()
        self.assertIsNotNone(log)

        # Check that confirmation email was sent
        mock_send_email.assert_called_once_with(subscription.id)

    def test_cancel_subscription(self):
        """Test canceling a subscription"""
        # Create an active subscription
        subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            status=STATUS_ACTIVE,
            period=PERIOD_MONTHLY,
            start_date=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            plan_name=self.plan.name,
            max_shops=self.plan.max_shops,
            max_services_per_shop=self.plan.max_services_per_shop,
            max_specialists_per_shop=self.plan.max_specialists_per_shop,
        )

        # Cancel the subscription
        with patch(
            "apps.subscriptionapp.services.subscription_service.SubscriptionService.send_cancellation_email"
        ) as mock_send_email:
            result = SubscriptionService.cancel_subscription(
                subscription_id=subscription.id,
                performed_by=self.user,
                reason="Testing cancellation",
            )

            # Verify the mock was called - fix for F841
            mock_send_email.assert_called_once_with(subscription.id)

        # Check result
        self.assertTrue(result)

        # Refresh subscription from database
        subscription.refresh_from_db()

        # Check that subscription was canceled
        self.assertEqual(subscription.status, STATUS_CANCELED)
        self.assertIsNotNone(subscription.canceled_at)
        self.assertFalse(subscription.auto_renew)

        # Check that log entry was created
        log = SubscriptionLog.objects.filter(
            subscription=subscription,
            action="status_change",
            status_before=STATUS_ACTIVE,
            status_after=STATUS_CANCELED,
            performed_by=self.user,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata.get("reason"), "Testing cancellation")


class PlanServiceTest(TestCase):
    """Test cases for the PlanService"""

    def setUp(self):
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

    def test_create_plan(self):
        """Test creating a new plan"""
        plan_data = {
            "name": "Standard Plan",
            "description": "Standard plan for testing",
            "monthly_price": 149.99,
            "max_shops": 2,
            "max_services_per_shop": 20,
            "max_specialists_per_shop": 10,
            "position": 2,
        }

        features_data = [
            {
                "name": "Shops",
                "category": "shops",
                "tier": "standard",
                "value": "2",
                "is_available": True,
            },
            {
                "name": "Services",
                "category": "services",
                "tier": "standard",
                "value": "20",
                "is_available": True,
            },
        ]

        plan = PlanService.create_plan(plan_data, features_data)

        # Check plan was created
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "Standard Plan")
        self.assertEqual(plan.monthly_price, 149.99)

        # Check features were created
        features = plan.features.all()
        self.assertEqual(features.count(), 2)

        # Check first feature
        shops_feature = features.filter(category="shops").first()
        self.assertIsNotNone(shops_feature)
        self.assertEqual(shops_feature.tier, "standard")
        self.assertEqual(shops_feature.value, "2")

    def test_get_active_plans(self):
        """Test getting active plans"""
        # Create an inactive plan
        Plan.objects.create(
            name="Inactive Plan",
            description="Inactive plan for testing",
            monthly_price=49.99,
            max_shops=1,
            max_services_per_shop=5,
            max_specialists_per_shop=2,
            is_active=False,
        )

        # Get active plans
        active_plans = PlanService.get_active_plans()

        # Should be 2 active plans
        self.assertEqual(active_plans.count(), 2)

        # Check ordering (by position)
        self.assertEqual(active_plans[0], self.basic_plan)
        self.assertEqual(active_plans[1], self.premium_plan)

    def test_compare_plans(self):
        """Test comparing plans"""
        # Compare the two plans
        comparison = PlanService.compare_plans([self.basic_plan, self.premium_plan])

        # Check structure
        self.assertIn("plans", comparison)
        self.assertIn("features", comparison)

        # Check plans data
        plans_data = comparison["plans"]
        self.assertEqual(len(plans_data), 2)

        # Check first plan
        basic_data = plans_data[0]
        self.assertEqual(basic_data["name"], "Basic Plan")
        self.assertEqual(basic_data["monthly_price"], 99.99)
        self.assertEqual(basic_data["max_shops"], 1)

        # Check second plan
        premium_data = plans_data[1]
        self.assertEqual(premium_data["name"], "Premium Plan")
        self.assertEqual(premium_data["is_featured"], True)

        # Check features data
        features_data = comparison["features"]
        self.assertIn("shops", features_data)

        # Check shops features
        shops_features = features_data["shops"]["features"]
        self.assertEqual(len(shops_features), 1)  # One feature with two plan values

        # Check shop feature values
        shop_feature = shops_features[0]
        self.assertEqual(shop_feature["name"], "Shops")
        self.assertIn(str(self.basic_plan.id), shop_feature["plans"])
        self.assertIn(str(self.premium_plan.id), shop_feature["plans"])

        # Check plan-specific feature values
        basic_value = shop_feature["plans"][str(self.basic_plan.id)]
        self.assertEqual(basic_value["value"], "1")
        self.assertEqual(basic_value["tier"], "basic")

        premium_value = shop_feature["plans"][str(self.premium_plan.id)]
        self.assertEqual(premium_value["value"], "3")
        self.assertEqual(premium_value["tier"], "premium")


class InvoiceServiceTest(TestCase):
    """Test cases for the InvoiceService"""

    def setUp(self):
        # Create test user
        self.user = User.objects.create(phone_number="1234567890", user_type="employee")

        # Create test company
        self.company = Company.objects.create(
            name="Test Company",
            contact_phone="1234567890",
            contact_email="test@example.com",
            owner=self.user,
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

    def test_generate_invoice_number(self):
        """Test generating a unique invoice number"""
        invoice_number = InvoiceService.generate_invoice_number()

        # Check format (INV-YYYYMMDD-XXXXXX)
        self.assertTrue(invoice_number.startswith("INV-"))
        self.assertEqual(len(invoice_number), 22)

        # Generate another number, should be different
        another_number = InvoiceService.generate_invoice_number()
        self.assertNotEqual(invoice_number, another_number)

    def test_create_invoice(self):
        """Test creating a new invoice"""
        now = timezone.now()
        period_end = now + timedelta(days=30)

        invoice = InvoiceService.create_invoice(
            subscription_id=self.subscription.id,
            amount=99.99,
            period_start=now,
            period_end=period_end,
            status="pending",
        )

        # Check invoice was created
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.subscription, self.subscription)
        self.assertEqual(invoice.amount, Decimal("99.99"))
        self.assertEqual(invoice.status, "pending")
        self.assertEqual(invoice.period_start, now)
        self.assertEqual(invoice.period_end, period_end)

        # Check invoice number format
        self.assertTrue(invoice.invoice_number.startswith("INV-"))

        # Check due date (should be 7 days from now)
        due_date_diff = (invoice.due_date - now).days
        self.assertTrue(6 <= due_date_diff <= 7)

    @patch("apps.subscriptionapp.services.invoice_service.EmailMultiAlternatives.send")
    def test_send_invoice_email(self, mock_send):
        """Test sending invoice email"""
        # Create a test invoice
        now = timezone.now()
        invoice = SubscriptionInvoice.objects.create(
            subscription=self.subscription,
            invoice_number="INV-20230101-123456",
            amount=99.99,
            status="paid",
            period_start=now,
            period_end=now + timedelta(days=30),
            due_date=now + timedelta(days=7),
            paid_date=now,
        )

        # Mock PDF generation
        with patch(
            "apps.subscriptionapp.services.invoice_service.InvoiceService.generate_invoice_pdf"
        ) as mock_pdf:
            # Create a mock file-like object
            mock_file = MagicMock()
            mock_file.read.return_value = b"PDF content"
            mock_pdf.return_value = mock_file

            # Send email
            result = InvoiceService.send_invoice_email(invoice.id)

        # Check result
        self.assertTrue(result)

        # Check that email was sent
        mock_send.assert_called_once()

        # Check that PDF was generated
        mock_pdf.assert_called_once_with(invoice.id)


class UsageMonitorTest(TestCase):
    """Test cases for the UsageMonitor"""

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

    def test_initialize_usage_tracking(self):
        """Test initializing usage tracking for a subscription"""
        UsageMonitor.initialize_usage_tracking(self.subscription.id)

        # Check that usage records were created
        records = FeatureUsage.objects.filter(subscription=self.subscription)
        self.assertEqual(records.count(), 3)

        # Check shop usage record
        shop_usage = records.filter(feature_category=FEATURE_CATEGORY_SHOPS).first()
        self.assertIsNotNone(shop_usage)
        self.assertEqual(shop_usage.limit, 3)
        self.assertEqual(shop_usage.current_usage, 0)

    def test_update_usage_limits(self):
        """Test updating usage limits"""
        # Create usage records
        shop_usage = FeatureUsage.objects.create(
            subscription=self.subscription,
            feature_category=FEATURE_CATEGORY_SHOPS,
            limit=2,
            current_usage=1,
        )

        # Update plan limits
        self.plan.max_shops = 5
        self.plan.save()

        # Update subscription cached limits
        self.subscription.max_shops = 5
        self.subscription.save()

        # Update usage limits
        UsageMonitor.update_usage_limits(self.subscription.id)

        # Refresh from DB
        shop_usage.refresh_from_db()

        # Check updated limit
        self.assertEqual(shop_usage.limit, 5)

        # Current usage should remain unchanged
        self.assertEqual(shop_usage.current_usage, 1)

    @patch("apps.subscriptionapp.services.usage_monitor.Shop.objects.filter")
    def test_check_shop_limit(self, mock_filter):
        """Test checking shop limit"""
        # Mock shop count
        mock_count = MagicMock()
        mock_count.count.return_value = 2
        mock_filter.return_value = mock_count

        # Create shop usage record
        FeatureUsage.objects.create(
            subscription=self.subscription,
            feature_category=FEATURE_CATEGORY_SHOPS,
            limit=3,
            current_usage=2,
        )

        # Check if can add more shops
        can_add, current, limit = UsageMonitor.check_shop_limit(self.company.id)

        # Should be allowed (2 < 3)
        self.assertTrue(can_add)
        self.assertEqual(current, 2)
        self.assertEqual(limit, 3)

        # Update usage to match limit
        shop_usage = FeatureUsage.objects.get(
            subscription=self.subscription, feature_category=FEATURE_CATEGORY_SHOPS
        )
        shop_usage.current_usage = 3
        shop_usage.save()

        # Check again
        can_add, current, limit = UsageMonitor.check_shop_limit(self.company.id)

        # Should not be allowed (3 >= 3)
        self.assertFalse(can_add)
        self.assertEqual(current, 3)
        self.assertEqual(limit, 3)
