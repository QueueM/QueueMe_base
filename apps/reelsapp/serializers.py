from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.authapp.serializers import UserSimpleSerializer
from apps.categoriesapp.serializers import CategorySimpleSerializer
from apps.geoapp.services.distance_service import DistanceService
from apps.geoapp.services.travel_time_service import TravelTimeService
from apps.packageapp.serializers import PackageListSerializer
from apps.serviceapp.serializers import ServiceListSerializer
from apps.shopapp.serializers import ShopSimpleSerializer

from .models import Reel, ReelComment, ReelReport, ReelShare, ReelView


class ReelViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReelView
        fields = ["id", "watch_duration", "watched_full", "created_at"]
        read_only_fields = ["id", "created_at"]


class ReelCommentSerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer(read_only=True)

    class Meta:
        model = ReelComment
        fields = ["id", "user", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class ReelShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReelShare
        fields = ["id", "share_type", "created_at"]
        read_only_fields = ["id", "created_at"]


class ReelReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReelReport
        fields = ["id", "reason", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


class ReelSerializer(serializers.ModelSerializer):
    shop = ShopSimpleSerializer(read_only=True)
    categories = CategorySimpleSerializer(many=True, read_only=True)
    services = ServiceListSerializer(many=True, read_only=True)
    packages = PackageListSerializer(many=True, read_only=True)
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    shares_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Reel
        fields = [
            "id",
            "shop",
            "title",
            "caption",
            "video",
            "thumbnail",
            "duration",
            "status",
            "categories",
            "services",
            "packages",
            "view_count",
            "likes_count",
            "comments_count",
            "shares_count",
            "is_liked",
            "created_at",
            "published_at",
        ]
        read_only_fields = [
            "id",
            "view_count",
            "likes_count",
            "comments_count",
            "shares_count",
            "is_liked",
            "created_at",
            "published_at",
        ]

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_shares_count(self, obj):
        return obj.shares.count()

    def get_is_liked(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False


class ReelDetailSerializer(ReelSerializer):
    comments = serializers.SerializerMethodField()

    class Meta(ReelSerializer.Meta):
        fields = ReelSerializer.Meta.fields + ["comments"]

    def get_comments(self, obj):
        # Get top comments (limited to 5)
        comments = obj.comments.filter(is_hidden=False).order_by("-created_at")[:5]
        return ReelCommentSerializer(comments, many=True, context=self.context).data


class ReelCreateUpdateSerializer(serializers.ModelSerializer):
    category_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True
    )
    service_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True
    )
    package_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True
    )

    class Meta:
        model = Reel
        fields = [
            "title",
            "caption",
            "video",
            "thumbnail",
            "status",
            "category_ids",
            "service_ids",
            "package_ids",
        ]

    def validate(self, data):
        # Ensure at least one service or package is linked if publishing
        if data.get("status") == "published":
            service_ids = data.get("service_ids", [])
            package_ids = data.get("package_ids", [])

            if not service_ids and not package_ids:
                raise serializers.ValidationError(
                    {
                        "service_ids": _(
                            "At least one service or package must be linked when publishing a reel."
                        )
                    }
                )

        return data

    def create(self, validated_data):
        category_ids = validated_data.pop("category_ids", [])
        service_ids = validated_data.pop("service_ids", [])
        package_ids = validated_data.pop("package_ids", [])

        request = self.context.get("request")
        shop_id = request.parser_context.get("kwargs", {}).get("shop_id")

        from apps.shopapp.models import Shop

        shop = Shop.objects.get(id=shop_id)
        validated_data["shop"] = shop

        # Set city from shop's location
        if shop.location:
            validated_data["city"] = shop.location.city

        # Create reel instance
        reel = Reel.objects.create(**validated_data)

        # Add categories, services, and packages
        if category_ids:
            reel.categories.add(*category_ids)

        if service_ids:
            reel.services.add(*service_ids)

        if package_ids:
            reel.packages.add(*package_ids)

        return reel

    def update(self, instance, validated_data):
        category_ids = validated_data.pop("category_ids", None)
        service_ids = validated_data.pop("service_ids", None)
        package_ids = validated_data.pop("package_ids", None)

        # Update reel fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Update relationships if provided
        if category_ids is not None:
            instance.categories.clear()
            instance.categories.add(*category_ids)

        if service_ids is not None:
            instance.services.clear()
            instance.services.add(*service_ids)

        if package_ids is not None:
            instance.packages.clear()
            instance.packages.add(*package_ids)

        return instance


