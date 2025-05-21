"""
Authentication API views for QueueMe platform.
Provides endpoints for user authentication, OTP verification, and token management.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from api.documentation.utils import dedupe_manual_parameters

# Import the actual implementations from apps
from apps.authapp.views import AuthViewSet as CoreAuthViewSet
from apps.authapp.serializers import (
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordResetRequestSerializer,
    UserRegistrationSerializer,
)


class LoginView(APIView):
    """API endpoint to authenticate users"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_summary="User login",
        operation_description="Authenticate a user and return JWT tokens",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phone_number', 'password'],
            properties={
                'phone_number': openapi.Schema(type=openapi.TYPE_STRING, description='User phone number'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='User password'),
            }
        ),
        responses={
            200: openapi.Response(
                description="Login successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'tokens': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'access': openapi.Schema(type=openapi.TYPE_STRING, description='JWT access token'),
                                'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='JWT refresh token'),
                            }
                        ),
                        'profile_completed': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'user_type': openapi.Schema(type=openapi.TYPE_STRING),
                        'language': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            401: "Unauthorized - Invalid credentials or account disabled",
            429: "Too Many Requests - Rate limited",
        }
    )
    def post(self, request):
        # Use the existing login implementation
        viewset = CoreAuthViewSet()
        viewset.request = request
        return viewset.login(request)


class RegisterView(APIView):
    """API endpoint for user registration"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_summary="User registration",
        operation_description="Register a new user account",
        request_body=UserRegistrationSerializer,
        responses={
            201: "User created successfully",
            400: "Invalid data provided",
        }
    )
    def post(self, request):
        # Forward to appropriate method in the core view
        viewset = CoreAuthViewSet()
        viewset.request = request
        return viewset.register(request)


class RequestOTPView(APIView):
    """API endpoint to request verification OTP"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_summary="Request OTP verification code",
        operation_description="Send a one-time password to the user's phone number",
        request_body=OTPRequestSerializer,
        responses={
            200: "OTP sent successfully",
            400: "Invalid request",
            429: "Too many attempts",
            500: "Failed to send OTP",
        }
    )
    def post(self, request):
        # Forward to appropriate method in the core view
        viewset = CoreAuthViewSet()
        viewset.request = request
        return viewset.request_otp(request)


class VerifyOTPView(APIView):
    """API endpoint to verify OTP codes"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_summary="Verify OTP code",
        operation_description="Validate a one-time password entered by the user",
        request_body=OTPVerifySerializer,
        responses={
            200: "OTP verified successfully",
            400: "Invalid code",
        }
    )
    def post(self, request):
        # Forward to appropriate method in the core view
        viewset = CoreAuthViewSet()
        viewset.request = request
        return viewset.verify_otp(request)


class PasswordResetRequestView(APIView):
    """API endpoint to request password reset"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_summary="Request password reset",
        operation_description="Send a password reset link to user's email",
        request_body=PasswordResetRequestSerializer,
        responses={
            200: "Password reset email sent",
            400: "Invalid email",
            404: "User not found",
        }
    )
    def post(self, request):
        # This would forward to a password reset method in your core AuthViewSet
        # If it doesn't exist yet, you would need to implement it
        return Response(
            {"detail": "Password reset functionality coming soon."},
            status=status.HTTP_200_OK
        )
