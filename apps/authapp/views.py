"""
Authentication app views for QueueMe platform
Handles user authentication, OTP verification, and profile management
"""

import logging

from django.contrib.auth import authenticate
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.documentation.api_doc_decorators import (
    document_api_endpoint,
    document_api_viewset,
)
from apps.authapp.models import User
from apps.authapp.serializers import (
    ChangeLanguageSerializer,
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    TokenRefreshSerializer,
    UserProfileSerializer,
    UserSerializer,
)
from apps.authapp.services.otp_service import OTPService
from apps.authapp.services.phone_verification import PhoneVerificationService
from apps.authapp.services.security_service import SecurityService
from apps.authapp.services.token_service import TokenService

logger = logging.getLogger(__name__)


@document_api_viewset(
    summary="Authentication",
    description="API endpoints for handling user authentication including OTP, login, and token operations",
    tags=["Authentication"],
)
class AuthViewSet(viewsets.GenericViewSet):
    """
    Authentication viewset handling OTP, login, and token operations.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    @document_api_endpoint(
        summary="Request OTP",
        description="Request a one-time password to be sent to the provided phone number",
        responses={
            200: "Success - OTP sent successfully",
            400: "Bad Request - Invalid data",
            429: "Too Many Requests - Rate limited",
            500: "Internal Server Error - Failed to send OTP",
        },
        tags=["Authentication", "OTP"],
    )
    @action(detail=False, methods=["post"])
    def request_otp(self, request):
        """
        Request OTP for phone number.
        """
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]

        # Check if rate limited
        if SecurityService.is_rate_limited(phone_number, "otp"):
            return Response(
                {"detail": _("Too many OTP requests. Please try again later.")},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            OTPService.send_otp(phone_number)

            return Response(
                {"detail": _("OTP sent successfully")}, status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        except Exception as e:
            logger.error(f"Error sending OTP: {str(e)}")
            return Response(
                {"detail": _("Failed to send OTP. Please try again later.")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @document_api_endpoint(
        summary="Verify OTP",
        description="Verify OTP code and return authentication tokens",
        responses={
            200: "Success - OTP verified successfully, returns tokens and user info",
            400: "Bad Request - Invalid OTP code or data",
        },
        tags=["Authentication", "OTP"],
    )
    @action(detail=False, methods=["post"])
    def verify_otp(self, request):
        """
        Verify OTP and return tokens.
        """
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        # Verify OTP
        user = OTPService.verify_otp(phone_number, code)

        if not user:
            return Response(
                {"detail": _("Invalid OTP code")}, status=status.HTTP_400_BAD_REQUEST
            )

        # Generate tokens
        tokens = TokenService.get_tokens_for_user(user)

        # Include profile completion status
        response_data = {
            "tokens": tokens,
            "profile_completed": user.profile_completed,
            "user_type": user.user_type,
            "language": user.language_preference,
        }

        # Log successful verification
        SecurityService.record_security_event(
            user_id=str(user.id),
            event_type="otp_verification_success",
            details=f"OTP verified for {phone_number}",
        )

        return Response(response_data, status=status.HTTP_200_OK)

    @document_api_endpoint(
        summary="Login",
        description="Login with phone number and password",
        responses={
            200: "Success - Login successful, returns tokens and user info",
            401: "Unauthorized - Invalid credentials or account disabled",
            429: "Too Many Requests - Rate limited",
        },
        tags=["Authentication", "Login"],
    )
    @action(detail=False, methods=["post"])
    def login(self, request):
        """
        Login with phone number and password.
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        password = serializer.validated_data["password"]

        # Check if rate limited
        if SecurityService.is_rate_limited(phone_number, "login"):
            return Response(
                {"detail": _("Too many login attempts. Please try again later.")},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Authenticate user
        user = authenticate(phone_number=phone_number, password=password)

        if not user:
            # Record failed login attempt
            SecurityService.record_security_event(
                user_id="unknown",
                event_type="login_failure",
                details=f"Failed login attempt for {phone_number}",
                severity="warning",
            )

            return Response(
                {"detail": _("Invalid credentials")},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Check if user is active
        if not user.is_active:
            return Response(
                {"detail": _("User account is disabled")},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        # Generate tokens
        tokens = TokenService.get_tokens_for_user(user)

        # Include profile completion status
        response_data = {
            "tokens": tokens,
            "profile_completed": user.profile_completed,
            "user_type": user.user_type,
            "language": user.language_preference,
        }

        # Record successful login
        SecurityService.record_security_event(
            user_id=str(user.id),
            event_type="login_success",
            details=f"User logged in: {phone_number}",
        )

        return Response(response_data, status=status.HTTP_200_OK)

    @document_api_endpoint(
        summary="Logout",
        description="Logout current user by invalidating tokens",
        responses={200: "Success - User logged out successfully"},
        tags=["Authentication", "Login"],
    )
    @action(
        detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def logout(self, request):
        """
        Logout user (invalidate tokens).
        """
        # In a real implementation, you might add the token to a blacklist
        # or revoke the refresh token

        # Record logout
        SecurityService.record_security_event(
            user_id=str(request.user.id),
            event_type="logout",
            details=f"User logged out: {request.user.phone_number}",
        )

        return Response({"detail": _("Successfully logged out")})

    @document_api_endpoint(
        summary="Refresh token",
        description="Get new access token using refresh token",
        responses={
            200: "Success - Returns new token pair",
            401: "Unauthorized - Invalid refresh token",
        },
        tags=["Authentication", "Tokens"],
    )
    @action(detail=False, methods=["post"])
    def refresh_token(self, request):
        """
        Refresh token.
        """
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh"]

        try:
            # Refresh token
            new_tokens = TokenService.refresh_token(refresh_token)

            return Response(new_tokens, status=status.HTTP_200_OK)
        except Exception as e:
            logger.warning(f"Token refresh failed: {str(e)}")
            return Response(
                {"detail": _("Invalid refresh token")},
                status=status.HTTP_401_UNAUTHORIZED,
            )

    @document_api_endpoint(
        summary="Change language",
        description="Update user language preference",
        responses={200: "Success - Language preference updated successfully"},
        tags=["User Settings"],
    )
    @action(
        detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def change_language(self, request):
        """
        Change user language preference.
        """
        serializer = ChangeLanguageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Update user's language preference
        user = request.user
        user.language_preference = serializer.validated_data["language"]
        user.save(update_fields=["language_preference"])

        return Response(
            {
                "detail": _("Language preference updated successfully"),
                "language": user.language_preference,
            },
            status=status.HTTP_200_OK,
        )


@document_api_viewset(
    summary="User Profile",
    description="API endpoints for managing user profile and account settings",
    tags=["Users", "Profile"],
)
class UserProfileViewSet(
    viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.UpdateModelMixin
):
    """
    User profile management.
    """

    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return UserSerializer
        return UserProfileSerializer

    def get_object(self):
        """
        Returns the authenticated user.
        """
        return self.request.user

    @document_api_endpoint(
        summary="Get user profile",
        description="Retrieve current user profile information",
        responses={200: "Success - Returns user profile details"},
        tags=["Users", "Profile"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().retrieve(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Update user profile",
        description="Update current user profile information",
        responses={
            200: "Success - User profile updated successfully",
            400: "Bad Request - Invalid data",
        },
        tags=["Users", "Profile"],
    )
    def update(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().update(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Change phone number",
        description="Request a phone number change and start verification process",
        responses={
            200: "Success - Verification code sent to new phone number",
            400: "Bad Request - Phone number is required or already in use",
            429: "Too Many Requests - Rate limited",
            500: "Internal Server Error - Failed to send verification",
        },
        tags=["Users", "Profile"],
    )
    @action(detail=False, methods=["post"])
    def change_phone(self, request):
        """
        Request phone number change.
        """
        new_phone = request.data.get("phone_number")
        if not new_phone:
            return Response(
                {"detail": _("Phone number is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Start verification process
        result = PhoneVerificationService.start_verification(new_phone)

        if result["status"] == "already_verified":
            return Response(
                {"detail": _("This phone number is already in use")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif result["status"] == "rate_limited":
            return Response(
                {"detail": result["message"]}, status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        elif result["status"] == "error":
            return Response(
                {"detail": result["message"]},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"detail": _("Verification code sent to new phone number")},
            status=status.HTTP_200_OK,
        )

    @document_api_endpoint(
        summary="Verify new phone number",
        description="Verify new phone number with OTP code",
        responses={
            200: "Success - Phone number updated successfully, returns new tokens",
            400: "Bad Request - Invalid code or phone already in use",
        },
        tags=["Users", "Profile"],
    )
    @action(detail=False, methods=["post"])
    def verify_new_phone(self, request):
        """
        Verify new phone number with OTP.
        """
        new_phone = request.data.get("phone_number")
        code = request.data.get("code")

        if not new_phone or not code:
            return Response(
                {"detail": _("Phone number and code are required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify new phone number
        result = PhoneVerificationService.verify_phone_change(
            request.user, new_phone, code
        )

        if result["status"] == "already_in_use":
            return Response(
                {"detail": _("This phone number is already in use")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif result["status"] == "invalid_code":
            return Response(
                {"detail": _("Invalid verification code")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate new tokens with updated phone number
        tokens = TokenService.get_tokens_for_user(request.user)

        return Response(
            {"detail": _("Phone number updated successfully"), "tokens": tokens},
            status=status.HTTP_200_OK,
        )
