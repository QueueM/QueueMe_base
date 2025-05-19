# apps/companiesapp/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from . import models


# ────────────────────────────────────────────────────────────────
#  Shared mixin – owner-only change / delete, admins unrestricted
# ────────────────────────────────────────────────────────────────
class OwnerRestrictedAdmin(admin.ModelAdmin):
    """
    Super-users & QueueMe platform admins can do anything.
    Company owners can only act on their own rows.
    """

    # -- list view: hide rows the user doesn't own ----------------
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or getattr(request.user, "user_type", "") == "admin":
            return qs
        return qs.filter(owner=request.user) if hasattr(qs.model, "owner") else qs

    # -- object-level perms ---------------------------------------
    def _is_owner(self, request, obj):
        return obj and hasattr(obj, "owner") and obj.owner == request.user

    def has_view_permission(self, request, obj=None):
        if obj is None:
            return True  # list view allowed by get_queryset
        return (
            request.user.is_superuser
            or getattr(request.user, "user_type", "") == "admin"
            or self._is_owner(request, obj)
        )

    # all other CRUD perms funnel through change/delete/add
    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_add_permission(self, request):
        # company owners may add; employees cannot
        return request.user.is_superuser or getattr(request.user, "user_type", "") in {"admin", "owner"}


# ────────────────────────────────────────────────────────────────
#  Inline helpers
# ────────────────────────────────────────────────────────────────
class CompanyDocumentInline(admin.TabularInline):
    model = models.CompanyDocument
    extra = 0
    fields = ("title", "document_type", "is_verified", "uploaded_at")
    readonly_fields = ("uploaded_at",)
    can_delete = False
    show_change_link = True


class CompanySettingsInline(admin.StackedInline):
    model = models.CompanySettings
    can_delete = False
    fk_name = "company"
    verbose_name_plural = _("Settings")
    fieldsets = (
        (_("Localization"), {"fields": ("default_language",)}),
        (_("Notifications"), {"fields": ("notification_email", "notification_sms")}),
        (_("Booking"), {"fields": ("auto_approve_bookings",)}),
        (_("Discounts"), {"fields": ("require_manager_approval_for_discounts",)}),
        (_("Chat"), {"fields": ("allow_employee_chat",)}),
    )


# ────────────────────────────────────────────────────────────────
#  Company admin
# ────────────────────────────────────────────────────────────────
@admin.register(models.Company)
class CompanyAdmin(OwnerRestrictedAdmin):
    list_display = (
        "name",
        "owner",
        "subscription_status",
        "employee_count",
        "shop_count",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "subscription_status", "created_at", "location__country")
    search_fields = ("name", "registration_number", "owner__username", "owner__email")
    autocomplete_fields = ("owner", "location")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    inlines = (CompanySettingsInline, CompanyDocumentInline)
    readonly_fields = ("created_at", "updated_at", "employee_count", "shop_count")

    fieldsets = (
        (_("General"), {"fields": ("name", "logo", "description")}),
        (_("Legal"), {"fields": ("registration_number",)}),
        (_("Owner & Contact"), {"fields": ("owner", "contact_email", "contact_phone")}),
        (_("Location"), {"fields": ("location",)}),
        (_("Subscription / Metrics"), {"fields": ("subscription_status", "subscription_end_date", "employee_count", "shop_count")}),
        (_("Status"), {"fields": ("is_active", "created_at", "updated_at")}),
    )


# ────────────────────────────────────────────────────────────────
#  Stand-alone document admin (for quick search / bulk verify)
# ────────────────────────────────────────────────────────────────
@admin.register(models.CompanyDocument)
class CompanyDocumentAdmin(OwnerRestrictedAdmin):
    list_display = ("title", "company", "document_type", "is_verified", "uploaded_at")
    list_filter = ("is_verified", "document_type", "uploaded_at")
    search_fields = ("title", "company__name", "company__owner__username")
    autocomplete_fields = ("company", "verified_by")
    readonly_fields = ("uploaded_at", "verified_at")


# CompanySettings is edited inline, but keep a direct link if you like:
@admin.register(models.CompanySettings)
class CompanySettingsAdmin(OwnerRestrictedAdmin):
    list_display = ("company", "default_language", "notification_email", "auto_approve_bookings")
    autocomplete_fields = ("company",)
