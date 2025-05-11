"""
Payment app views for QueueMe platform
Handles endpoints related to payments, transactions, and payment methods
"""

import logging

from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import PaymentMethod, Transaction
from .permissions import PaymentPermission
from .serializers import (
    AddPaymentMethodSerializer,
    CreatePaymentSerializer,
    CreateRefundSerializer,
    PaymentMethodSerializer,
    PaymentStatusSerializer,
    SetDefaultPaymentMethodSerializer,
    TransactionSerializer,
)
from .services.payment_method_recommender import PaymentMethodRecommender
from .services.payment_service import PaymentService
from ..api_doc_decorators import document_api_endpoint, document_api_viewset

logger = logging.getLogger(__name__)


@document_api_viewset(
    summary="Payment",
    description="API endpoints for payment-related operations including payment methods, transactions, and refunds",
    tags=["Payments"]
)
class PaymentViewSet(viewsets.ViewSet):
    """
    ViewSet for payment-related operations
    """

    permission_classes = [permissions.IsAuthenticated, PaymentPermission]

    @document_api_endpoint(
        summary="Get payment methods",
        description="Retrieve all saved payment methods for the current user",
        responses={
            200: "Success - Returns list of payment methods"
        },
        tags=["Payments", "Payment Methods"]
    )
    @action(detail=False, methods=["get"])
    def payment_methods(self, request):
        """Get user's saved payment methods"""
        payment_methods = PaymentMethod.objects.filter(user=request.user)
        serializer = PaymentMethodSerializer(payment_methods, many=True)
        return Response(serializer.data)

    @document_api_endpoint(
        summary="Add payment method",
        description="Add a new payment method for the current user",
        responses={
            201: "Created - Payment method added successfully",
            400: "Bad Request - Invalid data or unable to add payment method"
        },
        tags=["Payments", "Payment Methods"]
    )
    @action(detail=False, methods=["post"])
    def add_payment_method(self, request):
        """Add a new payment method"""
        serializer = AddPaymentMethodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = PaymentService.add_payment_method(
            user_id=request.user.id,
            token=serializer.validated_data["token"],
            payment_type=serializer.validated_data["payment_type"],
            make_default=serializer.validated_data.get("make_default", False),
        )

        if result["success"]:
            payment_method = PaymentMethod.objects.get(id=result["payment_method_id"])
            return Response(
                PaymentMethodSerializer(payment_method).data,
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                {"detail": result["error"]}, status=status.HTTP_400_BAD_REQUEST
            )

    @document_api_endpoint(
        summary="Set default payment method",
        description="Set a specific payment method as the default for the current user",
        responses={
            200: "Success - Default payment method updated",
            400: "Bad Request - Invalid data or payment method not found"
        },
        tags=["Payments", "Payment Methods"]
    )
    @action(detail=False, methods=["post"])
    def set_default_payment_method(self, request):
        """Set payment method as default"""
        serializer = SetDefaultPaymentMethodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = PaymentService.set_default_payment_method(
            user_id=request.user.id,
            payment_method_id=serializer.validated_data["payment_method_id"],
        )

        if result["success"]:
            return Response({"detail": _("Default payment method updated.")})
        else:
            return Response(
                {"detail": result["error"]}, status=status.HTTP_400_BAD_REQUEST
            )

    @document_api_endpoint(
        summary="Create payment",
        description="Create a new payment transaction for an object",
        responses={
            201: "Created - Payment created successfully, returns transaction details",
            400: "Bad Request - Invalid data or payment processing error"
        },
        tags=["Payments", "Transactions"]
    )
    @action(detail=False, methods=["post"])
    def create_payment(self, request):
        """Create a new payment transaction"""
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get content object
        content_type = ContentType.objects.get(
            app_label=serializer.validated_data["content_type"]["app_label"],
            model=serializer.validated_data["content_type"]["model"],
        )

        model_class = content_type.model_class()
        content_object = model_class.objects.get(
            id=serializer.validated_data["object_id"]
        )

        # Create payment
        result = PaymentService.create_payment(
            user_id=request.user.id,
            amount=serializer.validated_data["amount"],
            transaction_type=serializer.validated_data["transaction_type"],
            description=serializer.validated_data.get("description", ""),
            content_object=content_object,
            payment_method_id=serializer.validated_data.get("payment_method_id"),
            payment_type=serializer.validated_data.get("payment_type"),
        )

        if result["success"]:
            return Response(
                {
                    "transaction_id": result["transaction_id"],
                    "status": result["status"],
                    "redirect_url": result.get("redirect_url"),
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                {"detail": result["error"]}, status=status.HTTP_400_BAD_REQUEST
            )

    @document_api_endpoint(
        summary="Check payment status",
        description="Check the current status of a payment transaction",
        responses={
            200: "Success - Returns current transaction status",
            404: "Not Found - Transaction not found"
        },
        tags=["Payments", "Transactions"]
    )
    @action(detail=False, methods=["post"])
    def check_payment_status(self, request):
        """Check the status of a payment transaction"""
        serializer = PaymentStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        transaction_id = serializer.validated_data["transaction_id"]
        transaction = get_object_or_404(Transaction, id=transaction_id)

        # Verify permissions
        self.check_object_permissions(request, transaction)

        return Response(
            {
                "transaction_id": str(transaction.id),
                "status": transaction.status,
                "moyasar_id": transaction.moyasar_id,
            }
        )

    @document_api_endpoint(
        summary="List transactions",
        description="Retrieve transactions with optional filtering",
        responses={
            200: "Success - Returns list of transactions"
        },
        query_params=[
            {
                'name': 'content_type_id', 
                'description': 'Content type ID to filter transactions by', 
                'required': False, 
                'type': 'integer'
            },
            {
                'name': 'object_id', 
                'description': 'Object ID to filter transactions by', 
                'required': False, 
                'type': 'string'
            }
        ],
        tags=["Payments", "Transactions"]
    )
    @action(detail=False, methods=["get"])
    def transactions(self, request):
        """Get user's transactions"""
        # For customers, only show their own transactions
        if request.user.user_type == "customer":
            transactions = Transaction.objects.filter(user=request.user)
        else:
            # For shop staff/admins, filter by content_type_id and object_id if provided
            transactions = Transaction.objects.all()

            if (
                "content_type_id" in request.query_params
                and "object_id" in request.query_params
            ):
                transactions = transactions.filter(
                    content_type_id=request.query_params["content_type_id"],
                    object_id=request.query_params["object_id"],
                )

        # Apply filters, ordering, pagination, etc.
        page = self.paginate_queryset(transactions)
        if page is not None:
            serializer = TransactionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)

    @document_api_endpoint(
        summary="Create refund",
        description="Create a refund for a specific transaction",
        responses={
            200: "Success - Refund created successfully, returns refund details",
            400: "Bad Request - Invalid data or unable to process refund",
            404: "Not Found - Transaction not found"
        },
        tags=["Payments", "Refunds"]
    )
    @action(detail=False, methods=["post"])
    def create_refund(self, request):
        """Create a refund for a transaction"""
        serializer = CreateRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get transaction
        transaction = get_object_or_404(
            Transaction, id=serializer.validated_data["transaction_id"]
        )

        # Verify permissions
        self.check_object_permissions(request, transaction)

        result = PaymentService.create_refund(
            transaction_id=transaction.id,
            amount=serializer.validated_data["amount"],
            reason=serializer.validated_data["reason"],
            refunded_by_id=request.user.id,
        )

        if result["success"]:
            return Response(
                {
                    "refund_id": result["refund_id"],
                    "status": result["status"],
                    "amount": result["amount"],
                }
            )
        else:
            return Response(
                {"detail": result["error"]}, status=status.HTTP_400_BAD_REQUEST
            )

    @document_api_endpoint(
        summary="Recommend payment method",
        description="Get recommended payment methods for the current user",
        responses={
            200: "Success - Returns list of recommended payment methods"
        },
        query_params=[
            {
                'name': 'amount', 
                'description': 'Amount for the potential transaction (default: 100)', 
                'required': False, 
                'type': 'number'
            },
            {
                'name': 'transaction_type', 
                'description': 'Type of transaction for the recommendation', 
                'required': False, 
                'type': 'string'
            }
        ],
        tags=["Payments", "Payment Methods", "Recommendations"]
    )
    @action(detail=False, methods=["get"])
    def recommend_payment_method(self, request):
        """Get recommended payment method for user"""
        # Get amount from query params if provided
        amount = request.query_params.get("amount")
        if amount:
            try:
                amount = float(amount)
            except ValueError:
                amount = 100  # Default amount
        else:
            amount = 100  # Default amount

        # Get transaction type from query params if provided
        transaction_type = request.query_params.get("transaction_type")

        # Get recommendations
        recommendations = PaymentMethodRecommender.recommend_payment_method(
            request.user, amount, transaction_type
        )

        # Format response
        response_data = []
        for rec in recommendations:
            if isinstance(rec["method"], PaymentMethod):
                # Saved payment method
                method_data = PaymentMethodSerializer(rec["method"]).data
                method_data["score"] = rec["score"]
                method_data["usage_count"] = rec["usage_count"]
                method_data["success_rate"] = rec["success_rate"]
                response_data.append(method_data)
            else:
                # Generic payment method
                response_data.append(
                    {
                        "type": rec["method"]["type"],
                        "type_display": rec["method"]["name"],
                        "is_default": False,
                        "score": rec["score"],
                    }
                )

        return Response(response_data)

    # Helper methods
    def paginate_queryset(self, queryset):
        """
        Return a paginated queryset if pagination is configured.
        This is a simplified version - in a real project, use a paginator class.
        """
        # Just return all for now
        return queryset

    def get_paginated_response(self, data):
        """
        Return a paginated response.
        This is a simplified version - in a real project, use a paginator class.
        """
        return Response(data)
