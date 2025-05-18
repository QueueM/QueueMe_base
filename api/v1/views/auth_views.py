from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from api.v1.throttling import AnonStrictRateThrottle, AuthenticationRateThrottle


class LoginView(APIView):
    """
    User login view
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthenticationRateThrottle, AnonStrictRateThrottle]

    # ... existing code ...


class RegisterView(APIView):
    """
    User registration view
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthenticationRateThrottle, AnonStrictRateThrottle]

    # ... existing code ...


class RequestOTPView(APIView):
    """
    Request OTP view
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthenticationRateThrottle, AnonStrictRateThrottle]

    # ... existing code ...


class VerifyOTPView(APIView):
    """
    Verify OTP view
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthenticationRateThrottle, AnonStrictRateThrottle]

    # ... existing code ...


class PasswordResetRequestView(APIView):
    """
    Password reset request view
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthenticationRateThrottle, AnonStrictRateThrottle]

    # ... existing code ...


# ... Apply to other authentication views ...
