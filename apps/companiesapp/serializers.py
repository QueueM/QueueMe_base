# apps/companiesapp/serializers.py
from rest_framework import serializers

from apps.authapp.serializers import UserSerializer
from apps.companiesapp.validators import validate_company_name, validate_registration_number
from apps.geoapp.models import Location
from apps.geoapp.serializers import LocationSerializer

from .models import Company, CompanyDocument, CompanySettings


class CompanySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySettings
        fields = [
            "default_language",
            "notification_email",
            "notification_sms",
            "auto_approve_bookings",
            "require_manager_approval_for_discounts",
            "allow_employee_chat",
        ]


class CompanyDocumentSerializer(serializers.ModelSerializer):
    verified_by = UserSerializer(read_only=True)

    class Meta:
        model = CompanyDocument
        fields = [
            "id",
            "title",
            "document",
            "document_type",
            "is_verified",
            "verified_by",
            "verified_at",
            "uploaded_at",
        ]
        read_only_fields = ["is_verified", "verified_by", "verified_at", "uploaded_at"]


class CompanySerializer(serializers.ModelSerializer):
    location = LocationSerializer(required=False, allow_null=True)
    owner = UserSerializer(read_only=True)
    owner_id = serializers.UUIDField(write_only=True, required=False)
    settings = CompanySettingsSerializer(required=False)
    documents = CompanyDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "logo",
            "registration_number",
            "owner",
            "owner_id",
            "contact_email",
            "contact_phone",
            "description",
            "location",
            "is_active",
            "subscription_status",
            "subscription_end_date",
            "shop_count",
            "employee_count",
            "created_at",
            "updated_at",
            "settings",
            "documents",
        ]
        read_only_fields = [
            "id",
            "subscription_status",
            "subscription_end_date",
            "shop_count",
            "employee_count",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        """
        Validate company name using custom validator
        """
        validate_company_name(value)
        return value

    def validate_registration_number(self, value):
        """
        Validate registration number format
        """
        if value:
            validate_registration_number(value)
        return value

    def create(self, validated_data):
        """
        Create company with nested objects (location and settings)
        """
        # Handle location data
        location_data = validated_data.pop("location", None)
        settings_data = validated_data.pop("settings", None)

        # Get owner (either from context or from owner_id)
        owner_id = validated_data.pop("owner_id", None)
        if owner_id is None and "request" in self.context:
            # Use authenticated user if owner_id not provided
            validated_data["owner"] = self.context["request"].user
        else:
            from apps.authapp.models import User

            validated_data["owner"] = User.objects.get(id=owner_id)

        # Create location if provided
        if location_data:
            location = Location.objects.create(**location_data)
            validated_data["location"] = location

        # Create company
        company = Company.objects.create(**validated_data)

        # Create settings if provided, otherwise create defaults
        if settings_data:
            CompanySettings.objects.create(company=company, **settings_data)
        else:
            CompanySettings.objects.create(company=company)

        return company

    def update(self, instance, validated_data):
        """
        Update company with nested objects
        """
        # Handle location data
        location_data = validated_data.pop("location", None)
        settings_data = validated_data.pop("settings", None)

        # Update location if provided
        if location_data:
            if instance.location:
                # Update existing location
                for key, value in location_data.items():
                    setattr(instance.location, key, value)
                instance.location.save()
            else:
                # Create new location
                location = Location.objects.create(**location_data)
                instance.location = location

        # Update settings if provided
        if settings_data and hasattr(instance, "settings"):
            for key, value in settings_data.items():
                setattr(instance.settings, key, value)
            instance.settings.save()

        # Update remaining fields
        for key, value in validated_data.items():
            setattr(instance, key, value)

        instance.save()
        return instance


class CompanyMinimalSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for companies (used in nested contexts)
    """

    class Meta:
        model = Company
        fields = ["id", "name", "logo", "subscription_status"]


class VerifyCompanyDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for verifying company documents (admin only)
    """

    class Meta:
        model = CompanyDocument
        fields = ["is_verified"]
