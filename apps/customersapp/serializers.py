from rest_framework import serializers

from apps.categoriesapp.serializers import CategorySerializer
from apps.customersapp.models import (
    Customer,
    CustomerCategory,
    CustomerPreference,
    FavoriteService,
    FavoriteShop,
    FavoriteSpecialist,
    SavedPaymentMethod,
)
from apps.geoapp.serializers import LocationSerializer
from apps.serviceapp.serializers import ServiceMiniSerializer
from apps.shopapp.serializers import ShopMiniSerializer
from apps.specialistsapp.serializers import SpecialistMiniSerializer


class CustomerPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerPreference
        exclude = ("id", "customer", "created_at", "updated_at")


class SavedPaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedPaymentMethod
        exclude = ("customer", "token")
        read_only_fields = ("created_at",)


class SavedPaymentMethodCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedPaymentMethod
        fields = (
            "payment_type",
            "token",
            "last_digits",
            "expiry_month",
            "expiry_year",
            "card_brand",
            "is_default",
        )

    def create(self, validated_data):
        customer = self.context["request"].user.customer_profile
        validated_data["customer"] = customer
        return super().create(validated_data)


class FavoriteShopSerializer(serializers.ModelSerializer):
    shop = ShopMiniSerializer(read_only=True)

    class Meta:
        model = FavoriteShop
        exclude = ("customer",)
        read_only_fields = ("created_at",)


class FavoriteSpecialistSerializer(serializers.ModelSerializer):
    specialist = SpecialistMiniSerializer(read_only=True)

    class Meta:
        model = FavoriteSpecialist
        exclude = ("customer",)
        read_only_fields = ("created_at",)


class FavoriteServiceSerializer(serializers.ModelSerializer):
    service = ServiceMiniSerializer(read_only=True)

    class Meta:
        model = FavoriteService
        exclude = ("customer",)
        read_only_fields = ("created_at",)


class CustomerCategorySerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    class Meta:
        model = CustomerCategory
        exclude = ("customer",)
        read_only_fields = ("affinity_score", "created_at", "updated_at")


class CustomerSerializer(serializers.ModelSerializer):
    preferences = CustomerPreferenceSerializer(required=False)
    location = LocationSerializer(required=False)

    class Meta:
        model = Customer
        exclude = ("user",)
        read_only_fields = ("created_at", "updated_at")

    def create(self, validated_data):
        preferences_data = validated_data.pop("preferences", None)
        location_data = validated_data.pop("location", None)

        # Create customer
        customer = Customer.objects.create(
            user=self.context["request"].user, **validated_data
        )

        # Create location if provided
        if location_data:
            from apps.geoapp.models import Location

            location = Location.objects.create(**location_data)
            customer.location = location
            customer.save()

        # Create preferences
        if preferences_data:
            CustomerPreference.objects.create(customer=customer, **preferences_data)
        else:
            # Create with defaults
            CustomerPreference.objects.create(customer=customer)

        return customer

    def update(self, instance, validated_data):
        preferences_data = validated_data.pop("preferences", None)
        location_data = validated_data.pop("location", None)

        # Update customer
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update location if provided
        if location_data:
            if instance.location:
                # Update existing location
                location = instance.location
                for attr, value in location_data.items():
                    setattr(location, attr, value)
                location.save()
            else:
                # Create new location
                from apps.geoapp.models import Location

                location = Location.objects.create(**location_data)
                instance.location = location

        # Update preferences if provided
        if preferences_data and hasattr(instance, "preferences"):
            preferences = instance.preferences
            for attr, value in preferences_data.items():
                setattr(preferences, attr, value)
            preferences.save()

        instance.save()
        return instance


class CustomerDetailSerializer(CustomerSerializer):
    """Extended serializer with related data for detailed view"""

    payment_methods = SavedPaymentMethodSerializer(many=True, read_only=True)
    favorite_shops = FavoriteShopSerializer(many=True, read_only=True)
    favorite_specialists = FavoriteSpecialistSerializer(many=True, read_only=True)
    favorite_services = FavoriteServiceSerializer(many=True, read_only=True)
    category_interests = CustomerCategorySerializer(many=True, read_only=True)

    class Meta(CustomerSerializer.Meta):
        pass
