# apps/discountapp/tests/test_services.py
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.authapp.tests.factories import UserFactory
from apps.bookingapp.tests.factories import AppointmentFactory
from apps.categoriesapp.tests.factories import CategoryFactory
from apps.discountapp.constants import (
    ERROR_CODE_ALREADY_USED,
    ERROR_CODE_EXPIRED,
    ERROR_CODE_INVALID,
)
from apps.discountapp.models import CouponUsage
from apps.discountapp.services.coupon_service import CouponService
from apps.discountapp.services.discount_service import DiscountService
from apps.discountapp.services.eligibility_service import EligibilityService
from apps.discountapp.services.promotion_service import PromotionService
from apps.discountapp.tests.factories import (
    CouponFactory,
    CouponUsageFactory,
    PromotionalCampaignFactory,
    ServiceDiscountFactory,
)
from apps.serviceapp.tests.factories import ServiceFactory
from apps.shopapp.tests.factories import ShopFactory


class CouponServiceTestCase(TestCase):
    def setUp(self):
        self.shop = ShopFactory()
        self.service = ServiceFactory(shop=self.shop)
        self.customer = UserFactory()
        self.booking = AppointmentFactory(
            shop=self.shop, customer=self.customer, service=self.service
        )

    def test_generate_code(self):
        """Test coupon code generation"""
        # Generate a code
        code = CouponService.generate_code()

        # Verify format (prefix-random)
        self.assertRegex(code, r"^[A-Z]+-[A-Z0-9]+$")

        # Generate code with custom prefix
        code = CouponService.generate_code(prefix="TEST", length=12)

        # Verify prefix
        self.assertTrue(code.startswith("TEST-"))

        # Verify uniqueness
        code2 = CouponService.generate_code()
        self.assertNotEqual(code, code2)

    def test_create_coupon(self):
        """Test coupon creation"""
        # Create a coupon
        now = timezone.now()
        coupon = CouponService.create_coupon(
            shop=self.shop,
            name="Test Coupon",
            discount_type="percentage",
            value=20,
            start_date=now,
            end_date=now + datetime.timedelta(days=30),
        )

        # Verify coupon was created
        self.assertIsNotNone(coupon)
        self.assertEqual(coupon.name, "Test Coupon")
        self.assertEqual(coupon.discount_type, "percentage")
        self.assertEqual(coupon.value, 20)
        self.assertEqual(coupon.shop, self.shop)

        # Verify auto-generated code
        self.assertRegex(coupon.code, r"^[A-Z]+-[A-Z0-9]+$")

    def test_validate_coupon(self):
        """Test coupon validation logic"""
        # Create a valid coupon
        coupon = CouponFactory(
            shop=self.shop,
            discount_type="percentage",
            value=15,
            start_date=timezone.now() - datetime.timedelta(days=1),
            end_date=timezone.now() + datetime.timedelta(days=10),
            usage_limit=1,
            used_count=0,
            is_single_use=True,
            requires_authentication=True,
            apply_to_all_services=True,
        )

        # Test valid coupon
        is_valid, message, found_coupon = CouponService.validate_coupon(
            coupon.code,
            customer=self.customer,
            services=[self.service],
            amount=Decimal("100"),
        )

        self.assertTrue(is_valid)
        self.assertIsNone(message)
        self.assertEqual(found_coupon, coupon)

        # Test invalid code
        is_valid, message, found_coupon = CouponService.validate_coupon(
            "INVALID-CODE", customer=self.customer
        )

        self.assertFalse(is_valid)
        self.assertEqual(message, ERROR_CODE_INVALID)
        self.assertIsNone(found_coupon)

        # Test expired coupon
        expired_coupon = CouponFactory(
            shop=self.shop,
            start_date=timezone.now() - datetime.timedelta(days=10),
            end_date=timezone.now() - datetime.timedelta(days=1),
        )

        is_valid, message, found_coupon = CouponService.validate_coupon(
            expired_coupon.code, customer=self.customer
        )

        self.assertFalse(is_valid)
        self.assertEqual(message, ERROR_CODE_EXPIRED)
        self.assertEqual(found_coupon, expired_coupon)

        # Test single use restriction
        CouponUsageFactory(coupon=coupon, customer=self.customer)

        is_valid, message, found_coupon = CouponService.validate_coupon(
            coupon.code, customer=self.customer
        )

        self.assertFalse(is_valid)
        self.assertEqual(message, ERROR_CODE_ALREADY_USED)
        self.assertEqual(found_coupon, coupon)

    def test_apply_coupon(self):
        """Test coupon application"""
        # Create a valid coupon
        coupon = CouponFactory(
            shop=self.shop,
            discount_type="percentage",
            value=20,
            apply_to_all_services=True,
            usage_limit=1,
            used_count=0,
        )

        # Apply coupon
        success, message, discount_amount = CouponService.apply_coupon(
            coupon.code, self.customer, self.booking, Decimal("100")
        )

        # Verify application
        self.assertTrue(success)
        self.assertIsNone(message)
        self.assertEqual(discount_amount, Decimal("20"))

        # Verify usage record was created
        usage = CouponUsage.objects.filter(
            coupon=coupon, customer=self.customer, booking=self.booking
        ).first()
        self.assertIsNotNone(usage)
        self.assertEqual(usage.amount, Decimal("20"))

        # Verify coupon usage count was incremented
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)

        # Try to apply again (should fail due to single use)
        success, message, discount_amount = CouponService.apply_coupon(
            coupon.code,
            self.customer,
            AppointmentFactory(shop=self.shop, customer=self.customer),
            Decimal("100"),
        )

        self.assertFalse(success)
        self.assertEqual(discount_amount, 0)


