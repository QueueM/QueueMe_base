from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.categoriesapp.serializers import CategorySerializer
from apps.geoapp.services.geo_service import GeoService
from apps.shopapp.serializers import ShopMinimalSerializer

from .models import (
    Service,
    ServiceAftercare,
    ServiceAvailability,
    ServiceException,
    ServiceFAQ,
    ServiceOverview,
    ServiceStep,
)


class ServiceAvailabilitySerializer(serializers.ModelSerializer):
    weekday_name = serializers.SerializerMethodField()

    class Meta:
        model = ServiceAvailability
        fields = ("id", "weekday", "weekday_name", "from_hour", "to_hour", "is_closed")
        read_only_fields = ("id",)

    def get_weekday_name(self, obj):
        return obj.get_weekday_display()


class ServiceExceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceException
        fields = ("id", "date", "is_closed", "from_hour", "to_hour", "reason")
        read_only_fields = ("id",)


class ServiceFAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceFAQ
        fields = ("id", "question", "answer", "order")
        read_only_fields = ("id",)


class ServiceOverviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceOverview
        fields = ("id", "title", "image", "order")
        read_only_fields = ("id",)


class ServiceStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceStep
        fields = ("id", "title", "description", "image", "order")
        read_only_fields = ("id",)


class ServiceAftercareSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceAftercare
        fields = ("id", "title", "order")
        read_only_fields = ("id",)


class ServiceListSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source="category.name")
    shop_name = serializers.ReadOnlyField(source="shop.name")
    shop_city = serializers.ReadOnlyField(source="shop.location.city")
    service_location_display = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    specialists_count = serializers.ReadOnlyField()
    distance = serializers.SerializerMethodField()
    travel_time = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = (
            "id",
            "name",
            "short_description",
            "image",
            "price",
            "duration",
            "service_location",
            "service_location_display",
            "category_name",
            "shop_name",
            "shop_city",
            "average_rating",
            "review_count",
            "specialists_count",
            "distance",
            "travel_time",
            "is_featured",
        )
        read_only_fields = fields

    def get_service_location_display(self, obj):
        return obj.get_service_location_display()

    def get_average_rating(self, obj):
        return obj.average_rating

    def get_review_count(self, obj):
        return obj.review_count

    def get_distance(self, obj):
        """Calculate distance between customer and shop"""
        request = self.context.get("request")
        if (
            not request
            or not request.query_params.get("lat")
            or not request.query_params.get("lng")
        ):
            return None

        try:
            customer_lat = float(request.query_params.get("lat"))
            customer_lng = float(request.query_params.get("lng"))

            # Check if shop has location
            if not obj.shop.location:
                return None

            shop_lat = obj.shop.location.latitude
            shop_lng = obj.shop.location.longitude

            distance = GeoService.calculate_distance(customer_lat, customer_lng, shop_lat, shop_lng)

            return round(distance, 1)  # Round to 1 decimal place
        except (ValueError, TypeError, AttributeError):
            return None

    def get_travel_time(self, obj):
        """Estimate travel time based on distance"""
        distance = self.get_distance(obj)
        if distance is None:
            return None

        # Simple estimation: Assume 30 km/h in city traffic
        # This is about 0.5 km per minute
        time_minutes = int(distance / 0.5)

        return time_minutes


class ServiceDetailSerializer(serializers.ModelSerializer):
    shop = ShopMinimalSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    service_location_display = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    specialists_count = serializers.ReadOnlyField()
    distance = serializers.SerializerMethodField()
    travel_time = serializers.SerializerMethodField()
    overviews = ServiceOverviewSerializer(many=True, read_only=True)
    steps = ServiceStepSerializer(many=True, read_only=True)
    aftercare_tips = ServiceAftercareSerializer(many=True, read_only=True)
    faqs = ServiceFAQSerializer(many=True, read_only=True)
    availability = ServiceAvailabilitySerializer(many=True, read_only=True)
    exceptions = ServiceExceptionSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = (
            "id",
            "name",
            "description",
            "short_description",
            "image",
            "price",
            "duration",
            "service_location",
            "service_location_display",
            "shop",
            "category",
            "average_rating",
            "review_count",
            "specialists_count",
            "distance",
            "travel_time",
            "overviews",
            "steps",
            "aftercare_tips",
            "faqs",
            "buffer_before",
            "buffer_after",
            "is_featured",
            "availability",
            "exceptions",
            "min_booking_notice",
            "max_advance_booking_days",
        )
        read_only_fields = fields

    def get_service_location_display(self, obj):
        return obj.get_service_location_display()

    def get_average_rating(self, obj):
        return obj.average_rating

    def get_review_count(self, obj):
        return obj.review_count

    def get_distance(self, obj):
        """Calculate distance between customer and shop"""
        request = self.context.get("request")
        if (
            not request
            or not request.query_params.get("lat")
            or not request.query_params.get("lng")
        ):
            return None

        try:
            customer_lat = float(request.query_params.get("lat"))
            customer_lng = float(request.query_params.get("lng"))

            # Check if shop has location
            if not obj.shop.location:
                return None

            shop_lat = obj.shop.location.latitude
            shop_lng = obj.shop.location.longitude

            distance = GeoService.calculate_distance(customer_lat, customer_lng, shop_lat, shop_lng)

            return round(distance, 1)  # Round to 1 decimal place
        except (ValueError, TypeError, AttributeError):
            return None

    def get_travel_time(self, obj):
        """Estimate travel time based on distance"""
        distance = self.get_distance(obj)
        if distance is None:
            return None

        # Simple estimation: Assume 30 km/h in city traffic
        # This is about 0.5 km per minute
        time_minutes = int(distance / 0.5)

        return time_minutes


