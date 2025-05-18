"""
Review validation service with enhanced spam detection and content moderation.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.reviewapp.models import Review
from apps.reviewapp.services.content_moderation import ContentModerationService

logger = logging.getLogger(__name__)


class ReviewValidator:
    """Enhanced validation service for reviews with spam detection."""

    # Constants
    MAX_MEDIA_FILES = 5
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB
    MAX_REVIEW_LENGTH = 1000
    MIN_REVIEW_LENGTH = 10
    MAX_REVIEWS_PER_DAY = 5
    MAX_REVIEWS_PER_WEEK = 20
    MAX_REVIEWS_PER_MONTH = 50

    # Allowed file types
    ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    ALLOWED_VIDEO_TYPES = ["video/mp4", "video/quicktime", "video/x-msvideo"]

    # Spam detection patterns
    SPAM_PATTERNS = [
        r"(?i)(buy|sell|discount|offer|deal|cheap|price)",
        r"(?i)(http|https|www\.)",
        r"(?i)(click here|visit us|call now)",
        r"(?i)(earn money|make money|work from home)",
        r"(?i)(viagra|cialis|levitra)",
        r"(?i)(casino|betting|gambling)",
        r"(?i)(lottery|prize|winner)",
        r"(?i)(loan|mortgage|credit)",
        r"(?i)(weight loss|diet|supplement)",
    ]

    @classmethod
    def validate_review_data(cls, data: Dict[str, Any]) -> None:
        """
        Validate review data with enhanced spam detection.

        Args:
            data: Review data to validate

        Raises:
            ValidationError: If validation fails
        """
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()

        # Check required fields
        if not title:
            raise ValidationError(_("Title is required"))
        if not content:
            raise ValidationError(_("Content is required"))

        # Check length limits
        if len(title) > 100:
            raise ValidationError(_("Title must be at most 100 characters"))
        if len(content) < cls.MIN_REVIEW_LENGTH:
            raise ValidationError(_(f"Content must be at least {cls.MIN_REVIEW_LENGTH} characters"))
        if len(content) > cls.MAX_REVIEW_LENGTH:
            raise ValidationError(_(f"Content must be at most {cls.MAX_REVIEW_LENGTH} characters"))

        # Check for spam patterns
        if cls._contains_spam_patterns(title) or cls._contains_spam_patterns(content):
            raise ValidationError(_("Review appears to be spam. Please write a genuine review."))

        # Check for inappropriate content
        if cls._contains_inappropriate_content(title) or cls._contains_inappropriate_content(
            content
        ):
            raise ValidationError(_("Review contains inappropriate content."))

        # Check for duplicate content
        if cls._is_duplicate_content(content):
            raise ValidationError(_("This review appears to be a duplicate."))

    @classmethod
    def validate_media_files(cls, files: List[Any]) -> None:
        """
        Validate media files for a review.

        Args:
            files: List of media files to validate

        Raises:
            ValidationError: If validation fails
        """
        if not files:
            return

        # Check number of files
        if len(files) > cls.MAX_MEDIA_FILES:
            raise ValidationError(_("Maximum {} media files allowed").format(cls.MAX_MEDIA_FILES))

        # Check each file
        for file in files:
            # Check file type
            content_type = getattr(file, "content_type", "")
            if (
                content_type not in cls.ALLOWED_IMAGE_TYPES
                and content_type not in cls.ALLOWED_VIDEO_TYPES
            ):
                raise ValidationError(_("File type not allowed: {}").format(content_type))

            # Check file size
            if content_type in cls.ALLOWED_IMAGE_TYPES and file.size > cls.MAX_IMAGE_SIZE:
                raise ValidationError(_("Image size must be less than 5 MB"))

            if content_type in cls.ALLOWED_VIDEO_TYPES and file.size > cls.MAX_VIDEO_SIZE:
                raise ValidationError(_("Video size must be less than 50 MB"))

            # Check for malicious content
            if cls._contains_malicious_content(file):
                raise ValidationError(_("File appears to be malicious"))

    @classmethod
    def validate_review_eligibility(cls, entity_type: str, entity_id: str, user: Any) -> None:
        """
        Validate if user is eligible to review an entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            user: User attempting to create review

        Raises:
            ValidationError: If user is not eligible
        """
        if not user.is_authenticated:
            raise ValidationError(_("You must be logged in to leave a review"))

        # Check for duplicate reviews
        if cls._has_existing_review(entity_type, entity_id, user):
            raise ValidationError(_("You have already reviewed this {}").format(entity_type))

        # Check if user has used the service/shop
        if not cls._has_used_entity(entity_type, entity_id, user):
            raise ValidationError(_("You must have used this {} to review it").format(entity_type))

        # Check review frequency limits
        if cls._exceeds_review_limits(user):
            raise ValidationError(
                _("You have submitted too many reviews recently. Please try again later.")
            )

    @classmethod
    def _contains_spam_patterns(cls, text: str) -> bool:
        """Check if text contains spam patterns."""
        for pattern in cls.SPAM_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    @classmethod
    def _contains_inappropriate_content(cls, text: str) -> bool:
        """Check if text contains inappropriate content using content moderation service."""
        return ContentModerationService.is_inappropriate(text)

    @classmethod
    def _contains_malicious_content(cls, file: Any) -> bool:
        """Check if file contains malicious content."""
        return ContentModerationService.is_malicious_file(file)

    @classmethod
    def _is_duplicate_content(cls, content: str) -> bool:
        """Check if content is a duplicate of existing reviews."""
        # Normalize content for comparison
        normalized = re.sub(r"\s+", " ", content.lower().strip())

        # Check cache first
        cache_key = f"review_content_hash:{hash(normalized)}"
        if cache.get(cache_key):
            return True

        # Check database for similar content
        similar_reviews = Review.objects.filter(
            content__icontains=normalized[:100]  # Check first 100 chars
        ).values_list("content", flat=True)

        for review_content in similar_reviews:
            if (
                cls._calculate_similarity(normalized, review_content) > 0.8
            ):  # 80% similarity threshold
                # Cache the result
                cache.set(cache_key, True, 3600)  # Cache for 1 hour
                return True

        return False

    @classmethod
    def _calculate_similarity(cls, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using Levenshtein distance."""
        from Levenshtein import ratio

        return ratio(text1, text2)

    @classmethod
    def _has_existing_review(cls, entity_type: str, entity_id: str, user: Any) -> bool:
        """Check if user has already reviewed this entity."""
        return Review.objects.filter(
            entity_type=entity_type, entity_id=entity_id, user=user
        ).exists()

    @classmethod
    def _has_used_entity(cls, entity_type: str, entity_id: str, user: Any) -> bool:
        """Check if user has used this entity."""
        try:
            if entity_type == "shop":
                from apps.queueapp.models import QueueTicket

                return QueueTicket.objects.filter(
                    queue__shop_id=entity_id,
                    user=user,
                    status__in=["completed", "served"],
                ).exists()
            elif entity_type == "service":
                from apps.bookingapp.models import Appointment

                return Appointment.objects.filter(
                    service_id=entity_id, user=user, status="completed"
                ).exists()
            elif entity_type == "platform":
                from apps.companiesapp.models import Company
                from apps.shopapp.models import Shop

                # Check if user is company owner
                is_owner = Company.objects.filter(id=entity_id, owner=user).exists()

                # Check if user is shop manager for this company
                is_manager = Shop.objects.filter(company_id=entity_id, manager=user).exists()

                return is_owner or is_manager
            else:
                return False
        except Exception as e:
            logger.error(f"Error checking entity usage: {str(e)}")
            return False

    @classmethod
    def _exceeds_review_limits(cls, user: Any) -> bool:
        """Check if user has exceeded review frequency limits."""
        now = datetime.now()

        # Check daily limit
        daily_count = Review.objects.filter(
            user=user, created_at__gte=now - timedelta(days=1)
        ).count()
        if daily_count >= cls.MAX_REVIEWS_PER_DAY:
            return True

        # Check weekly limit
        weekly_count = Review.objects.filter(
            user=user, created_at__gte=now - timedelta(days=7)
        ).count()
        if weekly_count >= cls.MAX_REVIEWS_PER_WEEK:
            return True

        # Check monthly limit
        monthly_count = Review.objects.filter(
            user=user, created_at__gte=now - timedelta(days=30)
        ).count()
        if monthly_count >= cls.MAX_REVIEWS_PER_MONTH:
            return True

        return False
