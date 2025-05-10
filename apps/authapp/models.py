import random
import string
import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import FieldTracker

from apps.authapp.constants import OTP_LENGTH, USER_TYPE_CHOICES, USER_TYPE_CUSTOMER
from apps.authapp.validators import normalize_phone_number, validate_phone_number
from apps.authapp.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model that uses phone number for authentication instead of usernames.
    """

    USER_TYPE_CHOICES = (
        ("customer", _("Customer")),
        ("employee", _("Employee")),
        ("admin", _("Admin")),
    )

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, verbose_name=_("ID")
    )
    phone_number = models.CharField(
        _("Phone Number"),
        max_length=20,
        unique=True,
        validators=[validate_phone_number],
    )
    email = models.EmailField(_("Email Address"), blank=True, null=True)
    first_name = models.CharField(_("First Name"), max_length=150, blank=True)
    last_name = models.CharField(_("Last Name"), max_length=150, blank=True)
    is_staff = models.BooleanField(
        _("Staff Status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    is_verified = models.BooleanField(
        _("Verified"),
        default=False,
        help_text=_("Designates whether this user has verified their phone number."),
    )
    user_type = models.CharField(
        _("User Type"),
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default="customer",
    )
    language_preference = models.CharField(
        _("Language Preference"),
        max_length=10,
        choices=[("en", _("English")), ("ar", _("Arabic"))],
        default="en",
    )
    date_joined = models.DateTimeField(_("Date Joined"), default=timezone.now)
    last_login = models.DateTimeField(_("Last Login"), null=True, blank=True)
    
    # Field tracker for detecting changes
    tracker = FieldTracker(fields=['is_active', 'is_verified', 'user_type'])

    objects = UserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["phone_number"]),
            models.Index(fields=["user_type"]),
        ]

    def __str__(self):
        return self.phone_number

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    @property
    def profile_completed(self):
        """Check if user has completed their profile with essential information."""
        # Define what makes a completed profile based on user_type
        if not (self.first_name and self.last_name):
            return False
            
        if self.user_type == "customer":
            # For customers, basic personal info is sufficient
            return bool(self.phone_number and self.is_verified)
        elif self.user_type == "employee":
            # For employees, we might want to check if they have an employee profile
            try:
                return bool(hasattr(self, 'employee') and self.employee)
            except:
                return False
        else:
            # For admins or other types
            return bool(self.email)

    def save(self, *args, **kwargs):
        # Normalize phone number before saving
        self.phone_number = normalize_phone_number(self.phone_number)
        super().save(*args, **kwargs)


class OTP(models.Model):
    """
    One-Time Password model for phone verification.
    """

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, verbose_name=_("ID")
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="otps",
        null=True,
        blank=True,
        verbose_name=_("User"),
    )
    phone_number = models.CharField(
        _("Phone Number"), max_length=20, validators=[validate_phone_number]
    )
    code = models.CharField(_("OTP Code"), max_length=10)
    is_used = models.BooleanField(_("Is Used"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    expires_at = models.DateTimeField(_("Expires At"))
    verification_attempts = models.PositiveSmallIntegerField(
        _("Verification Attempts"),
        default=0,
        help_text=_("Number of times a verification has been attempted with this OTP."),
    )

    class Meta:
        verbose_name = _("OTP")
        verbose_name_plural = _("OTPs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone_number", "is_used"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.phone_number} - {self.code}"

    @staticmethod
    def generate_otp(length=OTP_LENGTH):
        """Generate a numeric OTP code with the specified length."""
        return "".join(random.choices(string.digits, k=length))

    def is_valid(self):
        """Check if OTP is valid (not used, not expired, and has attempts left)."""
        from apps.authapp.constants import MAX_OTP_VERIFICATION_ATTEMPTS

        return (
            not self.is_used
            and timezone.now() < self.expires_at
            and self.verification_attempts < MAX_OTP_VERIFICATION_ATTEMPTS
        )

    def save(self, *args, **kwargs):
        # Normalize phone number before saving
        self.phone_number = normalize_phone_number(self.phone_number)
        super().save(*args, **kwargs)


class SecurityEvent(models.Model):
    """
    Model for storing security-related events for auditing purposes.
    """
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]

    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_events'
    )
    event_type = models.CharField(max_length=100)
    details = models.JSONField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='info')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'event_type', 'created_at']),
            models.Index(fields=['severity', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.user} - {self.created_at}"
