import uuid

from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.utils.translation import gettext_lazy as _


class Country(models.Model):
    """Country model for geographic hierarchy"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=100, unique=True)
    code = models.CharField(_("Country Code"), max_length=3, unique=True)
    flag_icon = models.ImageField(
        _("Flag Icon"), upload_to="countries/flags/", null=True, blank=True
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        ordering = ["name"]

    def __str__(self):
        return self.name


class City(models.Model):
    """City model for geographic hierarchy"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=100)
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="cities",
        verbose_name=_("Country"),
    )
    # Represents the center point of the city
    location = models.PointField(_("Location"), geography=True, null=True)
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    # Cache fields for performance
    population = models.IntegerField(_("Population"), null=True, blank=True)
    area_km2 = models.FloatField(_("Area (km²)"), null=True, blank=True)

    class Meta:
        verbose_name = _("City")
        verbose_name_plural = _("Cities")
        unique_together = ("name", "country")
        ordering = ["country", "name"]
        indexes = [
            models.Index(fields=["name"]),
            # Spatial index for location queries
            models.Index(fields=["location"], name="city_location_idx"),
        ]

    def __str__(self):
        return f"{self.name}, {self.country.name}"


class Location(models.Model):
    """Precise location model for addresses and coordinates"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    address_line1 = models.CharField(_("Address Line 1"), max_length=255)
    address_line2 = models.CharField(_("Address Line 2"), max_length=255, blank=True)
    city = models.ForeignKey(
        City, on_delete=models.CASCADE, related_name="locations", verbose_name=_("City")
    )
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="locations",
        verbose_name=_("Country"),
    )
    postal_code = models.CharField(_("Postal Code"), max_length=20, blank=True)

    # Precise coordinates stored as geography for accurate distance calculations
    coordinates = models.PointField(_("Coordinates"), geography=True)

    # Metadata
    place_name = models.CharField(_("Place Name"), max_length=255, blank=True)
    place_type = models.CharField(_("Place Type"), max_length=50, blank=True)
    is_verified = models.BooleanField(_("Verified Address"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")
        indexes = [
            # Spatial index for performance
            models.Index(fields=["coordinates"], name="coordinates_idx"),
            models.Index(fields=["city", "country"]),
        ]

    def __str__(self):
        address = self.address_line1
        if self.address_line2:
            address += f", {self.address_line2}"
        return f"{address}, {self.city.name}"

    def save(self, *args, **kwargs):
        """Ensure country consistency with city"""
        self.country = self.city.country
        super().save(*args, **kwargs)

    @property
    def latitude(self):
        """Get latitude from coordinates"""
        return self.coordinates.y if self.coordinates else None

    @property
    def longitude(self):
        """Get longitude from coordinates"""
        return self.coordinates.x if self.coordinates else None

    @classmethod
    def create_from_latlong(cls, lat, lng, city_id, address_line1, **kwargs):
        """Create a location from latitude and longitude"""
        point = Point(float(lng), float(lat), srid=4326)
        return cls.objects.create(
            coordinates=point, city_id=city_id, address_line1=address_line1, **kwargs
        )


class Area(models.Model):
    """Defined geographic area for service zones, delivery areas, etc."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)

    # MultiPolygon field for complex area shapes
    boundary = models.MultiPolygonField(_("Boundary"), geography=True)

    # Area type (e.g., 'delivery_zone', 'service_area', 'district')
    area_type = models.CharField(_("Area Type"), max_length=50)

    # Relationships
    city = models.ForeignKey(
        City, on_delete=models.CASCADE, related_name="areas", verbose_name=_("City")
    )

    # Metadata
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Area")
        verbose_name_plural = _("Areas")
        indexes = [
            models.Index(fields=["boundary"], name="area_boundary_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.area_type})"
