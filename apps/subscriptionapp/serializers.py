# apps/subscriptionapp/serializers.py
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.companiesapp.models import Company
from apps.subscriptionapp.utils.billing_utils import calculate_period_price

from .models import FeatureUsage, Plan, PlanFeature, Subscription, SubscriptionInvoice


class PlanFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanFeature
        fields = [
            "id",
            "name",
            "name_ar",
            "description",
            "description_ar",
            "category",
            "tier",
            "value",
            "is_available",
        ]


class PlanSerializer(serializers.ModelSerializer):
    features = PlanFeatureSerializer(many=True, read_only=True)
    monthly_price_display = serializers.SerializerMethodField()
    quarterly_price = serializers.SerializerMethodField()
    semi_annual_price = serializers.SerializerMethodField()
    annual_price = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "name_ar",
            "description",
            "description_ar",
            "monthly_price",
            "monthly_price_display",
            "quarterly_price",
            "semi_annual_price",
            "annual_price",
            "max_shops",
            "max_services_per_shop",
            "max_specialists_per_shop",
            "is_active",
            "is_featured",
            "features",
        ]

    def get_monthly_price_display(self, obj):
        return f"{obj.monthly_price} SAR/{_('month')}"

    def get_quarterly_price(self, obj):
        return calculate_period_price(obj.monthly_price, "quarterly")

    def get_semi_annual_price(self, obj):
        return calculate_period_price(obj.monthly_price, "semi_annual")

    def get_annual_price(self, obj):
        return calculate_period_price(obj.monthly_price, "annual")


