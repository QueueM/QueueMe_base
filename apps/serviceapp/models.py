import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.categoriesapp.models import Category
from apps.shopapp.models import Shop

from .enums import DayOfWeek, ServiceLocationType, ServiceStatus


class Service(models.Model):
    """Service offered by a shop"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="services", verbose_name=_("Shop")
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name=_("Category"),
    )
    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    short_description = models.CharField(
        _("Short Description"), max_length=255, blank=True
    )
    image = models.ImageField(
        _("Image"), upload_to="services/images/", null=True, blank=True
    )
    price = models.DecimalField(_("Price"), max_digits=10, decimal_places=2)
    price_halalas = models.PositiveIntegerField(_("Price in Halalas"), editable=False)
    duration = models.PositiveIntegerField(
        _("Duration (minutes)"),
        validators=[MinValueValidator(1), MaxValueValidator(1440)],  # Max 24 hours
    )
    slot_granularity = models.PositiveIntegerField(
        _("Slot Granularity (minutes)"),
        default=30,
        validators=[
            MinValueValidator(5),
            MaxValueValidator(120),
        ],  # Between 5 min and 2 hours
    )
    buffer_before = models.PositiveIntegerField(
        _("Buffer Before (minutes)"),
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(120)],
    )
    buffer_after = models.PositiveIntegerField(
        _("Buffer After (minutes)"),
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(120)],
    )
    service_location = models.CharField(
        _("Service Location"),
        max_length=10,
        choices=ServiceLocationType.choices,
        default=ServiceLocationType.IN_SHOP,
    )
    status = models.CharField(
        _("Status"),
        max_length=10,
        choices=ServiceStatus.choices,
        default=ServiceStatus.ACTIVE,
    )
    has_custom_availability = models.BooleanField(
        _("Has Custom Availability"), default=False
    )
    min_booking_notice = models.PositiveIntegerField(
        _("Minimum Booking Notice (minutes)"),
        default=0,
        help_text=_("Minimum time before a slot that booking is allowed"),
    )
    max_advance_booking_days = models.PositiveIntegerField(
        _("Maximum Advance Booking (days)"),
        default=30,
        help_text=_("How far in advance bookings are allowed"),
    )
    order = models.PositiveIntegerField(
        _("Order"), default=0, help_text=_("Display order")
    )
    is_featured = models.BooleanField(_("Featured"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Service")
        verbose_name_plural = _("Services")
        ordering = ["order", "name"]
        indexes = [
            models.Index(fields=["shop", "status"]),
            models.Index(fields=["service_location"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.shop.name})"

    def save(self, *args, **kwargs):
        # Convert price to halalas (1 SAR = 100 Halalas)
        self.price_halalas = int(self.price * 100)
        super().save(*args, **kwargs)

    @property
    def total_duration(self):
        """Total duration including buffers"""
        return self.buffer_before + self.duration + self.buffer_after

    @property
    def is_available(self):
        """Check if service is currently available"""
        return self.status == ServiceStatus.ACTIVE

    @property
    def specialists_count(self):
        """Count of specialists assigned to this service"""
        return self.specialists.count()

    @property
    def average_rating(self):
        """Calculate average rating from reviews"""
        from apps.reviewapp.models import Review

        reviews = Review.objects.filter(
            content_type__model="service", object_id=self.id
        )
        if not reviews.exists():
            return 0
        return reviews.aggregate(models.Avg("rating"))["rating__avg"] or 0

    @property
    def review_count(self):
        """Count of reviews for this service"""
        from apps.reviewapp.models import Review

        return Review.objects.filter(
            content_type__model="service", object_id=self.id
        ).count()


class ServiceOverview(models.Model):
    """Overview item for a service (shown in service detail screen)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="overviews",
        verbose_name=_("Service"),
    )
    title = models.CharField(_("Title"), max_length=100)
    image = models.ImageField(
        _("Image"), upload_to="services/overviews/", null=True, blank=True
    )
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Service Overview")
        verbose_name_plural = _("Service Overviews")
        ordering = ["order"]

    def __str__(self):
        return f"{self.service.name} - {self.title}"


class ServiceStep(models.Model):
    """How It Works step for a service (shown in service detail screen)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="steps",
        verbose_name=_("Service"),
    )
    title = models.CharField(_("Title"), max_length=100)
    description = models.TextField(_("Description"))
    image = models.ImageField(
        _("Image"), upload_to="services/steps/", null=True, blank=True
    )
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Service Step")
        verbose_name_plural = _("Service Steps")
        ordering = ["order"]

    def __str__(self):
        return f"{self.service.name} - Step {self.order}: {self.title}"


class ServiceAftercare(models.Model):
    """Aftercare tip for a service (shown in service detail screen)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="aftercare_tips",
        verbose_name=_("Service"),
    )
    title = models.CharField(_("Title"), max_length=255)
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Aftercare Tip")
        verbose_name_plural = _("Aftercare Tips")
        ordering = ["order"]

    def __str__(self):
        return f"{self.service.name} - {self.title}"


class ServiceFAQ(models.Model):
    """FAQ for a service"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="faqs",
        verbose_name=_("Service"),
    )
    question = models.CharField(_("Question"), max_length=255)
    answer = models.TextField(_("Answer"))
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Service FAQ")
        verbose_name_plural = _("Service FAQs")
        ordering = ["order"]

    def __str__(self):
        return f"{self.service.name} - {self.question}"


class ServiceAvailability(models.Model):
    """Custom availability for a service"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="availability",
        verbose_name=_("Service"),
    )
    weekday = models.IntegerField(_("Weekday"), choices=DayOfWeek.choices)
    from_hour = models.TimeField(_("From Hour"))
    to_hour = models.TimeField(_("To Hour"))
    is_closed = models.BooleanField(_("Is Closed"), default=False)

    class Meta:
        verbose_name = _("Service Availability")
        verbose_name_plural = _("Service Availabilities")
        unique_together = ("service", "weekday")

    def __str__(self):
        return f"{self.service.name} - {self.get_weekday_display()}: {self.from_hour.strftime('%I:%M %p')} - {self.to_hour.strftime('%I:%M %p')}"


class ServiceException(models.Model):
    """Exception day for service (holiday, special hours, etc.)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="exceptions",
        verbose_name=_("Service"),
    )
    date = models.DateField(_("Date"))
    is_closed = models.BooleanField(_("Is Closed"), default=True)
    from_hour = models.TimeField(_("From Hour"), null=True, blank=True)
    to_hour = models.TimeField(_("To Hour"), null=True, blank=True)
    reason = models.CharField(_("Reason"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("Service Exception")
        verbose_name_plural = _("Service Exceptions")
        unique_together = ("service", "date")

    def __str__(self):
        if self.is_closed:
            return f"{self.service.name} - {self.date.strftime('%Y-%m-%d')} (Closed)"
        return f"{self.service.name} - {self.date.strftime('%Y-%m-%d')}: {self.from_hour.strftime('%I:%M %p')} - {self.to_hour.strftime('%I:%M %p')}"
