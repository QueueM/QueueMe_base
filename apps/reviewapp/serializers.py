from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.authapp.serializers import UserBasicSerializer
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
from apps.serviceapp.serializers import ServiceBasicSerializer
from apps.shopapp.serializers import ShopBasicSerializer
from apps.specialistsapp.serializers import SpecialistBasicSerializer


class ReviewMediaSerializer(serializers.ModelSerializer):
    """Serializer for review media attachments"""

    class Meta:
        model = ReviewMedia
        fields = ["id", "media_file", "media_type", "created_at"]


class BaseReviewSerializer(serializers.ModelSerializer):
    """Base serializer for all review types"""

    user = UserBasicSerializer(read_only=True)
    user_display_name = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()
    helpfulness_count = serializers.SerializerMethodField()
    report_count = serializers.SerializerMethodField()
    is_helpful = serializers.SerializerMethodField()
    has_reported = serializers.SerializerMethodField()

    class Meta:
        fields = [
            "id",
            "title",
            "rating",
            "content",
            "user",
            "user_display_name",
            "city",
            "status",
            "is_verified_purchase",
            "created_at",
            "media",
            "helpfulness_count",
            "report_count",
            "is_helpful",
            "has_reported",
        ]

    def get_user_display_name(self, obj):
        """Get user name (not phone number) for display"""
        # Try to get customer profile name if it exists
        try:
            from apps.customersapp.models import CustomerProfile

            profile = CustomerProfile.objects.filter(user=obj.user).first()
            if profile and profile.first_name:
                # Return full name or just first name
                if profile.last_name:
                    return f"{profile.first_name} {profile.last_name}"
                return profile.first_name
        except ImportError:
            pass

        # Try to get employee name if it exists
        try:
            from apps.employeeapp.models import Employee

            employee = Employee.objects.filter(user=obj.user).first()
            if employee and employee.first_name:
                # Return full name or just first name
                if employee.last_name:
                    return f"{employee.first_name} {employee.last_name}"
                return employee.first_name
        except ImportError:
            pass

        # Fallback: return username or phone number partial
        if obj.user:
            if hasattr(obj.user, "username") and obj.user.username:
                return obj.user.username

            # Mask most of the phone number
            phone = obj.user.phone_number
            if len(phone) > 4:
                return f"****{phone[-4:]}"
            return phone

        return _("Anonymous User")

    def get_media(self, obj):
        """Get all media attachments for the review"""
        content_type = ContentType.objects.get_for_model(obj)
        media = ReviewMedia.objects.filter(content_type=content_type, object_id=obj.id)
        return ReviewMediaSerializer(media, many=True).data

    def get_helpfulness_count(self, obj):
        """Get count of users who found the review helpful"""
        content_type = ContentType.objects.get_for_model(obj)
        return ReviewHelpfulness.objects.filter(
            content_type=content_type, object_id=obj.id, is_helpful=True
        ).count()

    def get_report_count(self, obj):
        """Get count of reports for this review"""
        content_type = ContentType.objects.get_for_model(obj)
        return ReviewReport.objects.filter(
            content_type=content_type, object_id=obj.id
        ).count()

    def get_is_helpful(self, obj):
        """Check if current user found review helpful"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        content_type = ContentType.objects.get_for_model(obj)
        try:
            helpfulness = ReviewHelpfulness.objects.get(
                content_type=content_type, object_id=obj.id, user=request.user
            )
            return helpfulness.is_helpful
        except ReviewHelpfulness.DoesNotExist:
            return None

    def get_has_reported(self, obj):
        """Check if current user reported this review"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        content_type = ContentType.objects.get_for_model(obj)
        return ReviewReport.objects.filter(
            content_type=content_type, object_id=obj.id, reporter=request.user
        ).exists()


