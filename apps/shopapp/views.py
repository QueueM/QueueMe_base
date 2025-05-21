"""
Shop app views for QueueMe platform
Handles endpoints related to shops, branches, followers, hours, and verifications
"""

from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from api.documentation.api_doc_decorators import document_api_endpoint, document_api_viewset

from .filters import ShopFilter, ShopFollowerFilter, ShopHoursFilter, ShopVerificationFilter
from .models import Shop, ShopFollower, ShopHours, ShopSettings, ShopVerification
from .permissions import CanManageShopHours, CanVerifyShops, CanViewShopFollowers, HasShopPermission
from .serializers import (
    ShopFollowerSerializer,
    ShopHoursSerializer,
    ShopLocationSerializer,
    ShopMinimalSerializer,
    ShopSerializer,
    ShopSettingsSerializer,
    ShopVerificationSerializer,
)
from .services.hours_service import HoursService
from .services.shop_service import ShopService
from .services.shop_visibility import ShopVisibilityService
from .services.verification_service import VerificationService


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


@document_api_viewset(
    summary="Shop",
    description="API endpoints for managing shops, their settings, hours, and verifications",
    tags=["Shops"],
)
class ShopViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing shops.
    """

    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [permissions.IsAuthenticated, HasShopPermission]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ShopFilter
    search_fields = ["name", "description", "username"]
    ordering_fields = ["name", "created_at", "is_featured"]
    ordering = ["-is_featured", "name"]

    def get_queryset(self):
        user = self.request.user

        # For customers, only return active and verified shops in their city
        if user.user_type == "customer":
            queryset = Shop.objects.filter(is_active=True, is_verified=True)

            # Apply city filter if customer has a city set and there's no explicit city filter
            city_filter = self.request.query_params.get("city")
            if not city_filter and hasattr(user, "profile") and user.profile.city:
                queryset = queryset.filter(location__city=user.profile.city)

            return queryset

        # For company users, return shops belonging to their company
        elif user.user_type == "employee" and hasattr(user, "company"):
            return Shop.objects.filter(company=user.company)

        # For Queue Me admins and employees, return all shops
        elif user.user_type == "admin":
            return Shop.objects.all()

        # Default - Return shops user has permission to view
        return ShopService.get_user_shops(user)

    def get_serializer_class(self):
        if self.action == "list":
            return ShopMinimalSerializer
        return ShopSerializer

    @document_api_endpoint(
        summary="Create a new shop",
        description="Create a new shop with default working hours",
        responses={
            201: "Created - Shop created successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission to create shops",
        },
        tags=["Shops"],
    )
    def perform_create(self, serializer):
        # unused_unused_company = self.request.data.get("company")
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        # Check if user has permission to create shop for this company
        if not PermissionResolver.has_permission(self.request.user, "shop", "add"):
            raise PermissionDenied(_("You do not have permission to create shops."))

        shop = serializer.save()

        # Create default working hours
        HoursService.create_default_hours(shop.id)

    @document_api_endpoint(
        summary="Request shop verification",
        description="Submit a verification request for a shop",
        responses={
            201: "Created - Verification request submitted successfully",
            400: "Bad Request - Verification already pending",
            403: "Forbidden - User doesn't have permission to request verification",
            404: "Not Found - Shop not found",
        },
        path_params=[{"name": "pk", "description": "Shop ID", "type": "integer"}],
        tags=["Shops", "Verification"],
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def request_verification(self, request, pk=None):
        """
        Request verification for a shop.
        """
        shop = self.get_object()

        # Check if user has permission to request verification
        if (
            request.user != shop.manager
            and not hasattr(request.user, "company")
            and request.user.company != shop.company
        ):
            raise PermissionDenied(
                _("Only shop manager or company admin can request verification.")
            )

        # Check if verification is already in progress
        pending_verification = ShopVerification.objects.filter(shop=shop, status="pending").exists()
        if pending_verification:
            raise ValidationError(_("Verification request is already pending."))

        # Create verification request
        documents = request.data.get("documents", [])
        verification = VerificationService.request_verification(shop.id, documents)

        return Response(
            ShopVerificationSerializer(verification).data,
            status=status.HTTP_201_CREATED,
        )

    @document_api_endpoint(
        summary="Get shop hours",
        description="Retrieve the operating hours for a shop",
        responses={
            200: "Success - Returns shop hours",
            404: "Not Found - Shop not found",
        },
        path_params=[{"name": "pk", "description": "Shop ID", "type": "integer"}],
        tags=["Shops", "Hours"],
    )
    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def hours(self, request, pk=None):
        """
        Get shop hours.
        """
        shop = self.get_object()
        hours = ShopHours.objects.filter(shop=shop)
        serializer = ShopHoursSerializer(hours, many=True)
        return Response(serializer.data)

    @document_api_endpoint(
        summary="Get shop settings",
        description="Retrieve the settings for a shop",
        responses={
            200: "Success - Returns shop settings",
            404: "Not Found - Shop not found",
        },
        path_params=[{"name": "pk", "description": "Shop ID", "type": "integer"}],
        tags=["Shops", "Settings"],
    )
    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def settings(self, request, pk=None):
        """
        Get shop settings.
        """
        shop = self.get_object()
        settings, created = ShopSettings.objects.get_or_create(shop=shop)
        serializer = ShopSettingsSerializer(settings)
        return Response(serializer.data)

    @document_api_endpoint(
        summary="Update shop settings",
        description="Update the settings for a shop",
        responses={
            200: "Success - Settings updated successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Shop not found",
        },
        path_params=[{"name": "pk", "description": "Shop ID", "type": "integer"}],
        tags=["Shops", "Settings"],
    )
    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[permissions.IsAuthenticated, HasShopPermission],
    )
    def update_settings(self, request, pk=None):
        """
        Update shop settings.
        """
        shop = self.get_object()
        settings, created = ShopSettings.objects.get_or_create(shop=shop)
        serializer = ShopSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @document_api_endpoint(
        summary="Get shop statistics",
        description="Retrieve statistical data about a shop including bookings, services, and specialists",
        responses={
            200: "Success - Returns shop statistics",
            404: "Not Found - Shop not found",
        },
        path_params=[{"name": "pk", "description": "Shop ID", "type": "integer"}],
        tags=["Shops", "Statistics"],
    )
    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def statistics(self, request, pk=None):
        """
        Get shop statistics.
        """
        shop = self.get_object()

        # Get today's date
        from django.utils import timezone

        from apps.bookingapp.models import Appointment
        from apps.queueapp.models import QueueTicket

        today = timezone.now().date()

        # Get statistics
        stats = {
            "total_bookings": Appointment.objects.filter(shop=shop).count(),
            "today_bookings": Appointment.objects.filter(shop=shop, start_time__date=today).count(),
            "upcoming_bookings": Appointment.objects.filter(
                shop=shop,
                start_time__gte=timezone.now(),
                status__in=["scheduled", "confirmed"],
            ).count(),
            "total_queue_tickets": QueueTicket.objects.filter(queue__shop=shop).count(),
            "today_queue_tickets": QueueTicket.objects.filter(
                queue__shop=shop, join_time__date=today
            ).count(),
            "active_queue_tickets": QueueTicket.objects.filter(
                queue__shop=shop, status__in=["waiting", "called"]
            ).count(),
            "total_services": shop.services.count(),
            "total_specialists": shop.get_specialist_count(),
            "total_followers": shop.followers.count(),
            "avg_rating": shop.get_avg_rating(),
        }

        # Get booking breakdown by day of week
        day_of_week_mapping = {
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday",
        }

        from django.db.models.functions import ExtractWeekDay

        bookings_by_day = (
            Appointment.objects.filter(shop=shop)
            .annotate(weekday=ExtractWeekDay("start_time"))
            .values("weekday")
            .annotate(count=Count("id"))
            .order_by("weekday")
        )

        stats["bookings_by_day"] = {
            day_of_week_mapping[item["weekday"] - 1]: item["count"] for item in bookings_by_day
        }

        # Get top services
        top_services = shop.services.annotate(booking_count=Count("appointments")).order_by(
            "-booking_count"
        )[:5]

        stats["top_services"] = [
            {
                "id": service.id,
                "name": service.name,
                "booking_count": service.booking_count,
            }
            for service in top_services
        ]

        # Get top specialists
        from apps.specialistsapp.models import Specialist

        top_specialists = (
            Specialist.objects.filter(employee__shop=shop)
            .annotate(booking_count=Count("appointments"))
            .order_by("-booking_count")[:5]
        )

        stats["top_specialists"] = [
            {
                "id": specialist.id,
                "name": f"{specialist.employee.first_name} {specialist.employee.last_name}",
                "booking_count": specialist.booking_count,
            }
            for specialist in top_specialists
        ]

        return Response(stats)


@document_api_viewset(
    summary="Shop Hours",
    description="API endpoints for managing shop operating hours",
    tags=["Shops", "Hours"],
)
class ShopHoursViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing shop hours.
    """

    queryset = ShopHours.objects.all()
    serializer_class = ShopHoursSerializer
    permission_classes = [permissions.IsAuthenticated, HasShopPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ShopHoursFilter

    @document_api_endpoint(
        summary="Create shop hours",
        description="Create new operating hours for a shop",
        responses={
            201: "Created - Hours created successfully",
            400: "Bad Request - Hours already exist for this day",
            403: "Forbidden - User doesn't have permission",
        },
        tags=["Shops", "Hours"],
    )
    def perform_create(self, serializer):
        shop = serializer.validated_data.get("shop")
        weekday = serializer.validated_data.get("weekday")

        # Check if hour already exists for this day
        existing_hour = ShopHours.objects.filter(shop=shop, weekday=weekday).first()
        if existing_hour:
            raise ValidationError(
                _("Shop hours for this day already exist. Please update existing hours.")
            )

        serializer.save()


@document_api_endpoint(
    summary="List and create shop hours",
    description="Retrieve all hours for a shop or create new hours",
    responses={
        200: "Success - Returns shop hours",
        201: "Created - Hours created successfully",
        400: "Bad Request - Hours already exist for this day",
        403: "Forbidden - User doesn't have permission",
        404: "Not Found - Shop not found",
    },
    path_params=[{"name": "shop_id", "description": "Shop ID", "type": "integer"}],
    tags=["Shops", "Hours"],
)
class ShopHoursListView(generics.ListCreateAPIView):
    """
    API endpoint for listing and creating shop hours for a specific shop.
    """

    serializer_class = ShopHoursSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageShopHours]

    def get_queryset(self):
        shop_id = self.kwargs.get("shop_id")
        return ShopHours.objects.filter(shop_id=shop_id).order_by("weekday")

    def perform_create(self, serializer):
        shop_id = self.kwargs.get("shop_id")
        weekday = serializer.validated_data.get("weekday")

        # Check if hour already exists for this day
        existing_hour = ShopHours.objects.filter(shop_id=shop_id, weekday=weekday).first()
        if existing_hour:
            raise ValidationError(
                _("Shop hours for this day already exist. Please update existing hours.")
            )

        serializer.save(shop_id=shop_id)


