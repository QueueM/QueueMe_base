"""
Customers app views for QueueMe platform
Handles endpoints related to customer profiles, payment methods, and favorites.
"""

from django.db import models
from django.shortcuts import get_object_or_404
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
from apps.customersapp.permissions import IsCustomerOrAdmin, IsCustomerOwner
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

    Provides CRUD operations for customer profiles with different
    permissions for customers vs. administrators.

    Endpoints:
    - GET /api/customers/ - List customers (admins can see all, customers see only their own)
    - POST /api/customers/ - Create a customer profile
    - GET /api/customers/{id}/ - Get a specific customer profile
    - PUT/PATCH /api/customers/{id}/ - Update a customer profile
    - DELETE /api/customers/{id}/ - Delete a customer profile
    - GET /api/customers/me/ - Get current user's profile
    - PATCH /api/customers/update_preferences/ - Update customer preferences
    - GET /api/customers/recommended_content/ - Get personalized recommendations

    Permissions:
    - Customer users can only access and modify their own profiles
    - Admin users can access and modify all customer profiles

    Filtering (admin only):
    - city: Filter by city
    - search: Search by name or phone number
    """

    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsCustomerOrAdmin]

    def get_queryset(self):
        """
        Filter customers based on user type and query parameters

        - Customers can only access their own profile
        - Admins can access all profiles with optional filtering

        Returns:
            QuerySet: Filtered queryset of customers
        """
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
        """
        Use appropriate serializer based on action

        Returns detailed serializer for retrieving a specific profile,
        standard serializer for other actions.

        Returns:
            Serializer class: The appropriate serializer
        """
        if self.action == "retrieve":
            return CustomerDetailSerializer
        return CustomerSerializer

    def perform_create(self, serializer):
        """
        Set the user when creating a customer profile

        Args:
            serializer: The customer serializer instance
        """
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """
        Get current user's profile

        Returns the customer profile for the authenticated user.
        If the profile doesn't exist, it creates one automatically.

        Returns:
            Response: Customer profile data

        Status codes:
            200: Profile retrieved successfully
            201: Profile created successfully
            403: User is not a customer
        """
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
        """
        Update customer preferences

        Updates specific preferences for the customer such as:
        - Notification settings
        - Privacy settings
        - Display preferences
        - Language/locale preferences

        Request body:
            Key-value pairs of preferences to update

        Returns:
            Response: Success message

        Status codes:
            200: Preferences updated successfully
            403: User is not a customer
            404: Customer profile not found
        """
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
        """
        Get personalized recommended content

        Returns personalized recommendations based on the customer's
        browsing history, preferences, and past bookings.

        Query parameters:
            type (optional): Type of content to recommend
                  (all, shops, specialists, services)

        Returns:
            Response: JSON object with recommended content

        Status codes:
            200: Recommendations retrieved successfully
            403: User is not a customer
            404: Customer profile not found
        """
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

    Allows customers to manage their saved payment methods for future bookings.
    Integrates with Moyasar payment gateway for tokenization and secure storage.

    Endpoints:
    - GET /api/payment-methods/ - List saved payment methods
    - POST /api/payment-methods/ - Add a new payment method
    - GET /api/payment-methods/{id}/ - Get a specific payment method
    - PUT/PATCH /api/payment-methods/{id}/ - Update a payment method
    - DELETE /api/payment-methods/{id}/ - Delete a payment method
    - POST /api/payment-methods/{id}/set_default/ - Set a payment method as default

    Permissions:
    - User must be authenticated as a customer
    - Customers can only access their own payment methods
    """

    queryset = SavedPaymentMethod.objects.all()
    serializer_class = SavedPaymentMethodSerializer
    permission_classes = [IsAuthenticated, IsCustomerOwner]

    def get_queryset(self):
        """
        Filter payment methods to show only those belonging to the customer

        Returns:
            QuerySet: Filtered queryset of payment methods
        """
        if self.request.user.user_type != "customer":
            return SavedPaymentMethod.objects.none()

        try:
            customer = self.request.user.customer_profile
            return SavedPaymentMethod.objects.filter(customer=customer)
        except Customer.DoesNotExist:
            return SavedPaymentMethod.objects.none()

    def get_serializer_class(self):
        """
        Use appropriate serializer based on action

        Create/update operations use a different serializer that handles
        card tokenization and validation.

        Returns:
            Serializer class: The appropriate serializer
        """
        if self.action in ["create", "update", "partial_update"]:
            return SavedPaymentMethodCreateSerializer
        return SavedPaymentMethodSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new payment method with Moyasar tokenization

        Validates payment information and stores a tokenized version of the
        card for future use. The actual card details are not stored in the database.

        Request body:
            {
                "card_number": "4111111111111111", (required - not stored)
                "cardholder_name": "John Doe", (required)
                "expiry_month": "12", (required)
                "expiry_year": "2025", (required)
                "cvc": "123", (required - not stored)
                "is_default": true/false (optional)
            }

        Returns:
            Response: Created payment method object

        Status codes:
            201: Payment method created successfully
            400: Invalid payment information
            404: Customer profile not found
        """
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
        """
        Set a payment method as default

        Marks the specified payment method as the default for future payments
        and removes the default status from all other payment methods.

        Returns:
            Response: Success message

        Status codes:
            200: Payment method set as default
            400: Error setting as default
        """
        try:
            payment_method = self.get_object()
            PaymentMethodService.set_as_default(payment_method)

            return Response({"detail": "Payment method set as default"})
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FavoritesViewSet(viewsets.GenericViewSet):
    """
    API endpoint for managing customer favorites (shops, specialists, services)

    Allows customers to save and manage their favorite entities for quick access.

    Endpoints:
    - GET /api/favorites/shops/ - Get favorite shops
    - POST /api/favorites/add_shop/ - Add a shop to favorites
    - POST /api/favorites/remove_shop/ - Remove a shop from favorites
    - GET /api/favorites/specialists/ - Get favorite specialists
    - POST /api/favorites/add_specialist/ - Add a specialist to favorites
    - POST /api/favorites/remove_specialist/ - Remove a specialist from favorites
    - GET /api/favorites/services/ - Get favorite services
    - POST /api/favorites/add_service/ - Add a service to favorites
    - POST /api/favorites/remove_service/ - Remove a service from favorites

    Permissions:
    - User must be authenticated as a customer
    """

    queryset = Customer.objects.all()
    permission_classes = [IsAuthenticated]

    def get_customer(self):
        """
        Helper to get customer profile or raise exception

        Returns:
            Customer: The customer profile

        Raises:
            ValueError: If user is not a customer or profile not found
        """
        if self.request.user.user_type != "customer":
            raise ValueError("Only customers can access favorites")

        try:
            return self.request.user.customer_profile
        except Customer.DoesNotExist:
            raise ValueError("Customer profile not found")

    @action(detail=False, methods=["get"])
    def shops(self, request):
        """
        Get customer's favorite shops

        Returns a list of shops that the customer has marked as favorites.

        Returns:
            Response: List of favorite shops

        Status codes:
            200: Shops retrieved successfully
            403: User is not a customer or profile not found
        """
        try:
            customer = self.get_customer()
            favorites = FavoriteShop.objects.filter(customer=customer)
            serializer = FavoriteShopSerializer(favorites, many=True)
            return Response(serializer.data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=["post"])
    def add_shop(self, request):
        """
        Add a shop to favorites

        Adds the specified shop to the customer's favorites.
        If the shop is already in favorites, returns success without duplication.

        Request body:
            {
                "shop_id": "uuid" (required)
            }

        Returns:
            Response: Success message

        Status codes:
            201: Shop added to favorites
            200: Shop already in favorites
            400: Missing shop_id parameter
            403: User is not a customer or profile not found
            404: Shop not found
        """
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
        """
        Remove a shop from favorites

        Removes the specified shop from the customer's favorites.

        Request body:
            {
                "shop_id": "uuid" (required)
            }

        Returns:
            Response: Success message

        Status codes:
            200: Shop removed from favorites
            400: Missing shop_id parameter
            403: User is not a customer or profile not found
            404: Shop not found in favorites
        """
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
        """
        Get customer's favorite specialists

        Returns a list of specialists that the customer has marked as favorites.

        Returns:
            Response: List of favorite specialists

        Status codes:
            200: Specialists retrieved successfully
            403: User is not a customer or profile not found
        """
        try:
            customer = self.get_customer()
            favorites = FavoriteSpecialist.objects.filter(customer=customer)
            serializer = FavoriteSpecialistSerializer(favorites, many=True)
            return Response(serializer.data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=["post"])
    def add_specialist(self, request):
        """
        Add a specialist to favorites

        Adds the specified specialist to the customer's favorites.
        If the specialist is already in favorites, returns success without duplication.

        Request body:
            {
                "specialist_id": "uuid" (required)
            }

        Returns:
            Response: Success message

        Status codes:
            201: Specialist added to favorites
            200: Specialist already in favorites
            400: Missing specialist_id parameter
            403: User is not a customer or profile not found
            404: Specialist not found
        """
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
        """
        Remove a specialist from favorites

        Removes the specified specialist from the customer's favorites.

        Request body:
            {
                "specialist_id": "uuid" (required)
            }

        Returns:
            Response: Success message

        Status codes:
            200: Specialist removed from favorites
            400: Missing specialist_id parameter
            403: User is not a customer or profile not found
            404: Specialist not found in favorites
        """
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
        """
        Get customer's favorite services

        Returns a list of services that the customer has marked as favorites.

        Returns:
            Response: List of favorite services

        Status codes:
            200: Services retrieved successfully
            403: User is not a customer or profile not found
        """
        try:
            customer = self.get_customer()
            favorites = FavoriteService.objects.filter(customer=customer)
            serializer = FavoriteServiceSerializer(favorites, many=True)
            return Response(serializer.data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=["post"])
    def add_service(self, request):
        """
        Add a service to favorites

        Adds the specified service to the customer's favorites.
        If the service is already in favorites, returns success without duplication.

        Request body:
            {
                "service_id": "uuid" (required)
            }

        Returns:
            Response: Success message

        Status codes:
            201: Service added to favorites
            200: Service already in favorites
            400: Missing service_id parameter
            403: User is not a customer or profile not found
            404: Service not found
        """
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
        """
        Remove a service from favorites

        Removes the specified service from the customer's favorites.

        Request body:
            {
                "service_id": "uuid" (required)
            }

        Returns:
            Response: Success message

        Status codes:
            200: Service removed from favorites
            400: Missing service_id parameter
            403: User is not a customer or profile not found
            404: Service not found in favorites
        """
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
