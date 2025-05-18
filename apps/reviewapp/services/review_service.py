import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.reviewapp.models import (
    PlatformReview,
    ReviewHelpfulness,
    ReviewMedia,
    ReviewReport,
    ServiceReview,
    ShopReview,
    SpecialistReview,
)
from apps.reviewapp.services.review_validator import ReviewValidator
from apps.reviewapp.services.sentiment_analyzer import SentimentAnalyzer

logger = logging.getLogger(__name__)


class ReviewService:
    """Service for review management"""

    @staticmethod
    def create_review(entity_type, entity_id, user, data, media_files=None):
        """Create a new review for an entity

        Args:
            entity_type (str): Type of entity being reviewed (shop, specialist, service, platform)
            entity_id (uuid): ID of the entity
            user (User): User creating the review
            data (dict): Review data (title, rating, content, etc.)
            media_files (list): Optional list of media files to attach

        Returns:
            Review: The created review
        """
        # Validate review data
        ReviewValidator.validate_review_data(data)

        # Validate media files if provided
        if media_files:
            ReviewValidator.validate_media_files(media_files)

        # Validate review eligibility
        ReviewValidator.validate_review_eligibility(entity_type, entity_id, user)

        # Analyze sentiment for potential automated moderation
        sentiment_score = None
        if data.get("content"):
            sentiment_score = SentimentAnalyzer.analyze_text(data["content"])

            # Log suspicious reviews for manual review
            if sentiment_score < -0.7:  # Very negative sentiment
                logger.warning(
                    f"Suspicious review detected from user {user.id} for {entity_type} {entity_id} with sentiment score {sentiment_score}"
                )

        with transaction.atomic():
            # Create the review based on entity type
            if entity_type == "shop":
                review = ShopReview.objects.create(
                    shop_id=entity_id,
                    user=user,
                    title=data["title"],
                    rating=data["rating"],
                    content=data.get("content", ""),
                    city=data.get("city", ""),
                    related_booking_id=data.get("booking_id"),
                    # Set status based on sentiment or config
                    status=(
                        "pending" if sentiment_score and sentiment_score < -0.5 else "approved"
                    ),
                )
            elif entity_type == "specialist":
                review = SpecialistReview.objects.create(
                    specialist_id=entity_id,
                    user=user,
                    title=data["title"],
                    rating=data["rating"],
                    content=data.get("content", ""),
                    city=data.get("city", ""),
                    related_booking_id=data.get("booking_id"),
                    # Set status based on sentiment or config
                    status=(
                        "pending" if sentiment_score and sentiment_score < -0.5 else "approved"
                    ),
                )
            elif entity_type == "service":
                review = ServiceReview.objects.create(
                    service_id=entity_id,
                    user=user,
                    title=data["title"],
                    rating=data["rating"],
                    content=data.get("content", ""),
                    city=data.get("city", ""),
                    related_booking_id=data.get("booking_id"),
                    # Set status based on sentiment or config
                    status=(
                        "pending" if sentiment_score and sentiment_score < -0.5 else "approved"
                    ),
                )
            elif entity_type == "platform":
                review = PlatformReview.objects.create(
                    company_id=entity_id,
                    user=user,
                    title=data["title"],
                    rating=data["rating"],
                    content=data.get("content", ""),
                    category=data.get("category", ""),
                    # Platform reviews always need moderation
                    status="pending",
                )
            else:
                raise ValueError(f"Invalid entity type: {entity_type}")

            # Attach media files if provided
            if media_files:
                ReviewService.attach_media_to_review(review, media_files)

            # Update metrics for the entity if review is approved
            if review.status == "approved":
                from apps.reviewapp.services.rating_service import RatingService

                if entity_type == "shop":
                    RatingService.update_entity_metrics("shopapp.Shop", entity_id)
                elif entity_type == "specialist":
                    RatingService.update_entity_metrics("specialistsapp.Specialist", entity_id)
                elif entity_type == "service":
                    RatingService.update_entity_metrics("serviceapp.Service", entity_id)

            return review

    @staticmethod
    def attach_media_to_review(review, media_files):
        """Attach media files to a review

        Args:
            review: The review to attach media to
            media_files (list): List of media files to attach
        """
        content_type = ContentType.objects.get_for_model(review)

        for media_file in media_files:
            # Determine media type from file extension
            filename = media_file.name.lower()
            media_type = "image"  # Default

            if filename.endswith((".mp4", ".mov", ".avi", ".wmv")):
                media_type = "video"

            # Create media attachment
            ReviewMedia.objects.create(
                content_type=content_type,
                object_id=review.id,
                media_file=media_file,
                media_type=media_type,
            )

    @staticmethod
    def moderate_review(review, status, moderator, comment=None):
        """Moderate a review

        Args:
            review: The review to moderate
            status (str): New status (approved, rejected)
            moderator (User): User performing the moderation
            comment (str, optional): Moderation comment

        Returns:
            Review: The updated review
        """
        if status not in ["approved", "rejected"]:
            raise ValueError(f"Invalid status: {status}")

        old_status = review.status
        review.status = status
        review.moderation_comment = comment or ""
        review.moderated_by = moderator
        review.save()

        # If status changed, update metrics
        if old_status != status:
            from apps.reviewapp.services.rating_service import RatingService

            if hasattr(review, "shop"):
                RatingService.update_entity_metrics("shopapp.Shop", review.shop_id)
            elif hasattr(review, "specialist"):
                RatingService.update_entity_metrics(
                    "specialistsapp.Specialist", review.specialist_id
                )
            elif hasattr(review, "service"):
                RatingService.update_entity_metrics("serviceapp.Service", review.service_id)

        return review

    @staticmethod
    def mark_review_helpful(review, user, is_helpful=True):
        """Mark a review as helpful or not helpful

        Args:
            review: The review to mark
            user (User): User marking the review
            is_helpful (bool): Whether the review was helpful

        Returns:
            ReviewHelpfulness: The helpfulness record
        """
        content_type = ContentType.objects.get_for_model(review)

        # Get or create helpfulness record
        helpfulness, created = ReviewHelpfulness.objects.get_or_create(
            content_type=content_type,
            object_id=review.id,
            user=user,
            defaults={"is_helpful": is_helpful},
        )

        # Update if existing
        if not created:
            helpfulness.is_helpful = is_helpful
            helpfulness.save()

        return helpfulness

    @staticmethod
    def report_review(review, user, reason, details=None):
        """Report a review as inappropriate

        Args:
            review: The review to report
            user (User): User reporting the review
            reason (str): Reason for the report
            details (str, optional): Additional details

        Returns:
            ReviewReport: The report record
        """
        if reason not in dict(ReviewReport.REPORT_REASON_CHOICES):
            raise ValueError(f"Invalid reason: {reason}")

        content_type = ContentType.objects.get_for_model(review)

        # Check if user already reported this review
        if ReviewReport.objects.filter(
            content_type=content_type, object_id=review.id, reporter=user
        ).exists():
            raise ValueError(_("You have already reported this review"))

        # Create report
        report = ReviewReport.objects.create(
            content_type=content_type,
            object_id=review.id,
            reporter=user,
            reason=reason,
            details=details or "",
        )

        # If review has received multiple reports, mark for moderation
        report_count = ReviewReport.objects.filter(
            content_type=content_type, object_id=review.id
        ).count()

        # If more than X reports, automatically mark for review
        if report_count >= 3 and review.status == "approved":
            review.status = "pending"
            review.save()

            # Record who triggered the change
            review.moderation_comment = _("Automatically marked for review due to multiple reports")
            review.save()

        return report

    @staticmethod
    def process_report(report, status, resolved_by=None, review_action=None):
        """Process a review report

        Args:
            report (ReviewReport): The report to process
            status (str): New status (reviewed, resolved, rejected)
            resolved_by (User, optional): User resolving the report
            review_action (str, optional): Action to take on the review (reject, remove)

        Returns:
            ReviewReport: The updated report
        """
        if status not in ["reviewed", "resolved", "rejected"]:
            raise ValueError(f"Invalid status: {status}")

        report.status = status
        report.save()

        # Take action on the review if requested
        if status == "resolved" and review_action in ["reject", "remove"]:
            review = report.review

            if review_action == "reject":
                review.status = "rejected"
                review.moderation_comment = _("Rejected due to report")
                if resolved_by:
                    review.moderated_by = resolved_by
                review.save()

                # Update entity metrics
                from apps.reviewapp.services.rating_service import RatingService

                if hasattr(review, "shop"):
                    RatingService.update_entity_metrics("shopapp.Shop", review.shop_id)
                elif hasattr(review, "specialist"):
                    RatingService.update_entity_metrics(
                        "specialistsapp.Specialist", review.specialist_id
                    )
                elif hasattr(review, "service"):
                    RatingService.update_entity_metrics("serviceapp.Service", review.service_id)

        return report

    @staticmethod
    def get_user_reviews(user, entity_type=None):
        """Get all reviews by a user

        Args:
            user (User): The user
            entity_type (str, optional): Filter by entity type

        Returns:
            QuerySet: User reviews
        """
        if entity_type == "shop":
            return ShopReview.objects.filter(user=user)
        elif entity_type == "specialist":
            return SpecialistReview.objects.filter(user=user)
        elif entity_type == "service":
            return ServiceReview.objects.filter(user=user)
        elif entity_type == "platform":
            return PlatformReview.objects.filter(user=user)
        else:
            # Return all types
            shop_reviews = ShopReview.objects.filter(user=user)
            specialist_reviews = SpecialistReview.objects.filter(user=user)
            service_reviews = ServiceReview.objects.filter(user=user)
            platform_reviews = PlatformReview.objects.filter(user=user)

            # Combine and sort by created_at (requires advanced handling)
            # For simplicity we'll return a dict of querysets for now
            return {
                "shop": shop_reviews,
                "specialist": specialist_reviews,
                "service": service_reviews,
                "platform": platform_reviews,
            }

    @staticmethod
    def get_entity_reviews(entity_type, entity_id, status=None):
        """Get all reviews for an entity

        Args:
            entity_type (str): Type of entity
            entity_id (uuid): ID of the entity
            status (str, optional): Filter by status

        Returns:
            QuerySet: Entity reviews
        """
        filters = {"status": status} if status else {}

        if entity_type == "shop":
            return ShopReview.objects.filter(shop_id=entity_id, **filters)
        elif entity_type == "specialist":
            return SpecialistReview.objects.filter(specialist_id=entity_id, **filters)
        elif entity_type == "service":
            return ServiceReview.objects.filter(service_id=entity_id, **filters)
        elif entity_type == "platform":
            return PlatformReview.objects.filter(company_id=entity_id, **filters)
        else:
            raise ValueError(f"Invalid entity type: {entity_type}")
