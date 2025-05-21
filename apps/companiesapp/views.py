"""
Companies app views for QueueMe platform
Handles endpoints related to companies, company settings, documents, and verification.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Company, CompanyDocument
from .permissions import CanManageCompanyDocuments, HasCompanyPermission, IsAdminOrCompanyOwner
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

    Allows creation, retrieval, updating, and deletion of companies.
    Different permission levels apply based on user role (admin, company owner, or general user).

    Endpoints:
    - GET /api/companies/ - List companies (filtered by permissions)
    - POST /api/companies/ - Create a new company (requires 'add' permission)
    - GET /api/companies/{id}/ - Retrieve company details
    - PUT/PATCH /api/companies/{id}/ - Update company (admin or owner only)
    - DELETE /api/companies/{id}/ - Delete company (admin or owner only)
    - PATCH /api/companies/{id}/verify/ - Verify a company (admin only)
    - GET /api/companies/{id}/subscription_status/ - Get subscription details
    - PATCH /api/companies/{id}/settings/ - Update company settings
    - GET /api/companies/{id}/statistics/ - Get company statistics

    Filtering:
    - is_active: Filter by active status
    - subscription_status: Filter by subscription status

    Search fields:
    - name: Company name
    - owner__phone_number: Owner's phone number
    - contact_phone: Company contact phone
    - registration_number: Company registration number

    Ordering:
    - name: Company name
    - created_at: Creation date
    - subscription_status: Subscription status
    - shop_count: Number of shops
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

        Different permissions apply based on the action:
        - list/retrieve: Any authenticated user
        - create: User must have 'add' permission on companies
        - update/delete: Admin or company owner only
        - verify: User must have 'edit' permission on companies

        Returns:
            list: List of permission classes
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
        Filter queryset based on user's role.

        - Admins can see all companies
        - Regular users only see their own companies

        Returns:
            QuerySet: Filtered list of companies
        """
        user = self.request.user

        # Queue Me admins see all companies
        if user.user_type == "admin":
            return Company.objects.all()

        # Regular users only see their own companies
        return Company.objects.filter(owner=user)

    def perform_create(self, serializer):
        """
        Create a new company.

        Sets the owner to the current user if not explicitly specified.

        Args:
            serializer: The company serializer instance
        """
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
        Verify a company (Queue Me admin only).

        Changes a company's verification status to verified.
        This is typically done after reviewing company documents and information.

        Returns:
            Response: Success message
        """
        company = self.get_object()
        CompanyService.verify_company(company, request.user)
        return Response({"status": "company verified"})

    @action(detail=True, methods=["get"], permission_classes=[IsAdminOrCompanyOwner])
    def subscription_status(self, request, pk=None):
        """
        Get detailed subscription status.

        Returns detailed information about the company's subscription including:
        - Current status
        - Plan details
        - Expiration date
        - Payment history

        Returns:
            Response: JSON object with subscription details
        """
        company = self.get_object()
        subscription_info = CompanyService.get_subscription_info(company)
        return Response(subscription_info)

    @action(detail=True, methods=["patch"], permission_classes=[IsAdminOrCompanyOwner])
    def settings(self, request, pk=None):
        """
        Update company settings.

        Updates various configuration settings for the company such as:
        - Notification preferences
        - Branding settings
        - Default configurations

        Request Body:
            JSON object with settings fields to update

        Returns:
            Response: Updated settings object

        Status Codes:
            200: Settings updated successfully
            404: Settings not found
        """
        company = self.get_object()

        if not hasattr(company, "settings"):
            return Response({"detail": "Settings not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CompanySettingsSerializer(company.settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[IsAdminOrCompanyOwner])
    def statistics(self, request, pk=None):
        """
        Get company statistics.

        Returns aggregated statistics about the company, such as:
        - Total shops count
        - Total revenue
        - Customer counts
        - Booking metrics
        - Growth trends

        Returns:
            Response: JSON object with company statistics
        """
        company = self.get_object()
        stats = CompanyService.generate_company_statistics(company)
        return Response(stats)


class CompanyDocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing company documents.

    Allows uploading, viewing, updating, and deleting company verification documents.
    Documents must be associated with a specific company.

    Endpoints:
    - GET /api/companies/{company_id}/documents/ - List documents for a company
    - POST /api/companies/{company_id}/documents/ - Upload a new document
    - GET /api/companies/{company_id}/documents/{id}/ - Get document details
    - PUT /api/companies/{company_id}/documents/{id}/ - Update document
    - DELETE /api/companies/{company_id}/documents/{id}/ - Delete document
    - PATCH /api/companies/{company_id}/documents/{id}/verify/ - Verify document (admin only)

    Permissions:
    - User must be authenticated
    - User must have permission to manage company documents
    """

    queryset = CompanyDocument.objects.all()
    serializer_class = CompanyDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageCompanyDocuments]

    def get_queryset(self):
        """
        Filter documents by company.

        Returns only documents for the specified company.

        Returns:
            QuerySet: Filtered list of company documents
        """
        company_id = self.kwargs.get("company_id")
        company = get_object_or_404(Company, id=company_id)
        return CompanyDocument.objects.filter(company=company)

    def perform_create(self, serializer):
        """
        Create a new company document.

        Associates the document with the specified company.

        Args:
            serializer: The document serializer instance
        """
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
        Verify a company document (Queue Me admin only).

        Marks a document as verified, which contributes to the company's overall verification status.
        Records which admin performed the verification and when.

        Request Body:
            {
                "is_verified": boolean (required)
            }

        Returns:
            Response: Success message
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
