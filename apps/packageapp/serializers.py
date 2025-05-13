from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.categoriesapp.serializers import CategoryLightSerializer
from apps.serviceapp.models import Service
from apps.serviceapp.serializers import ServiceDetailSerializer
from apps.shopapp.serializers import ShopLightSerializer

from .models import Package, PackageAvailability, PackageFAQ, PackageService
from .validators import (
    validate_date_range,
    validate_discount_price,
    validate_services_compatibility,
)


class PackageServiceSerializer(serializers.ModelSerializer):
    """Serializer for PackageService model"""

    service_id = serializers.UUIDField(write_only=True)
    service = ServiceDetailSerializer(read_only=True)

    class Meta:
        model = PackageService
        fields = [
            "id",
            "service_id",
            "service",
            "sequence",
            "custom_duration",
            "description",
            "effective_duration",
        ]
        read_only_fields = ["id", "effective_duration"]


class PackageAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for PackageAvailability model"""

    weekday_name = serializers.SerializerMethodField()

    class Meta:
        model = PackageAvailability
        fields = ["id", "weekday", "weekday_name", "from_hour", "to_hour", "is_closed"]
        read_only_fields = ["id"]

    def get_weekday_name(self, obj):
        return obj.get_weekday_display()


class PackageFAQSerializer(serializers.ModelSerializer):
    """Serializer for PackageFAQ model"""

    class Meta:
        model = PackageFAQ
        fields = ["id", "question", "answer", "order"]
        read_only_fields = ["id"]


class PackageListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for Package listing"""

    shop = ShopLightSerializer(read_only=True)
    primary_category = CategoryLightSerializer(read_only=True)
    service_count = serializers.SerializerMethodField()
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = Package
        fields = [
            "id",
            "name",
            "shop",
            "image",
            "original_price",
            "discounted_price",
            "discount_percentage",
            "total_duration",
            "package_location",
            "primary_category",
            "status",
            "service_count",
            "is_available",
        ]
        read_only_fields = fields

    def get_service_count(self, obj):
        return obj.services.count()


class PackageDetailSerializer(serializers.ModelSerializer):
    """Complete serializer for Package detail view"""

    shop = ShopLightSerializer(read_only=True)
    shop_id = serializers.UUIDField(write_only=True)
    primary_category = CategoryLightSerializer(read_only=True)
    primary_category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    services = PackageServiceSerializer(many=True, required=False)
    availability = PackageAvailabilitySerializer(many=True, required=False)
    faqs = PackageFAQSerializer(many=True, required=False)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = Package
        fields = [
            "id",
            "shop",
            "shop_id",
            "name",
            "description",
            "image",
            "original_price",
            "discounted_price",
            "discount_percentage",
            "total_duration",
            "package_location",
            "primary_category",
            "primary_category_id",
            "status",
            "start_date",
            "end_date",
            "max_purchases",
            "current_purchases",
            "services",
            "availability",
            "faqs",
            "is_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "discount_percentage",
            "total_duration",
            "current_purchases",
            "is_available",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """Validate package data"""

        # For updates, get the existing instance to merge with attrs
        instance = self.instance

        # Check for price validation
        if "original_price" in attrs and "discounted_price" in attrs:
            validate_discount_price(attrs["original_price"], attrs["discounted_price"])
        elif instance and "discounted_price" in attrs:
            validate_discount_price(instance.original_price, attrs["discounted_price"])
        elif instance and "original_price" in attrs:
            validate_discount_price(attrs["original_price"], instance.discounted_price)

        # Check date range validation
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if start_date is None and instance:
            start_date = instance.start_date
        if end_date is None and instance:
            end_date = instance.end_date

        if start_date and end_date:
            validate_date_range(start_date, end_date)

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create a new package with nested services, availability, and FAQs"""

        services_data = validated_data.pop("services", [])
        availability_data = validated_data.pop("availability", [])
        faqs_data = validated_data.pop("faqs", [])

        # Create package
        package = Package.objects.create(**validated_data)

        # Create services
        for service_data in services_data:
            service_id = service_data.pop("service_id")
            PackageService.objects.create(package=package, service_id=service_id, **service_data)

        # Create availability
        for avail_data in availability_data:
            PackageAvailability.objects.create(package=package, **avail_data)

        # Create FAQs
        for faq_data in faqs_data:
            PackageFAQ.objects.create(package=package, **faq_data)

        # Update calculated fields
        package.save()  # This will recalculate discount_percentage and total_duration

        return package

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update package with nested services, availability, and FAQs"""

        services_data = validated_data.pop("services", None)
        availability_data = validated_data.pop("availability", None)
        faqs_data = validated_data.pop("faqs", None)

        # Update package fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update services if provided
        if services_data is not None:
            # Clear existing services
            instance.services.all().delete()

            # Create new services
            for service_data in services_data:
                service_id = service_data.pop("service_id")
                PackageService.objects.create(
                    package=instance, service_id=service_id, **service_data
                )

        # Update availability if provided
        if availability_data is not None:
            # Clear existing availability
            instance.availability.all().delete()

            # Create new availability
            for avail_data in availability_data:
                PackageAvailability.objects.create(package=instance, **avail_data)

        # Update FAQs if provided
        if faqs_data is not None:
            # Clear existing FAQs
            instance.faqs.all().delete()

            # Create new FAQs
            for faq_data in faqs_data:
                PackageFAQ.objects.create(package=instance, **faq_data)

        # Save and recalculate fields
        instance.save()

        return instance


class PackageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a package with bundled services"""

    shop_id = serializers.UUIDField()
    primary_category_id = serializers.UUIDField(required=False, allow_null=True)
    service_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        help_text=_("List of service IDs to include in the package"),
    )

    class Meta:
        model = Package
        fields = [
            "shop_id",
            "name",
            "description",
            "image",
            "discounted_price",
            "package_location",
            "primary_category_id",
            "status",
            "start_date",
            "end_date",
            "max_purchases",
            "service_ids",
        ]

    def validate(self, attrs):
        """Validate package creation data"""
        service_ids = attrs.pop("service_ids", [])

        # Validate services compatibility
        validate_services_compatibility(service_ids)

        # Save service_ids for use in create method
        attrs["service_ids"] = service_ids

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create a package from the validated data and a list of service IDs"""
        from .services.bundle_optimizer import BundleOptimizer

        service_ids = validated_data.pop("service_ids")

        # Get services
        services = Service.objects.filter(id__in=service_ids)

        # Calculate original price as sum of all service prices
        original_price = sum(service.price for service in services)

        # Check if discounted price is less than original price
        validate_discount_price(original_price, validated_data["discounted_price"])

        # Create package
        package = Package.objects.create(original_price=original_price, **validated_data)

        # Add services with optimal sequence
        optimal_sequence = BundleOptimizer.optimize_service_sequence(services)

        for i, service in enumerate(optimal_sequence):
            PackageService.objects.create(package=package, service=service, sequence=i)

        # Calculate total duration and update
        package.save()

        return package
