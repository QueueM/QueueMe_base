from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Reel, ReelComment, ReelLike, ReelReport, ReelShare, ReelView


class ReelCommentsInline(admin.TabularInline):
    model = ReelComment
    extra = 0
    readonly_fields = ["user", "content", "created_at"]
    can_delete = True
    show_change_link = True


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "shop",
        "status",
        "view_count",
        "engagement_info",
        "city",
        "created_at",
    ]
    list_filter = ["status", "city", "is_featured", "created_at"]
    search_fields = ["title", "caption", "shop__name"]
    readonly_fields = [
        "view_count",
        "video_preview",
        "likes_count",
        "comments_count",
        "shares_count",
    ]
    fieldsets = (
        (
            None,
            {"fields": ("shop", "title", "caption", "status", "is_featured", "city")},
        ),
        (_("Media"), {"fields": ("video", "video_preview", "thumbnail", "duration")}),
        (
            _("Engagement"),
            {"fields": ("view_count", "likes_count", "comments_count", "shares_count")},
        ),
        (_("Dates"), {"fields": ("created_at", "updated_at", "published_at")}),
    )
    inlines = [ReelCommentsInline]

    def video_preview(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" width="150" height="auto" />', obj.thumbnail.url)
        return "-"

    def likes_count(self, obj):
        return obj.likes.count()

    def comments_count(self, obj):
        return obj.comments.count()

    def shares_count(self, obj):
        return obj.shares.count()

    def engagement_info(self, obj):
        likes = obj.likes.count()
        comments = obj.comments.count()
        shares = obj.shares.count()
        return format_html(
            '<span title="Likes: {}, Comments: {}, Shares: {}">{}L / {}C / {}S</span>',
            likes,
            comments,
            shares,
            likes,
            comments,
            shares,
        )

    engagement_info.short_description = _("Engagement")

    video_preview.short_description = _("Video Preview")
    likes_count.short_description = _("Likes")
    comments_count.short_description = _("Comments")
    shares_count.short_description = _("Shares")


@admin.register(ReelComment)
class ReelCommentAdmin(admin.ModelAdmin):
    list_display = ["user", "reel_title", "content_preview", "is_hidden", "created_at"]
    list_filter = ["is_hidden", "created_at"]
    search_fields = ["content", "user__phone_number", "reel__title"]
    actions = ["hide_comments", "show_comments"]

    def reel_title(self, obj):
        return obj.reel.title

    def content_preview(self, obj):
        if len(obj.content) > 50:
            return f"{obj.content[:50]}..."
        return obj.content

    def hide_comments(self, request, queryset):
        queryset.update(is_hidden=True)

    def show_comments(self, request, queryset):
        queryset.update(is_hidden=False)

    reel_title.short_description = _("Reel")
    content_preview.short_description = _("Content")
    hide_comments.short_description = _("Hide selected comments")
    show_comments.short_description = _("Show selected comments")


@admin.register(ReelReport)
class ReelReportAdmin(admin.ModelAdmin):
    list_display = ["user", "reel_title", "reason", "status", "created_at"]
    list_filter = ["reason", "status", "created_at"]
    search_fields = ["description", "user__phone_number", "reel__title"]
    readonly_fields = ["user", "reel", "reason", "description", "created_at"]
    actions = ["mark_reviewed", "mark_actioned", "mark_dismissed"]

    def reel_title(self, obj):
        return obj.reel.title

    def mark_reviewed(self, request, queryset):
        queryset.update(status="reviewed")

    def mark_actioned(self, request, queryset):
        queryset.update(status="actioned")

    def mark_dismissed(self, request, queryset):
        queryset.update(status="dismissed")

    reel_title.short_description = _("Reel")
    mark_reviewed.short_description = _("Mark as reviewed")
    mark_actioned.short_description = _("Mark as actioned")
    mark_dismissed.short_description = _("Mark as dismissed")


# Register smaller models with simple admin interfaces
admin.site.register(ReelLike)
admin.site.register(ReelShare)
admin.site.register(ReelView)