class DiscountServiceTestCase(TestCase):
    def setUp(self):
        self.shop = ShopFactory()
        self.service = ServiceFactory(shop=self.shop)
        self.customer = UserFactory()

    def test_get_active_discounts(self):
        """Test fetching active discounts"""
        # Create active and inactive discounts
        active_discount = ServiceDiscountFactory(
            shop=self.shop, status="active", apply_to_all_services=True
        )

        inactive_discount = ServiceDiscountFactory(
            shop=self.shop, status="paused", apply_to_all_services=True
        )

        expired_discount = ServiceDiscountFactory(
            shop=self.shop,
            start_date=timezone.now() - datetime.timedelta(days=10),
            end_date=timezone.now() - datetime.timedelta(days=1),
            apply_to_all_services=True,
        )

        future_discount = ServiceDiscountFactory(
            shop=self.shop,
            start_date=timezone.now() + datetime.timedelta(days=1),
            end_date=timezone.now() + datetime.timedelta(days=10),
            apply_to_all_services=True,
        )

        # Get active discounts
        active_discounts = DiscountService.get_active_discounts(self.shop)

        # Verify only active discount is returned
        self.assertEqual(len(active_discounts), 1)
        self.assertEqual(active_discounts[0], active_discount)

    def test_calculate_discount(self):
        """Test discount calculation"""
        # Create discount and coupon
        discount = ServiceDiscountFactory(
            shop=self.shop,
            discount_type="percentage",
            value=15,
            apply_to_all_services=True,
        )

        coupon = CouponFactory(
            shop=self.shop,
            discount_type="percentage",
            value=20,
            apply_to_all_services=True,
        )

        # Test basic discount calculation (no coupon)
        discounted_price, original_price, discount_info = DiscountService.calculate_discount(
            Decimal("100"), service=self.service, shop=self.shop
        )

        self.assertEqual(discounted_price, Decimal("85"))
        self.assertEqual(original_price, Decimal("100"))
        self.assertIsNotNone(discount_info)
        self.assertEqual(discount_info["type"], "service_discount")
        self.assertEqual(discount_info["amount"], Decimal("15"))

        # Test with coupon (better discount)
        discounted_price, original_price, discount_info = DiscountService.calculate_discount(
            Decimal("100"),
            service=self.service,
            shop=self.shop,
            customer=self.customer,
            coupon_code=coupon.code,
        )

        self.assertEqual(discounted_price, Decimal("80"))
        self.assertEqual(original_price, Decimal("100"))
        self.assertIsNotNone(discount_info)
        self.assertEqual(discount_info["type"], "coupon")
        self.assertEqual(discount_info["amount"], Decimal("20"))

    def test_apply_multiple_discounts(self):
        """Test applying multiple combinable discounts"""
        # Create combinable discounts
        discount1 = ServiceDiscountFactory(
            shop=self.shop,
            discount_type="percentage",
            value=10,
            apply_to_all_services=True,
            is_combinable=True,
            priority=2,
        )

        discount2 = ServiceDiscountFactory(
            shop=self.shop,
            discount_type="fixed",
            value=5,
            apply_to_all_services=True,
            is_combinable=True,
            priority=1,
        )

        coupon = CouponFactory(
            shop=self.shop,
            discount_type="percentage",
            value=15,
            apply_to_all_services=True,
            is_combinable=True,
        )

        # Test applying multiple discounts
        (
            discounted_price,
            original_price,
            discount_breakdown,
        ) = DiscountService.apply_multiple_discounts(
            Decimal("100"),
            service=self.service,
            shop=self.shop,
            customer=self.customer,
            coupon_code=coupon.code,
        )

        self.assertEqual(original_price, Decimal("100"))
        self.assertEqual(len(discount_breakdown), 3)  # Coupon + 2 discounts

        # Calculate expected price: 100 - 15 (15% coupon) - 8.5 (10% of 85) - 5 (fixed)
        # 100 - 15 = 85 (after coupon)
        # 85 - 8.5 = 76.5 (after percentage discount)
        # 76.5 - 5 = 71.5 (after fixed discount)
        self.assertEqual(discounted_price, Decimal("71.5"))

        # Verify breakdown contains correct discounts
        coupon_discount = next((d for d in discount_breakdown if d["type"] == "coupon"), None)
        self.assertIsNotNone(coupon_discount)
        self.assertEqual(coupon_discount["amount"], Decimal("15"))

        # Verify non-combinable discount
        non_combinable_discount = ServiceDiscountFactory(
            shop=self.shop,
            discount_type="percentage",
            value=25,  # Better than others combined
            apply_to_all_services=True,
            is_combinable=False,
        )

        # With non-combinable, we should get either non-combinable OR the combinable set
        (
            discounted_price,
            original_price,
            discount_breakdown,
        ) = DiscountService.apply_multiple_discounts(
            Decimal("100"),
            service=self.service,
            shop=self.shop,
            customer=self.customer,
            coupon_code=coupon.code,
        )

        # Expected: best discount is non-combinable at 25%
        self.assertEqual(discounted_price, Decimal("75"))


