# apps/discountapp/services/discount_service.py
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.discountapp.models import Coupon, ServiceDiscount


class DiscountService:
    @staticmethod
    @transaction.atomic
    def create_service_discount(shop, name, discount_type, value, start_date, end_date, **kwargs):
        """
        Create a service discount with the given parameters
        """
        # Create the discount
        discount = ServiceDiscount(
            shop=shop,
            name=name,
            discount_type=discount_type,
            value=value,
            start_date=start_date,
            end_date=end_date,
            **kwargs
        )

        discount.save()

        # Add services or categories if provided
        services = kwargs.get("services")
        if services:
            discount.services.set(services)

        categories = kwargs.get("categories")
        if categories:
            discount.categories.set(categories)

        return discount

    @staticmethod
    def get_active_discounts(shop, service=None):
        """
        Get active discounts for a shop and optionally a specific service
        """
        now = timezone.now()

        # Base query - active discounts within date range
        discounts = ServiceDiscount.objects.filter(
            shop=shop, status="active", start_date__lte=now, end_date__gte=now
        ).order_by("-priority")

        # If service is provided, filter for applicable discounts
        if service:
            category = service.category if service.category_id else None

            discounts = discounts.filter(
                Q(apply_to_all_services=True)
                | Q(services=service)
                | (Q(categories=category) if category else Q())
            ).distinct()

        return discounts

    @staticmethod
    def calculate_discount(price, service=None, shop=None, customer=None, coupon_code=None):
        """
        Calculate the best discount for a given price
        Returns (discounted_price, original_price, discount_info)
        """
        if price <= 0 or not shop:
            return price, price, None

        best_discount_amount = 0
        best_discount_info = None

        # First check if a coupon code is provided
        if coupon_code and customer:
            from apps.discountapp.services.coupon_service import CouponService

            is_valid, _, coupon = CouponService.validate_coupon(
                coupon_code,
                customer=customer,
                services=[service] if service else None,
                amount=price,
            )

            if is_valid and coupon:
                coupon_discount = coupon.calculate_discount_amount(price)

                if coupon_discount > best_discount_amount:
                    best_discount_amount = coupon_discount
                    best_discount_info = {
                        "type": "coupon",
                        "id": str(coupon.id),
                        "name": coupon.name,
                        "code": coupon.code,
                        "discount_type": coupon.discount_type,
                        "value": coupon.value,
                        "amount": best_discount_amount,
                    }

        # Then check service discounts if applicable
        if service and shop:
            applicable_discounts = DiscountService.get_active_discounts(shop, service)

            # Find the best discount based on priority and amount
            for discount in applicable_discounts:
                # Skip if not combinable with existing discount
                if (
                    best_discount_info
                    and best_discount_info["type"] == "coupon"
                    and not discount.is_combinable
                ):
                    continue

                discount_amount = discount.calculate_discount_amount(price)

                if discount_amount > best_discount_amount:
                    best_discount_amount = discount_amount
                    best_discount_info = {
                        "type": "service_discount",
                        "id": str(discount.id),
                        "name": discount.name,
                        "discount_type": discount.discount_type,
                        "value": discount.value,
                        "amount": best_discount_amount,
                    }

        # Calculate final price
        discounted_price = max(0, price - best_discount_amount)

        return discounted_price, price, best_discount_info

    @staticmethod
    def apply_multiple_discounts(price, service=None, shop=None, customer=None, coupon_code=None):
        """
        Apply multiple combinable discounts to a price
        Returns (discounted_price, original_price, discount_breakdown)
        """
        if price <= 0 or not shop:
            return price, price, []

        discount_breakdown = []
        remaining_price = price

        # First apply coupon if provided
        if coupon_code and customer:
            from apps.discountapp.services.coupon_service import CouponService

            is_valid, _, coupon = CouponService.validate_coupon(
                coupon_code,
                customer=customer,
                services=[service] if service else None,
                amount=price,
            )

            if is_valid and coupon:
                coupon_discount = coupon.calculate_discount_amount(price)

                if coupon_discount > 0:
                    discount_breakdown.append(
                        {
                            "type": "coupon",
                            "id": str(coupon.id),
                            "name": coupon.name,
                            "code": coupon.code,
                            "discount_type": coupon.discount_type,
                            "value": coupon.value,
                            "amount": coupon_discount,
                        }
                    )

                    remaining_price -= coupon_discount

        # Then apply service discounts if applicable
        if service and shop:
            applicable_discounts = DiscountService.get_active_discounts(shop, service)

            # Filter to only include combinable discounts if we already have a coupon discount
            if discount_breakdown:
                applicable_discounts = [d for d in applicable_discounts if d.is_combinable]

            # Apply discounts in order of priority
            for discount in applicable_discounts:
                discount_amount = discount.calculate_discount_amount(price)

                if discount_amount > 0:
                    # Make sure not to discount below 0
                    actual_discount = min(remaining_price, discount_amount)

                    if actual_discount > 0:
                        discount_breakdown.append(
                            {
                                "type": "service_discount",
                                "id": str(discount.id),
                                "name": discount.name,
                                "discount_type": discount.discount_type,
                                "value": discount.value,
                                "amount": actual_discount,
                            }
                        )

                        remaining_price -= actual_discount

                        # Stop if price is reduced to 0
                        if remaining_price <= 0:
                            break

        total_discount = sum(d["amount"] for d in discount_breakdown)
        discounted_price = max(0, price - total_discount)

        return discounted_price, price, discount_breakdown

    @staticmethod
    def update_discount_statuses():
        """
        Update status of all discounts based on current date and usage limits
        """
        now = timezone.now()

        # Update ServiceDiscount statuses
        service_discounts = ServiceDiscount.objects.filter(
            Q(status="active") | Q(status="scheduled")
        )

        for discount in service_discounts:
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

        # Update Coupon statuses
        coupons = Coupon.objects.filter(Q(status="active") | Q(status="scheduled"))

        for coupon in coupons:
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
