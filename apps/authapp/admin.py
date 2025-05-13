from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from apps.authapp.models import OTP, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "phone_number",
        "user_type",
        "email",
        "is_verified",
        "profile_completed",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = (
        "user_type",
        "is_verified",
        "is_staff",
        "is_active",
        "date_joined",
    )
    search_fields = ("phone_number", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_login")

    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email")}),
        (
            _("User info"),
            {
                "fields": (
                    "user_type",
                    "is_verified",
                    "language_preference",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone_number",
                    "password1",
                    "password2",
                    "user_type",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = (
        "phone_number",
        "code",
        "is_used",
        "created_at",
        "expires_at",
        "verification_attempts",
    )
    list_filter = ("is_used", "created_at", "expires_at")
    search_fields = ("phone_number", "code", "user__phone_number")
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("user",)

    fieldsets = (
        (None, {"fields": ("id", "user", "phone_number", "code")}),
        (_("Status"), {"fields": ("is_used", "verification_attempts")}),
        (_("Timing"), {"fields": ("created_at", "expires_at")}),
    )
