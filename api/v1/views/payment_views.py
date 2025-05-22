"""
Payment API views for QueueMe platform.
Provides endpoints for processing payments, refunds, and managing payment methods.
"""

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from api.documentation.utils import dedupe_manual_parameters
from apps.payment.serializers import (
    CreatePaymentSerializer,
    CreateRefundSerializer,
    PaymentMethodSerializer,
)

# Import the actual implementations from apps
from apps.payment.views import PaymentViewSet as CorePaymentViewSet


class ProcessPaymentView(APIView):
    """API endpoint to process payments"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Process payment",
        operation_description="Process a payment for a booking or service",
        request_body=CreatePaymentSerializer,
        responses={
            201: openapi.Response(
                description="Payment processed successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "transaction_id": openapi.Schema(type=openapi.TYPE_STRING),
                        "status": openapi.Schema(type=openapi.TYPE_STRING),
                        "transaction_type": openapi.Schema(type=openapi.TYPE_STRING),
                        "wallet_id": openapi.Schema(type=openapi.TYPE_STRING),
                        "redirect_url": openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            ),
            400: "Invalid payment data",
            402: "Payment failed",
            403: "Unauthorized payment attempt",
        },
    )
    def post(self, request):
        # Forward to appropriate method in the core view
        viewset = CorePaymentViewSet()
        viewset.request = request
        return viewset.create_payment(request)


class RefundPaymentView(APIView):
    """API endpoint to process refunds"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Refund payment",
        operation_description="Process a refund for a previous payment",
        request_body=CreateRefundSerializer,
        responses={
            200: openapi.Response(
                description="Refund processed successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "refund_id": openapi.Schema(type=openapi.TYPE_STRING),
                        "status": openapi.Schema(type=openapi.TYPE_STRING),
                        "amount": openapi.Schema(type=openapi.TYPE_STRING),
                        "transaction_type": openapi.Schema(type=openapi.TYPE_STRING),
                        "wallet_id": openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            ),
            400: "Invalid refund request",
            404: "Payment not found",
            403: "Unauthorized refund attempt",
        },
    )
    def post(self, request):
        # Forward to appropriate method in the core view
        viewset = CorePaymentViewSet()
        viewset.request = request
        return viewset.create_refund(request)


class PaymentMethodsView(APIView):
    """API endpoint to manage payment methods"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Get payment methods",
        operation_description="Retrieve available payment methods for the user",
        responses={
            200: openapi.Response(
                description="List of payment methods",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=PaymentMethodSerializer,
                ),
            ),
            401: "Unauthorized",
        },
    )
    def get(self, request):
        # Forward to appropriate method in the core view
        viewset = CorePaymentViewSet()
        viewset.request = request
        return viewset.payment_methods(request)


class PaymentHistoryView(APIView):
    """API endpoint to retrieve payment history"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Get payment history",
        operation_description="Retrieve payment history for the user",
        manual_parameters=dedupe_manual_parameters(
            [
                openapi.Parameter(
                    "start_date",
                    openapi.IN_QUERY,
                    description="Filter by start date (YYYY-MM-DD)",
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATE,
                    required=False,
                ),
                openapi.Parameter(
                    "end_date",
                    openapi.IN_QUERY,
                    description="Filter by end date (YYYY-MM-DD)",
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATE,
                    required=False,
                ),
                openapi.Parameter(
                    "status",
                    openapi.IN_QUERY,
                    description="Filter by payment status",
                    type=openapi.TYPE_STRING,
                    required=False,
                ),
                openapi.Parameter(
                    "transaction_type",
                    openapi.IN_QUERY,
                    description="Filter by transaction type",
                    type=openapi.TYPE_STRING,
                    required=False,
                ),
            ]
        ),
        responses={
            200: "Payment history returned successfully",
            401: "Unauthorized",
        },
    )
    def get(self, request):
        # Forward to appropriate method in the core view
        viewset = CorePaymentViewSet()
        viewset.request = request
        return viewset.transactions(request)
