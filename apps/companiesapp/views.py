# apps/companiesapp/views.py
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Company, CompanyDocument
from .permissions import (
    CanManageCompanyDocuments,
    HasCompanyPermission,
    IsAdminOrCompanyOwner,
)
from .serializers import (
    CompanyDocumentSerializer,
    CompanySerializer,
    CompanySettingsSerializer,
    VerifyCompanyDocumentSerializer,
)
from .services.company_service import CompanyService


class CompanyViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing companies.
    """

    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "subscription_status"]
    search_fields = [
        "name",
        "owner__phone_number",
        "contact_phone",
        "registration_number",
    ]
    ordering_fields = ["name", "created_at", "subscription_status", "shop_count"]
    ordering = ["-created_at"]

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action == "list" or self.action == "retrieve":
            permission_classes = [permissions.IsAuthenticated]
        elif self.action == "create":
            permission_classes = [HasCompanyPermission("company", "add")]
        elif self.action in ["update", "partial_update", "destroy"]:
            permission_classes = [IsAdminOrCompanyOwner]
        elif self.action == "verify":
            permission_classes = [HasCompanyPermission("company", "edit")]
        else:
            permission_classes = [permissions.IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """
        Filter queryset based on user's role
        """
        user = self.request.user

        # Queue Me admins see all companies
        if user.user_type == "admin":
            return Company.objects.all()

        # Regular users only see their own companies
        return Company.objects.filter(owner=user)

    def perform_create(self, serializer):
        """Create a new company"""
        # Set owner to current user if not specified
        if "owner_id" not in serializer.validated_data:
            serializer.save(owner=self.request.user)
        else:
            serializer.save()

    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[HasCompanyPermission("company", "edit")],
    )
    def verify(self, request, pk=None):
        """
        Verify a company (Queue Me admin only)
        """
        company = self.get_object()
        CompanyService.verify_company(company, request.user)
        return Response({"status": "company verified"})

    @action(detail=True, methods=["get"], permission_classes=[IsAdminOrCompanyOwner])
    def subscription_status(self, request, pk=None):
        """
        Get detailed subscription status
        """
        company = self.get_object()
        subscription_info = CompanyService.get_subscription_info(company)
        return Response(subscription_info)

    @action(detail=True, methods=["patch"], permission_classes=[IsAdminOrCompanyOwner])
    def settings(self, request, pk=None):
        """
        Update company settings
        """
        company = self.get_object()

        if not hasattr(company, "settings"):
            return Response(
                {"detail": "Settings not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = CompanySettingsSerializer(
            company.settings, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[IsAdminOrCompanyOwner])
    def statistics(self, request, pk=None):
        """
        Get company statistics
        """
        company = self.get_object()
        stats = CompanyService.generate_company_statistics(company)
        return Response(stats)


class CompanyDocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing company documents.
    """

    serializer_class = CompanyDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageCompanyDocuments]

    def get_queryset(self):
        company_id = self.kwargs.get("company_id")
        company = get_object_or_404(Company, id=company_id)
        return CompanyDocument.objects.filter(company=company)

    def perform_create(self, serializer):
        company_id = self.kwargs.get("company_id")
        company = get_object_or_404(Company, id=company_id)
        serializer.save(company=company)

    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[HasCompanyPermission("company", "edit")],
    )
    def verify(self, request, company_id=None, pk=None):
        """
        Verify a company document (Queue Me admin only)
        """
        document = self.get_object()
        serializer = VerifyCompanyDocumentSerializer(document, data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data.get("is_verified"):
            document.is_verified = True
            document.verified_by = request.user
            document.verified_at = timezone.now()
            document.save()

        return Response({"status": "document verified"})
