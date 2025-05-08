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

    Stories can be filtered by shop, expiry status, and followed status.
    """

    queryset = Story.objects.filter(is_active=True)
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = StoryFilter
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
    permission_classes = [permissions.IsAuthenticated, IsShopStaffOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action == "create":
            return StoryCreateSerializer
        return StorySerializer

    def get_queryset(self):
        """
        Filter stories based on user role:
        - For customers: Only show active, non-expired stories from shops in their city
        - For shop staff: Show their shop's stories
        - For admin: Show all stories
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
        Get stories for the home feed (followed shops only)
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
        Create a new story, ensuring the user has permission to create for the shop
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
    """

    serializer_class = StoryViewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """Create story view record"""
        serializer.save(customer=self.request.user)
