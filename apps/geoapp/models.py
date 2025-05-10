import uuid

# GeoDjango imports
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
    location = models.PointField(
        _("Location"),
        srid=4326,
        null=True,
        blank=True,
        default=None,
        help_text=_("Optional geographic point for this city"),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    population = models.IntegerField(_("Population"), null=True, blank=True)
    area_km2 = models.FloatField(_("Area (km²)"), null=True, blank=True)

    class Meta:
        verbose_name = _("City")
        verbose_name_plural = _("Cities")
        unique_together = ("name", "country")
        ordering = ["country", "name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["location"]),
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
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="locations",
        verbose_name=_("Country"),
    )
    postal_code = models.CharField(_("Postal Code"), max_length=20, blank=True)
    coordinates = models.PointField(
        _("Coordinates"),
        srid=4326,
        null=True,
        blank=True,
        default=None,
        help_text=_("Optional precise coordinates for this address"),
    )
    place_name = models.CharField(_("Place Name"), max_length=255, blank=True)
    place_type = models.CharField(_("Place Type"), max_length=50, blank=True)
    is_verified = models.BooleanField(_("Verified Address"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")
        indexes = [
            models.Index(fields=["coordinates"]),
            models.Index(fields=["city", "country"]),
        ]

    def __str__(self):
        address = self.address_line1
        if self.address_line2:
            address += f", {self.address_line2}"
        return f"{address}, {self.city.name}"

    def save(self, *args, **kwargs):
        # Ensure country consistency with city
        self.country = self.city.country
        super().save(*args, **kwargs)

    @property
    def latitude(self):
        return self.coordinates.y if self.coordinates else None

    @property
    def longitude(self):
        return self.coordinates.x if self.coordinates else None

    @classmethod
    def create_from_latlong(cls, lat, lng, city_id, address_line1, **kwargs):
        coordinates = Point(lng, lat, srid=4326)
        return cls.objects.create(
            coordinates=coordinates,
            city_id=city_id,
            address_line1=address_line1,
            **kwargs,
        )


class Area(models.Model):
    """Defined geographic area for service zones, delivery areas, etc."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)

    boundary = models.MultiPolygonField(
        _("Boundary"),
        srid=4326,
        null=True,
        blank=True,
        default=None,
        help_text=_("Optional boundary polygon for this area."),
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
        indexes = [
            models.Index(fields=["boundary"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.area_type})"
