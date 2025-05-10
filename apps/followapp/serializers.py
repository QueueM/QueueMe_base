from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.shopapp.models import Shop
from apps.shopapp.serializers import ShopCardSerializer

from .models import Follow, FollowEvent, FollowStats


class FollowSerializer(serializers.ModelSerializer):
    shop_details = ShopCardSerializer(source="shop", read_only=True)

    class Meta:
        model = Follow
        fields = ["id", "shop", "shop_details", "created_at", "notification_preference"]
        read_only_fields = ["id", "created_at"]

    def validate(self, data):
        # Validate that customer and shop are in the same city
        customer = self.context["request"].user
        shop = data.get("shop")

        if shop and customer.city and shop.location and shop.location.city:
            if customer.city != shop.location.city:
                raise serializers.ValidationError(
                    {"shop": _("You can only follow shops in your city.")}
                )

        return data

    def create(self, validated_data):
        # Set the customer to the current user
        validated_data["customer"] = self.context["request"].user
        return super().create(validated_data)


class FollowStatusSerializer(serializers.Serializer):
    is_following = serializers.BooleanField(read_only=True)
    follower_count = serializers.IntegerField(read_only=True)


class FollowStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowStats
        fields = [
            "follower_count",
            "weekly_growth",
            "monthly_growth",
            "last_calculated",
        ]
        read_only_fields = fields


class ShopFollowersSerializer(serializers.ModelSerializer):
    follower_count = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = ["id", "name", "avatar", "follower_count"]
        read_only_fields = fields

    def get_follower_count(self, obj):
        try:
            return obj.follow_stats.follower_count
        except Exception:
            return 0


class FollowEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowEvent
        fields = ["id", "customer", "shop", "event_type", "timestamp", "source"]
        read_only_fields = fields