class ShopReviewSerializer(BaseReviewSerializer):
    """Serializer for shop reviews"""

    shop = ShopBasicSerializer(read_only=True)
    shop_id = serializers.UUIDField(write_only=True)
    related_booking_id = serializers.UUIDField(
        required=False, allow_null=True, write_only=True
    )

    class Meta(BaseReviewSerializer.Meta):
        model = ShopReview
        fields = BaseReviewSerializer.Meta.fields + [
            "shop",
            "shop_id",
            "related_booking_id",
        ]

    def validate(self, data):
        """Validate the shop review"""
        # Get user from context
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("Authentication required"))

        user = request.user

        # Check if user has already reviewed this shop
        if ShopReview.objects.filter(user=user, shop_id=data["shop_id"]).exists():
            # Allow if related to a different booking
            if "related_booking_id" in data and data["related_booking_id"]:
                if ShopReview.objects.filter(
                    user=user,
                    shop_id=data["shop_id"],
                    related_booking_id=data["related_booking_id"],
                ).exists():
                    raise serializers.ValidationError(
                        _("You have already reviewed this shop for this booking")
                    )
            else:
                raise serializers.ValidationError(
                    _("You have already reviewed this shop")
                )

        # Verify user has visited the shop (has a booking)
        from apps.bookingapp.models import Appointment

        has_booking = Appointment.objects.filter(
            customer=user, shop_id=data["shop_id"], status="completed"
        ).exists()

        if not has_booking and "related_booking_id" not in data:
            raise serializers.ValidationError(
                _("You must have visited this shop to review it")
            )

        return data

    def create(self, validated_data):
        # Extract IDs
        shop_id = validated_data.pop("shop_id")
        related_booking_id = validated_data.pop("related_booking_id", None)

        # Get user from context
        request = self.context.get("request")
        user = request.user

        # Set verified purchase based on booking
        is_verified = False
        if related_booking_id:
            from apps.bookingapp.models import Appointment

            try:
                booking = Appointment.objects.get(id=related_booking_id)
                is_verified = booking.status == "completed" and booking.customer == user
            except Appointment.DoesNotExist:
                pass

        # Create the review
        review = ShopReview.objects.create(
            user=user,
            shop_id=shop_id,
            related_booking_id=related_booking_id,
            is_verified_purchase=is_verified,
            **validated_data,
        )

        # Update shop metrics (this will be handled by signals in production)
        from apps.reviewapp.services.rating_service import RatingService

        RatingService.update_entity_metrics("shopapp.Shop", shop_id)

        return review


class SpecialistReviewSerializer(BaseReviewSerializer):
    """Serializer for specialist reviews"""

    specialist = SpecialistBasicSerializer(read_only=True)
    specialist_id = serializers.UUIDField(write_only=True)
    related_booking_id = serializers.UUIDField(
        required=False, allow_null=True, write_only=True
    )

    class Meta(BaseReviewSerializer.Meta):
        model = SpecialistReview
        fields = BaseReviewSerializer.Meta.fields + [
            "specialist",
            "specialist_id",
            "related_booking_id",
        ]

    def validate(self, data):
        """Validate the specialist review"""
        # Get user from context
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("Authentication required"))

        user = request.user

        # Check if user has already reviewed this specialist
        if SpecialistReview.objects.filter(
            user=user, specialist_id=data["specialist_id"]
        ).exists():
            # Allow if related to a different booking
            if "related_booking_id" in data and data["related_booking_id"]:
                if SpecialistReview.objects.filter(
                    user=user,
                    specialist_id=data["specialist_id"],
                    related_booking_id=data["related_booking_id"],
                ).exists():
                    raise serializers.ValidationError(
                        _("You have already reviewed this specialist for this booking")
                    )
            else:
                raise serializers.ValidationError(
                    _("You have already reviewed this specialist")
                )

        # Verify user has had an appointment with the specialist
        from apps.bookingapp.models import Appointment

        has_booking = Appointment.objects.filter(
            customer=user, specialist_id=data["specialist_id"], status="completed"
        ).exists()

        if not has_booking and "related_booking_id" not in data:
            raise serializers.ValidationError(
                _(
                    "You must have had an appointment with this specialist to review them"
                )
            )

        return data

    def create(self, validated_data):
        # Extract IDs
        specialist_id = validated_data.pop("specialist_id")
        related_booking_id = validated_data.pop("related_booking_id", None)

        # Get user from context
        request = self.context.get("request")
        user = request.user

        # Set verified purchase based on booking
        is_verified = False
        if related_booking_id:
            from apps.bookingapp.models import Appointment

            try:
                booking = Appointment.objects.get(id=related_booking_id)
                is_verified = booking.status == "completed" and booking.customer == user
            except Appointment.DoesNotExist:
                pass

        # Create the review
        review = SpecialistReview.objects.create(
            user=user,
            specialist_id=specialist_id,
            related_booking_id=related_booking_id,
            is_verified_purchase=is_verified,
            **validated_data,
        )

        # Update specialist metrics (this will be handled by signals in production)
        from apps.reviewapp.services.rating_service import RatingService

        RatingService.update_entity_metrics("specialistsapp.Specialist", specialist_id)

        return review


