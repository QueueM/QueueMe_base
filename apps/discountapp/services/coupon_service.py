# apps/discountapp/services/coupon_service.py
import random
import string

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.discountapp.constants import (
    DEFAULT_COUPON_LENGTH,
    DEFAULT_COUPON_PREFIX,
    ERROR_CODE_ALREADY_USED,
    ERROR_CODE_AUTHENTICATION,
    ERROR_CODE_DATE_RANGE,
    ERROR_CODE_EXPIRED,
    ERROR_CODE_INVALID,
    ERROR_CODE_MIN_AMOUNT,
    ERROR_CODE_NOT_ELIGIBLE,
    ERROR_CODE_USAGE_LIMIT,
)
from apps.discountapp.models import Coupon, CouponUsage
from apps.discountapp.validators import validate_coupon_code


class CouponService:
    @staticmethod
    def generate_code(prefix=DEFAULT_COUPON_PREFIX, length=DEFAULT_COUPON_LENGTH):
        """
        Generate a unique coupon code with prefix and random characters
        """
        # Ensure prefix is uppercase
        prefix = prefix.upper()

        # Calculate random part length (subtract prefix length and 1 for the dash)
        random_length = max(4, length - len(prefix) - 1)

        # Generate random part
        characters = string.ascii_uppercase + string.digits
        random_part = "".join(random.choice(characters) for _ in range(random_length))

        # Combine prefix and random part
        code = f"{prefix}-{random_part}"

        # Validate the generated code
        try:
            validate_coupon_code(code)
        except Exception:
            # If validation fails, try again with a simpler code
            return CouponService.generate_code(prefix, length)

        # Check if code already exists
        if Coupon.objects.filter(code=code).exists():
            # If code exists, generate a new one
            return CouponService.generate_code(prefix, length)

        return code

    @staticmethod
    def create_coupon(shop, name, discount_type, value, start_date, end_date, **kwargs):
        """
        Create a new coupon with the given parameters
        """
        # Generate a unique code if not provided
        code = kwargs.get("code")
        if not code:
            code = CouponService.generate_code()

        # Create the coupon
        coupon = Coupon(
            shop=shop,
            name=name,
            code=code,
            discount_type=discount_type,
            value=value,
            start_date=start_date,
            end_date=end_date,
            **kwargs,
        )

        coupon.save()

        # Add services or categories if provided
        services = kwargs.get("services")
        if services:
            coupon.services.set(services)

        categories = kwargs.get("categories")
        if categories:
            coupon.categories.set(categories)

        return coupon

    @staticmethod
    def generate_bulk_coupons(
        shop,
        name_template,
        discount_type,
        value,
        start_date,
        end_date,
        quantity,
        **kwargs,
    ):
        """
        Generate multiple coupons with the same parameters but unique codes
        """
        coupons = []

        for i in range(quantity):
            name = name_template.format(i=i + 1)
            code = CouponService.generate_code()

            coupon = Coupon(
                shop=shop,
                name=name,
                code=code,
                discount_type=discount_type,
                value=value,
                start_date=start_date,
                end_date=end_date,
                **kwargs,
            )

            coupons.append(coupon)

        # Bulk create the coupons
        created_coupons = Coupon.objects.bulk_create(coupons)

        # Add services or categories if provided
        services = kwargs.get("services")
        categories = kwargs.get("categories")

        if services or categories:
            for coupon in created_coupons:
                if services:
                    coupon.services.set(services)
                if categories:
                    coupon.categories.set(categories)

        return created_coupons

    @staticmethod
    def validate_coupon(code, customer=None, services=None, amount=None):
        """
        Validate a coupon code for use with the given parameters
        Returns (is_valid, message, coupon_obj)
        """
        try:
            # Find the coupon
            try:
                coupon = Coupon.objects.get(code=code)
            except Coupon.DoesNotExist:
                return False, ERROR_CODE_INVALID, None

            # Check if the coupon is active
            if coupon.status != "active":
                return False, ERROR_CODE_EXPIRED, coupon

            now = timezone.now()

            # Check date validity
            if not (coupon.start_date <= now <= coupon.end_date):
                return False, ERROR_CODE_DATE_RANGE, coupon

            # Check usage limit
            if coupon.usage_limit > 0 and coupon.used_count >= coupon.usage_limit:
                return False, ERROR_CODE_USAGE_LIMIT, coupon

            # Check if customer authentication is required
            if coupon.requires_authentication and customer is None:
                return False, ERROR_CODE_AUTHENTICATION, coupon

            # Check if the coupon is single-use and has been used by this customer
            if customer and coupon.is_single_use:
                if CouponUsage.objects.filter(
                    coupon=coupon, customer=customer
                ).exists():
                    return False, ERROR_CODE_ALREADY_USED, coupon

            # Check minimum purchase amount
            if amount is not None and amount < coupon.min_purchase_amount:
                return False, ERROR_CODE_MIN_AMOUNT, coupon

            # Check service eligibility
            if services and not coupon.apply_to_all_services:
                # Check if any of the provided services are eligible

                # First check if services are directly attached to the coupon
                service_ids = [service.id for service in services]
                coupon_service_ids = coupon.services.values_list("id", flat=True)

                if not any(sid in coupon_service_ids for sid in service_ids):
                    # If no direct service match, check categories
                    service_category_ids = set()
                    for service in services:
                        if service.category_id:
                            service_category_ids.add(service.category_id)

                    coupon_category_ids = coupon.categories.values_list("id", flat=True)

                    if not any(
                        cid in coupon_category_ids for cid in service_category_ids
                    ):
                        return False, ERROR_CODE_NOT_ELIGIBLE, coupon

            # Coupon is valid
            return True, None, coupon

        except Exception as e:
            # Log the error
            print(f"Error validating coupon: {e}")
            return False, ERROR_CODE_INVALID, None

    @staticmethod
    @transaction.atomic
    def apply_coupon(code, customer, booking, amount):
        """
        Apply a coupon to a booking
        Returns (success, message, discount_amount)
        """
        if not booking or not customer:
            return False, ERROR_CODE_INVALID, 0

        # Validate the coupon
        is_valid, message, coupon = CouponService.validate_coupon(
            code,
            customer=customer,
            services=[booking.service] if booking.service else None,
            amount=amount,
        )

        if not is_valid:
            return False, message, 0

        # Calculate discount
        discount_amount = coupon.calculate_discount_amount(amount)

        if discount_amount <= 0:
            return False, ERROR_CODE_MIN_AMOUNT, 0

        # Record coupon usage
        CouponUsage.objects.create(
            coupon=coupon, customer=customer, booking=booking, amount=discount_amount
        )

        # Increment coupon usage counter
        coupon.increment_usage()

        return True, None, discount_amount

    @staticmethod
    def get_available_coupons(shop=None, customer=None, services=None):
        """
        Get available (valid) coupons for a customer and/or shop and/or services
        """
        now = timezone.now()

        # Base query - active coupons within date range
        coupons = Coupon.objects.filter(
            status="active", start_date__lte=now, end_date__gte=now
        )

        # Filter by shop if provided
        if shop:
            coupons = coupons.filter(shop=shop)

        # Further filtering logic for services
        if services:
            service_ids = [service.id for service in services]
            category_ids = set()
            for service in services:
                if service.category_id:
                    category_ids.add(service.category_id)

            # Get coupons that apply to all services OR to specific services/categories
            coupons = coupons.filter(
                Q(apply_to_all_services=True)
                | Q(services__id__in=service_ids)
                | Q(categories__id__in=category_ids)
            ).distinct()

        # Filter single-use coupons for customer
        if customer:
            # Exclude single-use coupons that the customer has already used
            used_coupon_ids = CouponUsage.objects.filter(
                customer=customer, coupon__is_single_use=True
            ).values_list("coupon_id", flat=True)

            coupons = coupons.exclude(id__in=used_coupon_ids)

        return coupons
