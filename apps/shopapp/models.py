import uuid

from django.db import models
from django.db.models import Avg
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.geoapp.models import Location


class Shop(models.Model):
    """Shop/branch that belongs to a company"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="shops",
        verbose_name=_("Company"),
    )
    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    avatar = models.ImageField(
        _("Avatar"), upload_to="shops/avatars/", null=True, blank=True
    )
    background_image = models.ImageField(
        _("Background Image"), upload_to="shops/backgrounds/", null=True, blank=True
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        related_name="shops",
        verbose_name=_("Location"),
        null=True,
    )
    phone_number = models.CharField(_("Phone Number"), max_length=20)
    email = models.EmailField(_("Email"), null=True, blank=True)
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="managed_shops",
        verbose_name=_("Manager"),
        null=True,
    )
    is_verified = models.BooleanField(_("Verified"), default=False)
    verification_date = models.DateTimeField(
        _("Verification Date"), null=True, blank=True
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    username = models.CharField(_("Username"), max_length=50, unique=True)

    # SEO and social media fields
    meta_title = models.CharField(_("Meta Title"), max_length=100, blank=True)
    meta_description = models.TextField(_("Meta Description"), blank=True)
    instagram_handle = models.CharField(
        _("Instagram Handle"), max_length=50, blank=True
    )
    twitter_handle = models.CharField(_("Twitter Handle"), max_length=50, blank=True)
    facebook_page = models.CharField(_("Facebook Page"), max_length=100, blank=True)

    # Advanced fields
    is_featured = models.BooleanField(_("Featured Shop"), default=False)
    has_parking = models.BooleanField(_("Has Parking"), default=False)
    accessibility_features = models.JSONField(
        _("Accessibility Features"), default=dict, blank=True
    )
    languages_supported = models.JSONField(_("Languages Supported"), default=list)

    class Meta:
        verbose_name = _("Shop")
        verbose_name_plural = _("Shops")
        ordering = ["-is_featured", "name"]
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["is_verified"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["company"]),
        ]

    def __str__(self):
        return self.name

    def get_avg_rating(self):
        """Get average rating for shop"""
        from apps.reviewapp.models import Review

        avg_rating = (
            Review.objects.filter(
                content_type__model="shop", object_id=self.id
            ).aggregate(Avg("rating"))["rating__avg"]
            or 0
        )
        return round(avg_rating, 1)

    def get_booking_count(self):
        """Get total booking count"""
        from apps.bookingapp.models import Appointment

        return Appointment.objects.filter(shop=self).count()

    def get_specialist_count(self):
        """Get count of specialists in this shop"""
        from apps.specialistsapp.models import Specialist

        return Specialist.objects.filter(employee__shop=self).count()

    def get_service_count(self):
        """Get count of services offered by this shop"""
        from apps.serviceapp.models import Service

        return Service.objects.filter(shop=self).count()

    def get_follower_count(self):
        """Get count of customers following this shop"""
        return self.followers.count()

    def is_open_now(self):
        """Check if shop is currently open"""
        now = timezone.now()
        weekday = now.weekday()

        # Convert to our weekday format (0 = Sunday)
        if weekday == 6:  # If Python's Sunday (6)
            weekday = 0  # Set to our Sunday (0)
        else:
            weekday += 1  # Otherwise add 1

        current_time = now.time()

        try:
            shop_hours = ShopHours.objects.get(shop=self, weekday=weekday)
            if shop_hours.is_closed:
                return False

            return shop_hours.from_hour <= current_time <= shop_hours.to_hour
        except ShopHours.DoesNotExist:
            return False

    def get_translated_field(self, field_name, language=None):
        """Get translated version of a field"""
        from django.utils.translation import get_language

        current_language = language or get_language()

        # Try language-specific field first
        lang_field = f"{field_name}_{current_language}"

        if hasattr(self, lang_field) and getattr(self, lang_field):
            return getattr(self, lang_field)

        # Fall back to default field
        return getattr(self, field_name)


class ShopHours(models.Model):
    """Working hours for a shop"""

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
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="hours", verbose_name=_("Shop")
    )
    weekday = models.IntegerField(_("Weekday"), choices=WEEKDAY_CHOICES)
    from_hour = models.TimeField(_("From Hour"))
    to_hour = models.TimeField(_("To Hour"))
    is_closed = models.BooleanField(_("Is Closed"), default=False)

    class Meta:
        verbose_name = _("Shop Hours")
        verbose_name_plural = _("Shop Hours")
        unique_together = ("shop", "weekday")
        ordering = ["weekday"]

    def __str__(self):
        return f"{self.shop.name} - {self.get_weekday_display()}: {self.from_hour.strftime('%I:%M %p')} - {self.to_hour.strftime('%I:%M %p')}"


class ShopFollower(models.Model):
    """Follower relationship between customer and shop"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="followers", verbose_name=_("Shop")
    )
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="followed_shops",
        verbose_name=_("Customer"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Shop Follower")
        verbose_name_plural = _("Shop Followers")
        unique_together = ("shop", "customer")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shop", "customer"]),
            models.Index(fields=["customer", "created_at"]),
        ]

    def __str__(self):
        return f"{self.customer.phone_number} follows {self.shop.name}"