class ServiceReviewSerializer(BaseReviewSerializer):
    """Serializer for service reviews"""

    service = ServiceBasicSerializer(read_only=True)
    service_id = serializers.UUIDField(write_only=True)
    related_booking_id = serializers.UUIDField(
        required=False, allow_null=True, write_only=True
    )

    class Meta(BaseReviewSerializer.Meta):
        model = ServiceReview
        fields = BaseReviewSerializer.Meta.fields + [
            "service",
            "service_id",
            "related_booking_id",
        ]

    def validate(self, data):
        """Validate the service review"""
        # Get user from context
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("Authentication required"))

        user = request.user

        # Check if user has already reviewed this service
        if ServiceReview.objects.filter(
            user=user, service_id=data["service_id"]
        ).exists():
            # Allow if related to a different booking
            if "related_booking_id" in data and data["related_booking_id"]:
                if ServiceReview.objects.filter(
                    user=user,
                    service_id=data["service_id"],
                    related_booking_id=data["related_booking_id"],
                ).exists():
                    raise serializers.ValidationError(
                        _("You have already reviewed this service for this booking")
                    )
            else:
                raise serializers.ValidationError(
                    _("You have already reviewed this service")
                )

        # Verify user has used the service (has a booking)
        from apps.bookingapp.models import Appointment

        has_booking = Appointment.objects.filter(
            customer=user, service_id=data["service_id"], status="completed"
        ).exists()

        if not has_booking and "related_booking_id" not in data:
            raise serializers.ValidationError(
                _("You must have used this service to review it")
            )

        return data

    def create(self, validated_data):
        # Extract IDs
        service_id = validated_data.pop("service_id")
        related_booking_id = validated_data.pop("related_booking_id", None)

        # Get user from context
        request = self.context.get("request")
        user = request.user

        # Set verified purchase based on booking
        is_verified = False
        if related_booking_id:
            from apps.bookingapp.models import Appointment

            try:
                booking = Appointment.objects.get(id=related_booking_id)
                is_verified = booking.status == "completed" and booking.customer == user
            except Appointment.DoesNotExist:
                pass

        # Create the review
        review = ServiceReview.objects.create(
            user=user,
            service_id=service_id,
            related_booking_id=related_booking_id,
            is_verified_purchase=is_verified,
            **validated_data,
        )

        # Update service metrics (this will be handled by signals in production)
        from apps.reviewapp.services.rating_service import RatingService

        RatingService.update_entity_metrics("serviceapp.Service", service_id)

        return review


class PlatformReviewSerializer(BaseReviewSerializer):
    """Serializer for platform reviews by shops"""

    company_id = serializers.UUIDField(write_only=True)
    category = serializers.CharField(required=False)

    class Meta(BaseReviewSerializer.Meta):
        model = PlatformReview
        fields = BaseReviewSerializer.Meta.fields + ["company_id", "category"]

    def validate(self, data):
        """Validate the platform review"""
        # Get user from context
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("Authentication required"))

        user = request.user

        # Verify user is associated with the company (either owner or manager)
        from apps.companiesapp.models import Company
        from apps.shopapp.models import Shop

        # Check if user is company owner
        is_owner = Company.objects.filter(id=data["company_id"], owner=user).exists()

        # Check if user is shop manager for the company
        is_manager = Shop.objects.filter(
            company_id=data["company_id"], manager=user
        ).exists()

        if not (is_owner or is_manager):
            raise serializers.ValidationError(
                _("You must be associated with this company to leave a platform review")
            )

        # Check if company has already reviewed the platform recently (within 30 days)
        from django.utils import timezone

        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)

        recent_review = PlatformReview.objects.filter(
            company_id=data["company_id"], created_at__gte=thirty_days_ago
        ).exists()

        if recent_review:
            raise serializers.ValidationError(
                _(
                    "This company has already reviewed the platform within the last 30 days"
                )
            )

        return data

    def create(self, validated_data):
        # Extract company ID
        company_id = validated_data.pop("company_id")

        # Get user from context
        request = self.context.get("request")
        user = request.user

        # Create the review
        review = PlatformReview.objects.create(
            user=user, company_id=company_id, **validated_data
        )

        # Platform reviews don't update metrics yet, but we could add this in the future

        return review


