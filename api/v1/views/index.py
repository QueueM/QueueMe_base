# api/v1/views/index.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request, format=None):
    """
    The Queue Me Platform API root.

    This endpoint provides links to all major API endpoints.
    """
    return Response(
        {
            "auth": {
                "request_otp": reverse(
                    "auth-request-otp", request=request, format=format
                ),
                "verify_otp": reverse(
                    "auth-verify-otp", request=request, format=format
                ),
            },
            "shops": reverse("shop-list", request=request, format=format),
            "services": reverse("service-list", request=request, format=format),
            "specialists": reverse("specialist-list", request=request, format=format),
            "appointments": reverse("appointment-list", request=request, format=format),
            "queues": reverse("queue-list", request=request, format=format),
            "customers": reverse("customer-list", request=request, format=format),
            "companies": reverse("company-list", request=request, format=format),
            "categories": reverse("category-list", request=request, format=format),
            "conversations": reverse(
                "conversation-list", request=request, format=format
            ),
            "reels": reverse("reel-list", request=request, format=format),
            "stories": reverse("story-list", request=request, format=format),
            "reviews": reverse("review-list", request=request, format=format),
            "notifications": reverse(
                "notification-list", request=request, format=format
            ),
            "payments": reverse("payment-list", request=request, format=format),
            "documentation": {
                "swagger": reverse("schema-swagger-ui", request=request, format=format),
                "redoc": reverse("schema-redoc", request=request, format=format),
            },
        }
    )
