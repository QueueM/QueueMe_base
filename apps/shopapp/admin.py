from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Shop, ShopFollower, ShopHours, ShopSettings, ShopVerification


class ShopHoursInline(admin.TabularInline):
    model = ShopHours
    extra = 7  # Show all days of the week
    max_num = 7


class ShopSettingsInline(admin.StackedInline):
    model = ShopSettings
    can_delete = False


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "location",
        "manager",
        "is_verified",
        "is_active",
        "created_at",
    )
    list_filter = ("is_verified", "is_active", "created_at")
    search_fields = ("name", "description", "phone_number", "email", "username")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ShopHoursInline, ShopSettingsInline]
    fieldsets = (
        (None, {"fields": ("id", "company", "name", "description", "username")}),
        (_("Contact Information"), {"fields": ("phone_number", "email")}),
        (_("Media"), {"fields": ("avatar", "background_image")}),
        (_("Location & Management"), {"fields": ("location", "manager")}),
        (_("Status"), {"fields": ("is_verified", "verification_date", "is_active")}),
        (_("Metadata"), {"fields": ("created_at", "updated_at")}),
        (
            _("SEO & Social"),
            {
                "fields": (
                    "meta_title",
                    "meta_description",
                    "instagram_handle",
                    "twitter_handle",
                    "facebook_page",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Advanced Options"),
            {
                "fields": (
                    "is_featured",
                    "has_parking",
                    "accessibility_features",
                    "languages_supported",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    actions = ["mark_as_verified", "mark_as_unverified", "activate", "deactivate"]

    def mark_as_verified(self, request, queryset):
        from django.utils import timezone

        count = queryset.update(is_verified=True, verification_date=timezone.now())
        self.message_user(request, _(f"{count} shops were marked as verified."))

    mark_as_verified.short_description = _("Mark selected shops as verified")

    def mark_as_unverified(self, request, queryset):
        count = queryset.update(is_verified=False, verification_date=None)
        self.message_user(request, _(f"{count} shops were marked as unverified."))

    mark_as_unverified.short_description = _("Mark selected shops as unverified")

    def activate(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, _(f"{count} shops were activated."))

    activate.short_description = _("Activate selected shops")

    def deactivate(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, _(f"{count} shops were deactivated."))

    deactivate.short_description = _("Deactivate selected shops")


@admin.register(ShopHours)
class ShopHoursAdmin(admin.ModelAdmin):
    list_display = ("shop", "weekday", "from_hour", "to_hour", "is_closed")
    list_filter = ("weekday", "is_closed")
    search_fields = ("shop__name",)


@admin.register(ShopFollower)
class ShopFollowerAdmin(admin.ModelAdmin):
    list_display = ("shop", "customer", "created_at")
    list_filter = ("created_at",)
    search_fields = ("shop__name", "customer__phone_number")
    readonly_fields = ("id", "created_at")


@admin.register(ShopSettings)
class ShopSettingsAdmin(admin.ModelAdmin):
    list_display = ("shop", "allow_booking", "allow_walk_ins", "auto_assign_specialist")
    list_filter = (
        "allow_booking",
        "allow_walk_ins",
        "enforce_check_in",
        "auto_assign_specialist",
    )
    search_fields = ("shop__name",)
    fieldsets = (
        (None, {"fields": ("shop",)}),
        (
            _("Booking Settings"),
            {
                "fields": (
                    "allow_booking",
                    "booking_lead_time_minutes",
                    "booking_future_days",
                )
            },
        ),
        (_("Walk-in Settings"), {"fields": ("allow_walk_ins",)}),
        (
            _("Check-in Settings"),
            {
                "fields": (
                    "enforce_check_in",
                    "check_in_timeout_minutes",
                    "grace_period_minutes",
                )
            },
        ),
        (_("Policies"), {"fields": ("cancellation_policy",)}),
        (_("Notifications"), {"fields": ("notification_preferences",)}),
        (
            _("Advanced Scheduling"),
            {
                "fields": (
                    "auto_assign_specialist",
                    "specialist_assignment_algorithm",
                    "double_booking_allowed",
                    "max_concurrent_bookings",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(ShopVerification)
class ShopVerificationAdmin(admin.ModelAdmin):
    list_display = ("shop", "status", "submitted_at", "processed_at", "processed_by")
    list_filter = ("status", "submitted_at", "processed_at")
    search_fields = ("shop__name",)
    readonly_fields = ("id", "submitted_at")
    fieldsets = (
        (None, {"fields": ("id", "shop", "status")}),
        (_("Documents"), {"fields": ("documents",)}),
        (
            _("Processing"),
            {"fields": ("processed_by", "processed_at", "rejection_reason")},
        ),
        (_("Metadata"), {"fields": ("submitted_at",)}),
    )
    actions = ["approve_verification", "reject_verification"]

    def approve_verification(self, request, queryset):
        pass

        from apps.shopapp.services.verification_service import VerificationService

        for verification in queryset.filter(status="pending"):
            VerificationService.approve_verification(verification.id, request.user.id)

        self.message_user(request, _("Selected verifications have been approved."))

    approve_verification.short_description = _("Approve selected verifications")

    def reject_verification(self, request, queryset):
        self.message_user(
            request, _("Please reject verifications individually to provide reason.")
        )

    reject_verification.short_description = _("Reject selected verifications")
