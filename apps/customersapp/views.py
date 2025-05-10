from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.customersapp.models import (
    Customer,
    FavoriteService,
    FavoriteShop,
    FavoriteSpecialist,
    SavedPaymentMethod,
)
from apps.customersapp.permissions import (
    IsCustomerOrAdmin,
    IsCustomerOwner,
)
from apps.customersapp.serializers import (
    CustomerDetailSerializer,
    CustomerSerializer,
    FavoriteServiceSerializer,
    FavoriteShopSerializer,
    FavoriteSpecialistSerializer,
    SavedPaymentMethodCreateSerializer,
    SavedPaymentMethodSerializer,
)
from apps.customersapp.services.customer_service import CustomerService
from apps.customersapp.services.payment_method_service import PaymentMethodService
from apps.customersapp.services.personalization_engine import PersonalizationEngine


class CustomerViewSet(viewsets.ModelViewSet):
    """
    API endpoint for customer profile management
    """

    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsCustomerOrAdmin]

    def get_queryset(self):
        if self.request.user.user_type == "customer":
            # Customers can only access their own profile
            return Customer.objects.filter(user=self.request.user)

        # Admin/staff can search and filter customers
        queryset = Customer.objects.all()

        # Filter by city if provided
        city = self.request.query_params.get("city", None)
        if city:
            queryset = queryset.filter(city=city)

        # Search by name or phone
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search)
                | models.Q(user__phone_number__icontains=search)
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CustomerDetailSerializer
        return CustomerSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user's profile"""
        if request.user.user_type != "customer":
            return Response(
                {"detail": "Only customers can access this endpoint"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            customer = request.user.customer_profile
            serializer = CustomerDetailSerializer(customer)
            return Response(serializer.data)
        except Customer.DoesNotExist:
            # Create profile if it doesn't exist
            customer = CustomerService.create_customer(request.user)
            serializer = CustomerDetailSerializer(customer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["patch"])
    def update_preferences(self, request):
        """Update customer preferences"""
        if request.user.user_type != "customer":
            return Response(
                {"detail": "Only customers can update preferences"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            customer = request.user.customer_profile
            preferences = customer.preferences

            for key, value in request.data.items():
                if hasattr(preferences, key):
                    setattr(preferences, key, value)

            preferences.save()

            return Response({"detail": "Preferences updated successfully"})
        except Customer.DoesNotExist:
            return Response(
                {"detail": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["get"])
    def recommended_content(self, request):
        """Get personalized recommended content"""
        if request.user.user_type != "customer":
            return Response(
                {"detail": "Only customers can access recommendations"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            customer = request.user.customer_profile

            # Get content type from query params
            content_type = request.query_params.get("type", "all")

            # Use personalization engine to get recommendations
            recommendations = PersonalizationEngine.get_recommendations(
                customer, content_type=content_type
            )

            return Response(recommendations)
        except Customer.DoesNotExist:
            return Response(
                {"detail": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing saved payment methods
    """

    serializer_class = SavedPaymentMethodSerializer
    permission_classes = [IsAuthenticated, IsCustomerOwner]

    def get_queryset(self):
        if self.request.user.user_type != "customer":
            return SavedPaymentMethod.objects.none()

        try:
            customer = self.request.user.customer_profile
            return SavedPaymentMethod.objects.filter(customer=customer)
        except Customer.DoesNotExist:
            return SavedPaymentMethod.objects.none()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SavedPaymentMethodCreateSerializer
        return SavedPaymentMethodSerializer

    def create(self, request, *args, **kwargs):
        """Create a new payment method with Moyasar tokenization"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            customer = request.user.customer_profile

            # Use payment service to validate and create payment method
            payment_method = PaymentMethodService.create_payment_method(
                customer=customer, **serializer.validated_data
            )

            response_serializer = SavedPaymentMethodSerializer(payment_method)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Customer.DoesNotExist:
            return Response(
                {"detail": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        """Set a payment method as default"""
        try:
            payment_method = self.get_object()
            PaymentMethodService.set_as_default(payment_method)

            return Response({"detail": "Payment method set as default"})
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FavoritesViewSet(viewsets.GenericViewSet):
    """
    API endpoint for managing customer favorites (shops, specialists, services)
    """

    permission_classes = [IsAuthenticated]

    def get_customer(self):
        """Helper to get customer profile or raise exception"""
        if self.request.user.user_type != "customer":
            raise ValueError("Only customers can access favorites")

        try:
            return self.request.user.customer_profile
        except Customer.DoesNotExist:
            raise ValueError("Customer profile not found")

    @action(detail=False, methods=["get"])
    def shops(self, request):
        """Get customer's favorite shops"""
        try:
            customer = self.get_customer()
            favorites = FavoriteShop.objects.filter(customer=customer)
            serializer = FavoriteShopSerializer(favorites, many=True)
            return Response(serializer.data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=["post"])
    def add_shop(self, request):
        """Add a shop to favorites"""
        try:
            customer = self.get_customer()
            shop_id = request.data.get("shop_id")

            if not shop_id:
                return Response(
                    {"detail": "shop_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Import here to avoid circular imports
            from apps.shopapp.models import Shop

            shop = get_object_or_404(Shop, id=shop_id)

            # Create if not exists
            favorite, created = FavoriteShop.objects.get_or_create(
                customer=customer, shop=shop
            )

            if created:
                return Response(
                    {"detail": "Shop added to favorites"},
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {"detail": "Shop already in favorites"}, status=status.HTTP_200_OK
                )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=["post"])
    def remove_shop(self, request):
        """Remove a shop from favorites"""
        try:
            customer = self.get_customer()
            shop_id = request.data.get("shop_id")

            if not shop_id:
                return Response(
                    {"detail": "shop_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Delete if exists
            result = FavoriteShop.objects.filter(
                customer=customer, shop_id=shop_id
            ).delete()

            if result[0] > 0:
                return Response(
                    {"detail": "Shop removed from favorites"}, status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"detail": "Shop not found in favorites"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=["get"])
    def specialists(self, request):
        """Get customer's favorite specialists"""
        try:
            customer = self.get_customer()
            favorites = FavoriteSpecialist.objects.filter(customer=customer)
            serializer = FavoriteSpecialistSerializer(favorites, many=True)
            return Response(serializer.data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=["post"])
    def add_specialist(self, request):
        """Add a specialist to favorites"""
        try:
            customer = self.get_customer()
            specialist_id = request.data.get("specialist_id")

            if not specialist_id:
                return Response(
                    {"detail": "specialist_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Import here to avoid circular imports
            from apps.specialistsapp.models import Specialist

            specialist = get_object_or_404(Specialist, id=specialist_id)

            # Create if not exists
            favorite, created = FavoriteSpecialist.objects.get_or_create(
                customer=customer, specialist=specialist
            )

            if created:
                return Response(
                    {"detail": "Specialist added to favorites"},
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {"detail": "Specialist already in favorites"},
                    status=status.HTTP_200_OK,
                )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=["post"])
    def remove_specialist(self, request):
        """Remove a specialist from favorites"""
        try:
            customer = self.get_customer()
            specialist_id = request.data.get("specialist_id")

            if not specialist_id:
                return Response(
                    {"detail": "specialist_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Delete if exists
            result = FavoriteSpecialist.objects.filter(
                customer=customer, specialist_id=specialist_id
            ).delete()

            if result[0] > 0:
                return Response(
                    {"detail": "Specialist removed from favorites"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"detail": "Specialist not found in favorites"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=["get"])
    def services(self, request):
        """Get customer's favorite services"""
        try:
            customer = self.get_customer()
            favorites = FavoriteService.objects.filter(customer=customer)
            serializer = FavoriteServiceSerializer(favorites, many=True)
            return Response(serializer.data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=["post"])
    def add_service(self, request):
        """Add a service to favorites"""
        try:
            customer = self.get_customer()
            service_id = request.data.get("service_id")

            if not service_id:
                return Response(
                    {"detail": "service_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Import here to avoid circular imports
            from apps.serviceapp.models import Service

            service = get_object_or_404(Service, id=service_id)

            # Create if not exists
            favorite, created = FavoriteService.objects.get_or_create(
                customer=customer, service=service
            )

            if created:
                return Response(
                    {"detail": "Service added to favorites"},
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {"detail": "Service already in favorites"},
                    status=status.HTTP_200_OK,
                )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=["post"])
    def remove_service(self, request):
        """Remove a service from favorites"""
        try:
            customer = self.get_customer()
            service_id = request.data.get("service_id")

            if not service_id:
                return Response(
                    {"detail": "service_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Delete if exists
            result = FavoriteService.objects.filter(
                customer=customer, service_id=service_id
            ).delete()

            if result[0] > 0:
                return Response(
                    {"detail": "Service removed from favorites"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"detail": "Service not found in favorites"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
