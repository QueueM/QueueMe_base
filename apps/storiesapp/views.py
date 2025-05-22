"""
Stories app views for QueueMe platform
Handles endpoints related to ephemeral stories created by shops,
similar to Instagram/Snapchat stories, that automatically expire after 24 hours.
"""

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.rolesapp.permissions import IsShopStaffOrReadOnly
from apps.storiesapp.filters import StoryFilter
from apps.storiesapp.models import Story
from apps.storiesapp.serializers import (
    StoryCreateSerializer,
    StoryMinimalSerializer,
    StorySerializer,
    StoryViewSerializer,
)
from apps.storiesapp.services.story_feed_generator import StoryFeedGenerator
from apps.storiesapp.services.story_service import StoryService


class StoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for creating, retrieving, and managing stories.

    Handles all CRUD operations for shop stories, which automatically expire
    after a specified time period (typically 24 hours). Stories can contain
    images, video, or text content highlighting shop services and promotions.

    Endpoints:
    - GET /api/stories/ - List stories (filtered based on user role)
    - POST /api/stories/ - Create a new story
    - GET /api/stories/{id}/ - Get story details
    - PUT/PATCH /api/stories/{id}/ - Update a story
    - DELETE /api/stories/{id}/ - Delete a story
    - GET /api/stories/home_feed/ - Get stories for customer home feed
    - GET /api/stories/shop_feed/ - Get stories for a specific shop
    - POST /api/stories/{id}/mark_viewed/ - Mark a story as viewed

    Permissions:
    - Authentication required for all actions
    - Shop staff can create/update/delete their shop's stories
    - Customers can only read/view stories

    Filtering:
    - shop: Filter by shop ID
    - is_expired: Filter by expiry status
    - is_viewed: Filter by viewed status (for current user)
    - followed: Filter by shops followed by the user

    Ordering:
    - created_at: Creation date/time
    """

    queryset = Story.objects.filter(is_active=True)
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = StoryFilter
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
    permission_classes = [permissions.IsAuthenticated, IsShopStaffOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        """
        Return appropriate serializer based on the action

        Uses a specialized creation serializer for the create action.

        Returns:
            Serializer class: The appropriate serializer for the current action
        """
        if self.action == "create":
            return StoryCreateSerializer
        return StorySerializer

    def get_queryset(self):
        """
        Filter stories based on user role

        Different users see different stories:
        - Customers see active, non-expired stories from shops in their city
        - Shop staff see their shop's stories
        - Admins see all stories

        Also filters out expired stories for all users.

        Returns:
            QuerySet: Filtered list of stories appropriate for the user
        """
        user = self.request.user
        queryset = super().get_queryset()

        # Add base filter for expired stories
        queryset = queryset.filter(expires_at__gt=timezone.now())

        # Filter based on user role
        if user.user_type == "customer":
            # Get customer's city
            from apps.customersapp.models import CustomerProfile

            try:
                profile = CustomerProfile.objects.get(user=user)
                city = profile.city
                if city:
                    # Filter to shops in same city as customer
                    queryset = queryset.filter(shop__location__city=city)
            except CustomerProfile.DoesNotExist:
                pass
        elif user.user_type in ["employee"]:
            # Get employee's shop
            from apps.employeeapp.models import Employee

            try:
                employee = Employee.objects.get(user=user)
                queryset = queryset.filter(shop=employee.shop)
            except Employee.DoesNotExist:
                queryset = Story.objects.none()

        return queryset

    @action(detail=False, methods=["get"])
    def home_feed(self, request):
        """
        Get stories for the customer home feed

        Returns stories from shops the customer follows, prioritized
        and organized in a personalized feed format.

        Only available to users with 'customer' type.

        Returns:
            Response: List of stories in feed format

        Status codes:
            200: Feed retrieved successfully
            403: User is not a customer
        """
        user = request.user

        if user.user_type != "customer":
            return Response(
                {"detail": "Only customers can access the home feed"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Generate feed using the advanced algorithm
        feed_generator = StoryFeedGenerator()
        stories = feed_generator.generate_home_feed(user.id)

        serializer = StoryMinimalSerializer(
            stories, many=True, context={"request": request}
        )

        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def shop_feed(self, request):
        """
        Get stories for a specific shop's screen

        Returns all active stories for a specific shop, organized
        in chronological order.

        Query parameters:
            shop_id: ID of the shop (required)

        Returns:
            Response: List of stories for the shop

        Status codes:
            200: Feed retrieved successfully
            400: Missing shop_id parameter
        """
        shop_id = request.query_params.get("shop_id")

        if not shop_id:
            return Response(
                {"detail": "shop_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate feed using shop feed generator
        feed_generator = StoryFeedGenerator()
        stories = feed_generator.generate_shop_feed(shop_id)

        serializer = StoryMinimalSerializer(
            stories, many=True, context={"request": request}
        )

        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def mark_viewed(self, request, pk=None):
        """
        Mark a story as viewed by the current user

        Records that the authenticated customer has viewed the story.
        This affects the story's view count and the user's feed.

        Only available to users with 'customer' type.

        Returns:
            Response: Success message

        Status codes:
            200: Story marked as viewed successfully
            403: User is not a customer
        """
        story = self.get_object()
        customer = request.user

        if customer.user_type != "customer":
            return Response(
                {"detail": "Only customers can mark stories as viewed"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Record the view
        StoryService.mark_viewed(story.id, customer.id)

        return Response({"detail": "Story marked as viewed"})

    def perform_create(self, serializer):
        """
        Create a new story with permission checks

        Verifies that the user has permission to create stories for the
        specified shop before creating the story.

        Args:
            serializer: The story serializer instance

        Raises:
            PermissionError: If user doesn't have permission to create stories for the shop
        """
        shop_id = serializer.validated_data.get("shop_id")
        user = self.request.user

        # Check if user has permission to create stories for this shop
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        if not PermissionResolver.has_shop_permission(user, shop_id, "story", "add"):
            raise PermissionError(
                "You don't have permission to create stories for this shop"
            )

        serializer.save()


class StoryViewCreateAPIView(generics.CreateAPIView):
    """
    API endpoint for recording story views.

    Creates a record when a customer views a story, which helps track
    engagement metrics and personalize the user's feed.

    Endpoint:
    - POST /api/story-views/ - Record a story view

    Request body:
        {
            "story": "story_id",
            "view_duration": seconds (optional),
            "device_info": "device information" (optional)
        }

    Permissions:
    - Authentication required
    """

    serializer_class = StoryViewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """
        Create story view record

        Automatically associates the view with the current user.

        Args:
            serializer: The story view serializer instance
        """
        serializer.save(customer=self.request.user)
