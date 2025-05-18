# apps/discountapp/tests/factories.py
import datetime
import uuid

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.authapp.tests.factories import UserFactory
from apps.bookingapp.tests.factories import AppointmentFactory
from apps.discountapp.models import Coupon, CouponUsage, PromotionalCampaign, ServiceDiscount
from apps.shopapp.tests.factories import ShopFactory


class ServiceDiscountFactory(DjangoModelFactory):
    class Meta:
        model = ServiceDiscount

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Test Discount {n}")
    description = factory.Faker("paragraph")
    discount_type = "percentage"
    value = factory.Faker("random_int", min=5, max=50)
    max_discount_amount = None
    min_purchase_amount = 0
    start_date = factory.LazyFunction(lambda: timezone.now())
    end_date = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=30))
    usage_limit = 0
    used_count = 0
    status = "active"
    is_combinable = False
    priority = 0
    shop = factory.SubFactory(ShopFactory)
    apply_to_all_services = True

    @factory.post_generation
    def services(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.services.add(*extracted)

    @factory.post_generation
    def categories(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.categories.add(*extracted)


class CouponFactory(DjangoModelFactory):
    class Meta:
        model = Coupon

    id = factory.LazyFunction(uuid.uuid4)
    code = factory.Sequence(lambda n: f"TEST-COUPON-{n:04d}")
    name = factory.Sequence(lambda n: f"Test Coupon {n}")
    description = factory.Faker("paragraph")
    discount_type = "percentage"
    value = factory.Faker("random_int", min=5, max=50)
    max_discount_amount = None
    min_purchase_amount = 0
    start_date = factory.LazyFunction(lambda: timezone.now())
    end_date = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=30))
    usage_limit = 1
    used_count = 0
    status = "active"
    is_combinable = False
    priority = 0
    shop = factory.SubFactory(ShopFactory)
    is_single_use = True
    requires_authentication = True
    is_referral = False
    referred_by = None
    apply_to_all_services = True

    @factory.post_generation
    def services(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.services.add(*extracted)

    @factory.post_generation
    def categories(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.categories.add(*extracted)


class CouponUsageFactory(DjangoModelFactory):
    class Meta:
        model = CouponUsage

    id = factory.LazyFunction(uuid.uuid4)
    coupon = factory.SubFactory(CouponFactory)
    customer = factory.SubFactory(UserFactory)
    used_at = factory.LazyFunction(timezone.now)
    booking = factory.SubFactory(AppointmentFactory)
    amount = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)


class PromotionalCampaignFactory(DjangoModelFactory):
    class Meta:
        model = PromotionalCampaign

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Test Campaign {n}")
    description = factory.Faker("paragraph")
    campaign_type = factory.Iterator(
        ["holiday", "seasonal", "flash_sale", "product_launch", "loyalty", "referral"]
    )
    start_date = factory.LazyFunction(lambda: timezone.now())
    end_date = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=30))
    is_active = True
    shop = factory.SubFactory(ShopFactory)

    @factory.post_generation
    def coupons(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.coupons.add(*extracted)

    @factory.post_generation
    def service_discounts(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.service_discounts.add(*extracted)
