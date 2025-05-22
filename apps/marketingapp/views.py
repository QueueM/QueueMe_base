"""
API views for Marketing app.
"""

import logging

from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    AdPayment,
    Advertisement,
    Campaign,
)
from .serializers import (
    AdPaymentSerializer,
    AdStatusChoiceSerializer,
    AdTypeChoiceSerializer,
    AdvertisementSerializer,
    CampaignSerializer,
    TargetingTypeChoiceSerializer,
)
from .services.ad_analytics_service import AdAnalyticsService
from .services.ad_management_service import AdManagementService
from .services.ad_payment_service import AdPaymentService
from .services.ad_serving_service import AdServingService

logger = logging.getLogger(__name__)


class CampaignViewSet(viewsets.ModelViewSet):
    """ViewSet for Campaign model"""

    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter campaigns by user's company or shop"""
        queryset = super().get_queryset()

        # Get query parameters
        company_id = self.request.query_params.get("company_id")
        shop_id = self.request.query_params.get("shop_id")
        is_active = self.request.query_params.get("is_active")

        # Filter by company
        if company_id:
            queryset = queryset.filter(company_id=company_id)

        # Filter by shop
        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)

        # Filter by active status
        if is_active is not None:
            is_active_bool = is_active.lower() == "true"
            queryset = queryset.filter(is_active=is_active_bool)

        return queryset

    @action(detail=True, methods=["get"])
    def ads(self, request, pk=None):
        """Get all advertisements for a campaign"""
        campaign = self.get_object()
        ads = Advertisement.objects.filter(campaign=campaign)
        serializer = AdvertisementSerializer(ads, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def performance(self, request, pk=None):
        """Get campaign performance metrics"""
        campaign = self.get_object()

        # Parse date range if provided
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if start_date:
            start_date = timezone.datetime.fromisoformat(start_date)

        if end_date:
            end_date = timezone.datetime.fromisoformat(end_date)

        # Get performance metrics
        performance = AdAnalyticsService.get_campaign_performance(
            str(campaign.id), start_date, end_date
        )

        return Response(performance)


class AdvertisementViewSet(viewsets.ModelViewSet):
    """ViewSet for Advertisement model"""

    queryset = Advertisement.objects.all()
    serializer_class = AdvertisementSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """Filter advertisements by parameters"""
        queryset = super().get_queryset()

        # Get query parameters
        campaign_id = self.request.query_params.get("campaign_id")
        status = self.request.query_params.get("status")
        ad_type = self.request.query_params.get("ad_type")
        shop_id = self.request.query_params.get("shop_id")

        # Filter by campaign
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)

        # Filter by status
        if status:
            queryset = queryset.filter(status=status)

        # Filter by ad type
        if ad_type:
            queryset = queryset.filter(ad_type=ad_type)

        # Filter by shop
        if shop_id:
            queryset = queryset.filter(campaign__shop_id=shop_id)

        return queryset

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        """Update the status of an advertisement"""
        advertisement = self.get_object()

        # Get status from request
        status = request.data.get("status")
        if not status:
            return Response(
                {"error": "Status is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Update status
        result = AdManagementService.update_advertisement_status(
            str(advertisement.id), status
        )

        if result["success"]:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def performance(self, request, pk=None):
        """Get advertisement performance metrics"""
        advertisement = self.get_object()

        # Parse date range if provided
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if start_date:
            start_date = timezone.datetime.fromisoformat(start_date)

        if end_date:
            end_date = timezone.datetime.fromisoformat(end_date)

        # Get performance metrics
        performance = AdAnalyticsService.get_ad_performance(
            str(advertisement.id), start_date, end_date
        )

        return Response(performance)

    @action(detail=True, methods=["post"])
    def process_payment(self, request, pk=None):
        """Process payment for an advertisement"""
        advertisement = self.get_object()

        # Get payment data from request
        amount = request.data.get("amount")
        payment_method = request.data.get("payment_method")
        payment_data = request.data.get("payment_data", {})

        if not amount or not payment_method:
            return Response(
                {"error": "Amount and payment method are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Process payment
        result = AdPaymentService.process_payment(
            str(advertisement.id), float(amount), payment_method, payment_data
        )

        if result["success"]:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


class AdPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for AdPayment model (read-only)"""

    queryset = AdPayment.objects.all()
    serializer_class = AdPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter payments by parameters"""
        queryset = super().get_queryset()

        # Get query parameters
        advertisement_id = self.request.query_params.get("advertisement_id")
        campaign_id = self.request.query_params.get("campaign_id")
        shop_id = self.request.query_params.get("shop_id")

        # Filter by advertisement
        if advertisement_id:
            queryset = queryset.filter(advertisement_id=advertisement_id)

        # Filter by campaign
        if campaign_id:
            queryset = queryset.filter(advertisement__campaign_id=campaign_id)

        # Filter by shop
        if shop_id:
            queryset = queryset.filter(advertisement__campaign__shop_id=shop_id)

        return queryset

    @action(detail=True, methods=["get"])
    def invoice(self, request, pk=None):
        """Get invoice details for a payment"""
        payment = self.get_object()

        # Generate invoice
        invoice = AdPaymentService.generate_invoice(str(payment.id))

        if invoice["success"]:
            return Response(invoice)
        else:
            return Response(invoice, status=status.HTTP_400_BAD_REQUEST)


class AdServingView(generics.CreateAPIView):
    """View for serving ads to users"""

    permission_classes = []  # No authentication required for ad serving

    def create(self, request, *args, **kwargs):
        """Get ads for a user"""
        # Get parameters from request
        user_id = request.data.get("user_id")
        session_id = request.data.get("session_id")
        city_id = request.data.get("city_id")
        category_ids = request.data.get("category_ids", [])
        count = int(request.data.get("count", 1))

        # Get ads
        result = AdServingService.get_ads_for_user(
            user_id, session_id, city_id, category_ids, count
        )

        return Response(result)


class AdClickView(generics.CreateAPIView):
    """View for recording ad clicks"""

    permission_classes = []  # No authentication required for ad clicks

    def create(self, request, *args, **kwargs):
        """Record an ad click"""
        # Get parameters from request
        ad_id = request.data.get("ad_id")
        user_id = request.data.get("user_id")
        session_id = request.data.get("session_id")
        ip_address = request.data.get("ip_address")
        city_id = request.data.get("city_id")
        referrer = request.data.get("referrer")

        if not ad_id:
            return Response(
                {"error": "Ad ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Record click
        result = AdServingService.record_ad_click(
            ad_id, user_id, session_id, ip_address, city_id, referrer
        )

        return Response(result)


class AdConversionView(generics.CreateAPIView):
    """View for recording ad conversions"""

    permission_classes = []  # No authentication required for conversions

    def create(self, request, *args, **kwargs):
        """Record an ad conversion"""
        # Get parameters from request
        ad_id = request.data.get("ad_id")
        booking_id = request.data.get("booking_id")
        user_id = request.data.get("user_id")
        session_id = request.data.get("session_id")

        if not ad_id or not booking_id:
            return Response(
                {"error": "Ad ID and booking ID are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Record conversion
        result = AdServingService.record_conversion(
            ad_id, booking_id, user_id, session_id
        )

        return Response(result)


class ShopAdvertisingOverviewView(generics.RetrieveAPIView):
    """View for getting an overview of shop advertising"""

    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        """Get advertising overview for a shop"""
        # Get shop ID from URL
        shop_id = kwargs.get("shop_id")

        if not shop_id:
            return Response(
                {"error": "Shop ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Parse date range if provided
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if start_date:
            start_date = timezone.datetime.fromisoformat(start_date)

        if end_date:
            end_date = timezone.datetime.fromisoformat(end_date)

        # Get overview
        overview = AdAnalyticsService.get_shop_advertising_overview(
            shop_id, start_date, end_date
        )

        return Response(overview)


class MetadataView(generics.RetrieveAPIView):
    """View for getting metadata for ad creation"""

    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        """Get ad types, statuses, and targeting types"""
        data = {
            "ad_types": AdTypeChoiceSerializer.get_choices(),
            "ad_statuses": AdStatusChoiceSerializer.get_choices(),
            "targeting_types": TargetingTypeChoiceSerializer.get_choices(),
        }

        return Response(data)
