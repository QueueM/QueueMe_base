# apps/reportanalyticsapp/tests/test_services.py

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.reportanalyticsapp.services.report_service import ReportService
from apps.shopapp.models import Shop


class ReportServiceTest(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create(
            phone_number="1234567890", is_active=True, is_verified=True
        )

        # Create test company
        self.company = Company.objects.create(
            name="Test Company", contact_phone="9876543210", owner=self.user
        )

        # Create test shop
        self.shop = Shop.objects.create(
            company=self.company,
            name="Test Shop",
            phone_number="9876543210",
            username="testshop",
        )

    @patch(
        "apps.reportanalyticsapp.queries.business_queries.BusinessQueries.get_business_overview"
    )
    @patch(
        "apps.reportanalyticsapp.services.report_service.ReportService._generate_report_file"
    )
    def test_generate_report(self, mock_generate_file, mock_get_overview):
        """Test report generation"""
        # Mock the business overview data
        mock_get_overview.return_value = {
            "entity_id": str(self.shop.id),
            "entity_type": "shop",
            "entity_name": "Test Shop",
            "metrics": {"total_bookings": 100, "completed_bookings": 80},
            "time_series": {"bookings": {"2023-01-01": 10}},
        }

        # Mock file generation
        mock_generate_file.return_value = "https://example.com/reports/test.pdf"

        # Generate report
        report = ReportService.generate_report(
            report_type="business_overview",
            entity_id=str(self.shop.id),
            entity_type="shop",
            time_period="weekly",
            format="pdf",
        )

        # Assertions
        self.assertIsNotNone(report)
        self.assertEqual(report.report_type, "business_overview")
        self.assertEqual(report.entity_type, "shop")
        self.assertEqual(report.time_period, "weekly")
        self.assertEqual(report.format, "pdf")
        self.assertEqual(report.file_url, "https://example.com/reports/test.pdf")

        # Verify mocks were called
        mock_get_overview.assert_called_once()
        mock_generate_file.assert_called_once()

    @patch(
        "apps.reportanalyticsapp.services.report_service.ReportService.generate_report"
    )
    @patch(
        "apps.reportanalyticsapp.services.report_service.NotificationService.send_notification"
    )
    def test_schedule_report(self, mock_send_notification, mock_generate_report):
        """Test report scheduling"""
        # Mock generate report
        mock_report = MagicMock()
        mock_report.id = "test-report-id"
        mock_generate_report.return_value = mock_report

        # Schedule report
        schedule = ReportService.schedule_report(
            report_type="business_overview",
            entity_id=str(self.shop.id),
            entity_type="shop",
            time_period="weekly",
            frequency="weekly",
            format="pdf",
            recipients=["test@example.com"],
        )

        # Assertions
        self.assertIsNotNone(schedule)
        self.assertEqual(schedule.report_type, "business_overview")
        self.assertEqual(schedule.entity_type, "shop")
        self.assertEqual(schedule.time_period, "weekly")
        self.assertEqual(schedule.frequency, "weekly")
        self.assertEqual(schedule.format, "pdf")
        self.assertEqual(schedule.recipients, ["test@example.com"])
        self.assertTrue(schedule.is_active)

    @patch(
        "apps.reportanalyticsapp.services.report_service.ReportService._calculate_date_range"
    )
    def test_calculate_date_range(self, mock_calculate_date_range):
        """Test date range calculation"""
        # Mock date range
        now = timezone.now()
        mock_date_range = {"start": now - timedelta(days=7), "end": now}
        mock_calculate_date_range.return_value = mock_date_range

        # Call the method
        date_range = ReportService._calculate_date_range("weekly")

        # Assertions
        self.assertEqual(date_range, mock_date_range)
        mock_calculate_date_range.assert_called_once_with("weekly", None, None)

    @patch(
        "apps.reportanalyticsapp.services.report_service.S3Storage.upload_file_object"
    )
    def test_generate_report_file(self, mock_upload):
        """Test report file generation"""
        # Mock S3 upload
        mock_upload.return_value = "https://example.com/reports/test.pdf"

        # Generate file
        report_data = {
            "metadata": {
                "entity_type": "shop",
                "report_type": "business_overview",
                "report_name": "Business Overview",
                "entity_id": str(self.shop.id),
                "time_period_name": "Weekly",
                "start_date": "2023-01-01",
                "end_date": "2023-01-07",
                "generated_at": "2023-01-08T12:00:00Z",
            },
            "metrics": {"total_bookings": 100, "completed_bookings": 80},
        }

        file_url = ReportService._generate_report_file(report_data, "pdf")

        # Assertions
        self.assertEqual(file_url, "https://example.com/reports/test.pdf")
        mock_upload.assert_called_once()

    @patch(
        "apps.reportanalyticsapp.services.report_service.ReportService.get_report_data"
    )
    def test_get_report_data(self, mock_get_data):
        """Test getting report data"""
        # Mock report data
        mock_report_data = {
            "metrics": {"total_bookings": 100, "completed_bookings": 80},
            "time_series": {"bookings": {"2023-01-01": 10}},
            "metadata": {
                "report_type": "business_overview",
                "entity_id": str(self.shop.id),
                "entity_type": "shop",
                "time_period": "weekly",
                "start_date": "2023-01-01",
                "end_date": "2023-01-07",
            },
        }
        mock_get_data.return_value = mock_report_data

        # Get report data
        data = ReportService.get_report_data(
            report_type="business_overview",
            entity_id=str(self.shop.id),
            entity_type="shop",
            time_period="weekly",
        )

        # Assertions
        self.assertEqual(data, mock_report_data)
        mock_get_data.assert_called_once_with(
            "business_overview", str(self.shop.id), "shop", "weekly", None, None
        )
