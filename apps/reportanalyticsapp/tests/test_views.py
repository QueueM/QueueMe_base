# apps/reportanalyticsapp/tests/test_views.py

from datetime import timedelta
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.authapp.services.token_service import TokenService
from apps.companiesapp.models import Company
from apps.reportanalyticsapp.models import Report, ReportSchedule
from apps.rolesapp.models import Permission, Role, UserRole
from apps.shopapp.models import Shop


class ReportAPITest(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create(
            phone_number="1234567890", is_active=True, is_verified=True, is_staff=True
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

        # Create admin role and permissions
        self.admin_role = Role.objects.create(
            name="Admin", role_type="queue_me_admin", description="Admin role"
        )

        # Create report permissions
        self.view_report_permission = Permission.objects.create(
            resource="report", action="view"
        )

        self.add_report_permission = Permission.objects.create(
            resource="report", action="add"
        )

        # Add permissions to role
        self.admin_role.permissions.add(self.view_report_permission)
        self.admin_role.permissions.add(self.add_report_permission)

        # Assign role to user
        UserRole.objects.create(user=self.user, role=self.admin_role)

        # Create API client
        self.client = APIClient()

        # Get JWT token
        tokens = TokenService.get_tokens_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        # Create test report
        self.shop_content_type = ContentType.objects.get_for_model(Shop)

        self.report = Report.objects.create(
            name="Test Report",
            report_type="business_overview",
            entity_type="shop",
            content_type=self.shop_content_type,
            object_id=self.shop.id,
            time_period="weekly",
            start_date=timezone.now() - timedelta(days=7),
            end_date=timezone.now(),
            format="pdf",
            file_url="https://example.com/reports/test.pdf",
            data={"metrics": {"total_bookings": 100, "completed_bookings": 80}},
        )

        # Create test schedule
        self.schedule = ReportSchedule.objects.create(
            name="Test Schedule",
            report_type="business_overview",
            entity_type="shop",
            content_type=self.shop_content_type,
            object_id=self.shop.id,
            time_period="weekly",
            frequency="weekly",
            format="pdf",
            recipients=["test@example.com"],
            parameters={},
            is_active=True,
        )

    def test_list_reports(self):
        """Test listing reports"""
        url = reverse("report-list")
        response = self.client.get(url)

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Test Report")

    def test_get_report_detail(self):
        """Test getting report detail"""
        url = reverse("report-detail", args=[self.report.id])
        response = self.client.get(url)

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Report")
        self.assertEqual(response.data["report_type"], "business_overview")

    @patch(
        "apps.reportanalyticsapp.services.report_service.ReportService.generate_report"
    )
    def test_create_report(self, mock_generate_report):
        """Test creating a report"""
        # Mock report generation
        mock_generate_report.return_value = self.report

        url = reverse("report-list")
        data = {
            "report_type": "business_overview",
            "entity_id": str(self.shop.id),
            "entity_type": "shop",
            "time_period": "weekly",
            "format": "pdf",
        }

        response = self.client.post(url, data=data, format="json")

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_generate_report.assert_called_once_with(
            report_type="business_overview",
            entity_id=str(self.shop.id),
            entity_type="shop",
            time_period="weekly",
            format="pdf",
            start_date=None,
            end_date=None,
        )

    def test_list_schedules(self):
        """Test listing schedules"""
        url = reverse("report-schedule-list")
        response = self.client.get(url)

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Test Schedule")

    def test_get_schedule_detail(self):
        """Test getting schedule detail"""
        url = reverse("report-schedule-detail", args=[self.schedule.id])
        response = self.client.get(url)

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Schedule")
        self.assertEqual(response.data["frequency"], "weekly")

    @patch(
        "apps.reportanalyticsapp.services.report_service.ReportService.schedule_report"
    )
    def test_create_schedule(self, mock_schedule_report):
        """Test creating a schedule"""
        # Mock schedule creation
        mock_schedule_report.return_value = self.schedule

        url = reverse("report-schedule-list")
        data = {
            "report_type": "business_overview",
            "entity_id": str(self.shop.id),
            "entity_type": "shop",
            "time_period": "weekly",
            "frequency": "weekly",
            "format": "pdf",
            "recipients": ["test@example.com"],
        }

        response = self.client.post(url, data=data, format="json")

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_schedule_report.assert_called_once()

    def test_update_schedule(self):
        """Test updating a schedule"""
        url = reverse("report-schedule-detail", args=[self.schedule.id])
        data = {"is_active": False}

        response = self.client.patch(url, data=data, format="json")

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["is_active"], False)

        # Verify in database
        self.schedule.refresh_from_db()
        self.assertFalse(self.schedule.is_active)

    @patch(
        "apps.reportanalyticsapp.services.report_service.ReportService.execute_scheduled_report"
    )
    def test_execute_schedule(self, mock_execute):
        """Test executing a schedule"""
        # Mock execution
        mock_execute.return_value = None

        url = reverse("report-schedule-execute", args=[self.schedule.id])
        response = self.client.post(url)

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_execute.assert_called_once_with(str(self.schedule.id))
