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
        if self.action == "list":
            # For shop managers/staff, show all reels for their shop
            shop_id = self.kwargs.get("shop_id")
            return Reel.objects.filter(shop_id=shop_id)

        return Reel.objects.all()

    def get_serializer_class(self):
        if (
            self.action == "create"
            or self.action == "update"
            or self.action == "partial_update"
        ):
            return ReelCreateUpdateSerializer
        elif self.action == "retrieve":
            return ReelDetailSerializer
        return ReelSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), CanManageReels()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        shop_id = self.kwargs.get("shop_id")
        shop = get_object_or_404(Shop, id=shop_id)

        # Let the serializer handle the shop assignment
        reel = serializer.save()

        # Process video for thumbnail and duration extraction
        ReelService.process_reel_video(reel)

    @action(detail=True, methods=["post"])
    def publish(self, request, shop_id=None, pk=None):
        """Publish a draft reel"""
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
                {
                    "detail": "At least one service or package must be linked before publishing."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update reel to published status
        reel.status = "published"
        reel.published_at = timezone.now()
        reel.save()

        return Response(self.get_serializer(reel).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, shop_id=None, pk=None):
        """Archive a published reel"""
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
        # Only show published reels
        queryset = Reel.objects.filter(status="published")

        # City-based restriction - only show reels from shops in same city as customer
        user = self.request.user
        # If customer's location is manually specified via query params
        lat = self.request.query_params.get("lat")
        lng = self.request.query_params.get("lng")
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
        Get personalized feed of reels.
        Feed types:
        - nearby: Reels from shops in the same city, sorted by distance
        - for_you: Personalized feed based on engagement and preferences
        - following: Reels from shops the customer follows
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
                {
                    "detail": "Invalid feed type. Choose from: nearby, for_you, following"
                },
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
        """Like or unlike a reel"""
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
        """Add a comment to a reel"""
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
        """Record a share of a reel"""
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
        """Report a reel for inappropriate content"""
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

        return Response(
            ReelReportSerializer(report).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"])
    def comments(self, request, pk=None):
        """Get comments for a reel"""
        reel = self.get_object()
        comments = reel.comments.filter(is_hidden=False).order_by("-created_at")

        page = self.paginate_queryset(comments)
        if page is not None:
            serializer = ReelCommentSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = ReelCommentSerializer(
            comments, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["delete"], url_path="comments/(?P<comment_id>[^/.]+)")
    def delete_comment(self, request, pk=None, comment_id=None):
        """Delete a comment by the comment author"""
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
        """Get recommended reels based on user preferences and behavior"""
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
