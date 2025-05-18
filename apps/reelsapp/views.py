"""
Reels app views for QueueMe platform
Handles endpoints related to short video content created by shops to showcase their services,
similar to Instagram Reels or TikTok. Includes both shop management and customer interaction endpoints.
"""

from django.db.models import Count, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.shopapp.models import Shop

from .filters import ReelFilter
from .models import Reel, ReelComment, ReelLike, ReelReport, ReelShare
from .permissions import CanManageReels
from .serializers import (
    ReelCommentSerializer,
    ReelCreateUpdateSerializer,
    ReelDetailSerializer,
    ReelFeedSerializer,
    ReelReportSerializer,
    ReelSerializer,
    ReelShareSerializer,
)
from .services.engagement_service import EngagementService
from .services.feed_curator import FeedCuratorService
from .services.recommendation_service import RecommendationService
from .services.reel_service import ReelService


class ReelViewSet(viewsets.ModelViewSet):
    """
    API endpoint for shop reels management.

    Allows shop owners and managers to create, view, edit, and remove reels for their shop.
    Reels can be in draft, published, or archived state. Video processing happens automatically.

    Endpoints:
    - GET /api/shops/{shop_id}/reels/ - List reels for a shop
    - POST /api/shops/{shop_id}/reels/ - Create a new reel
    - GET /api/shops/{shop_id}/reels/{id}/ - Get reel details
    - PUT/PATCH /api/shops/{shop_id}/reels/{id}/ - Update a reel
    - DELETE /api/shops/{shop_id}/reels/{id}/ - Delete a reel
    - POST /api/shops/{shop_id}/reels/{id}/publish/ - Publish a draft reel
    - POST /api/shops/{shop_id}/reels/{id}/archive/ - Archive a published reel

    Permissions:
    - Authentication required for all actions
    - Special permission required for create/update/delete actions

    Filtering:
    - status: Filter by reel status (draft, published, archived)
    - service: Filter by linked service
    - package: Filter by linked package
    - created_at: Filter by creation date

    Search fields:
    - title: Reel title
    - caption: Reel caption

    Ordering:
    - created_at: Creation date
    - view_count: Number of views
    """

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ReelFilter
    search_fields = ["title", "caption"]
    ordering_fields = ["created_at", "view_count"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """
        Filter reels by shop ID

        Returns:
            QuerySet: Reels belonging to the shop specified in the URL
        """
        if self.action == "list":
            # For shop managers/staff, show all reels for their shop
            shop_id = self.kwargs.get("shop_id")
            return Reel.objects.filter(shop_id=shop_id)

        return Reel.objects.all()

    def get_serializer_class(self):
        """
        Return appropriate serializer based on action

        - Create/update: ReelCreateUpdateSerializer
        - Retrieve: ReelDetailSerializer
        - List and other actions: ReelSerializer

        Returns:
            Serializer class: The appropriate serializer for the current action
        """
        if self.action == "create" or self.action == "update" or self.action == "partial_update":
            return ReelCreateUpdateSerializer
        elif self.action == "retrieve":
            return ReelDetailSerializer
        return ReelSerializer

    def get_permissions(self):
        """
        Set permissions based on action

        Create, update, and delete operations require special permissions.
        All other actions just require authentication.

        Returns:
            list: Permission classes for the current action
        """
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), CanManageReels()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        """
        Create a new reel and process its video

        Saves the reel with the shop from the URL and then processes
        the video to extract thumbnails and duration.

        Args:
            serializer: The reel serializer instance
        """
        # Get shop_id from URL but we don't need to use it explicitly
        # since the serializer will handle the shop assignment
        # Commented out unused variable - fix for F841
        # shop_id = self.kwargs.get("shop_id")

        # Let the serializer handle the shop assignment
        reel = serializer.save()

        # Process video for thumbnail and duration extraction
        ReelService.process_reel_video(reel)

    @action(detail=True, methods=["post"])
    def publish(self, request, shop_id=None, pk=None):
        """
        Publish a draft reel

        Changes a reel's status from 'draft' to 'published', making it visible
        to customers. Requires at least one service or package to be linked.

        Returns:
            Response: Updated reel data

        Status codes:
            200: Reel published successfully
            400: Reel can't be published (not draft or missing linked services/packages)
        """
        reel = self.get_object()

        # Ensure the reel is in draft status
        if reel.status != "draft":
            return Response(
                {"detail": "Only draft reels can be published."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure at least one service or package is linked
        if not reel.services.exists() and not reel.packages.exists():
            return Response(
                {"detail": "At least one service or package must be linked before publishing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update reel to published status
        reel.status = "published"
        reel.published_at = timezone.now()
        reel.save()

        return Response(self.get_serializer(reel).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, shop_id=None, pk=None):
        """
        Archive a published reel

        Changes a reel's status from 'published' to 'archived', hiding it
        from customers without deleting it.

        Returns:
            Response: Updated reel data

        Status codes:
            200: Reel archived successfully
            400: Reel can't be archived (not published)
        """
        reel = self.get_object()

        # Ensure the reel is in published status
        if reel.status != "published":
            return Response(
                {"detail": "Only published reels can be archived."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update reel to archived status
        reel.status = "archived"
        reel.save()

        return Response(self.get_serializer(reel).data)


class CustomerReelViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """
    API endpoint for customers to view and interact with reels.

    Allows customers to browse, view, and interact with shop reels through
    various actions like liking, commenting, and sharing.

    Endpoints:
    - GET /api/reels/ - List published reels
    - GET /api/reels/{id}/ - View a specific reel
    - GET /api/reels/feed/ - Get personalized feed of reels
    - POST /api/reels/{id}/like/ - Like/unlike a reel
    - POST /api/reels/{id}/comment/ - Comment on a reel
    - POST /api/reels/{id}/share/ - Share a reel
    - POST /api/reels/{id}/report/ - Report a reel
    - GET /api/reels/{id}/comments/ - Get comments for a reel
    - DELETE /api/reels/{id}/comments/{comment_id}/ - Delete own comment
    - GET /api/reels/recommended/ - Get recommended reels

    Permissions:
    - Authentication required for all actions

    Filtering:
    - Multiple filters are available via ReelFilter

    Search fields:
    - title: Reel title
    - caption: Reel caption
    - shop__name: Shop name

    Ordering:
    - created_at: Creation date
    - view_count: Number of views
    """

    serializer_class = ReelFeedSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ReelFilter
    search_fields = ["title", "caption", "shop__name"]
    ordering_fields = ["created_at", "view_count"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """
        Filter reels for customers

        Only shows published reels, with city-based filtering based on the
        customer's location or query parameters.

        Returns:
            QuerySet: Filtered reels that customers should be able to see
        """
        # Only show published reels
        queryset = Reel.objects.filter(status="published")

        # City-based restriction - only show reels from shops in same city as customer
        user = self.request.user
        # Commenting out unused variables - fix for F841
        # lat = self.request.query_params.get("lat")
        # lng = self.request.query_params.get("lng")
        city = self.request.query_params.get("city")

        if city:
            # Filter by city from query params
            queryset = queryset.filter(city=city)
        elif (
            hasattr(user, "customer")
            and hasattr(user.customer, "location")
            and user.customer.location
        ):
            # Filter by customer's saved city
            queryset = queryset.filter(city=user.customer.location.city)

        # Add subqueries for performance optimization
        queryset = queryset.annotate(
            likes_count=Count("likes", distinct=True),
            comments_count=Count("comments", distinct=True),
            shares_count=Count("shares", distinct=True),
        )

        return queryset

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a specific reel and record the view

        Records analytics data about the view, including watch duration,
        and increments the view counter.

        Args:
            request: The HTTP request

        Returns:
            Response: Reel data
        """
        # Record the view
        reel = self.get_object()
        watch_duration = request.data.get("watch_duration", 0)
        watched_full = request.data.get("watched_full", False)
        device_id = request.data.get("device_id")

        # Create view record
        EngagementService.record_view(
            reel_id=reel.id,
            user_id=request.user.id,
            device_id=device_id,
            watch_duration=watch_duration,
            watched_full=watched_full,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        # Increment view counter
        reel.view_count = F("view_count") + 1
        reel.save(update_fields=["view_count"])

        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def feed(self, request):
        """
        Get personalized feed of reels

        Returns a curated feed of reels based on the requested feed type.

        Query parameters:
            type: Feed type (nearby, for_you, following, default: nearby)
            lat: Latitude for location-based feed (optional)
            lng: Longitude for location-based feed (optional)

        Feed types:
        - nearby: Reels from shops in the same city, sorted by distance
        - for_you: Personalized feed based on engagement and preferences
        - following: Reels from shops the customer follows

        Returns:
            Response: List of reels for the feed

        Status codes:
            200: Feed retrieved successfully
            400: Invalid feed type
        """
        feed_type = request.query_params.get("type", "nearby")

        # Get customer's city
        user = request.user
        city = (
            user.customer.location.city
            if hasattr(user, "customer") and hasattr(user.customer, "location")
            else None
        )

        # Get location coordinates if provided
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        location = None
        if lat and lng:
            location = {"latitude": float(lat), "longitude": float(lng)}

        # Get nearby reels
        if feed_type == "nearby":
            reels = FeedCuratorService.get_nearby_feed(user.id, city, location)
        # Get "For You" reels
        elif feed_type == "for_you":
            reels = FeedCuratorService.get_personalized_feed(user.id, city)
        # Get reels from followed shops
        elif feed_type == "following":
            reels = FeedCuratorService.get_following_feed(user.id)
        else:
            return Response(
                {"detail": "Invalid feed type. Choose from: nearby, for_you, following"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        page = self.paginate_queryset(reels)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(reels, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        """
        Like or unlike a reel

        Toggles the like status for a reel. If already liked, unlikes it.
        If not yet liked, likes it and records the engagement.

        Returns:
            Response: Success message

        Status codes:
            200: Reel unliked successfully
            201: Reel liked successfully
        """
        reel = self.get_object()
        user = request.user

        # Check if already liked
        like, created = ReelLike.objects.get_or_create(reel=reel, user=user)

        if not created:
            # Unlike
            like.delete()
            return Response({"detail": "Reel unliked."}, status=status.HTTP_200_OK)

        # Like was created
        EngagementService.process_engagement_event(reel, user, "like")
        return Response({"detail": "Reel liked."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def comment(self, request, pk=None):
        """
        Add a comment to a reel

        Creates a new comment on the reel and records the engagement.

        Request body:
            {
                "content": "Comment text" (required)
            }

        Returns:
            Response: Created comment data

        Status codes:
            201: Comment created successfully
            400: Invalid request data
        """
        reel = self.get_object()
        user = request.user

        serializer = ReelCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment = ReelComment.objects.create(
            reel=reel, user=user, content=serializer.validated_data["content"]
        )

        EngagementService.process_engagement_event(reel, user, "comment")

        return Response(
            ReelCommentSerializer(comment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        """
        Record a share of a reel

        Creates a record of the user sharing a reel and records the engagement.

        Request body:
            {
                "share_type": "in_app|social|direct" (optional, default: "in_app")
            }

        Returns:
            Response: Created share record data

        Status codes:
            201: Share recorded successfully
            400: Invalid request data
        """
        reel = self.get_object()
        user = request.user

        serializer = ReelShareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        share = ReelShare.objects.create(
            reel=reel,
            user=user,
            share_type=serializer.validated_data.get("share_type", "in_app"),
        )

        EngagementService.process_engagement_event(reel, user, "share")

        return Response(ReelShareSerializer(share).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def report(self, request, pk=None):
        """
        Report a reel for inappropriate content

        Creates a report against a reel, which will be reviewed by moderators.
        Users can only report a reel once.

        Request body:
            {
                "reason": "copyright|inappropriate|offensive|other" (required),
                "description": "Detailed explanation" (optional)
            }

        Returns:
            Response: Created report data

        Status codes:
            201: Report created successfully
            400: Invalid request data or already reported
        """
        reel = self.get_object()
        user = request.user

        serializer = ReelReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check if user already reported this reel
        existing_report = ReelReport.objects.filter(reel=reel, user=user).first()
        if existing_report:
            return Response(
                {"detail": "You have already reported this reel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report = ReelReport.objects.create(
            reel=reel,
            user=user,
            reason=serializer.validated_data["reason"],
            description=serializer.validated_data.get("description", ""),
        )

        return Response(ReelReportSerializer(report).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def comments(self, request, pk=None):
        """
        Get comments for a reel

        Returns a paginated list of visible comments for the reel,
        ordered by creation time (newest first).

        Returns:
            Response: List of comments
        """
        reel = self.get_object()
        comments = reel.comments.filter(is_hidden=False).order_by("-created_at")

        page = self.paginate_queryset(comments)
        if page is not None:
            serializer = ReelCommentSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = ReelCommentSerializer(comments, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["delete"], url_path="comments/(?P<comment_id>[^/.]+)")
    def delete_comment(self, request, pk=None, comment_id=None):
        """
        Delete a comment by the comment author

        Allows users to delete their own comments on reels.

        Path parameters:
            comment_id: ID of the comment to delete

        Returns:
            Response: No content

        Status codes:
            204: Comment deleted successfully
            403: Not the comment author
            404: Comment not found
        """
        comment = get_object_or_404(ReelComment, id=comment_id)

        # Ensure the user is the comment author
        if comment.user != request.user:
            return Response(
                {"detail": "You can only delete your own comments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def recommended(self, request):
        """
        Get recommended reels based on user preferences and behavior

        Returns a personalized list of recommended reels, taking into account
        the user's past interactions, preferences, and location.

        Returns:
            Response: List of recommended reels
        """
        user = request.user
        city = (
            user.customer.location.city
            if hasattr(user, "customer") and hasattr(user.customer, "location")
            else None
        )

        # Use recommendation service to get personalized recommendations
        reels = RecommendationService.get_recommended_reels(user.id, city)

        page = self.paginate_queryset(reels)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(reels, many=True)
        return Response(serializer.data)
