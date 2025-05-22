# apps/discountapp/serializers.py
from django.utils import timezone
from rest_framework import serializers

from apps.discountapp.models import (
    Coupon,
    CouponUsage,
    PromotionalCampaign,
    ServiceDiscount,
)
from apps.discountapp.validators import (
    validate_coupon_code,
    validate_date_range,
    validate_fixed_discount,
    validate_min_purchase_amount,
    validate_percentage_discount,
)


class ServiceDiscountSerializer(serializers.ModelSerializer):
    services = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    categories = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = ServiceDiscount
        fields = [
            "id",
            "name",
            "description",
            "discount_type",
            "value",
            "max_discount_amount",
            "min_purchase_amount",
            "start_date",
            "end_date",
            "usage_limit",
            "used_count",
            "status",
            "is_combinable",
            "priority",
            "shop",
            "services",
            "categories",
            "apply_to_all_services",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "used_count", "status", "created_at", "updated_at"]

    def validate(self, data):
        """
        Validate model fields
        """
        discount_type = data.get("discount_type")
        value = data.get("value")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        min_purchase_amount = data.get("min_purchase_amount")

        # Validate discount value based on type
        if discount_type == "percentage":
            validate_percentage_discount(value)
        else:
            validate_fixed_discount(value)

        # Validate date range
        if start_date and end_date:
            validate_date_range(start_date, end_date)

        # Validate minimum purchase amount
        if min_purchase_amount is not None:
            validate_min_purchase_amount(min_purchase_amount)

        return data


class CouponSerializer(serializers.ModelSerializer):
    services = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    categories = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "name",
            "description",
            "discount_type",
            "value",
            "max_discount_amount",
            "min_purchase_amount",
            "start_date",
            "end_date",
            "usage_limit",
            "used_count",
            "status",
            "is_combinable",
            "priority",
            "shop",
            "is_single_use",
            "requires_authentication",
            "is_referral",
            "referred_by",
            "services",
            "categories",
            "apply_to_all_services",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "used_count", "status", "created_at", "updated_at"]

    def validate_code(self, value):
        """
        Validate coupon code format
        """
        return validate_coupon_code(value)

    def validate(self, data):
        """
        Validate model fields
        """
        discount_type = data.get("discount_type")
        value = data.get("value")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        min_purchase_amount = data.get("min_purchase_amount")

        # Validate discount value based on type
        if discount_type == "percentage":
            validate_percentage_discount(value)
        else:
            validate_fixed_discount(value)

        # Validate date range
        if start_date and end_date:
            validate_date_range(start_date, end_date)

        # Validate minimum purchase amount
        if min_purchase_amount is not None:
            validate_min_purchase_amount(min_purchase_amount)

        return data


class CouponUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CouponUsage
        fields = ["id", "coupon", "customer", "used_at", "booking", "amount"]
        read_only_fields = ["id", "used_at"]


class PromotionalCampaignSerializer(serializers.ModelSerializer):
    coupons = CouponSerializer(many=True, read_only=True)
    service_discounts = ServiceDiscountSerializer(many=True, read_only=True)

    class Meta:
        model = PromotionalCampaign
        fields = [
            "id",
            "name",
            "description",
            "campaign_type",
            "start_date",
            "end_date",
            "is_active",
            "coupons",
            "service_discounts",
            "shop",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        """
        Validate model fields
        """
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        # Validate date range
        if start_date and end_date:
            validate_date_range(start_date, end_date)

        return data


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    service_id = serializers.UUIDField(required=False)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class CouponApplySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20)
    booking_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class CouponGenerateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    discount_type = serializers.ChoiceField(choices=["percentage", "fixed"])
    value = serializers.DecimalField(max_digits=10, decimal_places=2)
    shop_id = serializers.UUIDField()
    start_date = serializers.DateTimeField(default=timezone.now)
    end_date = serializers.DateTimeField()
    usage_limit = serializers.IntegerField(default=0)
    is_single_use = serializers.BooleanField(default=False)
    apply_to_all_services = serializers.BooleanField(default=False)
    service_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    category_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    quantity = serializers.IntegerField(default=1, min_value=1, max_value=1000)


class DiscountCalculationSerializer(serializers.Serializer):
    service_id = serializers.UUIDField(required=False)
    shop_id = serializers.UUIDField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    coupon_code = serializers.CharField(max_length=20, required=False)
    combine_discounts = serializers.BooleanField(default=False)
