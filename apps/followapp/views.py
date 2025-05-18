"""
Follow app views for QueueMe platform
Handles endpoints related to shop following functionality, allowing customers to follow shops
and shop owners to view their followers and follower statistics.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.shopapp.models import Shop

from .models import Follow, FollowStats
from .permissions import CanViewFollowers, IsFollowOwner
from .serializers import (
    FollowSerializer,
    FollowStatsSerializer,
    FollowStatusSerializer,
    ShopFollowersSerializer,
)
from .services.analytics_service import FollowAnalyticsService
from .services.follow_service import FollowService


class FollowViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing shop follows.

    Allows customers to follow/unfollow shops and manage their following settings.
    Customers can only view and modify their own follows.

    Endpoints:
    - GET /api/follows/ - List all shops the current user is following
    - POST /api/follows/ - Follow a shop
    - GET /api/follows/{id}/ - Get details of a specific follow relationship
    - PUT/PATCH /api/follows/{id}/ - Update follow notification settings
    - DELETE /api/follows/{id}/ - Unfollow a shop
    - GET /api/follows/following/ - List all shops the user is following
    - POST /api/follows/toggle/ - Toggle follow status for a shop
    - GET /api/follows/status/ - Check if user is following a specific shop

    Permissions:
    - All actions require authentication
    - Retrieve/update/delete operations require follow ownership
    """

    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filter follows by the current user

        Returns:
            QuerySet: Follow objects for the current user
        """
        # Filter follows by the current user
        return Follow.objects.filter(customer=self.request.user)

    def get_permissions(self):
        """
        Set permissions based on action

        For operations on specific follow relationships, the user must own the follow.

        Returns:
            list: Permission classes for the current action
        """
        if self.action in ["retrieve", "update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated(), IsFollowOwner()]
        return super().get_permissions()

    def perform_create(self, serializer):
        """
        Create a new follow relationship

        Checks if the user already follows the shop before creating the relationship.

        Args:
            serializer: The follow serializer instance

        Returns:
            Response: Error response if already following the shop
        """
        # Check if the user already follows this shop
        shop = serializer.validated_data.get("shop")
        if Follow.objects.filter(customer=self.request.user, shop=shop).exists():
            return Response(
                {"detail": _("You are already following this shop.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create the follow relationship
        serializer.save(customer=self.request.user)

    @action(detail=False, methods=["get"])
    def following(self, request):
        """
        Get all shops the current user is following

        Returns a paginated list of all the shops the authenticated user is following.

        Returns:
            Response: List of follow relationships
        """
        follows = self.get_queryset()
        page = self.paginate_queryset(follows)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(follows, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def toggle(self, request):
        """
        Toggle follow status for a shop

        If the user is already following the shop, they will unfollow it.
        If the user is not following the shop, they will follow it.

        Request body:
            {
                "shop_id": "uuid" (required)
            }

        Returns:
            Response: Updated follow status
                {
                    "is_following": boolean,
                    "shop_id": "uuid",
                    "follow_id": "uuid" (only if is_following is true)
                }

        Status codes:
            200: Status toggled successfully
            400: Missing shop_id or city mismatch
            404: Shop not found
        """
        shop_id = request.data.get("shop_id")
        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shop = get_object_or_404(Shop, id=shop_id)

        # Check if user is in the same city as shop
        customer = request.user
        if customer.city and shop.location and shop.location.city:
            if customer.city != shop.location.city:
                return Response(
                    {"detail": _("You can only follow shops in your city.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Use the service to toggle follow status
        with transaction.atomic():
            is_following, follow_obj = FollowService.toggle_follow(request.user, shop)

        # Return the updated status
        result = {"is_following": is_following, "shop_id": shop_id}

        if is_following:
            result["follow_id"] = follow_obj.id

        return Response(result)

    @action(detail=False, methods=["get"])
    def status(self, request):
        """
        Check if user is following a specific shop

        Returns whether the current user is following the specified shop
        and the total follower count for that shop.

        Query parameters:
            shop_id: UUID of the shop (required)

        Returns:
            Response: Follow status and follower count
                {
                    "is_following": boolean,
                    "follower_count": integer
                }

        Status codes:
            200: Status retrieved successfully
            400: Missing shop_id
            404: Shop not found
        """
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shop = get_object_or_404(Shop, id=shop_id)

        # Get follow status and count
        is_following = Follow.objects.filter(customer=request.user, shop=shop).exists()

        try:
            follower_count = shop.follow_stats.follower_count
        except Exception:
            follower_count = 0

        serializer = FollowStatusSerializer(
            data={"is_following": is_following, "follower_count": follower_count}
        )
        serializer.is_valid()
        return Response(serializer.data)


class ShopFollowersViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    API endpoint for viewing shop followers.

    Allows shop owners, managers, and Queue Me admins to view followers of a shop
    and related statistics.

    Endpoints:
    - GET /api/shops/{shop_id}/followers/ - List followers of a shop
    - GET /api/shops/{shop_id}/followers/stats/ - Get follower statistics
    - GET /api/shops/followers/most_followed/ - Get most followed shops

    Permissions:
    - All actions require authentication
    - Most actions require permission to view followers (shop owners/managers/admins)
    """

    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewFollowers]

    def get_queryset(self):
        """
        Filter follows by shop ID

        Returns:
            QuerySet: Follow objects for the specified shop
        """
        shop_id = self.kwargs.get("shop_id")
        return Follow.objects.filter(shop_id=shop_id).select_related("customer")

    def list(self, request, *args, **kwargs):
        """
        List all followers of a shop

        Returns a paginated list of all users following the specified shop.

        Returns:
            Response: List of follow relationships
        """
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def stats(self, request, shop_id=None):
        """
        Get follower statistics for a shop

        Returns detailed statistics about a shop's followers, including:
        - Total follower count
        - Weekly growth rate
        - Monthly growth rate
        - Historical trend data

        Returns:
            Response: Follower statistics and trends
                {
                    "follower_count": integer,
                    "weekly_growth": float,
                    "monthly_growth": float,
                    "trends": {
                        "daily": [...],
                        "weekly": [...],
                        "monthly": [...]
                    }
                }

        Status codes:
            200: Statistics retrieved successfully
            404: Shop not found
        """
        shop = get_object_or_404(Shop, id=shop_id)

        try:
            stats = shop.follow_stats
        except FollowStats.DoesNotExist:
            # Create stats if they don't exist
            stats = FollowStats.objects.create(
                shop=shop,
                follower_count=Follow.objects.filter(shop=shop).count(),
                weekly_growth=0,
                monthly_growth=0,
            )

        # Get analytics
        trend_data = FollowAnalyticsService.get_follower_trends(shop)

        # Combine with serializer data
        serializer = FollowStatsSerializer(stats)
        response_data = serializer.data
        response_data.update({"trends": trend_data})

        return Response(response_data)

    @action(detail=False, methods=["get"])
    def most_followed(self, request):
        """
        Get most followed shops

        Returns a list of shops with the highest follower counts.
        This endpoint is accessible to all authenticated users.

        Returns:
            Response: List of most followed shops with their follower counts
                [
                    {
                        "shop": {shop_data},
                        "follower_count": integer
                    },
                    ...
                ]
        """
        # This action doesn't require shop_id, accessible to all authenticated users
        result = FollowAnalyticsService.get_most_followed_shops(limit=10)
        serializer = ShopFollowersSerializer(result, many=True)
        return Response(serializer.data)