@document_api_viewset(
    summary="Shop Follower",
    description="API endpoints for managing shop followers",
    tags=["Shops", "Followers"],
)
class FollowerViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing shop followers.
    """

    queryset = ShopFollower.objects.all()
    serializer_class = ShopFollowerSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ShopFollowerFilter

    def get_queryset(self):
        user = self.request.user

        # Customers can only see their own follows
        if user.user_type == "customer":
            return ShopFollower.objects.filter(customer=user)

        # Shop managers and company users can see their shop followers
        if user.user_type == "employee":
            pass

            shop_ids = [shop.id for shop in ShopService.get_user_shops(user)]
            return ShopFollower.objects.filter(shop_id__in=shop_ids)

        # Admins can see all
        return ShopFollower.objects.all()

    @document_api_endpoint(
        summary="Create shop follower",
        description="Follow a shop as a customer",
        responses={
            201: "Created - Now following the shop",
            400: "Bad Request - Already following this shop",
            403: "Forbidden - Only customers can follow shops",
        },
        tags=["Shops", "Followers"],
    )
    def perform_create(self, serializer):
        # Only allow customers to follow shops
        if self.request.user.user_type != "customer":
            raise PermissionDenied(_("Only customers can follow shops."))

        shop = serializer.validated_data.get("shop")

        # Check if customer already follows this shop
        existing_follow = ShopFollower.objects.filter(shop=shop, customer=self.request.user).first()

        if existing_follow:
            raise ValidationError(_("You are already following this shop."))

        serializer.save(customer=self.request.user)


@document_api_endpoint(
    summary="List shop followers",
    description="Retrieve all followers for a specific shop",
    responses={
        200: "Success - Returns list of followers",
        403: "Forbidden - User doesn't have permission to view followers",
        404: "Not Found - Shop not found",
    },
    path_params=[{"name": "shop_id", "description": "Shop ID", "type": "integer"}],
    tags=["Shops", "Followers"],
)
class ShopFollowersListView(generics.ListAPIView):
    """
    API endpoint for listing followers of a specific shop.
    """

    serializer_class = ShopFollowerSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewShopFollowers]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        shop_id = self.kwargs.get("shop_id")
        return ShopFollower.objects.filter(shop_id=shop_id).order_by("-created_at")


@document_api_viewset(
    summary="Shop Location",
    description="API endpoints for retrieving shop locations",
    tags=["Shops", "Locations"],
)
class ShopLocationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for shop locations.
    """

    queryset = Shop.objects.filter(is_active=True, is_verified=True)
    serializer_class = ShopLocationSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Shop.objects.filter(is_active=True, is_verified=True)

        # Filter by city if provided
        city = self.request.query_params.get("city")
        if city:
            queryset = queryset.filter(location__city__iexact=city)

        # Filter by category if provided
        category_id = self.request.query_params.get("category_id")
        if category_id:
            queryset = queryset.filter(services__category__id=category_id).distinct()

        return queryset


