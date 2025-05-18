from rest_framework import serializers

from .models import Area, City, Country, Location

# Commenting out GeoFeatureModelSerializer
# from rest_framework_gis.serializers import GeoFeatureModelSerializer


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "name", "code", "flag_icon")
        read_only_fields = ("id", "created_at", "updated_at")


class CitySerializer(serializers.ModelSerializer):
    country_name = serializers.StringRelatedField(source="country.name", read_only=True)

    class Meta:
        model = City
        fields = (
            "id",
            "name",
            "country",
            "country_name",
            "is_active",
            "latitude",
            "longitude",
        )
        read_only_fields = ("id", "created_at", "updated_at")


# Temporarily replaced with standard serializer
# class LocationGeoSerializer(GeoFeatureModelSerializer):
class LocationGeoSerializer(serializers.ModelSerializer):
    """Standard serializer replacing GeoJSON serializer for Location model"""

    city_name = serializers.StringRelatedField(source="city.name", read_only=True)
    country_name = serializers.StringRelatedField(source="country.name", read_only=True)

    class Meta:
        model = Location
        # geo_field = "coordinates"
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
        """Create location with lat/long fields"""
        # Just pass through the data as we now have direct fields
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update location with lat/long fields"""
        # Just pass through the data as we now have direct fields
        return super().update(instance, validated_data)


# Temporarily replaced with standard serializer
# class AreaSerializer(GeoFeatureModelSerializer):
class AreaSerializer(serializers.ModelSerializer):
    city_name = serializers.StringRelatedField(source="city.name", read_only=True)

    class Meta:
        model = Area
        # geo_field = "boundary"
        fields = (
            "id",
            "name",
            "description",
            "boundary_geojson",
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
