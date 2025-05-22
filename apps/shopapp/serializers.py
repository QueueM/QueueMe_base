from rest_framework import serializers

from apps.authapp.serializers import UserSerializer
from apps.categoriesapp.serializers import CategorySerializer
from apps.companiesapp.serializers import CompanySerializer
from apps.geoapp.models import Location
from apps.geoapp.serializers import LocationSerializer

from .models import Shop, ShopFollower, ShopHours, ShopSettings, ShopVerification

# Existing serializer classes...


class ShopHoursSerializer(serializers.ModelSerializer):
    weekday_display = serializers.CharField(
        source="get_weekday_display", read_only=True
    )
    from_hour_display = serializers.SerializerMethodField()
    to_hour_display = serializers.SerializerMethodField()

    class Meta:
        model = ShopHours
        fields = [
            "id",
            "shop",
            "weekday",
            "weekday_display",
            "from_hour",
            "to_hour",
            "from_hour_display",
            "to_hour_display",
            "is_closed",
        ]
        read_only_fields = ["id"]

    def get_from_hour_display(self, obj):
        return obj.from_hour.strftime("%I:%M %p") if obj.from_hour else None

    def get_to_hour_display(self, obj):
        return obj.to_hour.strftime("%I:%M %p") if obj.to_hour else None


class ShopSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopSettings
        fields = [
            "id",
            "shop",
            "allow_booking",
            "allow_walk_ins",
            "enforce_check_in",
            "check_in_timeout_minutes",
            "grace_period_minutes",
            "cancellation_policy",
            "notification_preferences",
            "booking_lead_time_minutes",
            "booking_future_days",
            "auto_assign_specialist",
            "specialist_assignment_algorithm",
            "double_booking_allowed",
            "max_concurrent_bookings",
        ]
        read_only_fields = ["id", "shop"]


class ShopFollowerSerializer(serializers.ModelSerializer):
    customer_phone = serializers.CharField(
        source="customer.phone_number", read_only=True
    )

    class Meta:
        model = ShopFollower
        fields = ["id", "shop", "customer", "customer_phone", "created_at"]
        read_only_fields = ["id", "created_at"]


class ShopVerificationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    processed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ShopVerification
        fields = [
            "id",
            "shop",
            "status",
            "status_display",
            "submitted_at",
            "processed_at",
            "processed_by",
            "processed_by_name",
            "rejection_reason",
            "documents",
        ]
        read_only_fields = [
            "id",
            "submitted_at",
            "processed_at",
            "processed_by",
            "processed_by_name",
        ]

    def get_processed_by_name(self, obj):
        if obj.processed_by:
            return obj.processed_by.phone_number
        return None


