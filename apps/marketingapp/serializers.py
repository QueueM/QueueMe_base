"""
Serializers for Marketing app models.
"""

from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from .models import (
    AdClick,
    AdPayment,
    AdStatus,
    AdType,
    Advertisement,
    AdView,
    Campaign,
    TargetingType,
)


class CampaignSerializer(serializers.ModelSerializer):
    """Serializer for Campaign model"""

    ads_count = serializers.SerializerMethodField()
    shop_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "company",
            "company_name",
            "shop",
            "shop_name",
            "start_date",
            "end_date",
            "budget",
            "budget_spent",
            "is_active",
            "created_at",
            "updated_at",
            "ads_count",
        ]
        read_only_fields = ["budget_spent", "created_at", "updated_at"]

    def get_ads_count(self, obj):
        return obj.advertisements.count()

    def get_shop_name(self, obj):
        return obj.shop.name if obj.shop else None

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None


class AdvertisementSerializer(serializers.ModelSerializer):
    """Serializer for Advertisement model"""

    campaign_name = serializers.SerializerMethodField()
    targeting_cities = serializers.SerializerMethodField()
    targeting_categories = serializers.SerializerMethodField()
    linked_content_type = serializers.CharField(write_only=True, required=False, allow_null=True)
    linked_content_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    linked_object_info = serializers.SerializerMethodField()
    click_through_rate = serializers.SerializerMethodField()

    class Meta:
        model = Advertisement
        fields = [
            "id",
            "campaign",
            "campaign_name",
            "title",
            "description",
            "ad_type",
            "image",
            "video",
            "targeting_type",
            "targeting_cities",
            "targeting_categories",
            "linked_content_type",
            "linked_content_id",
            "linked_object_info",
            "cost_per_view",
            "cost_per_click",
            "status",
            "payment_date",
            "amount",
            "impression_count",
            "click_count",
            "conversion_count",
            "click_through_rate",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "impression_count",
            "click_count",
            "conversion_count",
            "created_at",
            "updated_at",
            "payment_date",
        ]

    def get_campaign_name(self, obj):
        return obj.campaign.name if obj.campaign else None

    def get_targeting_cities(self, obj):
        return [{"id": str(city.id), "name": city.name} for city in obj.target_cities.all()]

    def get_targeting_categories(self, obj):
        return [
            {"id": str(category.id), "name": category.name}
            for category in obj.target_categories.all()
        ]

    def get_linked_object_info(self, obj):
        if obj.content_type and obj.object_id:
            return {"type": obj.content_type.model, "id": str(obj.object_id)}
        return None

    def get_click_through_rate(self, obj):
        return round(obj.click_through_rate, 2) if obj.impression_count > 0 else 0

    def create(self, validated_data):
        # Handle linked content type
        linked_content_type = validated_data.pop("linked_content_type", None)
        linked_content_id = validated_data.pop("linked_content_id", None)

        if linked_content_type and linked_content_id:
            try:
                content_type = ContentType.objects.get(model=linked_content_type.lower())
                validated_data["content_type"] = content_type
                validated_data["object_id"] = linked_content_id
            except ContentType.DoesNotExist:
                pass

        # Handle target cities and categories
        target_cities = validated_data.pop("target_cities", [])
        target_categories = validated_data.pop("target_categories", [])

        # Create advertisement
        advertisement = super().create(validated_data)

        # Set many-to-many fields
        if target_cities:
            advertisement.target_cities.set(target_cities)

        if target_categories:
            advertisement.target_categories.set(target_categories)

        return advertisement

    def update(self, instance, validated_data):
        # Handle linked content type
        linked_content_type = validated_data.pop("linked_content_type", None)
        linked_content_id = validated_data.pop("linked_content_id", None)

        if linked_content_type and linked_content_id:
            try:
                content_type = ContentType.objects.get(model=linked_content_type.lower())
                validated_data["content_type"] = content_type
                validated_data["object_id"] = linked_content_id
            except ContentType.DoesNotExist:
                pass

        # Handle target cities and categories
        target_cities = validated_data.pop("target_cities", None)
        target_categories = validated_data.pop("target_categories", None)

        # Update advertisement
        advertisement = super().update(instance, validated_data)

        # Set many-to-many fields if provided
        if target_cities is not None:
            advertisement.target_cities.set(target_cities)

        if target_categories is not None:
            advertisement.target_categories.set(target_categories)

        return advertisement


class AdViewSerializer(serializers.ModelSerializer):
    """Serializer for AdView model"""

    class Meta:
        model = AdView
        fields = [
            "id",
            "advertisement",
            "user",
            "session_id",
            "ip_address",
            "city",
            "viewed_at",
            "view_duration",
        ]
        read_only_fields = ["viewed_at"]


class AdClickSerializer(serializers.ModelSerializer):
    """Serializer for AdClick model"""

    class Meta:
        model = AdClick
        fields = [
            "id",
            "advertisement",
            "user",
            "session_id",
            "ip_address",
            "city",
            "clicked_at",
            "referrer",
            "led_to_booking",
            "booking",
        ]
        read_only_fields = ["clicked_at"]


class AdPaymentSerializer(serializers.ModelSerializer):
    """Serializer for AdPayment model"""

    class Meta:
        model = AdPayment
        fields = [
            "id",
            "advertisement",
            "amount",
            "transaction_id",
            "payment_method",
            "payment_date",
            "status",
            "invoice_number",
        ]
        read_only_fields = ["payment_date", "invoice_number"]


class AdTypeChoiceSerializer(serializers.Serializer):
    """Serializer for AdType choices"""

    value = serializers.CharField()
    label = serializers.CharField()

    @classmethod
    def get_choices(cls):
        return [{"value": choice[0], "label": choice[1]} for choice in AdType.choices]


class AdStatusChoiceSerializer(serializers.Serializer):
    """Serializer for AdStatus choices"""

    value = serializers.CharField()
    label = serializers.CharField()

    @classmethod
    def get_choices(cls):
        return [{"value": choice[0], "label": choice[1]} for choice in AdStatus.choices]


class TargetingTypeChoiceSerializer(serializers.Serializer):
    """Serializer for TargetingType choices"""

    value = serializers.CharField()
    label = serializers.CharField()

    @classmethod
    def get_choices(cls):
        return [{"value": choice[0], "label": choice[1]} for choice in TargetingType.choices]
