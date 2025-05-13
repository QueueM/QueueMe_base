"""
Discounts app views for QueueMe platform
Handles endpoints related to service discounts, coupons, promotional campaigns,
and discount calculations for the booking process.
"""

# apps/discountapp/views.py
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.bookingapp.models import Appointment
from apps.categoriesapp.models import Category
from apps.discountapp.models import Coupon, PromotionalCampaign, ServiceDiscount
from apps.discountapp.permissions import (
    CanManageDiscounts,
    IsShopManagerOrAdmin,
    IsShopManagerOrAdminOrReadOnly,
)
from apps.discountapp.serializers import (
    CouponApplySerializer,
    CouponGenerateSerializer,
    CouponSerializer,
    CouponValidateSerializer,
    DiscountCalculationSerializer,
    PromotionalCampaignSerializer,
    ServiceDiscountSerializer,
)
from apps.discountapp.services.coupon_service import CouponService
from apps.discountapp.services.discount_service import DiscountService
from apps.discountapp.services.promotion_service import PromotionService
from apps.serviceapp.models import Service
from apps.shopapp.models import Shop


class ServiceDiscountViewSet(viewsets.ModelViewSet):
    """
    API endpoint for service discounts

    Allows shop managers and administrators to create, retrieve, update,
    and delete discounts applied to specific services or categories.

    Endpoints:
    - GET /api/service-discounts/ - List all discounts (filtered by user permissions)
    - POST /api/service-discounts/ - Create a new service discount
    - GET /api/service-discounts/{id}/ - Get a specific discount
    - PUT/PATCH /api/service-discounts/{id}/ - Update a discount
    - DELETE /api/service-discounts/{id}/ - Delete a discount
    - GET /api/service-discounts/active/ - Get active discounts for a shop/service

    Permissions:
    - Authentication required for all actions
    - Shop managers can manage discounts for their shops
    - Admin users can manage all discounts
    - Regular users can only view discounts
    """

    queryset = ServiceDiscount.objects.all()
    serializer_class = ServiceDiscountSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopManagerOrAdminOrReadOnly]

    def get_queryset(self):
        """
        Filter queryset based on user permissions

        Returns discounts that the user is allowed to see based on their role:
        - Admins see all discounts
        - Shop managers see discounts for their shops
        - Other users don't see any discounts

        Returns:
            QuerySet: Filtered service discounts
        """
        user = self.request.user

        # Queue Me Admin can see all discounts
        if user.is_staff or user.is_superuser:
            return ServiceDiscount.objects.all()

        # Shop manager can see discounts for their shops
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        user_shops = PermissionResolver.get_user_shops(user)

        return ServiceDiscount.objects.filter(shop__in=user_shops)

    def perform_create(self, serializer):
        """
        Create service discount and add services/categories

        Saves the discount and associates it with the specified services
        and categories.

        Args:
            serializer: The service discount serializer instance
        """
        service_ids = self.request.data.get("service_ids", [])
        category_ids = self.request.data.get("category_ids", [])

        discount = serializer.save()

        # Add services if provided
        if service_ids:
            services = Service.objects.filter(id__in=service_ids)
            discount.services.set(services)

        # Add categories if provided
        if category_ids:
            categories = Category.objects.filter(id__in=category_ids)
            discount.categories.set(categories)

    def perform_update(self, serializer):
        """
        Update service discount and update services/categories

        Updates the discount and its associations with services and categories.
        Only updates associations if they are explicitly provided in the request.

        Args:
            serializer: The service discount serializer instance
        """
        service_ids = self.request.data.get("service_ids", None)
        category_ids = self.request.data.get("category_ids", None)

        discount = serializer.save()

        # Update services if provided
        if service_ids is not None:
            services = Service.objects.filter(id__in=service_ids)
            discount.services.set(services)

        # Update categories if provided
        if category_ids is not None:
            categories = Category.objects.filter(id__in=category_ids)
            discount.categories.set(categories)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """
        Get active discounts

        Returns currently active discounts for a specified shop and
        optionally a specific service.

        Query parameters:
            shop_id: ID of the shop (required)
            service_id: ID of the service (optional)

        Returns:
            Response: List of active discounts

        Status codes:
            200: Discounts retrieved successfully
            400: Missing shop_id parameter
            404: Shop or service not found
        """
        shop_id = request.query_params.get("shop_id")
        service_id = request.query_params.get("service_id")

        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shop = get_object_or_404(Shop, id=shop_id)

        # Get active discounts
        if service_id:
            service = get_object_or_404(Service, id=service_id)
            discounts = DiscountService.get_active_discounts(shop, service)
        else:
            discounts = DiscountService.get_active_discounts(shop)

        serializer = self.get_serializer(discounts, many=True)
        return Response(serializer.data)