@document_api_viewset(
    summary="Shop Settings",
    description="API endpoints for managing shop settings",
    tags=["Shops", "Settings"],
)
class ShopSettingsViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing shop settings.
    """

    queryset = ShopSettings.objects.all()
    serializer_class = ShopSettingsSerializer
    permission_classes = [permissions.IsAuthenticated, HasShopPermission]

    def get_queryset(self):
        user = self.request.user

        # Shop managers and company users can see their shop settings
        if user.user_type == "employee":
            pass

            shop_ids = [shop.id for shop in ShopService.get_user_shops(user)]
            return ShopSettings.objects.filter(shop_id__in=shop_ids)

        # Admins can see all
        if user.user_type == "admin":
            return ShopSettings.objects.all()

        # Customers can't see settings
        return ShopSettings.objects.none()


@document_api_viewset(
    summary="Shop Verification",
    description="API endpoints for managing shop verification requests",
    tags=["Shops", "Verification"],
)
class ShopVerificationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing shop verifications.
    """

    queryset = ShopVerification.objects.all()
    serializer_class = ShopVerificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ShopVerificationFilter

    def get_queryset(self):
        user = self.request.user

        # Shop managers and company users can see their shop verifications
        if user.user_type == "employee":
            pass

            shop_ids = [shop.id for shop in ShopService.get_user_shops(user)]
            return ShopVerification.objects.filter(shop_id__in=shop_ids)

        # Admins can see all
        if user.user_type == "admin":
            return ShopVerification.objects.all()

        # Customers can't see verifications
        return ShopVerification.objects.none()

    @document_api_endpoint(
        summary="Approve shop verification",
        description="Approve a pending shop verification request",
        responses={
            200: "Success - Verification approved successfully",
            400: "Bad Request - Only pending verifications can be approved",
            403: "Forbidden - User doesn't have permission to verify shops",
            404: "Not Found - Verification not found",
        },
        path_params=[{"name": "pk", "description": "Verification ID", "type": "integer"}],
        tags=["Shops", "Verification", "Admin"],
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, CanVerifyShops],
    )
    def approve(self, request, pk=None):
        """
        Approve shop verification.
        """
        verification = self.get_object()

        if verification.status != "pending":
            raise ValidationError(_("Only pending verifications can be approved."))

        VerificationService.approve_verification(verification.id, request.user.id)

        return Response({"status": "success", "message": _("Verification approved successfully.")})

    @document_api_endpoint(
        summary="Reject shop verification",
        description="Reject a pending shop verification request with a reason",
        responses={
            200: "Success - Verification rejected successfully",
            400: "Bad Request - Only pending verifications can be rejected or reason required",
            403: "Forbidden - User doesn't have permission to verify shops",
            404: "Not Found - Verification not found",
        },
        path_params=[{"name": "pk", "description": "Verification ID", "type": "integer"}],
        tags=["Shops", "Verification", "Admin"],
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, CanVerifyShops],
    )
    def reject(self, request, pk=None):
        """
        Reject shop verification.
        """
        verification = self.get_object()

        if verification.status != "pending":
            raise ValidationError(_("Only pending verifications can be rejected."))

        reason = request.data.get("reason")
        if not reason:
            raise ValidationError(_("Rejection reason is required."))

        VerificationService.reject_verification(verification.id, request.user.id, reason)

        return Response({"status": "success", "message": _("Verification rejected successfully.")})


