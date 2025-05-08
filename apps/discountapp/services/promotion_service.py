# apps/discountapp/services/promotion_service.py
from django.db import transaction
from django.utils import timezone

from apps.discountapp.models import PromotionalCampaign
from apps.discountapp.services.coupon_service import CouponService
from apps.discountapp.services.discount_service import DiscountService


class PromotionService:
    @staticmethod
    @transaction.atomic
    def create_campaign(shop, name, campaign_type, start_date, end_date, **kwargs):
        """
        Create a promotional campaign with optional associated discounts/coupons
        """
        # Create the campaign
        campaign = PromotionalCampaign(
            shop=shop,
            name=name,
            campaign_type=campaign_type,
            start_date=start_date,
            end_date=end_date,
            description=kwargs.get("description", ""),
            is_active=kwargs.get("is_active", True),
        )

        campaign.save()

        # Add existing discounts/coupons if provided
        existing_coupons = kwargs.get("coupons")
        if existing_coupons:
            campaign.coupons.set(existing_coupons)

        existing_discounts = kwargs.get("service_discounts")
        if existing_discounts:
            campaign.service_discounts.set(existing_discounts)

        # Create new discounts/coupons if configuration provided
        new_discount_configs = kwargs.get("new_discounts", [])
        new_coupon_configs = kwargs.get("new_coupons", [])

        # Create service discounts
        new_discounts = []
        for config in new_discount_configs:
            discount = DiscountService.create_service_discount(
                shop=shop,
                name=config.get("name", f"{name} Discount"),
                discount_type=config.get("discount_type", "percentage"),
                value=config.get("value"),
                start_date=start_date,
                end_date=end_date,
                max_discount_amount=config.get("max_discount_amount"),
                min_purchase_amount=config.get("min_purchase_amount", 0),
                usage_limit=config.get("usage_limit", 0),
                is_combinable=config.get("is_combinable", False),
                priority=config.get("priority", 0),
                apply_to_all_services=config.get("apply_to_all_services", False),
                services=config.get("services", []),
                categories=config.get("categories", []),
            )
            new_discounts.append(discount)

        # Create coupons
        new_coupons = []
        for config in new_coupon_configs:
            # Single coupon
            if not config.get("bulk", False):
                coupon = CouponService.create_coupon(
                    shop=shop,
                    name=config.get("name", f"{name} Coupon"),
                    discount_type=config.get("discount_type", "percentage"),
                    value=config.get("value"),
                    start_date=start_date,
                    end_date=end_date,
                    code=config.get("code"),
                    max_discount_amount=config.get("max_discount_amount"),
                    min_purchase_amount=config.get("min_purchase_amount", 0),
                    usage_limit=config.get("usage_limit", 0),
                    is_combinable=config.get("is_combinable", False),
                    priority=config.get("priority", 0),
                    apply_to_all_services=config.get("apply_to_all_services", False),
                    is_single_use=config.get("is_single_use", False),
                    requires_authentication=config.get("requires_authentication", True),
                    is_referral=config.get("is_referral", False),
                    referred_by=config.get("referred_by"),
                    services=config.get("services", []),
                    categories=config.get("categories", []),
                )
                new_coupons.append(coupon)
            else:
                # Bulk coupons
                bulk_coupons = CouponService.generate_bulk_coupons(
                    shop=shop,
                    name_template=config.get("name_template", f"{name} Coupon {{i}}"),
                    discount_type=config.get("discount_type", "percentage"),
                    value=config.get("value"),
                    start_date=start_date,
                    end_date=end_date,
                    quantity=config.get("quantity", 1),
                    max_discount_amount=config.get("max_discount_amount"),
                    min_purchase_amount=config.get("min_purchase_amount", 0),
                    usage_limit=config.get(
                        "usage_limit", 1
                    ),  # Default to single use for bulk
                    is_combinable=config.get("is_combinable", False),
                    priority=config.get("priority", 0),
                    apply_to_all_services=config.get("apply_to_all_services", False),
                    is_single_use=config.get(
                        "is_single_use", True
                    ),  # Default to single use for bulk
                    requires_authentication=config.get("requires_authentication", True),
                    services=config.get("services", []),
                    categories=config.get("categories", []),
                )
                new_coupons.extend(bulk_coupons)

        # Add new discounts/coupons to campaign
        if new_discounts:
            campaign.service_discounts.add(*new_discounts)

        if new_coupons:
            campaign.coupons.add(*new_coupons)

        return campaign

    @staticmethod
    def get_active_campaigns(shop):
        """
        Get active campaigns for a shop
        """
        now = timezone.now()

        return PromotionalCampaign.objects.filter(
            shop=shop, is_active=True, start_date__lte=now, end_date__gte=now
        )

    @staticmethod
    def create_referral_campaign(shop, discount_value=10, days_valid=30):
        """
        Create or update a referral campaign for a shop
        Returns the campaign and a sample referral coupon
        """
        now = timezone.now()
        end_date = now.replace(year=now.year + 1)  # 1 year validity for campaign

        # Check if referral campaign already exists
        campaign = PromotionalCampaign.objects.filter(
            shop=shop, campaign_type="referral", is_active=True
        ).first()

        if not campaign:
            # Create a new referral campaign
            campaign = PromotionalCampaign.objects.create(
                shop=shop,
                name="Referral Program",
                description="Earn discounts by referring friends",
                campaign_type="referral",
                start_date=now,
                end_date=end_date,
                is_active=True,
            )

        # Create a sample referral coupon
        coupon_name = f"Referral Reward {discount_value}%"
        sample_coupon = CouponService.create_coupon(
            shop=shop,
            name=coupon_name,
            discount_type="percentage",
            value=discount_value,
            start_date=now,
            end_date=now + timezone.timedelta(days=days_valid),
            is_single_use=True,
            requires_authentication=True,
            is_referral=True,
            apply_to_all_services=True,
            usage_limit=1,
        )

        # Add to campaign
        campaign.coupons.add(sample_coupon)

        return campaign, sample_coupon

    @staticmethod
    def generate_referral_coupon(shop, referred_by, days_valid=30, discount_value=10):
        """
        Generate a referral coupon for a new customer
        """
        now = timezone.now()
        end_date = now + timezone.timedelta(days=days_valid)

        coupon = CouponService.create_coupon(
            shop=shop,
            name=f"Referral Discount {discount_value}%",
            discount_type="percentage",
            value=discount_value,
            start_date=now,
            end_date=end_date,
            is_single_use=True,
            requires_authentication=True,
            is_referral=True,
            referred_by=referred_by,
            apply_to_all_services=True,
            usage_limit=1,
        )

        # Find referral campaign and add the coupon to it
        campaign = PromotionalCampaign.objects.filter(
            shop=shop, campaign_type="referral", is_active=True
        ).first()

        if campaign:
            campaign.coupons.add(coupon)

        return coupon
