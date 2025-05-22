import uuid

# Using GeoDjango models
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
    # Keep these for backward compatibility
    latitude = models.FloatField(_("Latitude"), null=True, blank=True)
    longitude = models.FloatField(_("Longitude"), null=True, blank=True)
    # Add PointField for spatial queries
    location = models.PointField(
        _("Location"),
        srid=4326,
        null=True,
        blank=True,
        default=None,
        help_text=_("Geographic point for this city"),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    population = models.IntegerField(_("Population"), null=True, blank=True)
    area_km2 = models.FloatField(_("Area (km²)"), null=True, blank=True)

    class Meta:
        verbose_name = _("City")
        verbose_name_plural = _("Cities")
        db_table = "city"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["country"]),
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
            # Use standard Index instead of SpatialIndex for compatibility
            models.Index(fields=["location"]),
        ]

    def __str__(self):
        return f"{self.name}, {self.country.name}"

    def save(self, *args, **kwargs):
        # Sync latitude/longitude with location
        if (
            not self.location
            and self.latitude is not None
            and self.longitude is not None
        ):
            self.location = Point(self.longitude, self.latitude, srid=4326)
        elif self.location and (self.latitude is None or self.longitude is None):
            self.latitude = self.location.y
            self.longitude = self.location.x
        super().save(*args, **kwargs)


class Region(models.Model):
    """Region/State model for geographic hierarchy"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=100)
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="regions",
        verbose_name=_("Country"),
    )
    code = models.CharField(_("Region Code"), max_length=10, blank=True)
    # Geography field for representing the region boundaries
    boundary = models.MultiPolygonField(
        _("Boundary"),
        srid=4326,
        null=True,
        blank=True,
        help_text=_("Geographic boundary for this region"),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Region")
        verbose_name_plural = _("Regions")
        db_table = "region"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["country"]),
            models.Index(fields=["name"]),
            # Use standard Index instead of SpatialIndex for compatibility
            models.Index(fields=["boundary"]),
        ]

    def __str__(self):
        return f"{self.name}, {self.country.name}"


class Location(models.Model):
    """Precise location model for addresses and coordinates"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    address_line1 = models.CharField(_("Address Line 1"), max_length=255)
    address_line2 = models.CharField(_("Address Line 2"), max_length=255, blank=True)
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name="locations",
        verbose_name=_("City"),
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name="locations",
        verbose_name=_("Region"),
        null=True,
        blank=True,
    )
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="locations",
        verbose_name=_("Country"),
    )
    postal_code = models.CharField(_("Postal Code"), max_length=20, blank=True)
    # Keep these for backward compatibility
    latitude = models.FloatField(_("Latitude"), null=True, blank=True)
    longitude = models.FloatField(_("Longitude"), null=True, blank=True)
    # Add PointField for spatial queries
    coordinates = models.PointField(
        _("Coordinates"),
        srid=4326,
        null=True,
        blank=True,
        default=None,
        help_text=_("Precise coordinates for this address"),
    )
    place_name = models.CharField(_("Place Name"), max_length=255, blank=True)
    place_type = models.CharField(_("Place Type"), max_length=50, blank=True)
    is_verified = models.BooleanField(_("Verified Address"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")
        db_table = "location"
        indexes = [
            models.Index(fields=["city"]),
            models.Index(fields=["country"]),
            models.Index(fields=["postal_code"]),
            # Use standard Index instead of SpatialIndex for compatibility
            models.Index(fields=["coordinates"]),
        ]

    def __str__(self):
        address = self.address_line1
        if self.address_line2:
            address += f", {self.address_line2}"
        return f"{address}, {self.city.name}"

    def save(self, *args, **kwargs):
        # Ensure country consistency with city
        self.country = self.city.country

        # Sync latitude/longitude with coordinates
        if (
            not self.coordinates
            and self.latitude is not None
            and self.longitude is not None
        ):
            self.coordinates = Point(self.longitude, self.latitude, srid=4326)
        elif self.coordinates and (self.latitude is None or self.longitude is None):
            self.latitude = self.coordinates.y
            self.longitude = self.coordinates.x

        super().save(*args, **kwargs)

    @classmethod
    def create_from_latlong(cls, lat, lng, city_id, address_line1, **kwargs):
        # Create a location with both lat/long and Point
        location = cls(
            latitude=lat,
            longitude=lng,
            coordinates=Point(lng, lat, srid=4326),
            city_id=city_id,
            address_line1=address_line1,
            **kwargs,
        )
        location.save()
        return location


class Area(models.Model):
    """Defined geographic area for service zones, delivery areas, etc."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)

    # Keep for backward compatibility
    boundary_geojson = models.TextField(_("Boundary GeoJSON"), blank=True, null=True)
    # Add MultiPolygonField for spatial queries
    boundary = models.MultiPolygonField(
        _("Boundary"),
        srid=4326,
        null=True,
        blank=True,
        default=None,
        help_text=_("Boundary polygon for this area"),
    )

    area_type = models.CharField(_("Area Type"), max_length=50)
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name="areas",
        verbose_name=_("City"),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Area")
        verbose_name_plural = _("Areas")
        db_table = "area"
        indexes = [
            models.Index(fields=["name"]),
            # Use standard Index instead of SpatialIndex for compatibility
            models.Index(fields=["boundary"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.area_type})"


class Geofence(models.Model):
    """
    Geofences for location-based triggers and notifications
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    center = models.PointField(
        _("Center Point"),
        srid=4326,
        help_text=_("Center point for circular geofence"),
    )
    radius_km = models.FloatField(_("Radius (km)"), help_text=_("Radius in kilometers"))
    boundary = models.PolygonField(
        _("Boundary"),
        srid=4326,
        null=True,
        blank=True,
        help_text=_("Optional explicit boundary instead of circle"),
    )
    entity_id = models.UUIDField(
        _("Entity ID"), help_text=_("ID of related entity (shop, promo, etc.)")
    )
    entity_type = models.CharField(
        _("Entity Type"), max_length=50, help_text=_("Type of related entity")
    )
    active_from = models.DateTimeField(_("Active From"))
    active_until = models.DateTimeField(_("Active Until"), null=True, blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Geofence")
        verbose_name_plural = _("Geofences")
        db_table = "geofence"
        indexes = [
            models.Index(fields=["name"]),
            # Use standard Index instead of SpatialIndex for compatibility
            models.Index(fields=["center"]),
            models.Index(fields=["boundary"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.entity_type})"

    def contains_point(self, point):
        """
        Check if a point is within this geofence

        Args:
            point: A Point object or tuple of (longitude, latitude)

        Returns:
            Boolean indicating if point is within geofence
        """
        if not isinstance(point, Point):
            # Convert tuple (lng, lat) to Point
            point = Point(point[0], point[1], srid=4326)

        # If we have an explicit boundary, use that
        if self.boundary:
            return self.boundary.contains(point)

        # Otherwise calculate using center and radius
        # Convert km to degrees (approximation, better to use geodesic distance)
        # This will return True if the point is within radius_km of center
        return self.center.distance(point) <= (
            self.radius_km / 111.32
        )  # approx km per degree
