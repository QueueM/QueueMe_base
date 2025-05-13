# apps/discountapp/tests/test_views.py
import datetime

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authapp.tests.factories import UserFactory
from apps.bookingapp.tests.factories import AppointmentFactory
from apps.discountapp.models import Coupon, CouponUsage, PromotionalCampaign, ServiceDiscount
from apps.discountapp.tests.factories import CouponFactory, ServiceDiscountFactory
from apps.serviceapp.tests.factories import ServiceFactory
from apps.shopapp.tests.factories import ShopFactory


class ServiceDiscountViewSetTestCase(APITestCase):
    def setUp(self):
        # Create test user
        self.user = UserFactory(is_staff=True)  # Admin user for simplicity
        self.client.force_authenticate(user=self.user)

        # Create shop
        self.shop = ShopFactory()

        # Create service
        self.service = ServiceFactory(shop=self.shop)

    def test_list_discounts(self):
        """Test listing service discounts"""
        # Create some discounts
        discount1 = ServiceDiscountFactory(shop=self.shop)
        discount2 = ServiceDiscountFactory(shop=self.shop)

        # Get discounts list
        url = reverse("servicediscount-list")
        response = self.client.get(url)

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_create_discount(self):
        """Test creating a service discount"""
        # Prepare data
        data = {
            "name": "Test Discount",
            "description": "Test description",
            "discount_type": "percentage",
            "value": 15,
            "start_date": timezone.now().isoformat(),
            "end_date": (timezone.now() + datetime.timedelta(days=30)).isoformat(),
            "shop": str(self.shop.id),
            "apply_to_all_services": True,
            "service_ids": [str(self.service.id)],
        }

        # Create discount
        url = reverse("servicediscount-list")
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Test Discount")
        self.assertEqual(response.data["discount_type"], "percentage")
        self.assertEqual(response.data["value"], "15.00")

        # Verify discount was created
        discount_id = response.data["id"]
        discount = ServiceDiscount.objects.get(id=discount_id)
        self.assertEqual(discount.name, "Test Discount")

        # Verify service was linked
        self.assertTrue(discount.services.filter(id=self.service.id).exists())

    def test_active_discounts(self):
        """Test getting active discounts"""
        # Create active and inactive discounts
        active_discount = ServiceDiscountFactory(
            shop=self.shop, status="active", apply_to_all_services=True
        )

        inactive_discount = ServiceDiscountFactory(
            shop=self.shop, status="paused", apply_to_all_services=True
        )

        # Get active discounts
        url = reverse("servicediscount-active")
        response = self.client.get(url, {"shop_id": str(self.shop.id)})

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(active_discount.id))


class CouponViewSetTestCase(APITestCase):
    def setUp(self):
        # Create test user
        self.user = UserFactory(is_staff=True)  # Admin user for simplicity
        self.client.force_authenticate(user=self.user)

        # Create shop
        self.shop = ShopFactory()

        # Create service
        self.service = ServiceFactory(shop=self.shop)

        # Create customer
        self.customer = UserFactory(user_type="customer")

    def test_validate_coupon(self):
        """Test coupon validation endpoint"""
        # Create a valid coupon
        coupon = CouponFactory(
            shop=self.shop,
            discount_type="percentage",
            value=15,
            apply_to_all_services=True,
        )

        # Validate coupon
        url = reverse("coupon-validate")
        data = {
            "code": coupon.code,
            "service_id": str(self.service.id),
            "amount": "100.00",
        }

        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["coupon"]["id"], str(coupon.id))
        self.assertEqual(response.data["discount_amount"], "15.00")

        # Test invalid coupon
        data["code"] = "INVALID-CODE"
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["valid"])

    def test_generate_coupon(self):
        """Test coupon generation endpoint"""
        # Prepare data
        data = {
            "name": "Test Coupon",
            "discount_type": "percentage",
            "value": 20,
            "shop_id": str(self.shop.id),
            "start_date": timezone.now().isoformat(),
            "end_date": (timezone.now() + datetime.timedelta(days=30)).isoformat(),
            "is_single_use": True,
            "apply_to_all_services": True,
            "quantity": 1,
        }

        # Generate coupon
        url = reverse("coupon-generate")
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Test Coupon")
        self.assertEqual(response.data["discount_type"], "percentage")
        self.assertEqual(response.data["value"], "20.00")

        # Test bulk generation
        data["quantity"] = 3
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["coupons"]), 3)

    def test_apply_coupon(self):
        """Test coupon application endpoint"""
        # Create customer and authenticate
        self.client.force_authenticate(user=self.customer)

        # Create a booking
        booking = AppointmentFactory(customer=self.customer, shop=self.shop, service=self.service)

        # Create a valid coupon
        coupon = CouponFactory(
            shop=self.shop,
            discount_type="percentage",
            value=15,
            apply_to_all_services=True,
        )

        # Apply coupon
        url = reverse("coupon-apply")
        data = {"code": coupon.code, "booking_id": str(booking.id), "amount": "100.00"}

        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["discount_amount"], "15.00")
        self.assertEqual(response.data["final_amount"], "85.00")

        # Verify usage record was created
        usage = CouponUsage.objects.filter(coupon=coupon, customer=self.customer).first()
        self.assertIsNotNone(usage)