class ShopSettings(models.Model):
    """Additional settings for a shop"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.OneToOneField(
        Shop, on_delete=models.CASCADE, related_name="settings", verbose_name=_("Shop")
    )
    allow_booking = models.BooleanField(_("Allow Booking"), default=True)
    allow_walk_ins = models.BooleanField(_("Allow Walk-ins"), default=True)
    enforce_check_in = models.BooleanField(_("Enforce Check-in"), default=False)
    check_in_timeout_minutes = models.PositiveIntegerField(
        _("Check-in Timeout (minutes)"), default=15
    )
    grace_period_minutes = models.PositiveIntegerField(
        _("Grace Period (minutes)"), default=10
    )
    cancellation_policy = models.TextField(_("Cancellation Policy"), blank=True)
    notification_preferences = models.JSONField(
        _("Notification Preferences"), default=dict
    )
    booking_lead_time_minutes = models.PositiveIntegerField(
        _("Booking Lead Time (minutes)"), default=0
    )
    booking_future_days = models.PositiveIntegerField(
        _("Booking Future Days"), default=30
    )

    # Advanced settings
    auto_assign_specialist = models.BooleanField(
        _("Auto Assign Specialist"), default=False
    )
    specialist_assignment_algorithm = models.CharField(
        _("Specialist Assignment Algorithm"),
        max_length=50,
        choices=(
            ("round_robin", _("Round Robin")),
            ("least_busy", _("Least Busy")),
            ("highest_rated", _("Highest Rated")),
            ("weighted", _("Weighted Algorithm")),
        ),
        default="round_robin",
    )
    double_booking_allowed = models.BooleanField(
        _("Double Booking Allowed"), default=False
    )
    max_concurrent_bookings = models.PositiveIntegerField(
        _("Max Concurrent Bookings"), default=1
    )

    class Meta:
        verbose_name = _("Shop Settings")
        verbose_name_plural = _("Shop Settings")

    def __str__(self):
        return f"Settings for {self.shop.name}"


class ShopVerification(models.Model):
    """Verification record for a shop"""

    STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("approved", _("Approved")),
        ("rejected", _("Rejected")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="verification_records",
        verbose_name=_("Shop"),
    )
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    submitted_at = models.DateTimeField(_("Submitted At"), auto_now_add=True)
    processed_at = models.DateTimeField(_("Processed At"), null=True, blank=True)
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="processed_verifications",
        verbose_name=_("Processed By"),
        null=True,
        blank=True,
    )
    rejection_reason = models.TextField(_("Rejection Reason"), blank=True)
    documents = models.JSONField(_("Verification Documents"), default=list)

    class Meta:
        verbose_name = _("Shop Verification")
        verbose_name_plural = _("Shop Verifications")
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.shop.name} - {self.get_status_display()}"
