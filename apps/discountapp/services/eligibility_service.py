# apps/discountapp/services/eligibility_service.py

from apps.discountapp.constants import ERROR_CODE_NOT_ELIGIBLE
from apps.discountapp.models import Coupon, CouponUsage


class EligibilityService:
    @staticmethod
    def check_service_eligibility(service, discount):
        """
        Check if a service is eligible for a discount
        """
        # If discount applies to all services, it's eligible
        if discount.apply_to_all_services:
            return True

        # Check if service is directly linked to discount
        if service in discount.services.all():
            return True

        # Check if service's category is linked to discount
        if service.category and service.category in discount.categories.all():
            return True

        return False

    @staticmethod
    def check_customer_eligibility(customer, discount_or_coupon):
        """
        Check if a customer is eligible for a discount or coupon
        """
        if not customer:
            # If discount requires authentication, customer is required
            if (
                hasattr(discount_or_coupon, "requires_authentication")
                and discount_or_coupon.requires_authentication
            ):
                return False, ERROR_CODE_NOT_ELIGIBLE
            return True, None

        # For coupons, check single use restriction
        if isinstance(discount_or_coupon, Coupon) and discount_or_coupon.is_single_use:
            used = CouponUsage.objects.filter(coupon=discount_or_coupon, customer=customer).exists()
            if used:
                return False, ERROR_CODE_NOT_ELIGIBLE

        return True, None

    @staticmethod
    def get_eligible_discounts(service, shop=None, customer=None):
        """
        Get all discounts eligible for a service/shop/customer combination
        """
        if not service:
            return []

        if not shop:
            shop = service.shop

        # Get active discounts for the shop
        from apps.discountapp.services.discount_service import DiscountService

        active_discounts = DiscountService.get_active_discounts(shop)

        # Filter discounts by service eligibility
        eligible_discounts = []
        for discount in active_discounts:
            if EligibilityService.check_service_eligibility(service, discount):
                if customer:
                    is_eligible, _ = EligibilityService.check_customer_eligibility(
                        customer, discount
                    )
                    if is_eligible:
                        eligible_discounts.append(discount)
                else:
                    eligible_discounts.append(discount)

        return eligible_discounts

    @staticmethod
    def get_eligible_coupons(customer, service=None, shop=None):
        """
        Get all coupons eligible for a customer/service/shop combination
        """
        if not customer:
            return []

        if service and not shop:
            shop = service.shop

        if not shop:
            return []

        # Get active coupons for the shop
        from apps.discountapp.services.coupon_service import CouponService

        active_coupons = CouponService.get_available_coupons(shop=shop, customer=customer)

        # Filter coupons by service eligibility if service is provided
        if service:
            eligible_coupons = []
            for coupon in active_coupons:
                if (
                    coupon.apply_to_all_services
                    or service in coupon.services.all()
                    or (service.category and service.category in coupon.categories.all())
                ):
                    eligible_coupons.append(coupon)
            return eligible_coupons

        return active_coupons