class ReelFeedSerializer(serializers.ModelSerializer):
    shop = ShopSimpleSerializer(read_only=True)
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    shares_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    linked_services = serializers.SerializerMethodField()
    linked_packages = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()
    travel_time = serializers.SerializerMethodField()

    class Meta:
        model = Reel
        fields = [
            "id",
            "shop",
            "title",
            "caption",
            "video",
            "thumbnail",
            "duration",
            "view_count",
            "likes_count",
            "comments_count",
            "shares_count",
            "is_liked",
            "created_at",
            "published_at",
            "linked_services",
            "linked_packages",
            "distance",
            "travel_time",
        ]

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_shares_count(self, obj):
        return obj.shares.count()

    def get_is_liked(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_linked_services(self, obj):
        """Get formatted linked services with essential information"""
        services = obj.services.all()[:3]  # Limit to 3 services
        result = []

        request = self.context.get("request")
        user_location = None
        if request and hasattr(request, "query_params"):
            lat = request.query_params.get("lat")
            lng = request.query_params.get("lng")
            if lat and lng:
                user_location = {"latitude": float(lat), "longitude": float(lng)}

        for service in services:
            service_data = {
                "id": service.id,
                "name": service.name,
                "image": service.image.url if service.image else None,
                "price": service.price,
                "city": service.shop.location.city if service.shop.location else None,
                "service_location": service.get_service_location_display(),
            }

            # Add distance and travel time if user location is available
            if user_location and service.shop.location:
                shop_location = {
                    "latitude": service.shop.location.latitude,
                    "longitude": service.shop.location.longitude,
                }
                service_data["distance"] = DistanceService.calculate_distance(
                    user_location, shop_location
                )
                service_data["travel_time"] = TravelTimeService.estimate_travel_time(
                    user_location, shop_location
                )

            result.append(service_data)

        return result

    def get_linked_packages(self, obj):
        """Get formatted linked packages with essential information"""
        packages = obj.packages.all()[:3]  # Limit to 3 packages
        result = []

        request = self.context.get("request")
        user_location = None
        if request and hasattr(request, "query_params"):
            lat = request.query_params.get("lat")
            lng = request.query_params.get("lng")
            if lat and lng:
                user_location = {"latitude": float(lat), "longitude": float(lng)}

        for package in packages:
            package_data = {
                "id": package.id,
                "name": package.name,
                "image": package.image.url if package.image else None,
                "price": package.price,
                "city": package.shop.location.city if package.shop.location else None,
                "service_location": (
                    package.get_service_location_display()
                    if hasattr(package, "get_service_location_display")
                    else None
                ),
            }

            # Add distance and travel time if user location is available
            if user_location and package.shop.location:
                shop_location = {
                    "latitude": package.shop.location.latitude,
                    "longitude": package.shop.location.longitude,
                }
                package_data["distance"] = DistanceService.calculate_distance(
                    user_location, shop_location
                )
                package_data["travel_time"] = TravelTimeService.estimate_travel_time(
                    user_location, shop_location
                )

            result.append(package_data)

        return result

    def get_distance(self, obj):
        """Calculate distance between user and shop in KM"""
        request = self.context.get("request")
        if not request or not hasattr(request, "query_params"):
            return None

        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")

        if not lat or not lng or not obj.shop.location:
            return None

        user_location = {"latitude": float(lat), "longitude": float(lng)}
        shop_location = {
            "latitude": obj.shop.location.latitude,
            "longitude": obj.shop.location.longitude,
        }

        return DistanceService.calculate_distance(user_location, shop_location)

    def get_travel_time(self, obj):
        """Estimate travel time in minutes"""
        request = self.context.get("request")
        if not request or not hasattr(request, "query_params"):
            return None

        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")

        if not lat or not lng or not obj.shop.location:
            return None

        user_location = {"latitude": float(lat), "longitude": float(lng)}
        shop_location = {
            "latitude": obj.shop.location.latitude,
            "longitude": obj.shop.location.longitude,
        }

        return TravelTimeService.estimate_travel_time(user_location, shop_location)
