import logging
import re

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class ReviewValidator:
    """Validation service for reviews"""

    # List of allowed media file types
    ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    ALLOWED_VIDEO_TYPES = ["video/mp4", "video/quicktime", "video/x-msvideo"]

    # Maximum file sizes (in bytes)
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB

    # Maximum number of media files per review
    MAX_MEDIA_FILES = 5

    @classmethod
    def validate_review_data(cls, data):
        """Validate review data

        Args:
            data (dict): Review data to validate

        Raises:
            ValidationError: If validation fails
        """
        # Required fields
        if "title" not in data:
            raise ValidationError(_("Review title is required"))

        if "rating" not in data:
            raise ValidationError(_("Rating is required"))

        # Validate title
        title = data.get("title", "")
        if not title or len(title) < 3:
            raise ValidationError(_("Title must be at least 3 characters"))

        if len(title) > 255:
            raise ValidationError(_("Title must be at most 255 characters"))

        # Validate rating
        rating = data.get("rating")
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValidationError(_("Rating must be between 1 and 5"))
        except (ValueError, TypeError):
            raise ValidationError(_("Rating must be a number between 1 and 5"))

        # Validate content (optional but if provided, must be valid)
        content = data.get("content", "")
        if content and len(content) < 5:
            raise ValidationError(_("Review content must be at least 5 characters"))

        # Check for spam patterns
        if cls.is_potential_spam(title) or cls.is_potential_spam(content):
            raise ValidationError(
                _("Review appears to be spam. Please write a genuine review.")
            )

    @classmethod
    def validate_media_files(cls, files):
        """Validate media files for a review

        Args:
            files (list): List of media files to validate

        Raises:
            ValidationError: If validation fails
        """
        if not files:
            return

        # Check number of files
        if len(files) > cls.MAX_MEDIA_FILES:
            raise ValidationError(
                _("Maximum {} media files allowed").format(cls.MAX_MEDIA_FILES)
            )

        # Check each file
        for file in files:
            # Check file type
            content_type = getattr(file, "content_type", "")
            if (
                content_type not in cls.ALLOWED_IMAGE_TYPES
                and content_type not in cls.ALLOWED_VIDEO_TYPES
            ):
                raise ValidationError(
                    _("File type not allowed: {}").format(content_type)
                )

            # Check file size
            if (
                content_type in cls.ALLOWED_IMAGE_TYPES
                and file.size > cls.MAX_IMAGE_SIZE
            ):
                raise ValidationError(_("Image size must be less than 5 MB"))

            if (
                content_type in cls.ALLOWED_VIDEO_TYPES
                and file.size > cls.MAX_VIDEO_SIZE
            ):
                raise ValidationError(_("Video size must be less than 50 MB"))

    @classmethod
    def validate_review_eligibility(cls, entity_type, entity_id, user):
        """Validate if user is eligible to review an entity

        Args:
            entity_type (str): Type of entity
            entity_id (uuid): ID of the entity
            user (User): User attempting to create review

        Raises:
            ValidationError: If user is not eligible
        """
        if not user.is_authenticated:
            raise ValidationError(_("You must be logged in to leave a review"))

        # Check for duplicate reviews
        if cls.has_existing_review(entity_type, entity_id, user):
            raise ValidationError(
                _("You have already reviewed this {}").format(entity_type)
            )

        # Check if user has used the service/shop
        if not cls.has_used_entity(entity_type, entity_id, user):
            raise ValidationError(
                _("You must have used this {} to review it").format(entity_type)
            )

        # Check for review bombing (too many reviews in short time)
        if cls.is_review_bombing(user):
            raise ValidationError(
                _(
                    "You have submitted too many reviews recently. Please try again later."
                )
            )

    @classmethod
    def has_existing_review(cls, entity_type, entity_id, user):
        """Check if user has already reviewed this entity

        Args:
            entity_type (str): Type of entity
            entity_id (uuid): ID of the entity
            user (User): User to check

        Returns:
            bool: True if user has already reviewed
        """
        try:
            if entity_type == "shop":
                from apps.reviewapp.models import ShopReview

                return ShopReview.objects.filter(shop_id=entity_id, user=user).exists()
            elif entity_type == "specialist":
                from apps.reviewapp.models import SpecialistReview

                return SpecialistReview.objects.filter(
                    specialist_id=entity_id, user=user
                ).exists()
            elif entity_type == "service":
                from apps.reviewapp.models import ServiceReview

                return ServiceReview.objects.filter(
                    service_id=entity_id, user=user
                ).exists()
            elif entity_type == "platform":
                from apps.reviewapp.models import PlatformReview

                # For platform, check within last 30 days
                thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
                return PlatformReview.objects.filter(
                    company_id=entity_id, user=user, created_at__gte=thirty_days_ago
                ).exists()
            else:
                return False
        except Exception as e:
            logger.error(f"Error checking existing review: {str(e)}")
            return False

    @classmethod
    def has_used_entity(cls, entity_type, entity_id, user):
        """Check if user has used this entity (has bookings/visits)

        Args:
            entity_type (str): Type of entity
            entity_id (uuid): ID of the entity
            user (User): User to check

        Returns:
            bool: True if user has used the entity
        """
        try:
            # Skip check for admins or special roles
            from apps.rolesapp.services.permission_resolver import PermissionResolver

            if PermissionResolver.has_permission(user, "review", "edit"):
                return True

            if entity_type == "shop":
                # Check if user has completed bookings at this shop
                from apps.bookingapp.models import Appointment

                return Appointment.objects.filter(
                    customer=user, shop_id=entity_id, status="completed"
                ).exists()
            elif entity_type == "specialist":
                # Check if user has completed bookings with this specialist
                from apps.bookingapp.models import Appointment

                return Appointment.objects.filter(
                    customer=user, specialist_id=entity_id, status="completed"
                ).exists()
            elif entity_type == "service":
                # Check if user has completed bookings for this service
                from apps.bookingapp.models import Appointment

                return Appointment.objects.filter(
                    customer=user, service_id=entity_id, status="completed"
                ).exists()
            elif entity_type == "platform":
                # Check if user is associated with the company
                from apps.companiesapp.models import Company
                from apps.shopapp.models import Shop

                # Check if user is company owner
                is_owner = Company.objects.filter(id=entity_id, owner=user).exists()

                # Check if user is shop manager for this company
                is_manager = Shop.objects.filter(
                    company_id=entity_id, manager=user
                ).exists()

                return is_owner or is_manager
            else:
                return False
        except Exception as e:
            logger.error(f"Error checking entity usage: {str(e)}")
            return False

    @classmethod
    def is_review_bombing(cls, user):
        """Check if user is submitting too many reviews in a short time

        Args:
            user (User): User to check

        Returns:
            bool: True if review bombing detected
        """
        try:
            # Get recent reviews from this user (last hour)
            one_hour_ago = timezone.now() - timezone.timedelta(hours=1)

            from apps.reviewapp.models import (
                PlatformReview,
                ServiceReview,
                ShopReview,
                SpecialistReview,
            )

            # Count reviews in different categories
            shop_count = ShopReview.objects.filter(
                user=user, created_at__gte=one_hour_ago
            ).count()

            specialist_count = SpecialistReview.objects.filter(
                user=user, created_at__gte=one_hour_ago
            ).count()

            service_count = ServiceReview.objects.filter(
                user=user, created_at__gte=one_hour_ago
            ).count()

            platform_count = PlatformReview.objects.filter(
                user=user, created_at__gte=one_hour_ago
            ).count()

            total_count = shop_count + specialist_count + service_count
            # Check if total exceeds threshold (10 reviews per hour)
            MAX_REVIEWS_PER_HOUR = 10
            return total_count >= MAX_REVIEWS_PER_HOUR

        except Exception as e:
            logger.error(f"Error checking review bombing: {str(e)}")
            return False

    @classmethod
    def is_potential_spam(cls, text):
        """Check if text appears to be spam

        Args:
            text (str): Text to check

        Returns:
            bool: True if potentially spam
        """
        if not text:
            return False

        # Check for excessive capitalization
        if cls._has_excessive_caps(text):
            return True

        # Check for excessive punctuation
        if cls._has_excessive_punctuation(text):
            return True

        # Check for repeated text patterns
        if cls._has_repeated_patterns(text):
            return True

        # Check for URL density
        if cls._has_high_url_density(text):
            return True

        return False

    @staticmethod
    def _has_excessive_caps(text):
        """Check for excessive capitalization

        Args:
            text (str): Text to check

        Returns:
            bool: True if excessive caps detected
        """
        if not text or len(text) < 5:
            return False

        # Count uppercase characters (excluding non-letters)
        uppercase_chars = sum(1 for c in text if c.isupper())
        total_chars = sum(1 for c in text if c.isalpha())

        if total_chars == 0:
            return False

        uppercase_ratio = uppercase_chars / total_chars

        # If more than 50% of text is uppercase, it's excessive
        return uppercase_ratio > 0.5 and total_chars > 10

    @staticmethod
    def _has_excessive_punctuation(text):
        """Check for excessive punctuation

        Args:
            text (str): Text to check

        Returns:
            bool: True if excessive punctuation detected
        """
        if not text:
            return False

        # Count punctuation
        punctuation_count = sum(1 for c in text if c in "!?.,:;")
        total_length = len(text)

        if total_length == 0:
            return False

        punctuation_ratio = punctuation_count / total_length

        # If more than 15% of text is punctuation, it's excessive
        return punctuation_ratio > 0.15

    @staticmethod
    def _has_repeated_patterns(text):
        """Check for repeated text patterns (spam indicator)

        Args:
            text (str): Text to check

        Returns:
            bool: True if repeated patterns detected
        """
        if not text or len(text) < 10:
            return False

        # Look for repeated words
        words = re.findall(r"\b\w+\b", text.lower())

        if len(words) < 5:
            return False

        # Check for repeated word sequences
        word_pairs = [words[i] + " " + words[i + 1] for i in range(len(words) - 1)]
        word_triplets = [
            words[i] + " " + words[i + 1] + " " + words[i + 2]
            for i in range(len(words) - 2)
        ]

        # Count occurrences
        pair_count = {}
        triplet_count = {}

        for pair in word_pairs:
            pair_count[pair] = pair_count.get(pair, 0) + 1

        for triplet in word_triplets:
            triplet_count[triplet] = triplet_count.get(triplet, 0) + 1

        # Check if any sequence is repeated excessively
        max_pair_count = max(pair_count.values()) if pair_count else 0
        max_triplet_count = max(triplet_count.values()) if triplet_count else 0

        total_pairs = len(word_pairs)
        if total_pairs < 5:
            return False

        # If a pair appears more than 30% of the time, it's excessive
        return (
            max_pair_count > 3 and max_pair_count / total_pairs > 0.3
        ) or max_triplet_count > 2

    @staticmethod
    def _has_high_url_density(text):
        """Check for high density of URLs (spam indicator)

        Args:
            text (str): Text to check

        Returns:
            bool: True if high URL density detected
        """
        if not text:
            return False

        # Simple URL pattern
        url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        urls = re.findall(url_pattern, text)

        # Count URLs and calculate density
        url_count = len(urls)
        text_length = len(text)

        if text_length == 0:
            return False

        # Calculate total URL characters
        url_chars = sum(len(url) for url in urls)
        url_density = url_chars / text_length

        # If URLs make up more than 20% of the text, it's high density
        return url_density > 0.2 or url_count > 3