class ReviewHelpfulnessSerializer(serializers.ModelSerializer):
    """Serializer for recording if a review was helpful"""

    content_type_str = serializers.CharField(write_only=True)
    object_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = ReviewHelpfulness
        fields = ["id", "is_helpful", "content_type_str", "object_id", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, data):
        """Validate the helpfulness vote"""
        # Get content type from string (e.g., 'shopapp.shopreview')
        try:
            app_label, model = data.pop("content_type_str").lower().split(".")
            data["content_type"] = ContentType.objects.get(
                app_label=app_label, model=model
            )
        except (ValueError, ContentType.DoesNotExist):
            raise serializers.ValidationError(_("Invalid review type"))

        # Get user from context
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("Authentication required"))

        # Validate that the review exists
        try:
            review_model = data["content_type"].model_class()
            review_model.objects.get(id=data["object_id"])
        except review_model.DoesNotExist:
            raise serializers.ValidationError(_("Review not found"))

        return data

    def create(self, validated_data):
        # Get user from context
        request = self.context.get("request")
        user = request.user

        # Check if user already voted for this review
        existing_vote = ReviewHelpfulness.objects.filter(
            content_type=validated_data["content_type"],
            object_id=validated_data["object_id"],
            user=user,
        ).first()

        if existing_vote:
            # Update existing vote
            existing_vote.is_helpful = validated_data["is_helpful"]
            existing_vote.save()
            return existing_vote

        # Create new vote
        return ReviewHelpfulness.objects.create(user=user, **validated_data)


class ReviewReportSerializer(serializers.ModelSerializer):
    """Serializer for reporting inappropriate reviews"""

    content_type_str = serializers.CharField(write_only=True)
    object_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = ReviewReport
        fields = [
            "id",
            "reason",
            "details",
            "status",
            "content_type_str",
            "object_id",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def validate(self, data):
        """Validate the report"""
        # Get content type from string (e.g., 'shopapp.shopreview')
        try:
            app_label, model = data.pop("content_type_str").lower().split(".")
            data["content_type"] = ContentType.objects.get(
                app_label=app_label, model=model
            )
        except (ValueError, ContentType.DoesNotExist):
            raise serializers.ValidationError(_("Invalid review type"))

        # Get user from context
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("Authentication required"))

        # Validate that the review exists
        try:
            review_model = data["content_type"].model_class()
            review_model.objects.get(id=data["object_id"])
        except review_model.DoesNotExist:
            raise serializers.ValidationError(_("Review not found"))

        # Check if user already reported this review
        user = request.user
        existing_report = ReviewReport.objects.filter(
            content_type=data["content_type"],
            object_id=data["object_id"],
            reporter=user,
        ).exists()

        if existing_report:
            raise serializers.ValidationError(
                _("You have already reported this review")
            )

        return data

    def create(self, validated_data):
        # Get user from context
        request = self.context.get("request")
        reporter = request.user

        # Create the report
        return ReviewReport.objects.create(reporter=reporter, **validated_data)


class ReviewMetricSerializer(serializers.ModelSerializer):
    """Serializer for review metrics"""

    content_type_str = serializers.SerializerMethodField()
    entity_id = serializers.SerializerMethodField()

    class Meta:
        model = ReviewMetric
        fields = [
            "id",
            "content_type_str",
            "entity_id",
            "avg_rating",
            "weighted_rating",
            "review_count",
            "rating_distribution",
            "last_reviewed_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_content_type_str(self, obj):
        """Convert content type to string representation"""
        return f"{obj.content_type.app_label}.{obj.content_type.model}"

    def get_entity_id(self, obj):
        """Get entity ID"""
        return str(obj.object_id)
