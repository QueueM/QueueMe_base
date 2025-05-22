from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.translation import gettext_lazy as _

from apps.reviewapp.models import (
    PlatformReview,
    ReviewHelpfulness,
    ReviewMedia,
    ReviewMetric,
    ReviewReport,
    ServiceReview,
    ShopReview,
    SpecialistReview,
)
from apps.reviewapp.services.rating_service import RatingService


class ReviewMediaInline(GenericTabularInline):
    model = ReviewMedia
    extra = 0
    fields = ["media_file", "media_type", "created_at"]
    readonly_fields = ["created_at"]
    can_delete = True


class BaseReviewAdmin(admin.ModelAdmin):
    """Base admin for all review types"""

    list_display = ["get_user_name", "title", "rating", "status", "created_at"]
    list_filter = ["rating", "status", "created_at", "is_verified_purchase"]
    search_fields = ["title", "content", "user__phone_number"]
    readonly_fields = ["created_at", "updated_at", "user", "moderated_by"]
    actions = ["approve_reviews", "reject_reviews"]

    def get_user_name(self, obj):
        """Get user name for display"""
        if not obj.user:
            return _("Anonymous")
        return obj.user.phone_number

    get_user_name.short_description = _("User")

    def approve_reviews(self, request, queryset):
        """Approve selected reviews"""
        updated = queryset.update(status="approved", moderated_by=request.user)

        # Update metrics for each entity
        for review in queryset:
            if hasattr(review, "shop"):
                RatingService.update_entity_metrics("shopapp.Shop", review.shop.id)
            elif hasattr(review, "specialist"):
                RatingService.update_entity_metrics(
                    "specialistsapp.Specialist", review.specialist.id
                )
            elif hasattr(review, "service"):
                RatingService.update_entity_metrics(
                    "serviceapp.Service", review.service.id
                )

        self.message_user(request, _("Approved {} reviews.").format(updated))

    approve_reviews.short_description = _("Approve selected reviews")

    def reject_reviews(self, request, queryset):
        """Reject selected reviews"""
        updated = queryset.update(status="rejected", moderated_by=request.user)

        # Update metrics for each entity
        for review in queryset:
            if hasattr(review, "shop"):
                RatingService.update_entity_metrics("shopapp.Shop", review.shop.id)
            elif hasattr(review, "specialist"):
                RatingService.update_entity_metrics(
                    "specialistsapp.Specialist", review.specialist.id
                )
            elif hasattr(review, "service"):
                RatingService.update_entity_metrics(
                    "serviceapp.Service", review.service.id
                )

        self.message_user(request, _("Rejected {} reviews.").format(updated))

    reject_reviews.short_description = _("Reject selected reviews")


@admin.register(ShopReview)
class ShopReviewAdmin(BaseReviewAdmin):
    """Admin for shop reviews"""

    list_display = BaseReviewAdmin.list_display + ["shop"]
    list_filter = BaseReviewAdmin.list_filter + ["shop"]
    raw_id_fields = ["shop", "related_booking"]
    inlines = [ReviewMediaInline]


@admin.register(SpecialistReview)
class SpecialistReviewAdmin(BaseReviewAdmin):
    """Admin for specialist reviews"""

    list_display = BaseReviewAdmin.list_display + ["specialist"]
    list_filter = BaseReviewAdmin.list_filter + ["specialist"]
    raw_id_fields = ["specialist", "related_booking"]
    inlines = [ReviewMediaInline]


@admin.register(ServiceReview)
class ServiceReviewAdmin(BaseReviewAdmin):
    """Admin for service reviews"""

    list_display = BaseReviewAdmin.list_display + ["service"]
    list_filter = BaseReviewAdmin.list_filter + ["service"]
    raw_id_fields = ["service", "related_booking"]
    inlines = [ReviewMediaInline]


@admin.register(PlatformReview)
class PlatformReviewAdmin(BaseReviewAdmin):
    """Admin for platform reviews"""

    list_display = BaseReviewAdmin.list_display + ["company", "category"]
    list_filter = BaseReviewAdmin.list_filter + ["category"]
    raw_id_fields = ["company"]


@admin.register(ReviewMedia)
class ReviewMediaAdmin(admin.ModelAdmin):
    """Admin for review media"""

    list_display = ["id", "content_type", "media_type", "created_at"]
    list_filter = ["media_type", "content_type", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(ReviewHelpfulness)
class ReviewHelpfulnessAdmin(admin.ModelAdmin):
    """Admin for review helpfulness votes"""

    list_display = ["user", "content_type", "is_helpful", "created_at"]
    list_filter = ["is_helpful", "content_type", "created_at"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["user"]


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    """Admin for review reports"""

    list_display = ["reporter", "content_type", "reason", "status", "created_at"]
    list_filter = ["reason", "status", "content_type", "created_at"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["reporter"]
    search_fields = ["details", "reporter__phone_number"]
    actions = ["mark_reviewed", "mark_resolved", "mark_rejected"]

    def mark_reviewed(self, request, queryset):
        """Mark selected reports as reviewed"""
        updated = queryset.update(status="reviewed")
        self.message_user(request, _("Marked {} reports as reviewed.").format(updated))

    mark_reviewed.short_description = _("Mark as reviewed")

    def mark_resolved(self, request, queryset):
        """Mark selected reports as resolved"""
        updated = queryset.update(status="resolved")
        self.message_user(request, _("Marked {} reports as resolved.").format(updated))

    mark_resolved.short_description = _("Mark as resolved")

    def mark_rejected(self, request, queryset):
        """Mark selected reports as rejected"""
        updated = queryset.update(status="rejected")
        self.message_user(request, _("Marked {} reports as rejected.").format(updated))

    mark_rejected.short_description = _("Reject reports")


@admin.register(ReviewMetric)
class ReviewMetricAdmin(admin.ModelAdmin):
    """Admin for review metrics"""

    list_display = [
        "id",
        "content_type",
        "avg_rating",
        "weighted_rating",
        "review_count",
        "updated_at",
    ]
    list_filter = ["content_type", "updated_at"]
    readonly_fields = [
        "avg_rating",
        "weighted_rating",
        "review_count",
        "rating_distribution",
        "last_reviewed_at",
        "updated_at",
    ]
    search_fields = ["object_id"]

    def has_add_permission(self, request):
        """Prevent adding metrics manually"""
        return False