class PlanCreateUpdateSerializer(serializers.ModelSerializer):
    features = PlanFeatureSerializer(many=True, required=False)

    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "name_ar",
            "description",
            "description_ar",
            "monthly_price",
            "max_shops",
            "max_services_per_shop",
            "max_specialists_per_shop",
            "is_active",
            "is_featured",
            "position",
            "features",
        ]

    def create(self, validated_data):
        features_data = validated_data.pop("features", [])
        plan = Plan.objects.create(**validated_data)

        for feature_data in features_data:
            PlanFeature.objects.create(plan=plan, **feature_data)

        return plan

    def update(self, instance, validated_data):
        features_data = validated_data.pop("features", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if features_data is not None:
            # Clear existing features and recreate
            instance.features.all().delete()

            for feature_data in features_data:
                PlanFeature.objects.create(plan=instance, **feature_data)

        return instance


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_details = PlanSerializer(source="plan", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    is_trial_active = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "id",
            "company",
            "company_name",
            "plan",
            "plan_details",
            "status",
            "period",
            "start_date",
            "end_date",
            "auto_renew",
            "created_at",
            "updated_at",
            "canceled_at",
            "trial_end",
            "current_period_start",
            "current_period_end",
            "moyasar_id",
            "plan_name",
            "max_shops",
            "max_services_per_shop",
            "max_specialists_per_shop",
            "is_trial_active",
            "days_remaining",
        ]
        read_only_fields = [
            "id",
            "moyasar_id",
            "created_at",
            "updated_at",
            "start_date",
            "end_date",
            "canceled_at",
            "trial_end",
            "current_period_start",
            "current_period_end",
            "plan_name",
            "max_shops",
            "max_services_per_shop",
            "max_specialists_per_shop",
        ]

    def get_is_trial_active(self, obj):
        return obj.is_in_trial()

    def get_days_remaining(self, obj):
        return obj.days_remaining()


class SubscriptionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["company", "plan", "period", "auto_renew"]

    def validate_company(self, value):
        # Check if company already has an active subscription
        existing = Subscription.objects.filter(
            company=value, status__in=["active", "trial"]
        ).first()

        if existing:
            raise serializers.ValidationError(
                _("Company already has an active subscription")
            )

        return value

    def validate(self, data):
        # Ensure company and plan are provided
        if "company" not in data:
            raise serializers.ValidationError(_("Company is required"))

        if "plan" not in data:
            raise serializers.ValidationError(_("Subscription plan is required"))

        return data

    def create(self, validated_data):
        from apps.subscriptionapp.services.subscription_service import (
            SubscriptionService,
        )

        # Create subscription via service
        subscription = SubscriptionService.create_subscription(
            company_id=validated_data["company"].id,
            plan_id=validated_data["plan"].id,
            period=validated_data.get("period", "monthly"),
            auto_renew=validated_data.get("auto_renew", True),
        )

        return subscription


class SubscriptionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["plan", "period", "auto_renew", "status"]

    def validate_status(self, value):
        # Only admins can change certain statuses
        if value in ["active", "trial"] and not self.context["request"].user.is_staff:
            raise serializers.ValidationError(
                _("You don't have permission to set this status")
            )

        return value

    def update(self, instance, validated_data):
        from apps.subscriptionapp.services.subscription_service import (
            SubscriptionService,
        )

        # Track old status for change detection
        old_status = instance.status

        # Update fields that don't need special handling
        for field in ["auto_renew"]:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        # Handle plan change if present
        if "plan" in validated_data and validated_data["plan"] != instance.plan:
            SubscriptionService.change_plan(
                subscription_id=instance.id, new_plan_id=validated_data["plan"].id
            )

        # Handle period change if present
        if "period" in validated_data and validated_data["period"] != instance.period:
            SubscriptionService.change_period(
                subscription_id=instance.id, new_period=validated_data["period"]
            )

        # Handle status change if present
        if "status" in validated_data and validated_data["status"] != old_status:
            SubscriptionService.change_status(
                subscription_id=instance.id,
                new_status=validated_data["status"],
                performed_by=self.context["request"].user,
            )

        instance.save()
        return instance


class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(
        source="subscription.company.name", read_only=True
    )
    plan_name = serializers.CharField(source="subscription.plan_name", read_only=True)
    transaction_id = serializers.UUIDField(source="transaction.id", read_only=True)

    class Meta:
        model = SubscriptionInvoice
        fields = [
            "id",
            "subscription",
            "company_name",
            "plan_name",
            "invoice_number",
            "amount",
            "status",
            "period_start",
            "period_end",
            "issued_date",
            "due_date",
            "paid_date",
            "transaction_id",
        ]
        read_only_fields = [
            "id",
            "subscription",
            "invoice_number",
            "amount",
            "status",
            "period_start",
            "period_end",
            "issued_date",
            "due_date",
            "paid_date",
            "transaction_id",
        ]


class FeatureUsageSerializer(serializers.ModelSerializer):
    feature_category_display = serializers.CharField(
        source="get_feature_category_display", read_only=True
    )
    is_limit_reached = serializers.BooleanField(read_only=True)

    class Meta:
        model = FeatureUsage
        fields = [
            "id",
            "subscription",
            "feature_category",
            "feature_category_display",
            "limit",
            "current_usage",
            "last_updated",
            "is_limit_reached",
        ]
        read_only_fields = [
            "id",
            "subscription",
            "feature_category",
            "limit",
            "current_usage",
            "last_updated",
        ]


class SubscriptionPaymentSerializer(serializers.Serializer):
    """Serializer for initiating subscription payment"""

    company_id = serializers.UUIDField(required=True)
    plan_id = serializers.UUIDField(required=True)
    period = serializers.CharField(required=True)
    return_url = serializers.URLField(required=True)

    def validate_company_id(self, value):
        try:
            Company.objects.get(id=value)
        except Company.DoesNotExist:
            raise serializers.ValidationError("Company not found")
        return value

    def validate_plan_id(self, value):
        try:
            Plan.objects.get(id=value)
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Plan not found")
        return value

    def validate_period(self, value):
        valid_periods = ["monthly", "quarterly", "semi_annual", "annual"]
        if value not in valid_periods:
            raise serializers.ValidationError(
                f"Invalid period. Must be one of: {', '.join(valid_periods)}"
            )
        return value


class SubscriptionRenewalSerializer(serializers.Serializer):
    """Serializer for manual subscription renewal"""

    subscription_id = serializers.UUIDField(required=True)

    def validate_subscription_id(self, value):
        try:
            subscription = Subscription.objects.get(id=value)
            if subscription.status not in ["active", "past_due", "expired"]:
                raise serializers.ValidationError(
                    "Only active, past due, or expired subscriptions can be renewed"
                )
        except Subscription.DoesNotExist:
            raise serializers.ValidationError("Subscription not found")
        return value


class SubscriptionCancelSerializer(serializers.Serializer):
    """Serializer for canceling a subscription"""

    subscription_id = serializers.UUIDField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True)

    def validate_subscription_id(self, value):
        try:
            subscription = Subscription.objects.get(id=value)
            if subscription.status not in ["active", "trial", "past_due"]:
                raise serializers.ValidationError(
                    "Only active, trial, or past due subscriptions can be canceled"
                )
        except Subscription.DoesNotExist:
            raise serializers.ValidationError("Subscription not found")
        return value
