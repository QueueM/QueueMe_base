from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.storiesapp.models import Story, StoryView


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("id", "shop", "story_type", "created_at", "expires_at", "is_active")
    list_filter = ("story_type", "is_active", "shop")
    search_fields = ("shop__name",)
    readonly_fields = ("expires_at",)
    date_hierarchy = "created_at"
    fieldsets = (
        (
            _("Story Information"),
            {
                "fields": (
                    "shop",
                    "story_type",
                    "media_url",
                    "thumbnail_url",
                    "is_active",
                )
            },
        ),
        (_("Timestamps"), {"fields": ("created_at", "expires_at")}),
    )


@admin.register(StoryView)
class StoryViewAdmin(admin.ModelAdmin):
    list_display = ("id", "story", "customer", "viewed_at")
    list_filter = ("viewed_at",)
    search_fields = ("story__shop__name", "customer__phone_number")
    date_hierarchy = "viewed_at"