class PromotionServiceTestCase(TestCase):
    def setUp(self):
        self.shop = ShopFactory()
        self.service = ServiceFactory(shop=self.shop)

    def test_create_campaign(self):
        """Test creating a promotional campaign"""
        now = timezone.now()

        # Create a campaign
        campaign = PromotionService.create_campaign(
            shop=self.shop,
            name="Holiday Sale",
            campaign_type="holiday",
            start_date=now,
            end_date=now + datetime.timedelta(days=30),
            description="Special holiday discounts",
            is_active=True,
            new_discounts=[
                {
                    "name": "Holiday Discount",
                    "discount_type": "percentage",
                    "value": 15,
                    "apply_to_all_services": True,
                }
            ],
            new_coupons=[
                {
                    "name": "Holiday Coupon",
                    "discount_type": "percentage",
                    "value": 20,
                    "is_single_use": True,
                }
            ],
        )

        # Verify campaign was created
        self.assertIsNotNone(campaign)
        self.assertEqual(campaign.name, "Holiday Sale")
        self.assertEqual(campaign.campaign_type, "holiday")

        # Verify discounts were created and linked
        self.assertEqual(campaign.service_discounts.count(), 1)
        discount = campaign.service_discounts.first()
        self.assertEqual(discount.name, "Holiday Discount")
        self.assertEqual(discount.value, 15)

        # Verify coupons were created and linked
        self.assertEqual(campaign.coupons.count(), 1)
        coupon = campaign.coupons.first()
        self.assertEqual(coupon.name, "Holiday Coupon")
        self.assertEqual(coupon.value, 20)

    def test_get_active_campaigns(self):
        """Test getting active campaigns"""
        now = timezone.now()

        # Create active and inactive campaigns
        active_campaign = PromotionalCampaignFactory(
            shop=self.shop,
            start_date=now - datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=10),
            is_active=True,
        )

        inactive_campaign = PromotionalCampaignFactory(
            shop=self.shop,
            start_date=now - datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=10),
            is_active=False,
        )

        future_campaign = PromotionalCampaignFactory(
            shop=self.shop,
            start_date=now + datetime.timedelta(days=1),
            end_date=now + datetime.timedelta(days=10),
            is_active=True,
        )

        past_campaign = PromotionalCampaignFactory(
            shop=self.shop,
            start_date=now - datetime.timedelta(days=10),
            end_date=now - datetime.timedelta(days=1),
            is_active=True,
        )

        # Get active campaigns
        active_campaigns = PromotionService.get_active_campaigns(self.shop)

        # Verify only truly active campaign is returned
        self.assertEqual(len(active_campaigns), 1)
        self.assertEqual(active_campaigns[0], active_campaign)

    def test_create_referral_campaign(self):
        """Test creating a referral campaign"""
        # Create a referral campaign
        campaign, sample_coupon = PromotionService.create_referral_campaign(
            shop=self.shop, discount_value=15, days_valid=30
        )

        # Verify campaign was created
        self.assertIsNotNone(campaign)
        self.assertEqual(campaign.campaign_type, "referral")
        self.assertTrue(campaign.is_active)

        # Verify sample coupon was created
        self.assertIsNotNone(sample_coupon)
        self.assertEqual(sample_coupon.discount_type, "percentage")
        self.assertEqual(sample_coupon.value, 15)
        self.assertTrue(sample_coupon.is_referral)
        self.assertEqual(sample_coupon.usage_limit, 1)

        # Verify coupon is linked to campaign
        self.assertTrue(campaign.coupons.filter(id=sample_coupon.id).exists())