@document_api_endpoint(
    summary="Verify shop directly",
    description="Verify a shop directly (admin only)",
    responses={
        200: "Success - Shop verified successfully",
        403: "Forbidden - User doesn't have permission to verify shops",
        404: "Not Found - Shop not found",
    },
    path_params=[{"name": "shop_id", "description": "Shop ID", "type": "integer"}],
    tags=["Shops", "Verification", "Admin"],
)
class VerifyShopView(APIView):
    """
    API endpoint for verifying a shop directly (admin only).
    """

    permission_classes = [permissions.IsAuthenticated, CanVerifyShops]

    def post(self, request, shop_id):
        shop = get_object_or_404(Shop, id=shop_id)

        # Verify shop
        ShopService.verify_shop(shop.id, request.user.id)

        return Response({"status": "success", "message": _("Shop verified successfully.")})


@document_api_endpoint(
    summary="Follow a shop",
    description="Follow a shop as a customer",
    responses={
        200: "Success - Now following the shop or already following",
        403: "Forbidden - Only customers can follow shops",
        404: "Not Found - Shop not found",
    },
    path_params=[{"name": "shop_id", "description": "Shop ID", "type": "integer"}],
    tags=["Shops", "Followers"],
)
class FollowShopView(APIView):
    """
    API endpoint for following a shop.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, shop_id):
        shop = get_object_or_404(Shop, id=shop_id)

        # Only customers can follow shops
        if request.user.user_type != "customer":
            raise PermissionDenied(_("Only customers can follow shops."))

        # Check if customer already follows this shop
        existing_follow = ShopFollower.objects.filter(shop=shop, customer=request.user).first()

        if existing_follow:
            return Response(
                {"status": "info", "message": _("You are already following this shop.")}
            )

        # Create follow relationship
        ShopFollower.objects.create(shop=shop, customer=request.user)

        return Response({"status": "success", "message": _("You are now following this shop.")})


@document_api_endpoint(
    summary="Unfollow a shop",
    description="Unfollow a shop as a customer",
    responses={
        200: "Success - Unfollowed the shop or wasn't following",
        403: "Forbidden - Only customers can unfollow shops",
        404: "Not Found - Shop not found",
    },
    path_params=[{"name": "shop_id", "description": "Shop ID", "type": "integer"}],
    tags=["Shops", "Followers"],
)
class UnfollowShopView(APIView):
    """
    API endpoint for unfollowing a shop.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, shop_id):
        shop = get_object_or_404(Shop, id=shop_id)

        # Only customers can unfollow shops
        if request.user.user_type != "customer":
            raise PermissionDenied(_("Only customers can unfollow shops."))

        # Check if customer follows this shop
        existing_follow = ShopFollower.objects.filter(shop=shop, customer=request.user).first()

        if not existing_follow:
            return Response({"status": "info", "message": _("You are not following this shop.")})

        # Delete follow relationship
        existing_follow.delete()

        return Response({"status": "success", "message": _("You have unfollowed this shop.")})


