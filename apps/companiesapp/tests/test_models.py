# apps/companiesapp/tests/test_models.py
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.companiesapp.models import Company, CompanyDocument, CompanySettings
from apps.geoapp.models import Location


class CompanyModelTestCase(TestCase):
    def setUp(self):
        # Create a test user (owner)
        self.user = User.objects.create(
            phone_number="1234567890", user_type="customer", is_verified=True
        )

        # Create location
        self.location = Location.objects.create(
            latitude=24.7136,
            longitude=46.6753,
            country="Saudi Arabia",
            city="Riyadh",
            address="Test Address",
        )

        # Create company
        self.company = Company.objects.create(
            name="Test Company",
            registration_number="1234567890",
            owner=self.user,
            contact_phone="1234567890",
            location=self.location,
        )

    def test_company_creation(self):
        """Test company can be created with required fields"""
        self.assertEqual(self.company.name, "Test Company")
        self.assertEqual(self.company.owner, self.user)
        self.assertEqual(self.company.contact_phone, "1234567890")
        self.assertEqual(self.company.location, self.location)
        self.assertTrue(self.company.is_active)
        self.assertEqual(self.company.subscription_status, "inactive")

    def test_company_str_method(self):
        """Test string representation of company"""
        self.assertEqual(str(self.company), "Test Company")

    def test_company_settings_creation(self):
        """Test company settings are created automatically"""
        self.assertTrue(hasattr(self.company, "settings"))
        self.assertEqual(self.company.settings.default_language, "ar")
        self.assertTrue(self.company.settings.notification_email)
        self.assertTrue(self.company.settings.notification_sms)

    @patch("apps.shopapp.models.Shop.objects.filter")
    def test_update_counts(self, mock_shop_filter):
        """Test update_counts method for shop and employee counts"""
        # Setup mock
        mock_shop_query = mock_shop_filter.return_value
        mock_shop_query.count.return_value = 3
        mock_shop_query.values_list.return_value = [1, 2, 3]

        with patch(
            "apps.employeeapp.models.Employee.objects.filter"
        ) as mock_employee_filter:
            mock_employee_filter.return_value.count.return_value = 10

            # Call method
            self.company.update_counts()

            # Check counts were updated
            self.assertEqual(self.company.shop_count, 3)
            self.assertEqual(self.company.employee_count, 10)

            # Verify correct filter calls
            mock_shop_filter.assert_called_once_with(company=self.company)
            mock_shop_query.values_list.assert_called_once_with("id", flat=True)
            mock_employee_filter.assert_called_once_with(shop_id__in=[1, 2, 3])


class CompanyDocumentTestCase(TestCase):
    def setUp(self):
        # Create company first
        self.user = User.objects.create(
            phone_number="1234567890", user_type="customer", is_verified=True
        )

        self.company = Company.objects.create(
            name="Test Company", owner=self.user, contact_phone="1234567890"
        )

        # Create document
        self.document = CompanyDocument.objects.create(
            company=self.company, title="Test Document", document_type="License"
        )

    def test_document_creation(self):
        """Test document can be created properly"""
        self.assertEqual(self.document.title, "Test Document")
        self.assertEqual(self.document.company, self.company)
        self.assertEqual(self.document.document_type, "License")
        self.assertFalse(self.document.is_verified)

    def test_document_str_method(self):
        """Test string representation of document"""
        self.assertEqual(str(self.document), "Test Company - Test Document")

    def test_document_verification(self):
        """Test document verification"""
        verifier = User.objects.create(
            phone_number="9876543210", user_type="admin", is_verified=True
        )

        self.document.is_verified = True
        self.document.verified_by = verifier
        self.document.verified_at = timezone.now()
        self.document.save()

        # Reload from database
        updated_doc = CompanyDocument.objects.get(id=self.document.id)

        self.assertTrue(updated_doc.is_verified)
        self.assertEqual(updated_doc.verified_by, verifier)
        self.assertIsNotNone(updated_doc.verified_at)


class CompanySettingsTestCase(TestCase):
    def setUp(self):
        # Create company first
        self.user = User.objects.create(
            phone_number="1234567890", user_type="customer", is_verified=True
        )

        self.company = Company.objects.create(
            name="Test Company", owner=self.user, contact_phone="1234567890"
        )

        # Settings created by signal

    def test_settings_creation_by_signal(self):
        """Test settings are created automatically by signal"""
        settings = CompanySettings.objects.get(company=self.company)
        self.assertEqual(settings.default_language, "ar")
        self.assertTrue(settings.notification_email)
        self.assertTrue(settings.notification_sms)

    def test_settings_update(self):
        """Test settings can be updated"""
        settings = self.company.settings
        settings.default_language = "en"
        settings.notification_sms = False
        settings.save()

        # Reload from database
        updated_settings = CompanySettings.objects.get(company=self.company)

        self.assertEqual(updated_settings.default_language, "en")
        self.assertFalse(updated_settings.notification_sms)
        self.assertTrue(updated_settings.notification_email)  # Unchanged
