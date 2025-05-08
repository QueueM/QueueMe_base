from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import Area, City, Country, Location


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "name", "code", "flag_icon")
        read_only_fields = ("id", "created_at", "updated_at")


class CitySerializer(serializers.ModelSerializer):
    country_name = serializers.StringRelatedField(source="country.name", read_only=True)

    class Meta:
        model = City
        fields = ("id", "name", "country", "country_name", "is_active")
        read_only_fields = ("id", "created_at", "updated_at")


class LocationGeoSerializer(GeoFeatureModelSerializer):
    """GeoJSON serializer for Location model"""

    city_name = serializers.StringRelatedField(source="city.name", read_only=True)
    country_name = serializers.StringRelatedField(source="country.name", read_only=True)

    class Meta:
        model = Location
        geo_field = "coordinates"
        fields = (
            "id",
            "address_line1",
            "address_line2",
            "city",
            "city_name",
            "country",
            "country_name",
            "postal_code",
            "place_name",
            "place_type",
            "is_verified",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class LocationSerializer(serializers.ModelSerializer):
    """Standard serializer for Location model"""

    city_name = serializers.StringRelatedField(source="city.name", read_only=True)
    country_name = serializers.StringRelatedField(source="country.name", read_only=True)
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)

    class Meta:
        model = Location
        fields = (
            "id",
            "address_line1",
            "address_line2",
            "city",
            "city_name",
            "country",
            "country_name",
            "postal_code",
            "latitude",
            "longitude",
            "place_name",
            "place_type",
            "is_verified",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "country_name",
            "city_name",
        )

    def create(self, validated_data):
        """Create location with separate lat/long fields"""
        lat = validated_data.pop("latitude", None)
        lng = validated_data.pop("longitude", None)

        if lat is not None and lng is not None:
            from django.contrib.gis.geos import Point

            validated_data["coordinates"] = Point(float(lng), float(lat), srid=4326)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update location with separate lat/long fields"""
        lat = validated_data.pop("latitude", None)
        lng = validated_data.pop("longitude", None)

        if lat is not None and lng is not None:
            from django.contrib.gis.geos import Point

            validated_data["coordinates"] = Point(float(lng), float(lat), srid=4326)

        return super().update(instance, validated_data)


class AreaSerializer(GeoFeatureModelSerializer):
    city_name = serializers.StringRelatedField(source="city.name", read_only=True)

    class Meta:
        model = Area
        geo_field = "boundary"
        fields = (
            "id",
            "name",
            "description",
            "area_type",
            "city",
            "city_name",
            "is_active",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class NearbyLocationQuerySerializer(serializers.Serializer):
    """Serializer for nearby location query parameters"""

    latitude = serializers.FloatField(required=True)
    longitude = serializers.FloatField(required=True)
    radius = serializers.FloatField(required=False, default=5.0)  # kilometers
    max_results = serializers.IntegerField(required=False, default=20)
    entity_type = serializers.CharField(required=False)
