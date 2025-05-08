import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.categoriesapp.models import Category
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop


class Package(models.Model):
    """
    A package represents a bundle of services offered at a discounted price.
    Packages can contain multiple services and offer special pricing.
    """

    LOCATION_CHOICES = (
        ("in_shop", _("In Shop")),
        ("in_home", _("In Home")),
        ("both", _("Both")),
    )

    STATUS_CHOICES = (
        ("active", _("Active")),
        ("inactive", _("Inactive")),
        ("upcoming", _("Upcoming")),
        ("expired", _("Expired")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="packages", verbose_name=_("Shop")
    )
    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    image = models.ImageField(
        _("Image"), upload_to="packages/images/", null=True, blank=True
    )

    # Price details
    original_price = models.DecimalField(
        _("Original Price"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Total price of all services if purchased separately"),
    )
    discounted_price = models.DecimalField(
        _("Discounted Price"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Package price (must be less than original price)"),
    )
    discount_percentage = models.DecimalField(
        _("Discount Percentage"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        blank=True,
        null=True,
        help_text=_("Automatically calculated"),
    )

    # Time details
    total_duration = models.PositiveIntegerField(
        _("Total Duration (minutes)"),
        blank=True,
        null=True,
        help_text=_("Automatically calculated from services"),
    )

    # Location and availability
    package_location = models.CharField(
        _("Package Location"), max_length=10, choices=LOCATION_CHOICES
    )

    # Category - for filtering and discovery
    primary_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="primary_packages",
        verbose_name=_("Primary Category"),
        null=True,
    )

    # Status and dates
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default="active"
    )
    start_date = models.DateField(_("Start Date"), null=True, blank=True)
    end_date = models.DateField(_("End Date"), null=True, blank=True)

    # Limitations
    max_purchases = models.PositiveIntegerField(
        _("Maximum Purchases"),
        null=True,
        blank=True,
        help_text=_("Maximum number of times this package can be purchased"),
    )
    current_purchases = models.PositiveIntegerField(
        _("Current Purchases"),
        default=0,
        help_text=_("Number of times this package has been purchased"),
    )

    # Tracking
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Package")
        verbose_name_plural = _("Packages")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shop", "status"]),
            models.Index(fields=["package_location"]),
            models.Index(fields=["primary_category"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.shop.name})"

    def save(self, *args, **kwargs):
        # Calculate discount percentage if not provided
        if (
            self.original_price
            and self.discounted_price
            and (self.discount_percentage is None)
        ):
            if self.original_price > 0:
                discount = (
                    (self.original_price - self.discounted_price) / self.original_price
                ) * 100
                self.discount_percentage = round(discount, 2)

        # Calculate total duration if not provided
        if self.total_duration is None:
            total_mins = sum(
                service_item.service.duration for service_item in self.services.all()
            )
            self.total_duration = total_mins if total_mins > 0 else None

        super().save(*args, **kwargs)

    @property
    def is_available(self):
        """Check if package is currently available for purchase"""
        if self.status != "active":
            return False

        # Check purchase limit if set
        if self.max_purchases and self.current_purchases >= self.max_purchases:
            return False

        # Check date range if set
        import datetime

        today = datetime.date.today()
        if self.start_date and self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False

        return True

    @property
    def services_list(self):
        """Return a list of all services in this package"""
        return [service_item.service for service_item in self.services.all()]


class PackageService(models.Model):
    """
    Associates services with packages and specifies service sequence.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name=_("Package"),
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="packages",
        verbose_name=_("Service"),
    )
    sequence = models.PositiveIntegerField(
        _("Sequence"), default=0, help_text=_("Order of services within the package")
    )
    description = models.TextField(
        _("Custom Description"),
        blank=True,
        help_text=_("Custom description of this service within the package"),
    )

    # Optional overrides for this service when part of the package
    custom_duration = models.PositiveIntegerField(
        _("Custom Duration (minutes)"),
        blank=True,
        null=True,
        help_text=_("Override the service duration when part of this package"),
    )

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Package Service")
        verbose_name_plural = _("Package Services")
        ordering = ["sequence"]
        unique_together = ("package", "service")

    def __str__(self):
        return f"{self.package.name} - {self.service.name}"

    @property
    def effective_duration(self):
        """Get the effective duration of this service in the package"""
        return self.custom_duration if self.custom_duration else self.service.duration


class PackageAvailability(models.Model):
    """
    Custom availability windows for packages, overriding shop hours if specified.
    """

    WEEKDAY_CHOICES = (
        (0, _("Sunday")),
        (1, _("Monday")),
        (2, _("Tuesday")),
        (3, _("Wednesday")),
        (4, _("Thursday")),
        (5, _("Friday")),
        (6, _("Saturday")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name="availability",
        verbose_name=_("Package"),
    )
    weekday = models.IntegerField(_("Weekday"), choices=WEEKDAY_CHOICES)
    from_hour = models.TimeField(_("From Hour"))
    to_hour = models.TimeField(_("To Hour"))
    is_closed = models.BooleanField(_("Is Closed"), default=False)

    class Meta:
        verbose_name = _("Package Availability")
        verbose_name_plural = _("Package Availabilities")
        unique_together = ("package", "weekday")

    def __str__(self):
        return f"{self.package.name} - {self.get_weekday_display()}: {self.from_hour.strftime('%I:%M %p')} - {self.to_hour.strftime('%I:%M %p')}"


class PackageFAQ(models.Model):
    """
    Frequently asked questions specific to a package.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name="faqs",
        verbose_name=_("Package"),
    )
    question = models.CharField(_("Question"), max_length=255)
    answer = models.TextField(_("Answer"))
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Package FAQ")
        verbose_name_plural = _("Package FAQs")
        ordering = ["order"]

    def __str__(self):
        return f"{self.package.name} - {self.question}"
