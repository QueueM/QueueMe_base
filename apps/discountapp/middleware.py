# apps/discountapp/middleware.py
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from apps.discountapp.models import Coupon, ServiceDiscount


class DiscountStatusMiddleware(MiddlewareMixin):
    """
    Middleware to automatically update the status of discounts and coupons
    based on current date and usage limits.
    This middleware only checks a small sample of discounts on each request
    to avoid performance issues, relying on the scheduled task for complete updates.
    """

    def process_request(self, request):
        """
        Randomly sample a few discounts and coupons to check their status
        """
        # Only check on every 100th request (approximate) to reduce DB load
        import random

        if random.random() > 0.01:
            return None

        now = timezone.now()

        # Check a sample of active or scheduled discounts
        service_discounts = ServiceDiscount.objects.filter(
            status__in=["active", "scheduled"]
        ).order_by("?")[
            :5
        ]  # Random sampling

        for discount in service_discounts:
            # Update status based on current date and usage
            if discount.start_date <= now <= discount.end_date:
                if discount.usage_limit > 0 and discount.used_count >= discount.usage_limit:
                    discount.status = "expired"
                else:
                    discount.status = "active"
            elif now < discount.start_date:
                discount.status = "scheduled"
            elif now > discount.end_date:
                discount.status = "expired"

            discount.save(update_fields=["status"])

        # Check a sample of active or scheduled coupons
        coupons = Coupon.objects.filter(status__in=["active", "scheduled"]).order_by("?")[
            :5
        ]  # Random sampling

        for coupon in coupons:
            # Update status based on current date and usage
            if coupon.start_date <= now <= coupon.end_date:
                if coupon.usage_limit > 0 and coupon.used_count >= coupon.usage_limit:
                    coupon.status = "expired"
                else:
                    coupon.status = "active"
            elif now < coupon.start_date:
                coupon.status = "scheduled"
            elif now > coupon.end_date:
                coupon.status = "expired"

            coupon.save(update_fields=["status"])

        return None
