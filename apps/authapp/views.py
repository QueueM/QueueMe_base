"""
Authentication Views Module for QueueMe Backend

This module provides API endpoints for user authentication, OTP verification,
token management, and profile operations. It implements secure authentication
flows specifically designed for Saudi phone numbers and OTP verification.
"""

import logging

from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from api.documentation.api_doc_decorators import (
    document_api_endpoint,
    document_api_viewset,
)
from apps.authapp.models import User
from apps.authapp.serializers import (
    ChangeLanguageSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    TokenRefreshSerializer,
    UserProfileSerializer,
    UserSerializer,
)
from apps.authapp.services.otp_service import OTPService
from apps.authapp.services.security_service import SecurityService
from apps.authapp.services.token_service import TokenService

# Configure logging
logger = logging.getLogger(__name__)


@document_api_viewset(
    summary="Authentication",
    description="API endpoints for handling user authentication including OTP, login, and token operations",
    tags=["Authentication"],
)
class AuthViewSet(viewsets.GenericViewSet):
    """
    Authentication viewset handling OTP, login, and token operations.

    This viewset provides endpoints for:
    - Requesting OTP codes for phone verification
    - Verifying OTP codes and authenticating users
    - Refreshing authentication tokens
    - Managing user profiles and settings

    All endpoints implement proper error handling, rate limiting,
    and security measures to prevent abuse.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    @document_api_endpoint(
        summary="Request OTP",
        description="Request a one-time password to be sent to the provided phone number",
        request_body=OTPRequestSerializer,
        responses={
            200: "OTP sent successfully",
            400: "Invalid phone number format",
            429: "Too many requests, please try again later",
        },
    )
    @action(detail=False, methods=["post"], url_path="request-otp")
    def request_otp(self, request: Request) -> Response:
        """
        Request a one-time password to be sent to the provided phone number.

        This endpoint:
        1. Validates the phone number format (must be Saudi phone number)
        2. Generates a new OTP code
        3. Sends the OTP via SMS
        4. Implements rate limiting to prevent abuse

        Args:
            request: HTTP request with phone_number in request data

        Returns:
            Response with success status and message

        Raises:
            ValidationError: If phone number format is invalid
            Throttled: If too many requests from same IP/phone
        """
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]

        # Check rate limiting
        if SecurityService.is_rate_limited(
            identifier=phone_number,
            action="otp_request",
            max_attempts=5,
            window_minutes=15,
        ):
            logger.warning(f"Rate limit exceeded for OTP request: {phone_number}")
            return Response(
                {"detail": _("Too many OTP requests. Please try again later.")},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Generate and send OTP
        try:
            OTPService.generate_and_send_otp(phone_number)
            logger.info(f"OTP sent successfully to {phone_number}")

            return Response(
                {"detail": _("OTP sent successfully")}, status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Failed to send OTP: {str(e)}")
            return Response(
                {"detail": _("Failed to send OTP. Please try again later.")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @document_api_endpoint(
        summary="Verify OTP",
        description="Verify OTP code and authenticate user",
        request_body=OTPVerifySerializer,
        responses={
            200: "OTP verified successfully, returns authentication tokens",
            400: "Invalid OTP code or phone number",
            401: "OTP verification failed",
            429: "Too many failed attempts, please try again later",
        },
    )
    @action(detail=False, methods=["post"], url_path="verify-otp")
    def verify_otp(self, request: Request) -> Response:
        """
        Verify OTP code and authenticate user.

        This endpoint:
        1. Validates the phone number and OTP code format
        2. Verifies the OTP code against stored value
        3. Creates or authenticates the user
        4. Generates authentication tokens
        5. Implements rate limiting for failed attempts

        Args:
            request: HTTP request with phone_number and code in request data

        Returns:
            Response with authentication tokens and user data on success

        Raises:
            ValidationError: If input data format is invalid
            Throttled: If too many failed attempts
        """
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        # Check rate limiting for failed attempts
        if SecurityService.is_rate_limited(
            identifier=phone_number,
            action="otp_verify",
            max_attempts=5,
            window_minutes=15,
        ):
            logger.warning(f"Rate limit exceeded for OTP verification: {phone_number}")
            return Response(
                {"detail": _("Too many failed attempts. Please try again later.")},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Verify OTP
        verification_result = OTPService.verify_otp(phone_number, code)

        if not verification_result["success"]:
            # Record failed attempt
            SecurityService.record_failed_attempt(
                identifier=phone_number, action="otp_verify"
            )

            logger.warning(
                f"OTP verification failed for {phone_number}: {verification_result['message']}"
            )
            return Response(
                {"detail": verification_result["message"]},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # OTP verified successfully, get or create user
        user, created = User.objects.get_or_create(
            phone_number=phone_number, defaults={"is_verified": True}
        )

        if not created and not user.is_verified:
            user.is_verified = True
            user.save(update_fields=["is_verified"])

        # Generate tokens
        tokens = TokenService.generate_tokens(user)

        # Clear rate limiting records for successful verification
        SecurityService.clear_rate_limiting(
            identifier=phone_number, action="otp_verify"
        )

        # Log successful authentication
        logger.info(f"User authenticated via OTP: {user.id} ({phone_number})")

        # Return tokens and user data
        return Response(
            {"tokens": tokens, "user": UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )

    @document_api_endpoint(
        summary="Refresh Token",
        description="Refresh authentication tokens using a valid refresh token",
        request_body=TokenRefreshSerializer,
        responses={
            200: "Tokens refreshed successfully",
            401: "Invalid or expired refresh token",
        },
    )
    @action(detail=False, methods=["post"], url_path="refresh-token")
    def refresh_token(self, request: Request) -> Response:
        """
        Refresh authentication tokens using a valid refresh token.

        This endpoint:
        1. Validates the refresh token
        2. Generates new access and refresh tokens
        3. Invalidates the old refresh token

        Args:
            request: HTTP request with refresh_token in request data

        Returns:
            Response with new authentication tokens

        Raises:
            ValidationError: If refresh token format is invalid
            AuthenticationFailed: If refresh token is invalid or expired
        """
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh_token"]

        try:
            # Validate refresh token and get user
            token_info = TokenService.validate_refresh_token(refresh_token)
            user = User.objects.get(id=token_info["user_id"])

            # Generate new tokens
            new_tokens = TokenService.generate_tokens(user)

            # Invalidate old refresh token
            TokenService.invalidate_refresh_token(refresh_token)

            logger.info(f"Tokens refreshed for user: {user.id}")

            return Response(new_tokens, status=status.HTTP_200_OK)

        except Exception as e:
            logger.warning(f"Token refresh failed: {str(e)}")
            return Response(
                {"detail": _("Invalid or expired refresh token")},
                status=status.HTTP_401_UNAUTHORIZED,
            )

    @document_api_endpoint(
        summary="Get User Profile",
        description="Get the authenticated user's profile information",
        responses={
            200: "User profile retrieved successfully",
            401: "Authentication required",
        },
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="profile",
        permission_classes=[permissions.IsAuthenticated],
    )
    def get_profile(self, request: Request) -> Response:
        """
        Get the authenticated user's profile information.

        This endpoint:
        1. Retrieves the authenticated user
        2. Returns serialized user profile data

        Args:
            request: HTTP request with authenticated user

        Returns:
            Response with user profile data

        Raises:
            NotAuthenticated: If user is not authenticated
        """
        user = request.user
        serializer = UserSerializer(user)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @document_api_endpoint(
        summary="Update User Profile",
        description="Update the authenticated user's profile information",
        request_body=UserProfileSerializer,
        responses={
            200: "User profile updated successfully",
            400: "Invalid profile data",
            401: "Authentication required",
        },
        methods=["put", "patch"]
    )
    @action(
        detail=False,
        methods=["put", "patch"],
        url_path="profile",
        permission_classes=[permissions.IsAuthenticated],
    )
    def update_profile(self, request: Request) -> Response:
        """
        Update the authenticated user's profile information.

        This endpoint:
        1. Validates the profile update data
        2. Updates the user profile
        3. Returns the updated profile data

        Args:
            request: HTTP request with authenticated user and profile data

        Returns:
            Response with updated user profile data

        Raises:
            NotAuthenticated: If user is not authenticated
            ValidationError: If profile data is invalid
        """
        user = request.user
        serializer = UserProfileSerializer(
            user, data=request.data, partial=request.method == "PATCH"
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        logger.info(f"Profile updated for user: {user.id}")

        # Return full user data
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    @document_api_endpoint(
        summary="Change Language Preference",
        description="Update the user's language preference",
        request_body=ChangeLanguageSerializer,
        responses={
            200: "Language preference updated successfully",
            400: "Invalid language code",
            401: "Authentication required",
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="change-language",
        permission_classes=[permissions.IsAuthenticated],
    )
    def change_language(self, request: Request) -> Response:
        """
        Update the user's language preference.

        This endpoint:
        1. Validates the language code
        2. Updates the user's language preference

        Args:
            request: HTTP request with authenticated user and language code

        Returns:
            Response with success message

        Raises:
            NotAuthenticated: If user is not authenticated
            ValidationError: If language code is invalid
        """
        serializer = ChangeLanguageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        language = serializer.validated_data["language"]
        user = request.user

        user.language_preference = language
        user.save(update_fields=["language_preference"])

        logger.info(f"Language preference updated for user {user.id}: {language}")

        return Response(
            {"detail": _("Language preference updated successfully")},
            status=status.HTTP_200_OK,
        )


@document_api_viewset(
    summary="User Management",
    description="API endpoints for user management and administration",
    tags=["User Management"],
)
class UserViewSet(viewsets.ModelViewSet):
    """
    User management viewset for administrative operations.

    This viewset provides CRUD operations for user management,
    restricted to administrative users only.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        """
        Get filtered queryset based on request parameters.

        Returns:
            Filtered User queryset
        """
        queryset = super().get_queryset()

        # Filter by user type if provided
        user_type = self.request.query_params.get("user_type")
        if user_type:
            queryset = queryset.filter(user_type=user_type)

        # Filter by verification status if provided
        is_verified = self.request.query_params.get("is_verified")
        if is_verified is not None:
            is_verified = is_verified.lower() == "true"
            queryset = queryset.filter(is_verified=is_verified)

        return queryset

    @document_api_endpoint(
        summary="Deactivate User",
        description="Deactivate a user account",
        responses={
            200: "User deactivated successfully",
            404: "User not found",
            403: "Permission denied",
        },
    )
    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request: Request, pk: str = None) -> Response:
        """
        Deactivate a user account.

        This endpoint:
        1. Retrieves the specified user
        2. Deactivates the user account
        3. Logs the deactivation event

        Args:
            request: HTTP request
            pk: User ID

        Returns:
            Response with success message

        Raises:
            NotFound: If user does not exist
            PermissionDenied: If requester lacks permission
        """
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active"])

        logger.info(f"User deactivated: {user.id} by admin {request.user.id}")

        return Response(
            {"detail": _("User deactivated successfully")}, status=status.HTTP_200_OK
        )

    @document_api_endpoint(
        summary="Activate User",
        description="Activate a user account",
        responses={
            200: "User activated successfully",
            404: "User not found",
            403: "Permission denied",
        },
    )
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request: Request, pk: str = None) -> Response:
        """
        Activate a user account.

        This endpoint:
        1. Retrieves the specified user
        2. Activates the user account
        3. Logs the activation event

        Args:
            request: HTTP request
            pk: User ID

        Returns:
            Response with success message

        Raises:
            NotFound: If user does not exist
            PermissionDenied: If requester lacks permission
        """
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active"])

        logger.info(f"User activated: {user.id} by admin {request.user.id}")

        return Response(
            {"detail": _("User activated successfully")}, status=status.HTTP_200_OK
        )