class ServiceCreateSerializer(serializers.ModelSerializer):
    availability = ServiceAvailabilitySerializer(many=True, required=False)
    faqs = ServiceFAQSerializer(many=True, required=False)
    overviews = ServiceOverviewSerializer(many=True, required=False)
    steps = ServiceStepSerializer(many=True, required=False)
    aftercare_tips = ServiceAftercareSerializer(many=True, required=False)

    class Meta:
        model = Service
        fields = (
            "id",
            "shop",
            "category",
            "name",
            "description",
            "short_description",
            "image",
            "price",
            "duration",
            "slot_granularity",
            "buffer_before",
            "buffer_after",
            "service_location",
            "has_custom_availability",
            "min_booking_notice",
            "max_advance_booking_days",
            "order",
            "is_featured",
            "status",
            "availability",
            "faqs",
            "overviews",
            "steps",
            "aftercare_tips",
        )
        read_only_fields = ("id",)

    def validate(self, data):
        # Ensure shop belongs to the current user's company
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            from apps.rolesapp.services.permission_resolver import PermissionResolver

            shop_id = data.get("shop").id
            if not PermissionResolver.has_shop_permission(request.user, shop_id, "service", "add"):
                raise serializers.ValidationError(
                    _("You don't have permission to add services to this shop")
                )

        return data

    def create(self, validated_data):
        availability_data = validated_data.pop("availability", [])
        faqs_data = validated_data.pop("faqs", [])
        overviews_data = validated_data.pop("overviews", [])
        steps_data = validated_data.pop("steps", [])
        aftercare_tips_data = validated_data.pop("aftercare_tips", [])

        # Create service
        service = Service.objects.create(**validated_data)

        # Create related objects
        for availability in availability_data:
            ServiceAvailability.objects.create(service=service, **availability)

        for faq in faqs_data:
            ServiceFAQ.objects.create(service=service, **faq)

        for overview in overviews_data:
            ServiceOverview.objects.create(service=service, **overview)

        for step in steps_data:
            ServiceStep.objects.create(service=service, **step)

        for tip in aftercare_tips_data:
            ServiceAftercare.objects.create(service=service, **tip)

        return service


class ServiceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = (
            "category",
            "name",
            "description",
            "short_description",
            "image",
            "price",
            "duration",
            "slot_granularity",
            "buffer_before",
            "buffer_after",
            "service_location",
            "has_custom_availability",
            "min_booking_notice",
            "max_advance_booking_days",
            "order",
            "is_featured",
            "status",
        )

    def validate(self, data):
        # Ensure user has permission to edit this service
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            from apps.rolesapp.services.permission_resolver import PermissionResolver

            shop_id = self.instance.shop.id
            if not PermissionResolver.has_shop_permission(request.user, shop_id, "service", "edit"):
                raise serializers.ValidationError(
                    _("You don't have permission to edit services in this shop")
                )

        return data


class ServiceAvailabilityCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceAvailability
        fields = ("weekday", "from_hour", "to_hour", "is_closed")

    def validate(self, data):
        # Ensure from_hour is before to_hour
        if not data.get("is_closed") and data.get("from_hour") and data.get("to_hour"):
            if data["from_hour"] >= data["to_hour"]:
                raise serializers.ValidationError(_("From hour must be before to hour"))

        return data


class ServiceExceptionCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceException
        fields = ("date", "is_closed", "from_hour", "to_hour", "reason")

    def validate(self, data):
        # Ensure from_hour is before to_hour if not closed
        if not data.get("is_closed") and data.get("from_hour") and data.get("to_hour"):
            if data["from_hour"] >= data["to_hour"]:
                raise serializers.ValidationError(_("From hour must be before to hour"))

        return data


class ServiceFAQCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceFAQ
        fields = ("question", "answer", "order")


class ServiceOverviewCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceOverview
        fields = ("title", "image", "order")


class ServiceStepCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceStep
        fields = ("title", "description", "image", "order")


class ServiceAftercareCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceAftercare
        fields = ("title", "order")


class AvailabilitySlotSerializer(serializers.Serializer):
    """Serializer for available time slots"""

    start = serializers.TimeField(format="%H:%M")
    end = serializers.TimeField(format="%H:%M")
    duration = serializers.IntegerField()
    buffer_before = serializers.IntegerField()
    buffer_after = serializers.IntegerField()


ServiceSerializer = ServiceDetailSerializer
# Create an alias for ServiceMiniSerializer that's being imported by customersapp
ServiceMiniSerializer = ServiceListSerializer
ServiceBasicSerializer = ServiceSerializer
