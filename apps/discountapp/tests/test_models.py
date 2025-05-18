# apps/discountapp/tests/test_models.py
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.authapp.tests.factories import UserFactory
from apps.bookingapp.tests.factories import AppointmentFactory
from apps.discountapp.tests.factories import (
    CouponFactory,
    CouponUsageFactory,
    PromotionalCampaignFactory,
    ServiceDiscountFactory,
)
from apps.serviceapp.tests.factories import ServiceFactory
from apps.shopapp.tests.factories import ShopFactory


class ServiceDiscountTestCase(TestCase):
    def setUp(self):
        self.shop = ShopFactory()
        self.service = ServiceFactory(shop=self.shop)

    def test_percentage_discount_calculation(self):
        """Test percentage discount calculation"""
        # Create a 20% discount
        discount = ServiceDiscountFactory(
            shop=self.shop,
            discount_type="percentage",
            value=20,
            max_discount_amount=None,
            min_purchase_amount=0,
            apply_to_all_services=True,
        )

        # Test basic calculation
        self.assertEqual(discount.calculate_discount_amount(Decimal("100")), Decimal("20"))
        self.assertEqual(discount.calculate_discount_amount(Decimal("150")), Decimal("30"))

        # Test with max discount amount
        discount.max_discount_amount = Decimal("25")
        discount.save()

        self.assertEqual(discount.calculate_discount_amount(Decimal("100")), Decimal("20"))
        self.assertEqual(
            discount.calculate_discount_amount(Decimal("150")), Decimal("25")
        )  # Capped at max

        # Test with minimum purchase amount
        discount.min_purchase_amount = Decimal("120")
        discount.save()

        self.assertEqual(
            discount.calculate_discount_amount(Decimal("100")), Decimal("0")
        )  # Below minimum
        self.assertEqual(
            discount.calculate_discount_amount(Decimal("150")), Decimal("25")
        )  # Above minimum

    def test_fixed_discount_calculation(self):
        """Test fixed discount calculation"""
        # Create a 15 SAR fixed discount
        discount = ServiceDiscountFactory(
            shop=self.shop,
            discount_type="fixed",
            value=15,
            max_discount_amount=None,
            min_purchase_amount=0,
            apply_to_all_services=True,
        )

        # Test basic calculation
        self.assertEqual(discount.calculate_discount_amount(Decimal("100")), Decimal("15"))
        self.assertEqual(
            discount.calculate_discount_amount(Decimal("10")), Decimal("10")
        )  # Can't discount more than price

        # Test with minimum purchase amount
        discount.min_purchase_amount = Decimal("50")
        discount.save()

        self.assertEqual(
            discount.calculate_discount_amount(Decimal("40")), Decimal("0")
        )  # Below minimum
        self.assertEqual(
            discount.calculate_discount_amount(Decimal("100")), Decimal("15")
        )  # Above minimum

    def test_status_changes_based_on_dates(self):
        """Test status changes based on date ranges"""
        now = timezone.now()

        # Future discount (scheduled)
        future_discount = ServiceDiscountFactory(
            shop=self.shop,
            start_date=now + datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=10),
            status="active",  # This should change to scheduled on save
        )

        self.assertEqual(future_discount.status, "scheduled")

        # Current discount (active)
        current_discount = ServiceDiscountFactory(
            shop=self.shop,
            start_date=now - datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=10),
        )

        self.assertEqual(current_discount.status, "active")

        # Past discount (expired)
        past_discount = ServiceDiscountFactory(
            shop=self.shop,
            start_date=now - datetime.timedelta(days=10),
            end_date=now - datetime.timedelta(days=1),
            status="active",  # This should change to expired on save
        )

        self.assertEqual(past_discount.status, "expired")

    def test_usage_limit(self):
        """Test usage limit functionality"""
        discount = ServiceDiscountFactory(shop=self.shop, usage_limit=3, used_count=0)

        # Increment usage
        discount.increment_usage()
        discount.refresh_from_db()
        self.assertEqual(discount.used_count, 1)
        self.assertEqual(discount.status, "active")

        # Increment to limit
        discount.increment_usage()
        discount.increment_usage()
        discount.refresh_from_db()
        self.assertEqual(discount.used_count, 3)
        self.assertEqual(discount.status, "expired")

        # Verify is_valid check
        self.assertFalse(discount.is_valid())


class CouponTestCase(TestCase):
    def setUp(self):
        self.shop = ShopFactory()
        self.service = ServiceFactory(shop=self.shop)
        self.customer = UserFactory()

    def test_coupon_validation(self):
        """Test coupon validation"""
        now = timezone.now()

        # Create a valid coupon
        coupon = CouponFactory(
            shop=self.shop,
            discount_type="percentage",
            value=15,
            start_date=now - datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=10),
            usage_limit=1,
            used_count=0,
            is_single_use=True,
            requires_authentication=True,
        )

        # Test basic validation
        self.assertTrue(coupon.is_valid())

        # Test expired coupon
        expired_coupon = CouponFactory(
            shop=self.shop,
            start_date=now - datetime.timedelta(days=10),
            end_date=now - datetime.timedelta(days=1),
        )

        self.assertFalse(expired_coupon.is_valid())

        # Test usage limit
        used_coupon = CouponFactory(shop=self.shop, usage_limit=1, used_count=1)

        self.assertFalse(used_coupon.is_valid())

    def test_coupon_usage_records(self):
        """Test coupon usage records"""
        coupon = CouponFactory(shop=self.shop)
        booking = AppointmentFactory(shop=self.shop, customer=self.customer)

        # Create usage record
        usage = CouponUsageFactory(
            coupon=coupon,
            customer=self.customer,
            booking=booking,
            amount=Decimal("15.00"),
        )

        # Verify usage record
        self.assertEqual(usage.coupon, coupon)
        self.assertEqual(usage.customer, self.customer)
        self.assertEqual(usage.booking, booking)
        self.assertEqual(usage.amount, Decimal("15.00"))


class PromotionalCampaignTestCase(TestCase):
    def setUp(self):
        self.shop = ShopFactory()

    def test_campaign_date_validation(self):
        """Test campaign date validation"""
        now = timezone.now()

        # Valid date range
        campaign = PromotionalCampaignFactory(
            shop=self.shop, start_date=now, end_date=now + datetime.timedelta(days=10)
        )

        # Invalid date range (end before start)
        with self.assertRaises(Exception):
            invalid_campaign = PromotionalCampaignFactory(
                shop=self.shop,
                start_date=now,
                end_date=now - datetime.timedelta(days=1),
            )

    def test_campaign_active_status(self):
        """Test campaign active status"""
        now = timezone.now()

        # Current active campaign
        active_campaign = PromotionalCampaignFactory(
            shop=self.shop,
            start_date=now - datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=10),
            is_active=True,
        )

        self.assertTrue(active_campaign.is_active_now())

        # Current inactive campaign
        inactive_campaign = PromotionalCampaignFactory(
            shop=self.shop,
            start_date=now - datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=10),
            is_active=False,
        )

        self.assertFalse(inactive_campaign.is_active_now())

        # Future campaign
        future_campaign = PromotionalCampaignFactory(
            shop=self.shop,
            start_date=now + datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=10),
            is_active=True,
        )

        self.assertFalse(future_campaign.is_active_now())

        # Past campaign
        past_campaign = PromotionalCampaignFactory(
            shop=self.shop,
            start_date=now - datetime.timedelta(days=10),
            end_date=now - datetime.timedelta(days=1),
            is_active=True,
        )

        self.assertFalse(past_campaign.is_active_now())