class PromotionalCampaignViewSetTestCase(APITestCase):
    def setUp(self):
        # Create test user
        self.user = UserFactory(is_staff=True)  # Admin user for simplicity
        self.client.force_authenticate(user=self.user)

        # Create shop
        self.shop = ShopFactory()

    def test_create_referral_campaign(self):
        """Test creating a referral campaign"""
        # Prepare data
        data = {"shop_id": str(self.shop.id), "discount_value": 15, "days_valid": 30}

        # Create campaign
        url = reverse("promotionalcampaign-create-referral")
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("campaign", response.data)
        self.assertIn("sample_coupon", response.data)

        # Verify campaign was created
        campaign_id = response.data["campaign"]["id"]
        campaign = PromotionalCampaign.objects.get(id=campaign_id)
        self.assertEqual(campaign.campaign_type, "referral")
        self.assertTrue(campaign.is_active)

        # Verify sample coupon was created and linked
        coupon_id = response.data["sample_coupon"]["id"]
        coupon = Coupon.objects.get(id=coupon_id)
        self.assertEqual(coupon.value, 15)
        self.assertTrue(campaign.coupons.filter(id=coupon.id).exists())


class DiscountCalculationViewSetTestCase(APITestCase):
    def setUp(self):
        # Create test user
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

        # Create shop
        self.shop = ShopFactory()

        # Create service
        self.service = ServiceFactory(shop=self.shop)

        # Create discount
        self.discount = ServiceDiscountFactory(
            shop=self.shop,
            discount_type="percentage",
            value=15,
            apply_to_all_services=True,
        )

        # Create coupon
        self.coupon = CouponFactory(
            shop=self.shop,
            discount_type="percentage",
            value=20,
            apply_to_all_services=True,
        )

    def test_calculate_discount(self):
        """Test discount calculation endpoint"""
        # Prepare data
        data = {
            "shop_id": str(self.shop.id),
            "service_id": str(self.service.id),
            "price": "100.00",
            "coupon_code": self.coupon.code,
        }

        # Calculate discount
        url = reverse("discount-calculation-calculate")
        response = self.client.post(url, data, format="json")

        # Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["original_price"], "100.00")
        self.assertEqual(response.data["discounted_price"], "80.00")  # 20% off for coupon
        self.assertEqual(response.data["discount_amount"], "20.00")
        self.assertIsNotNone(response.data["discount_info"])
        self.assertEqual(response.data["discount_info"]["type"], "coupon")

        # Test with combined discounts
        data["combine_discounts"] = True

        # Make both discount and coupon combinable
        self.discount.is_combinable = True
        self.discount.save()

        # Make coupon combinable
        self.coupon.is_combinable = True
        self.coupon.save()

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Coupon (20%) + Discount (15% of 80) = 20 + 12 = 32
        self.assertEqual(response.data["discounted_price"], "68.00")
        self.assertEqual(response.data["total_discount"], "32.00")
        self.assertEqual(len(response.data["discount_breakdown"]), 2)