class EligibilityServiceTestCase(TestCase):
    def setUp(self):
        self.shop = ShopFactory()
        self.service = ServiceFactory(shop=self.shop)
        self.category = CategoryFactory()
        self.service.category = self.category
        self.service.save()
        self.customer = UserFactory()

    def test_check_service_eligibility(self):
        """Test service eligibility checks"""
        # Test all services discount
        all_services_discount = ServiceDiscountFactory(shop=self.shop, apply_to_all_services=True)

        self.assertTrue(
            EligibilityService.check_service_eligibility(self.service, all_services_discount)
        )

        # Test specific service discount
        specific_discount = ServiceDiscountFactory(shop=self.shop, apply_to_all_services=False)
        specific_discount.services.add(self.service)

        self.assertTrue(
            EligibilityService.check_service_eligibility(self.service, specific_discount)
        )

        # Test category discount
        category_discount = ServiceDiscountFactory(shop=self.shop, apply_to_all_services=False)
        category_discount.categories.add(self.category)

        self.assertTrue(
            EligibilityService.check_service_eligibility(self.service, category_discount)
        )

        # Test non-eligible service
        other_service = ServiceFactory(shop=self.shop)
        other_discount = ServiceDiscountFactory(shop=self.shop, apply_to_all_services=False)

        self.assertFalse(
            EligibilityService.check_service_eligibility(other_service, other_discount)
        )

    def test_check_customer_eligibility(self):
        """Test customer eligibility checks"""
        # Test single-use coupon
        single_use_coupon = CouponFactory(shop=self.shop, is_single_use=True)

        # Customer should be eligible initially
        is_eligible, _ = EligibilityService.check_customer_eligibility(
            self.customer, single_use_coupon
        )
        self.assertTrue(is_eligible)

        # After using, they should not be eligible
        CouponUsageFactory(coupon=single_use_coupon, customer=self.customer)

        is_eligible, _ = EligibilityService.check_customer_eligibility(
            self.customer, single_use_coupon
        )
        self.assertFalse(is_eligible)

        # Test authentication requirement
        auth_coupon = CouponFactory(shop=self.shop, requires_authentication=True)

        is_eligible, _ = EligibilityService.check_customer_eligibility(None, auth_coupon)
        self.assertFalse(is_eligible)

        is_eligible, _ = EligibilityService.check_customer_eligibility(self.customer, auth_coupon)
        self.assertTrue(is_eligible)

    def test_get_eligible_discounts(self):
        """Test getting eligible discounts"""
        # Create various discounts
        all_discount = ServiceDiscountFactory(shop=self.shop, apply_to_all_services=True)

        specific_discount = ServiceDiscountFactory(shop=self.shop, apply_to_all_services=False)
        specific_discount.services.add(self.service)

        category_discount = ServiceDiscountFactory(shop=self.shop, apply_to_all_services=False)
        category_discount.categories.add(self.category)

        other_discount = ServiceDiscountFactory(shop=self.shop, apply_to_all_services=False)

        # Get eligible discounts
        eligible_discounts = EligibilityService.get_eligible_discounts(self.service, self.shop)

        # Verify all applicable discounts are returned
        self.assertEqual(len(eligible_discounts), 3)
        self.assertIn(all_discount, eligible_discounts)
        self.assertIn(specific_discount, eligible_discounts)
        self.assertIn(category_discount, eligible_discounts)
        self.assertNotIn(other_discount, eligible_discounts)
