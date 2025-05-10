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
    """ViewSet for subscription plans"""

    queryset = Plan.objects.all().order_by("position", "monthly_price")
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return PlanCreateUpdateSerializer
        return PlanSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            # Only Queue Me admins can manage plans
            return [CanManageSubscriptions()]

        # Anyone can view plans
        return [IsAuthenticated()]

    @action(detail=True, methods=["get"])
    def features(self, request, pk=None):
        """Get features for a specific plan"""
        plan = self.get_object()
        features = plan.features.all().order_by("category", "tier")

        from .serializers import PlanFeatureSerializer

        serializer = PlanFeatureSerializer(features, many=True)

        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def compare(self, request):
        """Compare multiple plans side by side"""
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
    """ViewSet for subscriptions"""

    queryset = Subscription.objects.all().select_related("company", "plan")

    def get_serializer_class(self):
        if self.action == "create":
            return SubscriptionCreateSerializer
        if self.action in ["update", "partial_update"]:
            return SubscriptionUpdateSerializer
        return SubscriptionSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [CanManageSubscriptions()]
        return [CanViewSubscriptions()]

    def get_queryset(self):
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
        """Get invoices for a specific subscription"""
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
        """Get feature usage for a specific subscription"""
        subscription = self.get_object()
        usage = subscription.feature_usage.all()

        serializer = FeatureUsageSerializer(usage, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        """Manually renew a subscription"""
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
        """Cancel a subscription"""
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
        """Change subscription plan"""
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
    """ViewSet for subscription invoices"""

    queryset = SubscriptionInvoice.objects.all().select_related(
        "subscription", "transaction"
    )
    serializer_class = SubscriptionInvoiceSerializer
    permission_classes = [CanViewSubscriptions]

    def get_queryset(self):
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
        """Download invoice as PDF"""
        invoice = self.get_object()

        try:
            unused_unused_pdf_file = InvoiceService.generate_invoice_pdf(invoice.id)

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
    """ViewSet for feature usage monitoring"""

    queryset = FeatureUsage.objects.all()
    serializer_class = FeatureUsageSerializer
    permission_classes = [CanViewSubscriptions]

    def get_queryset(self):
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
    """View for initiating subscription payment"""

    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
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
    """View for manually renewing a subscription"""

    serializer_class = SubscriptionRenewalSerializer
    permission_classes = [IsAuthenticated, CanManageOwnCompanySubscription]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            from apps.subscriptionapp.services.renewal_manager import RenewalManager

            result = RenewalManager.process_renewal(
                serializer.validated_data["subscription_id"]
            )

            return Response(
                {
                    "detail": _("Renewal initiated successfully"),
                    "payment_url": result.get("payment_url"),
                }
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionCancelView(generics.GenericAPIView):
    """View for canceling a subscription"""

    serializer_class = SubscriptionCancelSerializer
    permission_classes = [IsAuthenticated, CanManageOwnCompanySubscription]

    def post(self, request, *args, **kwargs):
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
    """View for getting subscription info for a specific company"""

    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated, CanViewOwnCompanySubscription]

    def get_object(self):
        company_id = self.kwargs["company_id"]
        company = get_object_or_404(Company, id=company_id)

        # Get the active subscription for this company
        subscription = (
            Subscription.objects.filter(
                company=company, status__in=["active", "trial", "past_due"]
            )
            .order_by("-created_at")
            .first()
        )

        if not subscription:
            return Response(
                {"detail": _("No active subscription found for this company")},
                status=status.HTTP_404_NOT_FOUND,
            )

        return subscription
