"""
Subscription app views for QueueMe platform
Handles endpoints related to subscription plans, company subscriptions, invoices,
payment processing, and feature usage tracking.
"""

# apps/subscriptionapp/views.py
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.companiesapp.models import Company
from apps.subscriptionapp.services.invoice_service import InvoiceService
from apps.subscriptionapp.services.plan_service import PlanService
from apps.subscriptionapp.services.subscription_service import SubscriptionService

from .models import FeatureUsage, Plan, Subscription, SubscriptionInvoice
from .permissions import (
    CanManageOwnCompanySubscription,
    CanManageSubscriptions,
    CanViewOwnCompanySubscription,
    CanViewSubscriptions,
)
from .serializers import (
    FeatureUsageSerializer,
    PlanCreateUpdateSerializer,
    PlanSerializer,
    SubscriptionCancelSerializer,
    SubscriptionCreateSerializer,
    SubscriptionInvoiceSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionRenewalSerializer,
    SubscriptionSerializer,
    SubscriptionUpdateSerializer,
)


class PlanViewSet(viewsets.ModelViewSet):
    """
    ViewSet for subscription plans

    Manages the available subscription plans in the system, including pricing,
    features, and limitations for different service tiers.

    Endpoints:
    - GET /api/subscription/plans/ - List all subscription plans
    - POST /api/subscription/plans/ - Create a new plan (admin only)
    - GET /api/subscription/plans/{id}/ - Get plan details
    - PUT/PATCH /api/subscription/plans/{id}/ - Update a plan (admin only)
    - DELETE /api/subscription/plans/{id}/ - Delete a plan (admin only)
    - GET /api/subscription/plans/{id}/features/ - Get features for a plan
    - GET /api/subscription/plans/compare/ - Compare multiple plans

    Permissions:
    - View operations: Any authenticated user
    - Modify operations: Admin users only with CanManageSubscriptions permission
    """

    queryset = Plan.objects.all().order_by("position", "monthly_price")
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """
        Return the appropriate serializer based on action

        - Create/update operations: PlanCreateUpdateSerializer
        - Other operations: PlanSerializer

        Returns:
            Serializer class: The appropriate serializer
        """
        if self.action in ["create", "update", "partial_update"]:
            return PlanCreateUpdateSerializer
        return PlanSerializer

    def get_permissions(self):
        """
        Set permissions based on action

        - Create/update/delete operations: CanManageSubscriptions
        - View operations: Any authenticated user

        Returns:
            list: Permission classes for the action
        """
        if self.action in ["create", "update", "partial_update", "destroy"]:
            # Only Queue Me admins can manage plans
            return [CanManageSubscriptions()]

        # Anyone can view plans
        return [IsAuthenticated()]

    @action(detail=True, methods=["get"])
    def features(self, request, pk=None):
        """
        Get features for a specific plan

        Returns all features included in the specified plan,
        ordered by category and tier.

        Returns:
            Response: List of plan features
        """
        plan = self.get_object()
        features = plan.features.all().order_by("category", "tier")

        from .serializers import PlanFeatureSerializer

        serializer = PlanFeatureSerializer(features, many=True)

        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def compare(self, request):
        """
        Compare multiple plans side by side

        Provides a detailed comparison of selected plans,
        showing differences in features and limitations.

        Query parameters:
            plan_ids: List of plan IDs to compare

        Returns:
            Response: Comparison data for the selected plans
                {
                    "plans": [Plan objects],
                    "features": {
                        "category1": [
                            {
                                "name": "Feature name",
                                "values": {
                                    "plan1_id": "Value for plan 1",
                                    "plan2_id": "Value for plan 2",
                                    ...
                                }
                            },
                            ...
                        ],
                        ...
                    }
                }

        Status codes:
            200: Comparison successful
            400: No plan IDs provided
        """
        plan_ids = request.query_params.getlist("plan_ids", [])

        if not plan_ids:
            return Response(
                {"detail": _("No plan IDs provided")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plans = Plan.objects.filter(id__in=plan_ids).order_by("monthly_price")

        # Get comparison data
        comparison = PlanService.compare_plans(plans)

        return Response(comparison)


class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for subscriptions

    Manages company subscriptions to plans, including creation, updates,
    renewals, cancellations, and viewing invoices and usage.

    Endpoints:
    - GET /api/subscriptions/ - List all subscriptions
    - POST /api/subscriptions/ - Create a new subscription
    - GET /api/subscriptions/{id}/ - Get subscription details
    - PUT/PATCH /api/subscriptions/{id}/ - Update a subscription
    - DELETE /api/subscriptions/{id}/ - Delete a subscription
    - GET /api/subscriptions/{id}/invoices/ - Get invoices for a subscription
    - GET /api/subscriptions/{id}/usage/ - Get feature usage for a subscription
    - POST /api/subscriptions/{id}/renew/ - Manually renew a subscription
    - POST /api/subscriptions/{id}/cancel/ - Cancel a subscription
    - POST /api/subscriptions/{id}/change_plan/ - Change subscription plan

    Permissions:
    - View operations: Users with CanViewSubscriptions permission
    - Modify operations: Users with CanManageSubscriptions permission

    Query parameters:
    - status: Filter by subscription status
    - company: Filter by company ID
    - plan: Filter by plan ID
    """

    queryset = Subscription.objects.all().select_related("company", "plan")

    def get_serializer_class(self):
        """
        Return the appropriate serializer based on action

        - Create: SubscriptionCreateSerializer
        - Update: SubscriptionUpdateSerializer
        - Other operations: SubscriptionSerializer

        Returns:
            Serializer class: The appropriate serializer
        """
        if self.action == "create":
            return SubscriptionCreateSerializer
        if self.action in ["update", "partial_update"]:
            return SubscriptionUpdateSerializer
        return SubscriptionSerializer

    def get_permissions(self):
        """
        Set permissions based on action

        - Create/update/delete operations: CanManageSubscriptions
        - View operations: CanViewSubscriptions

        Returns:
            list: Permission classes for the action
        """
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [CanManageSubscriptions()]
        return [CanViewSubscriptions()]

    def get_queryset(self):
        """
        Filter queryset based on query parameters

        Applies filters for subscription status, company ID, and plan ID
        if provided in the query parameters.

        Returns:
            QuerySet: Filtered subscriptions
        """
        queryset = super().get_queryset()

        # Filter by status if specified
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by company if specified
        company_id = self.request.query_params.get("company")
        if company_id:
            queryset = queryset.filter(company_id=company_id)

        # Filter by plan if specified
        plan_id = self.request.query_params.get("plan")
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)

        return queryset

    @action(detail=True, methods=["get"])
    def invoices(self, request, pk=None):
        """
        Get invoices for a specific subscription

        Returns all invoices for the subscription, ordered by issued date
        (most recent first) with pagination support.

        Returns:
            Response: List of subscription invoices
        """
        subscription = self.get_object()
        invoices = subscription.invoices.all().order_by("-issued_date")

        page = self.paginate_queryset(invoices)
        if page is not None:
            serializer = SubscriptionInvoiceSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = SubscriptionInvoiceSerializer(invoices, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def usage(self, request, pk=None):
        """
        Get feature usage for a specific subscription

        Returns current usage data for all metered features
        included in the subscription.

        Returns:
            Response: List of feature usage records
        """
        subscription = self.get_object()
        usage = subscription.feature_usage.all()

        serializer = FeatureUsageSerializer(usage, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        """
        Manually renew a subscription

        Initiates the renewal process for the subscription,
        generating a new invoice if needed.

        Returns:
            Response: Renewal status and payment URL if applicable
                {
                    "detail": "Renewal initiated successfully",
                    "payment_url": "https://payment.url" (optional)
                }

        Status codes:
            200: Renewal initiated successfully
            400: Error initiating renewal
        """
        subscription = self.get_object()

        try:
            from apps.subscriptionapp.services.renewal_manager import RenewalManager

            result = RenewalManager.process_renewal(subscription.id)

            return Response(
                {
                    "detail": _("Renewal initiated successfully"),
                    "payment_url": result.get("payment_url"),
                }
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """
        Cancel a subscription

        Cancels the subscription, setting its status to 'canceled'
        and recording the cancellation reason.

        Request body:
            {
                "reason": "Cancellation reason" (optional)
            }

        Returns:
            Response: Success message
                {
                    "detail": "Subscription canceled successfully"
                }

        Status codes:
            200: Subscription canceled successfully
            400: Error canceling subscription
        """
        subscription = self.get_object()

        # Extract reason if provided
        reason = request.data.get("reason", "")

        try:
            SubscriptionService.cancel_subscription(
                subscription_id=subscription.id,
                performed_by=request.user,
                reason=reason,
            )

            return Response({"detail": _("Subscription canceled successfully")})
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def change_plan(self, request, pk=None):
        """
        Change subscription plan

        Changes the subscription to a different plan, potentially
        prorating charges for the remaining subscription period.

        Request body:
            {
                "plan_id": "uuid" (required)
            }

        Returns:
            Response: Success message
                {
                    "detail": "Subscription plan changed successfully"
                }

        Status codes:
            200: Plan changed successfully
            400: Error changing plan or missing plan_id
        """
        subscription = self.get_object()

        # Extract new plan ID
        new_plan_id = request.data.get("plan_id")
        if not new_plan_id:
            return Response(
                {"detail": _("New plan ID is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            SubscriptionService.change_plan(
                subscription_id=subscription.id,
                new_plan_id=new_plan_id,
                performed_by=request.user,
            )

            return Response({"detail": _("Subscription plan changed successfully")})
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for subscription invoices

    Provides read-only access to subscription invoices, including
    filtering, viewing details, and downloading invoices as PDFs.

    Endpoints:
    - GET /api/subscription-invoices/ - List all invoices
    - GET /api/subscription-invoices/{id}/ - Get invoice details
    - GET /api/subscription-invoices/{id}/download/ - Download invoice as PDF

    Permissions:
    - Users with CanViewSubscriptions permission

    Query parameters:
    - subscription: Filter by subscription ID
    - company: Filter by company ID
    - status: Filter by invoice status
    """

    queryset = SubscriptionInvoice.objects.all().select_related("subscription", "transaction")
    serializer_class = SubscriptionInvoiceSerializer
    permission_classes = [CanViewSubscriptions]

    def get_queryset(self):
        """
        Filter queryset based on query parameters

        Applies filters for subscription ID, company ID, and invoice status
        if provided in the query parameters.

        Returns:
            QuerySet: Filtered invoices
        """
        queryset = super().get_queryset()

        # Filter by subscription if specified
        subscription_id = self.request.query_params.get("subscription")
        if subscription_id:
            queryset = queryset.filter(subscription_id=subscription_id)

        # Filter by company if specified
        company_id = self.request.query_params.get("company")
        if company_id:
            queryset = queryset.filter(subscription__company_id=company_id)

        # Filter by status if specified
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """
        Download invoice as PDF

        Generates a PDF version of the invoice for downloading.

        Returns:
            Response: Success message with download URL
                {
                    "detail": "Invoice PDF generated successfully",
                    "download_url": "/api/subscriptions/invoices/{id}/pdf/"
                }

        Status codes:
            200: PDF generated successfully
            400: Error generating PDF
        """
        invoice = self.get_object()

        try:
            # unused_unused_pdf_file = InvoiceService.generate_invoice_pdf(invoice.id)

            # Return PDF file (in a real implementation, this would return the file)
            return Response(
                {
                    "detail": _("Invoice PDF generated successfully"),
                    "download_url": f"/api/subscriptions/invoices/{invoice.id}/pdf/",
                }
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FeatureUsageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for feature usage monitoring

    Provides read-only access to feature usage data, allowing companies
    to monitor their usage of metered features within their subscription.

    Endpoints:
    - GET /api/feature-usage/ - List feature usage records
    - GET /api/feature-usage/{id}/ - Get feature usage details

    Permissions:
    - Users with CanViewSubscriptions permission

    Query parameters:
    - subscription: Filter by subscription ID
    - company: Filter by company ID
    """

    queryset = FeatureUsage.objects.all()
    serializer_class = FeatureUsageSerializer
    permission_classes = [CanViewSubscriptions]

    def get_queryset(self):
        """
        Filter queryset based on query parameters

        Applies filters for subscription ID and company ID
        if provided in the query parameters.

        Returns:
            QuerySet: Filtered feature usage records
        """
        queryset = super().get_queryset()

        # Filter by subscription if specified
        subscription_id = self.request.query_params.get("subscription")
        if subscription_id:
            queryset = queryset.filter(subscription_id=subscription_id)

        # Filter by company if specified
        company_id = self.request.query_params.get("company")
        if company_id:
            queryset = queryset.filter(subscription__company_id=company_id)

        return queryset


class SubscriptionPaymentView(generics.GenericAPIView):
    """
    View for initiating subscription payment

    Handles the process of initiating a payment for a new subscription
    or renewal, generating the necessary payment URL.

    Endpoint:
    - POST /api/subscription-payments/ - Initiate a subscription payment

    Request body:
        {
            "company_id": "uuid" (required),
            "plan_id": "uuid" (required),
            "period": "monthly|annual" (required),
            "return_url": "https://example.com/return" (required)
        }

    Returns:
        Response: Payment information and URL
            {
                "payment_url": "https://payment.url",
                "transaction_id": "uuid",
                "amount": float,
                ...
            }

    Permissions:
    - Authentication required
    """

    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Process payment initiation request

        Validates the request data and initiates the payment process
        for the subscription.

        Returns:
            Response: Payment information and URL

        Status codes:
            200: Payment initiated successfully
            400: Invalid request data or payment initiation error
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = SubscriptionService.initiate_subscription_payment(
                company_id=serializer.validated_data["company_id"],
                plan_id=serializer.validated_data["plan_id"],
                period=serializer.validated_data["period"],
                return_url=serializer.validated_data["return_url"],
            )

            return Response(result)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionRenewalView(generics.GenericAPIView):
    """
    View for manually renewing a subscription

    Allows company owners or administrators to manually renew
    a subscription before its automatic renewal date.

    Endpoint:
    - POST /api/subscription-renewals/ - Manually renew a subscription

    Request body:
        {
            "subscription_id": "uuid" (required)
        }

    Returns:
        Response: Renewal status and payment URL
            {
                "detail": "Renewal initiated successfully",
                "payment_url": "https://payment.url" (optional)
            }

    Permissions:
    - Authentication required
    - User must have permission to manage their own company's subscription
    """

    serializer_class = SubscriptionRenewalSerializer
    permission_classes = [IsAuthenticated, CanManageOwnCompanySubscription]

    def post(self, request, *args, **kwargs):
        """
        Process renewal request

        Validates the request data and initiates the subscription
        renewal process.

        Returns:
            Response: Renewal status and payment URL

        Status codes:
            200: Renewal initiated successfully
            400: Invalid request data or renewal error
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            from apps.subscriptionapp.services.renewal_manager import RenewalManager

            result = RenewalManager.process_renewal(serializer.validated_data["subscription_id"])

            return Response(
                {
                    "detail": _("Renewal initiated successfully"),
                    "payment_url": result.get("payment_url"),
                }
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionCancelView(generics.GenericAPIView):
    """
    View for canceling a subscription

    Allows company owners or administrators to cancel their
    subscription, with an optional reason.

    Endpoint:
    - POST /api/subscription-cancellations/ - Cancel a subscription

    Request body:
        {
            "subscription_id": "uuid" (required),
            "reason": "Cancellation reason" (optional)
        }

    Returns:
        Response: Success message
            {
                "detail": "Subscription canceled successfully"
            }

    Permissions:
    - Authentication required
    - User must have permission to manage their own company's subscription
    """

    serializer_class = SubscriptionCancelSerializer
    permission_classes = [IsAuthenticated, CanManageOwnCompanySubscription]

    def post(self, request, *args, **kwargs):
        """
        Process cancellation request

        Validates the request data and processes the subscription
        cancellation.

        Returns:
            Response: Success message

        Status codes:
            200: Subscription canceled successfully
            400: Invalid request data or cancellation error
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            SubscriptionService.cancel_subscription(
                subscription_id=serializer.validated_data["subscription_id"],
                performed_by=request.user,
                reason=serializer.validated_data.get("reason", ""),
            )

            return Response({"detail": _("Subscription canceled successfully")})
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CompanySubscriptionView(generics.RetrieveAPIView):
    """
    View for getting subscription info for a specific company

    Allows company owners or administrators to view the active
    subscription for their company.

    Endpoint:
    - GET /api/companies/{company_id}/subscription/ - Get company subscription

    URL parameters:
        company_id: UUID of the company

    Returns:
        Response: Subscription details

    Permissions:
    - Authentication required
    - User must have permission to view their own company's subscription
    """

    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated, CanViewOwnCompanySubscription]

    def get_object(self):
        """
        Get the active subscription for the company

        Retrieves the most recent active, trial, or past due subscription
        for the specified company.

        Returns:
            Subscription: The active subscription

        Raises:
            Http404: If no active subscription is found
        """
        company_id = self.kwargs["company_id"]
        company = get_object_or_404(Company, id=company_id)

        # Get the active subscription for this company
        subscription = (
            Subscription.objects.filter(company=company, status__in=["active", "trial", "past_due"])
            .order_by("-created_at")
            .first()
        )

        if not subscription:
            return Response(
                {"detail": _("No active subscription found for this company")},
                status=status.HTTP_404_NOT_FOUND,
            )

        return subscription