@document_api_endpoint(
    summary="List nearby shops",
    description="Find shops near a geographical location or in user's city",
    responses={200: "Success - Returns list of nearby shops"},
    query_params=[
        {
            "name": "lat",
            "description": "Latitude coordinate",
            "required": False,
            "type": "number",
        },
        {
            "name": "lng",
            "description": "Longitude coordinate",
            "required": False,
            "type": "number",
        },
        {
            "name": "radius",
            "description": "Search radius in kilometers (default: 10)",
            "required": False,
            "type": "number",
        },
        {
            "name": "category_id",
            "description": "Filter by service category ID",
            "required": False,
            "type": "integer",
        },
    ],
    tags=["Shops", "Locations"],
)
class NearbyShopsView(generics.ListAPIView):
    """
    API endpoint for listing nearby shops.
    """

    serializer_class = ShopSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user

        # Only verified and active shops
        queryset = Shop.objects.filter(is_verified=True, is_active=True)

        # Get customer location
        lat = self.request.query_params.get("lat")
        lng = self.request.query_params.get("lng")

        # Get radius (default 10km)
        radius = float(self.request.query_params.get("radius", 10))

        if lat and lng:
            # Find nearby shops using geo service
            try:
                from apps.geoapp.services.geo_service import GeoService

                shop_ids = GeoService.find_nearby_entities((float(lat), float(lng)), radius, "shop")
                queryset = queryset.filter(id__in=shop_ids)
            except (ValueError, TypeError):
                pass

        # Filter by customer city if location not provided
        elif hasattr(user, "profile") and user.profile.city:
            queryset = queryset.filter(location__city=user.profile.city)

        # Apply category filter if provided
        category_id = self.request.query_params.get("category_id")
        if category_id:
            queryset = queryset.filter(services__category__id=category_id).distinct()

        # Use shop visibility service to sort by relevance
        return ShopVisibilityService.sort_shops_by_relevance(queryset, user)


