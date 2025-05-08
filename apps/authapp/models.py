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

from apps.authapp.constants import OTP_LENGTH, USER_TYPE_CHOICES, USER_TYPE_CUSTOMER
from apps.authapp.validators import normalize_phone_number, validate_phone_number


class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        """
        Create and save a user with the given phone number and password.
        """
        if not phone_number:
            raise ValueError(_("Phone number is required"))

        # Normalize the phone number
        phone_number = normalize_phone_number(phone_number)

        user = self.model(phone_number=phone_number, **extra_fields)

        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        """
        Create and save a superuser with the given phone number and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("profile_completed", True)
        extra_fields.setdefault("user_type", "admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model that uses phone number for authentication instead of usernames.
    """

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, verbose_name=_("ID")
    )
    phone_number = models.CharField(
        _("Phone Number"),
        max_length=20,
        unique=True,
        validators=[validate_phone_number],
    )
    user_type = models.CharField(
        _("User Type"),
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default=USER_TYPE_CUSTOMER,
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
    profile_completed = models.BooleanField(
        _("Profile Completed"),
        default=False,
        help_text=_("Designates whether the user has completed their profile."),
    )
    language_preference = models.CharField(
        _("Language Preference"),
        max_length=10,
        choices=[("en", _("English")), ("ar", _("Arabic"))],
        default="en",
    )
    date_joined = models.DateTimeField(_("Date Joined"), default=timezone.now)
    last_login = models.DateTimeField(_("Last Login"), null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["-date_joined"]

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