class ShopSerializer(serializers.ModelSerializer):
    hours = ShopHoursSerializer(many=True, read_only=True)
    location_details = LocationSerializer(source="location", read_only=True)
    settings = ShopSettingsSerializer(read_only=True)
    avg_rating = serializers.SerializerMethodField()
    service_count = serializers.SerializerMethodField()
    specialist_count = serializers.SerializerMethodField()
    follower_count = serializers.SerializerMethodField()
    is_open_now = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()
    travel_time = serializers.SerializerMethodField()
    is_followed = serializers.SerializerMethodField()
    location = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Shop
        fields = [
            "id",
            "company",
            "name",
            "description",
            "avatar",
            "background_image",
            "location",
            "location_details",
            "phone_number",
            "email",
            "manager",
            "is_verified",
            "verification_date",
            "is_active",
            "created_at",
            "updated_at",
            "username",
            "hours",
            "settings",
            "avg_rating",
            "service_count",
            "specialist_count",
            "follower_count",
            "is_open_now",
            "distance",
            "travel_time",
            "is_followed",
            "meta_title",
            "meta_description",
            "instagram_handle",
            "twitter_handle",
            "facebook_page",
            "is_featured",
            "has_parking",
            "accessibility_features",
            "languages_supported",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "verification_date",
            "distance",
            "travel_time",
            "is_followed",
        ]

    def get_avg_rating(self, obj):
        return obj.get_avg_rating()

    def get_service_count(self, obj):
        return obj.get_service_count()

    def get_specialist_count(self, obj):
        return obj.get_specialist_count()

    def get_follower_count(self, obj):
        return obj.get_follower_count()

    def get_is_open_now(self, obj):
        return obj.is_open_now()

    def get_distance(self, obj):
        """Get distance between shop and customer in km"""
        request = self.context.get("request")
        if not request:
            return None

        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")

        if not lat or not lng or not obj.location:
            return None

        from apps.geoapp.services.distance_service import DistanceService

        try:
            distance = DistanceService.calculate_distance(
                (float(lat), float(lng)),
                (obj.location.latitude, obj.location.longitude),
            )
            return round(distance, 2)
        except (ValueError, TypeError):
            return None

    def get_travel_time(self, obj):
        """Get estimated travel time by car in minutes"""
        request = self.context.get("request")
        if not request:
            return None

        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")

        if not lat or not lng or not obj.location:
            return None

        from apps.geoapp.services.travel_time_service import TravelTimeService

        try:
            travel_time = TravelTimeService.estimate_travel_time(
                (float(lat), float(lng)),
                (obj.location.latitude, obj.location.longitude),
            )
            return round(travel_time)
        except (ValueError, TypeError):
            return None

    def get_is_followed(self, obj):
        """Check if current user follows this shop"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        return ShopFollower.objects.filter(shop=obj, customer=request.user).exists()


class ShopMinimalSerializer(serializers.ModelSerializer):
    """Minimal shop serializer for list views"""

    avg_rating = serializers.SerializerMethodField()
    is_open_now = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = [
            "id",
            "name",
            "avatar",
            "username",
            "is_verified",
            "avg_rating",
            "is_open_now",
            "distance",
            "city",
        ]

    def get_avg_rating(self, obj):
        return obj.get_avg_rating()

    def get_is_open_now(self, obj):
        return obj.is_open_now()

    def get_distance(self, obj):
        """Get distance between shop and customer in km"""
        request = self.context.get("request")
        if not request:
            return None

        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")

        if not lat or not lng or not obj.location:
            return None

        from apps.geoapp.services.distance_service import DistanceService

        try:
            distance = DistanceService.calculate_distance(
                (float(lat), float(lng)),
                (obj.location.latitude, obj.location.longitude),
            )
            return round(distance, 2)
        except (ValueError, TypeError):
            return None

    def get_city(self, obj):
        if obj.location:
            return obj.location.city
        return None


class ShopLocationSerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = ["id", "name", "latitude", "longitude", "address", "city", "country"]

    def get_latitude(self, obj):
        if obj.location:
            return obj.location.latitude
        return None

    def get_longitude(self, obj):
        if obj.location:
            return obj.location.longitude
        return None

    def get_address(self, obj):
        if obj.location:
            return obj.location.address
        return None

    def get_city(self, obj):
        if obj.location:
            return obj.location.city
        return None

    def get_country(self, obj):
        if obj.location:
            return obj.location.country
        return None


# Add imports for company, user, and category serializers


# Add the missing ShopDetailSerializer
class ShopDetailSerializer(ShopSerializer):
    """
    Extended Shop serializer with additional details for admin views
    """

    company_details = CompanySerializer(source="company", read_only=True)
    manager_details = UserSerializer(source="manager", read_only=True)
    verification = ShopVerificationSerializer(
        source="shopverification_set", many=True, read_only=True
    )
    followers = serializers.SerializerMethodField()
    revenue_stats = serializers.SerializerMethodField()
    bookings_stats = serializers.SerializerMethodField()
    category_details = serializers.SerializerMethodField()

    class Meta(ShopSerializer.Meta):
        fields = ShopSerializer.Meta.fields + [
            "company_details",
            "manager_details",
            "verification",
            "followers",
            "revenue_stats",
            "bookings_stats",
            "category_details",
        ]

    def get_followers(self, obj):
        # Return limited follower information for admin purposes
        followers = obj.shopfollower_set.all()[:10]
        return ShopFollowerSerializer(followers, many=True).data

    def get_revenue_stats(self, obj):
        # Placeholder - in a real implementation, you'd calculate this from booking data
        return {"total_revenue": 0, "this_month": 0, "last_month": 0, "growth_rate": 0}

    def get_bookings_stats(self, obj):
        # Placeholder - in a real implementation, you'd calculate this from booking data
        return {"total_bookings": 0, "completed": 0, "cancelled": 0, "no_show": 0}

    def get_category_details(self, obj):
        if hasattr(obj, "category") and obj.category:
            return CategorySerializer(obj.category).data
        return None


# Aliases
ShopMiniSerializer = ShopMinimalSerializer
ShopCardSerializer = ShopMinimalSerializer
ShopLightSerializer = ShopMiniSerializer
ShopSimpleSerializer = ShopMiniSerializer
ShopBasicSerializer = ShopMiniSerializer