@document_api_endpoint(
    summary="List top rated shops",
    description="Get top shops based on ratings and bookings, optionally filtered by city or category",
    responses={200: "Success - Returns list of top shops"},
    query_params=[
        {
            "name": "category_id",
            "description": "Filter by service category ID",
            "required": False,
            "type": "integer",
        }
    ],
    tags=["Shops"],
)
class TopShopsView(generics.ListAPIView):
    """
    API endpoint for listing top shops based on ratings and bookings.
    """

    serializer_class = ShopSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # Only verified and active shops
        queryset = Shop.objects.filter(is_verified=True, is_active=True)

        # Get customer city
        user = self.request.user
        city = None

        if hasattr(user, "profile") and user.profile.city:
            city = user.profile.city

        # Filter by city if customer has a city
        if city:
            queryset = queryset.filter(location__city=city)

        # Filter by category if provided
        category_id = self.request.query_params.get("category_id")
        if category_id:
            queryset = queryset.filter(services__category__id=category_id).distinct()

        # Get top shops based on reviews and booking count
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Avg, Case, Count, F, FloatField, Value, When

        shop_type = ContentType.objects.get_for_model(Shop)

        # Get review statistics
        queryset = queryset.annotate(
            review_count=Count(
                Case(When(review__content_type=shop_type, then=1), default=None),
                distinct=True,
            ),
            booking_count=Count("appointments", distinct=True),
            avg_rating=Avg(
                Case(
                    When(review__content_type=shop_type, then=F("review__rating")),
                    default=None,
                    output_field=FloatField(),
                )
            ),
        )

        # Calculate weighted score
        queryset = queryset.annotate(
            weighted_score=Case(
                When(
                    review_count__gt=0,
                    then=F("avg_rating") * 0.6 + (F("booking_count") / Value(10.0)) * 0.4,
                ),
                default=F("booking_count") / Value(10.0),
                output_field=FloatField(),
            )
        )

        # Order by weighted score
        return queryset.order_by("-weighted_score")


@document_api_endpoint(
    summary="List followed shops",
    description="Get all shops followed by the current customer",
    responses={200: "Success - Returns list of followed shops"},
    tags=["Shops", "Followers"],
)
class FollowedShopsView(generics.ListAPIView):
    """
    API endpoint for listing shops followed by the customer.
    """

    serializer_class = ShopSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user

        # Only customers can see followed shops
        if user.user_type != "customer":
            return Shop.objects.none()

        # Get shops followed by the customer
        return Shop.objects.filter(
            followers__customer=user, is_verified=True, is_active=True
        ).order_by("-followers__created_at")
