# apps/companiesapp/tests/test_views.py
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.companiesapp.models import Company, CompanyDocument
from apps.geoapp.models import Location


class CompanyViewSetTestCase(TestCase):
    def setUp(self):
        # Create test users
        self.client = APIClient()

        # Admin user
        self.admin_user = User.objects.create(
            phone_number="9876543210",
            user_type="admin",
            is_verified=True,
            is_staff=True,
            is_superuser=True,
        )

        # Regular user (company owner)
        self.user = User.objects.create(
            phone_number="1234567890", user_type="customer", is_verified=True
        )

        # Another regular user
        self.other_user = User.objects.create(
            phone_number="5556667777", user_type="customer", is_verified=True
        )

        # Create test location
        self.location = Location.objects.create(
            latitude=24.7136,
            longitude=46.6753,
            country="Saudi Arabia",
            city="Riyadh",
            address="Test Address",
        )

        # Create test company
        self.company = Company.objects.create(
            name="Test Company",
            owner=self.user,
            contact_phone="1234567890",
            location=self.location,
        )

    def test_list_companies_as_admin(self):
        """Test admin can list all companies"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("company-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_list_companies_as_owner(self):
        """Test owner can only see their own companies"""
        self.client.force_authenticate(user=self.user)
        url = reverse("company-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Test Company")

    def test_list_companies_as_other_user(self):
        """Test other users can only see their own companies (none)"""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("company-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_retrieve_company_as_owner(self):
        """Test owner can retrieve their company"""
        self.client.force_authenticate(user=self.user)
        url = reverse("company-detail", args=[self.company.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Company")

    def test_update_company_as_owner(self):
        """Test owner can update their company"""
        self.client.force_authenticate(user=self.user)
        url = reverse("company-detail", args=[self.company.id])
        data = {"name": "Updated Company Name", "contact_phone": "9998887777"}
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Company Name")

        # Refresh from database
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "Updated Company Name")
        self.assertEqual(self.company.contact_phone, "9998887777")

    def test_update_company_as_other_user(self):
        """Test other users cannot update company"""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("company-detail", args=[self.company.id])
        data = {
            "name": "Unauthorized Update",
        }
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify no change
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "Test Company")

    def test_create_company(self):
        """Test creating a new company"""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("company-list")

        # Mock the permission checker
        with patch(
            "apps.rolesapp.services.permission_resolver.PermissionResolver.has_permission"
        ) as mock_has_perm:
            mock_has_perm.return_value = True

            data = {
                "name": "New Test Company",
                "contact_phone": "1231231234",
                "description": "A test company",
            }
            response = self.client.post(url, data)

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data["name"], "New Test Company")

            # Verify company was created with correct owner
            company = Company.objects.get(name="New Test Company")
            self.assertEqual(company.owner, self.other_user)

    def test_update_settings(self):
        """Test updating company settings"""
        self.client.force_authenticate(user=self.user)
        url = reverse("company-settings", args=[self.company.id])
        data = {"default_language": "en", "notification_sms": False}
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["default_language"], "en")
        self.assertFalse(response.data["notification_sms"])

        # Verify changes in database
        self.company.settings.refresh_from_db()
        self.assertEqual(self.company.settings.default_language, "en")
        self.assertFalse(self.company.settings.notification_sms)


class CompanyDocumentViewSetTestCase(TestCase):
    def setUp(self):
        # Create test users and company
        self.client = APIClient()

        # Company owner
        self.user = User.objects.create(
            phone_number="1234567890", user_type="customer", is_verified=True
        )

        # Admin user
        self.admin_user = User.objects.create(
            phone_number="9876543210",
            user_type="admin",
            is_verified=True,
            is_staff=True,
        )

        # Create test company
        self.company = Company.objects.create(
            name="Test Company", owner=self.user, contact_phone="1234567890"
        )

        # Create test document
        self.document = CompanyDocument.objects.create(
            company=self.company, title="Test Document", document_type="License"
        )

    def test_list_documents(self):
        """Test listing company documents"""
        self.client.force_authenticate(user=self.user)
        url = reverse("company-documents-list", args=[self.company.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Test Document")

    def test_create_document(self):
        """Test creating a company document"""
        self.client.force_authenticate(user=self.user)
        url = reverse("company-documents-list", args=[self.company.id])
        data = {"title": "New Document", "document_type": "Certificate"}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "New Document")

        # Verify in database
        doc = CompanyDocument.objects.get(title="New Document")
        self.assertEqual(doc.company, self.company)

    def test_verify_document(self):
        """Test verifying a document (admin only)"""
        self.client.force_authenticate(user=self.admin_user)

        # Mock the permission checker
        with patch(
            "apps.rolesapp.services.permission_resolver.PermissionResolver.has_permission"
        ) as mock_has_perm:
            mock_has_perm.return_value = True

            url = reverse(
                "company-documents-verify", args=[self.company.id, self.document.id]
            )
            data = {"is_verified": True}
            response = self.client.patch(url, data)

            self.assertEqual(response.status_code, status.HTTP_200_OK)

            # Verify in database
            self.document.refresh_from_db()
            self.assertTrue(self.document.is_verified)
            self.assertEqual(self.document.verified_by, self.admin_user)
            self.assertIsNotNone(self.document.verified_at)

    def test_delete_document(self):
        """Test deleting a document"""
        self.client.force_authenticate(user=self.user)
        url = reverse(
            "company-documents-detail", args=[self.company.id, self.document.id]
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify document is deleted
        with self.assertRaises(CompanyDocument.DoesNotExist):
            CompanyDocument.objects.get(id=self.document.id)
