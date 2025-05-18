# apps/storiesapp/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.storiesapp.models import Story, StoryView


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("id", "shop", "story_type", "created_at", "expires_at", "is_active")
    list_filter = ("story_type", "is_active", "shop")
    search_fields = ("shop__name",)
    date_hierarchy = "created_at"

    # Make both expires_at and created_at readonly
    readonly_fields = ("expires_at", "created_at")

    def get_fieldsets(self, request, obj=None):
        # On add: omit timestamps
        info_fields = ["shop", "story_type", "media_url", "thumbnail_url", "is_active"]
        if obj is None:
            return [
                (
                    _("Story Information"),
                    {"fields": info_fields},
                ),
            ]
        # On change: include timestamps
        return [
            (
                _("Story Information"),
                {"fields": info_fields},
            ),
            (
                _("Timestamps"),
                {"fields": ("created_at", "expires_at")},
            ),
        ]


@admin.register(StoryView)
class StoryViewAdmin(admin.ModelAdmin):
    list_display = ("id", "story", "customer", "viewed_at")
    list_filter = ("viewed_at",)
    search_fields = ("story__shop__name", "customer__phone_number")
    date_hierarchy = "viewed_at"

    # viewed_at is auto_now_add
    readonly_fields = ("viewed_at",)

    def get_fieldsets(self, request, obj=None):
        # On add: omit viewed_at
        base = ["story", "customer"]
        if obj is None:
            return [
                (None, {"fields": base}),
            ]
        # On change: include viewed_at
        return [
            (None, {"fields": base}),
            (_("Timestamps"), {"fields": ("viewed_at",)}),
        ]
