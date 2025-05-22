"""
Review app views for QueueMe platform
Handles endpoints related to reviews, ratings, and moderation
"""

from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from api.documentation.api_doc_decorators import (
    document_api_endpoint,
    document_api_viewset,
)
from apps.reviewapp.filters import (
    PlatformReviewFilter,
    ReviewReportFilter,
    ServiceReviewFilter,
    ShopReviewFilter,
    SpecialistReviewFilter,
)
from apps.reviewapp.models import (
    PlatformReview,
    ReviewMetric,
    ReviewReport,
    ServiceReview,
    ShopReview,
    SpecialistReview,
)
from apps.reviewapp.permissions import (
    CanManageReviews,
    CanModerateReviews,
    CanReportReviews,
    CanViewReviews,
    CanVoteReviewHelpfulness,
)
from apps.reviewapp.serializers import (
    PlatformReviewSerializer,
    ReviewHelpfulnessSerializer,
    ReviewMetricSerializer,
    ReviewReportSerializer,
    ServiceReviewSerializer,
    ShopReviewSerializer,
    SpecialistReviewSerializer,
)
from apps.reviewapp.services.rating_service import RatingService
from apps.rolesapp.services.permission_resolver import PermissionResolver


@document_api_viewset(
    summary="Review",
    description="Main API endpoint for reviews - routes to specialized review types based on the review type parameter",
    tags=["Reviews"],
)
class ReviewViewSet(viewsets.ViewSet):
    """
    Main ViewSet for reviews - routes to appropriate specialized review ViewSets
    based on the review type. This serves as a consolidated API endpoint.
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_shop_review_viewset(self):
        return ShopReviewViewSet.as_view({"get": "list", "post": "create"})

    def get_specialist_review_viewset(self):
        return SpecialistReviewViewSet.as_view({"get": "list", "post": "create"})

    def get_service_review_viewset(self):
        return ServiceReviewViewSet.as_view({"get": "list", "post": "create"})

    def get_platform_review_viewset(self):
        return PlatformReviewViewSet.as_view({"get": "list", "post": "create"})

    @document_api_endpoint(
        summary="List reviews",
        description="Return reviews based on the review_type parameter",
        responses={
            200: "Success - Returns list of reviews",
            400: "Bad Request - Invalid review type",
        },
        query_params=[
            {
                "name": "review_type",
                "description": "Type of reviews to list (shop, specialist, service, platform)",
                "required": False,
                "type": "string",
            }
        ],
        tags=["Reviews"],
    )
    def list(self, request):
        """Return reviews based on the review_type parameter"""
        review_type = request.query_params.get("review_type", "shop")

        if review_type == "shop":
            return self.get_shop_review_viewset()(request)
        elif review_type == "specialist":
            return self.get_specialist_review_viewset()(request)
        elif review_type == "service":
            return self.get_service_review_viewset()(request)
        elif review_type == "platform":
            return self.get_platform_review_viewset()(request)
        else:
            return Response(
                {"error": _("Invalid review type")}, status=status.HTTP_400_BAD_REQUEST
            )

    @document_api_endpoint(
        summary="Create review",
        description="Create a review based on the review_type parameter",
        responses={
            201: "Created - Review created successfully",
            400: "Bad Request - Invalid review type or data",
            401: "Unauthorized - Authentication required",
        },
        tags=["Reviews"],
    )
    def create(self, request):
        """Create a review based on the review_type parameter"""
        review_type = request.data.get("review_type", "shop")

        if review_type == "shop":
            return self.get_shop_review_viewset()(request)
        elif review_type == "specialist":
            return self.get_specialist_review_viewset()(request)
        elif review_type == "service":
            return self.get_service_review_viewset()(request)
        elif review_type == "platform":
            return self.get_platform_review_viewset()(request)
        else:
            return Response(
                {"error": _("Invalid review type")}, status=status.HTTP_400_BAD_REQUEST
            )

    # Add this line at the end to ensure the ViewSet has a queryset attribute
    # needed for router registration
    queryset = ShopReview.objects.none()  # Empty queryset as a fallback


@document_api_viewset(
    summary="Shop Review",
    description="API endpoints for managing shop reviews",
    tags=["Reviews", "Shops"],
)
class ShopReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for shop reviews"""

    queryset = ShopReview.objects.all()
    serializer_class = ShopReviewSerializer
    permission_classes = [CanViewReviews, CanManageReviews]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ShopReviewFilter
    search_fields = ["title", "content"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter queryset based on permissions"""
        queryset = super().get_queryset()

        # For regular users, only show approved reviews
        user = self.request.user
        if not user.is_authenticated or not PermissionResolver.has_permission(
            user, "review", "view"
        ):
            queryset = queryset.filter(status="approved")

        # Filter by user
        user_id = self.request.query_params.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        return queryset

    @document_api_endpoint(
        summary="Mark review as helpful",
        description="Vote on whether a review was helpful or not",
        responses={
            200: "Success - Vote recorded successfully",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Review not found",
        },
        path_params=[{"name": "pk", "description": "Review ID", "type": "string"}],
        tags=["Reviews", "Shops", "Helpfulness"],
    )
    @action(
        detail=True, methods=["post"], permission_classes=[CanVoteReviewHelpfulness]
    )
    def helpful(self, request, pk=None):
        """Mark review as helpful/not helpful"""
        review = self.get_object()

        serializer = ReviewHelpfulnessSerializer(
            data={
                "content_type_str": "reviewapp.shopreview",
                "object_id": review.id,
                "is_helpful": request.data.get("is_helpful", True),
            },
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"status": "success"})

    @document_api_endpoint(
        summary="Report review",
        description="Report a review for inappropriate content",
        responses={
            200: "Success - Report submitted successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Review not found",
        },
        path_params=[{"name": "pk", "description": "Review ID", "type": "string"}],
        tags=["Reviews", "Shops", "Moderation"],
    )
    @action(detail=True, methods=["post"], permission_classes=[CanReportReviews])
    def report(self, request, pk=None):
        """Report inappropriate review"""
        review = self.get_object()

        serializer = ReviewReportSerializer(
            data={
                "content_type_str": "reviewapp.shopreview",
                "object_id": review.id,
                "reason": request.data.get("reason"),
                "details": request.data.get("details", ""),
            },
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"status": "report submitted"})

    @document_api_endpoint(
        summary="Moderate review",
        description="Approve or reject a review (admin/moderator only)",
        responses={
            200: "Success - Review moderated successfully",
            400: "Bad Request - Invalid status",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Review not found",
        },
        path_params=[{"name": "pk", "description": "Review ID", "type": "string"}],
        tags=["Reviews", "Shops", "Moderation", "Admin"],
    )
    @action(detail=True, methods=["post"], permission_classes=[CanModerateReviews])
    def moderate(self, request, pk=None):
        """Moderate a review (approve/reject)"""
        review = self.get_object()

        status_val = request.data.get("status")
        if status_val not in ["approved", "rejected"]:
            return Response(
                {"error": _('Invalid status. Use "approved" or "rejected".')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = request.data.get("comment", "")

        # Update review status
        review.status = status_val
        review.moderation_comment = comment
        review.moderated_by = request.user
        review.save()

        # If status changed, update metrics
        if status_val == "approved" or status_val == "rejected":
            entity_model_name = "shopapp.Shop"
            entity_id = review.shop_id
            RatingService.update_entity_metrics(entity_model_name, entity_id)

        return Response({"status": "review moderated"})


@document_api_viewset(
    summary="Specialist Review",
    description="API endpoints for managing specialist reviews",
    tags=["Reviews", "Specialists"],
)
class SpecialistReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for specialist reviews"""

    queryset = SpecialistReview.objects.all()
    serializer_class = SpecialistReviewSerializer
    permission_classes = [CanViewReviews, CanManageReviews]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SpecialistReviewFilter
    search_fields = ["title", "content"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter queryset based on permissions"""
        queryset = super().get_queryset()

        # For regular users, only show approved reviews
        user = self.request.user
        if not user.is_authenticated or not PermissionResolver.has_permission(
            user, "review", "view"
        ):
            queryset = queryset.filter(status="approved")

        # Filter by user
        user_id = self.request.query_params.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        return queryset

    @document_api_endpoint(
        summary="Mark review as helpful",
        description="Vote on whether a review was helpful or not",
        responses={
            200: "Success - Vote recorded successfully",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Review not found",
        },
        path_params=[{"name": "pk", "description": "Review ID", "type": "string"}],
        tags=["Reviews", "Specialists", "Helpfulness"],
    )
    @action(
        detail=True, methods=["post"], permission_classes=[CanVoteReviewHelpfulness]
    )
    def helpful(self, request, pk=None):
        """Mark review as helpful/not helpful"""
        review = self.get_object()

        serializer = ReviewHelpfulnessSerializer(
            data={
                "content_type_str": "reviewapp.specialistreview",
                "object_id": review.id,
                "is_helpful": request.data.get("is_helpful", True),
            },
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"status": "success"})

    @document_api_endpoint(
        summary="Report review",
        description="Report a review for inappropriate content",
        responses={
            200: "Success - Report submitted successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Review not found",
        },
        path_params=[{"name": "pk", "description": "Review ID", "type": "string"}],
        tags=["Reviews", "Specialists", "Moderation"],
    )
    @action(detail=True, methods=["post"], permission_classes=[CanReportReviews])
    def report(self, request, pk=None):
        """Report inappropriate review"""
        review = self.get_object()

        serializer = ReviewReportSerializer(
            data={
                "content_type_str": "reviewapp.specialistreview",
                "object_id": review.id,
                "reason": request.data.get("reason"),
                "details": request.data.get("details", ""),
            },
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"status": "report submitted"})

    @document_api_endpoint(
        summary="Moderate review",
        description="Approve or reject a review (admin/moderator only)",
        responses={
            200: "Success - Review moderated successfully",
            400: "Bad Request - Invalid status",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Review not found",
        },
        path_params=[{"name": "pk", "description": "Review ID", "type": "string"}],
        tags=["Reviews", "Specialists", "Moderation", "Admin"],
    )
    @action(detail=True, methods=["post"], permission_classes=[CanModerateReviews])
    def moderate(self, request, pk=None):
        """Moderate a review (approve/reject)"""
        review = self.get_object()

        status_val = request.data.get("status")
        if status_val not in ["approved", "rejected"]:
            return Response(
                {"error": _('Invalid status. Use "approved" or "rejected".')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = request.data.get("comment", "")

        # Update review status
        review.status = status_val
        review.moderation_comment = comment
        review.moderated_by = request.user
        review.save()

        # If status changed, update metrics
        if status_val == "approved" or status_val == "rejected":
            entity_model_name = "specialistsapp.Specialist"
            entity_id = review.specialist_id
            RatingService.update_entity_metrics(entity_model_name, entity_id)

        return Response({"status": "review moderated"})


@document_api_viewset(
    summary="Service Review",
    description="API endpoints for managing service reviews",
    tags=["Reviews", "Services"],
)
class ServiceReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for service reviews"""

    queryset = ServiceReview.objects.all()
    serializer_class = ServiceReviewSerializer
    permission_classes = [CanViewReviews, CanManageReviews]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ServiceReviewFilter
    search_fields = ["title", "content"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter queryset based on permissions"""
        queryset = super().get_queryset()

        # For regular users, only show approved reviews
        user = self.request.user
        if not user.is_authenticated or not PermissionResolver.has_permission(
            user, "review", "view"
        ):
            queryset = queryset.filter(status="approved")

        # Filter by user
        user_id = self.request.query_params.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        return queryset

    @document_api_endpoint(
        summary="Mark review as helpful",
        description="Vote on whether a review was helpful or not",
        responses={
            200: "Success - Vote recorded successfully",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Review not found",
        },
        path_params=[{"name": "pk", "description": "Review ID", "type": "string"}],
        tags=["Reviews", "Services", "Helpfulness"],
    )
    @action(
        detail=True, methods=["post"], permission_classes=[CanVoteReviewHelpfulness]
    )
    def helpful(self, request, pk=None):
        """Mark review as helpful/not helpful"""
        review = self.get_object()

        serializer = ReviewHelpfulnessSerializer(
            data={
                "content_type_str": "reviewapp.servicereview",
                "object_id": review.id,
                "is_helpful": request.data.get("is_helpful", True),
            },
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"status": "success"})

    @document_api_endpoint(
        summary="Report review",
        description="Report a review for inappropriate content",
        responses={
            200: "Success - Report submitted successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Review not found",
        },
        path_params=[{"name": "pk", "description": "Review ID", "type": "string"}],
        tags=["Reviews", "Services", "Moderation"],
    )
    @action(detail=True, methods=["post"], permission_classes=[CanReportReviews])
    def report(self, request, pk=None):
        """Report inappropriate review"""
        review = self.get_object()

        serializer = ReviewReportSerializer(
            data={
                "content_type_str": "reviewapp.servicereview",
                "object_id": review.id,
                "reason": request.data.get("reason"),
                "details": request.data.get("details", ""),
            },
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"status": "report submitted"})

    @document_api_endpoint(
        summary="Moderate review",
        description="Approve or reject a review (admin/moderator only)",
        responses={
            200: "Success - Review moderated successfully",
            400: "Bad Request - Invalid status",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Review not found",
        },
        path_params=[{"name": "pk", "description": "Review ID", "type": "string"}],
        tags=["Reviews", "Services", "Moderation", "Admin"],
    )
    @action(detail=True, methods=["post"], permission_classes=[CanModerateReviews])
    def moderate(self, request, pk=None):
        """Moderate a review (approve/reject)"""
        review = self.get_object()

        status_val = request.data.get("status")
        if status_val not in ["approved", "rejected"]:
            return Response(
                {"error": _('Invalid status. Use "approved" or "rejected".')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = request.data.get("comment", "")

        # Update review status
        review.status = status_val
        review.moderation_comment = comment
        review.moderated_by = request.user
        review.save()

        # If status changed, update metrics
        if status_val == "approved" or status_val == "rejected":
            entity_model_name = "serviceapp.Service"
            entity_id = review.service_id
            RatingService.update_entity_metrics(entity_model_name, entity_id)

        return Response({"status": "review moderated"})


@document_api_viewset(
    summary="Platform Review",
    description="API endpoints for managing platform reviews by shops",
    tags=["Reviews", "Platform"],
)
class PlatformReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for platform reviews by shops"""

    queryset = PlatformReview.objects.all()
    serializer_class = PlatformReviewSerializer
    permission_classes = [CanViewReviews, CanManageReviews]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = PlatformReviewFilter
    search_fields = ["title", "content"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter queryset based on permissions"""
        queryset = super().get_queryset()

        # Filter platform reviews for admins only, unless the company is related to user
        user = self.request.user

        # Queue Me admins can see all
        if user.is_authenticated and PermissionResolver.has_permission(
            user, "review", "view"
        ):
            return queryset

        # Companies can see their own reviews
        if user.is_authenticated:
            # Check if user is company owner
            from apps.companiesapp.models import Company

            company_ids = Company.objects.filter(owner=user).values_list(
                "id", flat=True
            )

            # Check if user is shop manager for any company
            from apps.shopapp.models import Shop

            managed_shop_companies = Shop.objects.filter(manager=user).values_list(
                "company_id", flat=True
            )

            # Combine lists
            company_ids = list(company_ids) + list(managed_shop_companies)

            return queryset.filter(company_id__in=company_ids, status="approved")

        # No platform reviews for unauthenticated users
        return queryset.none()

    @document_api_endpoint(
        summary="Moderate platform review",
        description="Approve or reject a platform review (admin/moderator only)",
        responses={
            200: "Success - Review moderated successfully",
            400: "Bad Request - Invalid status",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Review not found",
        },
        path_params=[{"name": "pk", "description": "Review ID", "type": "string"}],
        tags=["Reviews", "Platform", "Moderation", "Admin"],
    )
    @action(detail=True, methods=["post"], permission_classes=[CanModerateReviews])
    def moderate(self, request, pk=None):
        """Moderate a platform review (approve/reject)"""
        review = self.get_object()

        status_val = request.data.get("status")
        if status_val not in ["approved", "rejected"]:
            return Response(
                {"error": _('Invalid status. Use "approved" or "rejected".')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = request.data.get("comment", "")

        # Update review status
        review.status = status_val
        review.moderation_comment = comment
        review.moderated_by = request.user
        review.save()

        # Platform reviews don't update metrics yet

        return Response({"status": "review moderated"})


@document_api_viewset(
    summary="Review Report",
    description="API endpoints for managing reports of reviews",
    tags=["Reviews", "Moderation", "Admin"],
)
class ReviewReportViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for managing review reports"""

    queryset = ReviewReport.objects.all()
    serializer_class = ReviewReportSerializer
    permission_classes = [CanModerateReviews]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ReviewReportFilter
    ordering_fields = ["created_at", "status"]
    ordering = ["-created_at"]

    @document_api_endpoint(
        summary="Resolve report",
        description="Resolve a review report with a specific status",
        responses={
            200: "Success - Report resolved successfully",
            400: "Bad Request - Invalid status",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Report not found",
        },
        path_params=[{"name": "pk", "description": "Report ID", "type": "string"}],
        tags=["Reviews", "Moderation", "Admin"],
    )
    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        """Resolve a report"""
        report = self.get_object()

        status_val = request.data.get("status")
        if status_val not in ["reviewed", "resolved", "rejected"]:
            return Response(
                {"error": _("Invalid status.")}, status=status.HTTP_400_BAD_REQUEST
            )

        # Update report status
        report.status = status_val
        report.save()

        # If resolving as valid, we might want to take action on the review
        if status_val == "resolved":
            review_action = request.data.get("review_action")
            if review_action in ["reject", "remove"]:
                # Get the review
                review = report.review

                if review_action == "reject":
                    # Reject the review
                    review.status = "rejected"
                    review.moderation_comment = _("Rejected due to report")
                    review.moderated_by = request.user
                    review.save()

                    # Update metrics
                    content_type = ContentType.objects.get_for_model(review)
                    if content_type.model == "shopreview":
                        entity_model_name = "shopapp.Shop"
                        entity_id = review.shop_id
                    elif content_type.model == "specialistreview":
                        entity_model_name = "specialistsapp.Specialist"
                        entity_id = review.specialist_id
                    elif content_type.model == "servicereview":
                        entity_model_name = "serviceapp.Service"
                        entity_id = review.service_id

                    RatingService.update_entity_metrics(entity_model_name, entity_id)

        return Response({"status": "report updated"})


@document_api_viewset(
    summary="Review Metric",
    description="API endpoints for retrieving review metrics and statistics",
    tags=["Reviews", "Metrics"],
)
class ReviewMetricViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for review metrics"""

    queryset = ReviewMetric.objects.all()
    serializer_class = ReviewMetricSerializer
    permission_classes = [permissions.AllowAny]

    @document_api_endpoint(
        summary="Get entity metrics",
        description="Get review metrics for a specific entity (shop, specialist, or service)",
        responses={
            200: "Success - Returns entity metrics",
            400: "Bad Request - Missing parameters or invalid entity type",
        },
        query_params=[
            {
                "name": "entity_type",
                "description": "Entity type (e.g., shopapp.Shop)",
                "required": True,
                "type": "string",
            },
            {
                "name": "entity_id",
                "description": "Entity ID",
                "required": True,
                "type": "string",
            },
        ],
        tags=["Reviews", "Metrics"],
    )
    @action(detail=False, methods=["get"])
    def entity(self, request):
        """Get metrics for a specific entity"""
        entity_type = request.query_params.get("entity_type")
        entity_id = request.query_params.get("entity_id")

        if not entity_type or not entity_id:
            return Response(
                {"error": _("Both entity_type and entity_id are required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            app_label, model = entity_type.split(".")
            content_type = ContentType.objects.get(app_label=app_label, model=model)
        except (ValueError, ContentType.DoesNotExist):
            return Response(
                {"error": _("Invalid entity type")}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create metrics
        metrics, created = ReviewMetric.objects.get_or_create(
            content_type=content_type,
            object_id=entity_id,
            defaults={
                "avg_rating": 0,
                "weighted_rating": 0,
                "review_count": 0,
                "rating_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
            },
        )

        serializer = self.get_serializer(metrics)
        return Response(serializer.data)

    @document_api_endpoint(
        summary="Recalculate metrics",
        description="Recalculate review metrics for a specific entity (admin only)",
        responses={
            200: "Success - Metrics recalculated",
            400: "Bad Request - Missing parameters or invalid entity type",
            403: "Forbidden - User doesn't have permission",
        },
        tags=["Reviews", "Metrics", "Admin"],
    )
    @action(detail=False, methods=["post"])
    def recalculate(self, request):
        """Recalculate metrics for an entity"""
        entity_type = request.data.get("entity_type")
        entity_id = request.data.get("entity_id")

        if not entity_type or not entity_id:
            return Response(
                {"error": _("Both entity_type and entity_id are required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check permissions
        if not PermissionResolver.has_permission(request.user, "review", "edit"):
            return Response(
                {"error": _("You do not have permission to recalculate metrics")},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Update metrics
        try:
            RatingService.update_entity_metrics(entity_type, entity_id)
            return Response({"status": "metrics recalculated"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
