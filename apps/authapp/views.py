import logging

from django.contrib.auth import authenticate
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

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


class AuthViewSet(viewsets.GenericViewSet):
    """
    Authentication viewset handling OTP, login, and token operations.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

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
