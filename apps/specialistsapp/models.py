import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.categoriesapp.models import Category
from apps.employeeapp.models import Employee
from apps.serviceapp.models import Service
from apps.specialistsapp.constants import EXPERIENCE_LEVEL_CHOICES


class Specialist(models.Model):
    """Specialist profile extending an employee"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="specialist",
        verbose_name=_("Employee"),
    )
    bio = models.TextField(_("Bio"), blank=True)
    experience_years = models.PositiveIntegerField(_("Experience (years)"), default=0)
    experience_level = models.CharField(
        _("Experience Level"),
        max_length=20,
        choices=EXPERIENCE_LEVEL_CHOICES,
        default="intermediate",
    )
    is_verified = models.BooleanField(_("Verified"), default=False)
    verified_at = models.DateTimeField(_("Verified At"), null=True, blank=True)
    expertise = models.ManyToManyField(
        Category,
        related_name="specialists",
        verbose_name=_("Expertise Categories"),
        blank=True,
    )
    services = models.ManyToManyField(
        Service,
        through="SpecialistService",
        related_name="specialists",
        verbose_name=_("Services"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    avg_rating = models.DecimalField(
        _("Average Rating"),
        max_digits=3,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    total_bookings = models.PositiveIntegerField(_("Total Bookings"), default=0)

    class Meta:
        verbose_name = _("Specialist")
        verbose_name_plural = _("Specialists")
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["is_verified"]),
            models.Index(fields=["avg_rating"]),
            models.Index(fields=["total_bookings"]),
        ]

    def __str__(self):
        return f"{self.employee.first_name} {self.employee.last_name}"

    def get_shop(self):
        """Get the shop this specialist belongs to"""
        return self.employee.shop

    def update_rating(self):
        """Update average rating based on reviews"""
        from apps.reviewapp.models import Review

        reviews = Review.objects.filter(
            content_type__model="specialist", object_id=str(self.id)
        )

        if reviews.exists():
            total_rating = sum(review.rating for review in reviews)
            self.avg_rating = total_rating / reviews.count()
        else:
            self.avg_rating = 0

        self.save(update_fields=["avg_rating"])

    def get_top_services(self, limit=3):
        """Get the specialist's top services based on bookings"""
        return self.specialist_services.order_by("-booking_count")[:limit]

    def is_available_on_date(self, date):
        """Check if specialist is available on a specific date"""
        weekday = date.weekday()
        # Convert to our weekday format (0 = Sunday)
        if weekday == 6:  # If it's Sunday in Python's format
            weekday = 0
        else:
            weekday += 1

        return self.working_hours.filter(weekday=weekday, is_off=False).exists()


class SpecialistService(models.Model):
    """Association between specialists and services"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    specialist = models.ForeignKey(
        Specialist,
        on_delete=models.CASCADE,
        related_name="specialist_services",
        verbose_name=_("Specialist"),
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="specialist_services",
        verbose_name=_("Service"),
    )
    is_primary = models.BooleanField(_("Primary Service"), default=False)
    proficiency_level = models.PositiveSmallIntegerField(
        _("Proficiency Level"),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=3,
        help_text=_("Proficiency level from 1 (basic) to 5 (expert)"),
    )
    custom_duration = models.PositiveIntegerField(
        _("Custom Duration (minutes)"),
        null=True,
        blank=True,
        help_text=_("If different from service default duration"),
    )
    booking_count = models.PositiveIntegerField(_("Booking Count"), default=0)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Specialist Service")
        verbose_name_plural = _("Specialist Services")
        unique_together = ("specialist", "service")
        ordering = ["-is_primary", "-booking_count"]

    def __str__(self):
        return f"{self.specialist.employee.first_name} - {self.service.name}"

    def get_effective_duration(self):
        """Get the effective duration (custom or service default)"""
        return self.custom_duration or self.service.duration

    def increment_booking_count(self):
        """Increment the booking count for this service"""
        self.booking_count += 1
        self.save(update_fields=["booking_count"])

        # Also increment specialist's total bookings
        self.specialist.total_bookings += 1
        self.specialist.save(update_fields=["total_bookings"])


class SpecialistWorkingHours(models.Model):
    """Working hours for a specialist"""

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
    specialist = models.ForeignKey(
        Specialist,
        on_delete=models.CASCADE,
        related_name="working_hours",
        verbose_name=_("Specialist"),
    )
    weekday = models.IntegerField(_("Weekday"), choices=WEEKDAY_CHOICES)
    from_hour = models.TimeField(_("From Hour"))
    to_hour = models.TimeField(_("To Hour"))
    is_off = models.BooleanField(_("Day Off"), default=False)

    class Meta:
        verbose_name = _("Specialist Working Hours")
        verbose_name_plural = _("Specialist Working Hours")
        unique_together = ("specialist", "weekday")
        ordering = ["weekday", "from_hour"]

    def __str__(self):
        specialist_name = f"{self.specialist.employee.first_name} {self.specialist.employee.last_name}"
        return f"{specialist_name} - {self.get_weekday_display()}: {self.from_hour.strftime('%I:%M %p')} - {self.to_hour.strftime('%I:%M %p')}"

    def overlaps_with_shop_hours(self):
        """Check if working hours overlap with shop hours"""
        shop = self.specialist.employee.shop
        shop_hours = shop.hours.filter(weekday=self.weekday).first()

        if not shop_hours or shop_hours.is_closed:
            return False

        return (
            self.from_hour >= shop_hours.from_hour
            and self.to_hour <= shop_hours.to_hour
        )


class PortfolioItem(models.Model):
    """Portfolio item for a specialist"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    specialist = models.ForeignKey(
        Specialist,
        on_delete=models.CASCADE,
        related_name="portfolio",
        verbose_name=_("Specialist"),
    )
    title = models.CharField(_("Title"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    image = models.ImageField(_("Image"), upload_to="specialists/portfolio/")
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        related_name="portfolio_items",
        verbose_name=_("Service"),
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="portfolio_items",
        verbose_name=_("Category"),
        null=True,
        blank=True,
    )
    likes_count = models.PositiveIntegerField(_("Likes Count"), default=0)
    is_featured = models.BooleanField(_("Featured"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Portfolio Item")
        verbose_name_plural = _("Portfolio Items")
        ordering = ["-is_featured", "-created_at"]

    def __str__(self):
        return f"{self.specialist.employee.first_name} - {self.title}"

    def thumbnail_url(self):
        """Get thumbnail URL, useful for serializers"""
        if self.image:
            return self.image.url
        return None