class CouponViewSet(viewsets.ModelViewSet):
    """
    API endpoint for coupons

    Allows shop managers and administrators to create, retrieve, update,
    delete, and manage coupon codes. Also provides endpoints for customers
    to validate and apply coupons.

    Endpoints:
    - GET /api/coupons/ - List all coupons (filtered by user permissions)
    - POST /api/coupons/ - Create a new coupon
    - GET /api/coupons/{id}/ - Get a specific coupon
    - PUT/PATCH /api/coupons/{id}/ - Update a coupon
    - DELETE /api/coupons/{id}/ - Delete a coupon
    - POST /api/coupons/validate/ - Validate a coupon code
    - POST /api/coupons/apply/ - Apply a coupon to a booking
    - POST /api/coupons/generate/ - Generate one or more coupons
    - GET /api/coupons/available/ - Get available coupons for the current user

    Permissions:
    - Authentication required for all actions
    - Shop managers can manage coupons for their shops
    - Admin users can manage all coupons
    - Regular users can only view coupons and use validation/application endpoints
    """

    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopManagerOrAdminOrReadOnly]

    def get_queryset(self):
        """
        Filter queryset based on user permissions

        Returns coupons that the user is allowed to see based on their role:
        - Admins see all coupons
        - Shop managers see coupons for their shops
        - Other users don't see any coupons

        Returns:
            QuerySet: Filtered coupons
        """
        user = self.request.user

        # Queue Me Admin can see all coupons
        if user.is_staff or user.is_superuser:
            return Coupon.objects.all()

        # Shop manager can see coupons for their shops
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        user_shops = PermissionResolver.get_user_shops(user)

        return Coupon.objects.filter(shop__in=user_shops)

    def perform_create(self, serializer):
        """
        Create coupon and add services/categories

        Saves the coupon and associates it with the specified services
        and categories.

        Args:
            serializer: The coupon serializer instance
        """
        service_ids = self.request.data.get("service_ids", [])
        category_ids = self.request.data.get("category_ids", [])

        coupon = serializer.save()

        # Add services if provided
        if service_ids:
            services = Service.objects.filter(id__in=service_ids)
            coupon.services.set(services)

        # Add categories if provided
        if category_ids:
            categories = Category.objects.filter(id__in=category_ids)
            coupon.categories.set(categories)

    def perform_update(self, serializer):
        """
        Update coupon and update services/categories

        Updates the coupon and its associations with services and categories.
        Only updates associations if they are explicitly provided in the request.

        Args:
            serializer: The coupon serializer instance
        """
        service_ids = self.request.data.get("service_ids", None)
        category_ids = self.request.data.get("category_ids", None)

        coupon = serializer.save()

        # Update services if provided
        if service_ids is not None:
            services = Service.objects.filter(id__in=service_ids)
            coupon.services.set(services)

        # Update categories if provided
        if category_ids is not None:
            categories = Category.objects.filter(id__in=category_ids)
            coupon.categories.set(categories)

    @action(detail=False, methods=["post"])
    def validate(self, request):
        """
        Validate a coupon code

        Checks if a coupon code is valid for the current user, optionally
        for a specific service and amount.

        Request body:
            {
                "code": "COUPON123" (required),
                "service_id": "uuid" (optional),
                "amount": float (optional)
            }

        Returns:
            Response: Validation result with coupon details and discount amount
                {
                    "valid": boolean,
                    "message": "Error message" (only if invalid),
                    "coupon": {...} (only if valid),
                    "discount_amount": float (only if valid and amount provided)
                }

        Status codes:
            200: Validation processed successfully
            400: Invalid request data
        """
        serializer = CouponValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["code"]
        service_id = serializer.validated_data.get("service_id")
        amount = serializer.validated_data.get("amount")

        # Get service if provided
        service = None
        if service_id:
            service = get_object_or_404(Service, id=service_id)

        # Validate coupon
        is_valid, message, coupon = CouponService.validate_coupon(
            code,
            customer=request.user,
            services=[service] if service else None,
            amount=amount,
        )

        if not is_valid:
            return Response({"valid": False, "message": message}, status=status.HTTP_200_OK)

        # Calculate discount if amount is provided
        discount_amount = 0
        if amount and coupon:
            discount_amount = coupon.calculate_discount_amount(amount)

        response_data = {
            "valid": True,
            "coupon": CouponSerializer(coupon).data if coupon else None,
            "discount_amount": discount_amount,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def apply(self, request):
        """
        Apply a coupon to a booking

        Applies a coupon code to a booking, calculating the discount
        and updating the booking's payment information.

        Request body:
            {
                "code": "COUPON123" (required),
                "booking_id": "uuid" (required),
                "amount": float (required)
            }

        Returns:
            Response: Application result with discount and final amounts
                {
                    "success": boolean,
                    "message": "Error message" (only if unsuccessful),
                    "discount_amount": float (only if successful),
                    "final_amount": float (only if successful)
                }

        Status codes:
            200: Coupon applied successfully
            400: Invalid coupon or application failed
            403: User not authorized to apply coupon to this booking
            404: Booking not found
        """
        serializer = CouponApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["code"]
        booking_id = serializer.validated_data["booking_id"]
        amount = serializer.validated_data["amount"]

        # Get booking
        booking = get_object_or_404(Appointment, id=booking_id)

        # Verify booking belongs to current user
        if booking.customer != request.user:
            return Response(
                {"detail": _("You do not have permission to apply coupons to this booking.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Apply coupon
        success, message, discount_amount = CouponService.apply_coupon(
            code, request.user, booking, amount
        )

        if not success:
            return Response(
                {"success": False, "message": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,
                "discount_amount": discount_amount,
                "final_amount": max(0, amount - discount_amount),
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, CanManageDiscounts],
    )
    def generate(self, request):
        """
        Generate one or more coupons

        Creates one or more coupons for a shop with the specified parameters.
        When quantity > 1, generates multiple coupons with unique codes.

        Request body:
            {
                "shop_id": "uuid" (required),
                "name": "Coupon Name" (required),
                "discount_type": "percentage|fixed" (required),
                "value": float (required),
                "start_date": "YYYY-MM-DD" (required),
                "end_date": "YYYY-MM-DD" (required),
                "quantity": integer (optional, default: 1),
                "usage_limit": integer (optional, default: 0),
                "is_single_use": boolean (optional, default: false),
                "apply_to_all_services": boolean (optional, default: false),
                "service_ids": ["uuid", ...] (optional),
                "category_ids": ["uuid", ...] (optional)
            }

        Returns:
            Response: Created coupon(s)
                For single coupon:
                    Coupon object
                For multiple coupons:
                    {
                        "count": integer,
                        "coupons": [Coupon objects]
                    }

        Status codes:
            201: Coupon(s) created successfully
            400: Invalid request data
            403: User not authorized to manage coupons for this shop
            404: Shop not found
        """
        serializer = CouponGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shop_id = serializer.validated_data["shop_id"]
        shop = get_object_or_404(Shop, id=shop_id)

        # Verify user has permission to manage this shop
        user = request.user
        if not (user.is_staff or user.is_superuser):
            from apps.rolesapp.services.permission_resolver import PermissionResolver

            user_shops = PermissionResolver.get_user_shops(user)

            if shop not in user_shops:
                return Response(
                    {"detail": _("You do not have permission to manage coupons for this shop.")},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Extract services and categories
        services = None
        if "service_ids" in serializer.validated_data:
            services = Service.objects.filter(id__in=serializer.validated_data["service_ids"])

        categories = None
        if "category_ids" in serializer.validated_data:
            categories = Category.objects.filter(id__in=serializer.validated_data["category_ids"])

        # Generate coupons
        quantity = serializer.validated_data.get("quantity", 1)

        if quantity == 1:
            # Generate single coupon
            coupon = CouponService.create_coupon(
                shop=shop,
                name=serializer.validated_data["name"],
                discount_type=serializer.validated_data["discount_type"],
                value=serializer.validated_data["value"],
                start_date=serializer.validated_data["start_date"],
                end_date=serializer.validated_data["end_date"],
                usage_limit=serializer.validated_data.get("usage_limit", 0),
                is_single_use=serializer.validated_data.get("is_single_use", False),
                apply_to_all_services=serializer.validated_data.get("apply_to_all_services", False),
                services=services,
                categories=categories,
            )

            return Response(CouponSerializer(coupon).data, status=status.HTTP_201_CREATED)
        else:
            # Generate bulk coupons
            coupons = CouponService.generate_bulk_coupons(
                shop=shop,
                name_template=serializer.validated_data["name"] + " {i}",
                discount_type=serializer.validated_data["discount_type"],
                value=serializer.validated_data["value"],
                start_date=serializer.validated_data["start_date"],
                end_date=serializer.validated_data["end_date"],
                quantity=quantity,
                usage_limit=serializer.validated_data.get("usage_limit", 0),
                is_single_use=serializer.validated_data.get("is_single_use", False),
                apply_to_all_services=serializer.validated_data.get("apply_to_all_services", False),
                services=services,
                categories=categories,
            )

            return Response(
                {
                    "count": len(coupons),
                    "coupons": CouponSerializer(coupons, many=True).data,
                },
                status=status.HTTP_201_CREATED,
            )

    @action(detail=False, methods=["get"])
    def available(self, request):
        """
        Get available coupons for the current user

        Returns coupons that the current user can use for a specified shop
        and optionally for a specific service.

        Query parameters:
            shop_id: ID of the shop (required)
            service_id: ID of the service (optional)

        Returns:
            Response: List of available coupons

        Status codes:
            200: Coupons retrieved successfully
            400: Missing shop_id parameter
            404: Shop or service not found
        """
        shop_id = request.query_params.get("shop_id")
        service_id = request.query_params.get("service_id")

        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shop = get_object_or_404(Shop, id=shop_id)

        # Get services if provided
        services = None
        if service_id:
            service = get_object_or_404(Service, id=service_id)
            services = [service]

        # Get available coupons
        coupons = CouponService.get_available_coupons(
            shop=shop, customer=request.user, services=services
        )

        serializer = self.get_serializer(coupons, many=True)
        return Response(serializer.data)


class PromotionalCampaignViewSet(viewsets.ModelViewSet):
    """
    API endpoint for promotional campaigns

    Allows shop managers and administrators to create, retrieve, update,
    and delete promotional campaigns, which can generate coupons and other
    promotional content automatically.

    Endpoints:
    - GET /api/campaigns/ - List all campaigns (filtered by user permissions)
    - POST /api/campaigns/ - Create a new campaign
    - GET /api/campaigns/{id}/ - Get a specific campaign
    - PUT/PATCH /api/campaigns/{id}/ - Update a campaign
    - DELETE /api/campaigns/{id}/ - Delete a campaign
    - GET /api/campaigns/active/ - Get active campaigns for a shop
    - POST /api/campaigns/create_referral/ - Create or update a referral campaign

    Permissions:
    - Authentication required for all actions
    - Shop managers can manage campaigns for their shops
    - Admin users can manage all campaigns
    """

    queryset = PromotionalCampaign.objects.all()
    serializer_class = PromotionalCampaignSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopManagerOrAdmin]

    def get_queryset(self):
        """
        Filter queryset based on user permissions

        Returns campaigns that the user is allowed to see based on their role:
        - Admins see all campaigns
        - Shop managers see campaigns for their shops
        - Other users don't see any campaigns

        Returns:
            QuerySet: Filtered promotional campaigns
        """
        user = self.request.user

        # Queue Me Admin can see all campaigns
        if user.is_staff or user.is_superuser:
            return PromotionalCampaign.objects.all()

        # Shop manager can see campaigns for their shops
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        user_shops = PermissionResolver.get_user_shops(user)

        return PromotionalCampaign.objects.filter(shop__in=user_shops)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """
        Get active campaigns

        Returns currently active promotional campaigns for a specified shop.

        Query parameters:
            shop_id: ID of the shop (required)

        Returns:
            Response: List of active campaigns

        Status codes:
            200: Campaigns retrieved successfully
            400: Missing shop_id parameter
            404: Shop not found
        """
        shop_id = request.query_params.get("shop_id")

        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shop = get_object_or_404(Shop, id=shop_id)

        # Get active campaigns
        campaigns = PromotionService.get_active_campaigns(shop)

        serializer = self.get_serializer(campaigns, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, CanManageDiscounts],
    )
    @transaction.atomic
    def create_referral(self, request):
        """
        Create or update referral campaign for a shop

        Creates or updates a referral promotional campaign for a shop,
        which generates referral coupons for customers to share.

        Request body:
            {
                "shop_id": "uuid" (required),
                "discount_value": float (optional, default: 10),
                "days_valid": integer (optional, default: 30)
            }

        Returns:
            Response: Created campaign and sample coupon
                {
                    "campaign": Campaign object,
                    "sample_coupon": Coupon object
                }

        Status codes:
            201: Campaign created successfully
            400: Invalid request data
            403: User not authorized to manage campaigns for this shop
            404: Shop not found
        """
        shop_id = request.data.get("shop_id")
        discount_value = request.data.get("discount_value", 10)
        days_valid = request.data.get("days_valid", 30)

        if not shop_id:
            return Response(
                {"detail": _("Shop ID is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shop = get_object_or_404(Shop, id=shop_id)

        # Verify user has permission to manage this shop
        user = request.user
        if not (user.is_staff or user.is_superuser):
            from apps.rolesapp.services.permission_resolver import PermissionResolver

            user_shops = PermissionResolver.get_user_shops(user)

            if shop not in user_shops:
                return Response(
                    {"detail": _("You do not have permission to manage campaigns for this shop.")},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Create referral campaign
        campaign, sample_coupon = PromotionService.create_referral_campaign(
            shop, discount_value=discount_value, days_valid=days_valid
        )

        return Response(
            {
                "campaign": PromotionalCampaignSerializer(campaign).data,
                "sample_coupon": CouponSerializer(sample_coupon).data,
            },
            status=status.HTTP_201_CREATED,
        )


class DiscountCalculationViewSet(viewsets.ViewSet):
    """
    API endpoint for discount calculations

    Provides utilities for calculating discounts on prices based on
    various discount types, promotional campaigns, and coupons.

    Endpoints:
    - POST /api/discount-calculations/calculate/ - Calculate discount for a price

    Permissions:
    - Authentication required for all actions
    """

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    def calculate(self, request):
        """
        Calculate discount for a price

        Calculates the discounted price for a given original price,
        applying discounts from service discounts, coupons, and promotions
        as applicable.

        Request body:
            {
                "shop_id": "uuid" (required),
                "price": float (required),
                "service_id": "uuid" (optional),
                "coupon_code": "CODE123" (optional),
                "combine_discounts": boolean (optional, default: false)
            }

        Returns:
            Response: Discount calculation results

            For combine_discounts=false:
                {
                    "original_price": float,
                    "discounted_price": float,
                    "discount_amount": float,
                    "discount_info": {
                        "type": "service_discount|coupon|promotion",
                        "name": "Discount name",
                        ...
                    }
                }

            For combine_discounts=true:
                {
                    "original_price": float,
                    "discounted_price": float,
                    "total_discount": float,
                    "discount_breakdown": [
                        {
                            "type": "service_discount|coupon|promotion",
                            "name": "Discount name",
                            "amount": float,
                            ...
                        },
                        ...
                    ]
                }

        Status codes:
            200: Calculation performed successfully
            400: Invalid request data
            404: Shop or service not found
        """
        serializer = DiscountCalculationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shop_id = serializer.validated_data["shop_id"]
        price = serializer.validated_data["price"]
        service_id = serializer.validated_data.get("service_id")
        coupon_code = serializer.validated_data.get("coupon_code")
        combine_discounts = serializer.validated_data.get("combine_discounts", False)

        shop = get_object_or_404(Shop, id=shop_id)

        # Get service if provided
        service = None
        if service_id:
            service = get_object_or_404(Service, id=service_id)

        # Calculate discount
        if combine_discounts:
            (
                discounted_price,
                original_price,
                discount_breakdown,
            ) = DiscountService.apply_multiple_discounts(
                price,
                service=service,
                shop=shop,
                customer=request.user,
                coupon_code=coupon_code,
            )

            return Response(
                {
                    "original_price": original_price,
                    "discounted_price": discounted_price,
                    "total_discount": original_price - discounted_price,
                    "discount_breakdown": discount_breakdown,
                }
            )
        else:
            discounted_price, original_price, discount_info = DiscountService.calculate_discount(
                price,
                service=service,
                shop=shop,
                customer=request.user,
                coupon_code=coupon_code,
            )

            return Response(
                {
                    "original_price": original_price,
                    "discounted_price": discounted_price,
                    "discount_amount": original_price - discounted_price,
                    "discount_info": discount_info,
                }
            )
