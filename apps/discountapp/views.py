# apps/discountapp/views.py
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.bookingapp.models import Appointment
from apps.categoriesapp.models import Category
from apps.discountapp.models import (
    Coupon,
    PromotionalCampaign,
    ServiceDiscount,
)
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
    """

    queryset = ServiceDiscount.objects.all()
    serializer_class = ServiceDiscountSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopManagerOrAdminOrReadOnly]

    def get_queryset(self):
        """
        Filter queryset based on user permissions
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
    """

    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopManagerOrAdminOrReadOnly]

    def get_queryset(self):
        """
        Filter queryset based on user permissions
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
            return Response(
                {"valid": False, "message": message}, status=status.HTTP_200_OK
            )

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
                {
                    "detail": _(
                        "You do not have permission to apply coupons to this booking."
                    )
                },
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
                    {
                        "detail": _(
                            "You do not have permission to manage coupons for this shop."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Extract services and categories
        services = None
        if "service_ids" in serializer.validated_data:
            services = Service.objects.filter(
                id__in=serializer.validated_data["service_ids"]
            )

        categories = None
        if "category_ids" in serializer.validated_data:
            categories = Category.objects.filter(
                id__in=serializer.validated_data["category_ids"]
            )

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
                apply_to_all_services=serializer.validated_data.get(
                    "apply_to_all_services", False
                ),
                services=services,
                categories=categories,
            )

            return Response(
                CouponSerializer(coupon).data, status=status.HTTP_201_CREATED
            )
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
                apply_to_all_services=serializer.validated_data.get(
                    "apply_to_all_services", False
                ),
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
    """

    queryset = PromotionalCampaign.objects.all()
    serializer_class = PromotionalCampaignSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopManagerOrAdmin]

    def get_queryset(self):
        """
        Filter queryset based on user permissions
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
                    {
                        "detail": _(
                            "You do not have permission to manage campaigns for this shop."
                        )
                    },
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
    """

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    def calculate(self, request):
        """
        Calculate discount for a price
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
            discounted_price, original_price, discount_breakdown = (
                DiscountService.apply_multiple_discounts(
                    price,
                    service=service,
                    shop=shop,
                    customer=request.user,
                    coupon_code=coupon_code,
                )
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
            discounted_price, original_price, discount_info = (
                DiscountService.calculate_discount(
                    price,
                    service=service,
                    shop=shop,
                    customer=request.user,
                    coupon_code=coupon_code,
                )
            )

            return Response(
                {
                    "original_price": original_price,
                    "discounted_price": discounted_price,
                    "discount_amount": original_price - discounted_price,
                    "discount_info": discount_info,
                }
            )
