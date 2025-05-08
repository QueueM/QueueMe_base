# apps/reportanalyticsapp/tests/test_models.py

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.reportanalyticsapp.models import Report, ReportExecution, ReportSchedule
from apps.shopapp.models import Shop


class ReportModelTest(TestCase):
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

        # Get content type for shop
        self.shop_content_type = ContentType.objects.get_for_model(Shop)

        # Create a test report
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

    def test_report_creation(self):
        """Test that a report can be created"""
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(self.report.name, "Test Report")
        self.assertEqual(self.report.report_type, "business_overview")

    def test_report_entity_relation(self):
        """Test that a report is properly related to its entity"""
        self.assertEqual(self.report.content_type, self.shop_content_type)
        self.assertEqual(self.report.object_id, str(self.shop.id))
        self.assertEqual(self.report.content_object, self.shop)

    def test_get_entity_name(self):
        """Test get_entity_name method"""
        self.assertEqual(self.report.get_entity_name(), "Test Shop")

    def test_get_entity_id(self):
        """Test get_entity_id method"""
        self.assertEqual(self.report.get_entity_id(), str(self.shop.id))


class ReportScheduleTest(TestCase):
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

        # Get content type for shop
        self.shop_content_type = ContentType.objects.get_for_model(Shop)

        # Create a test report schedule
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
            parameters={"include_charts": True},
            is_active=True,
        )

    def test_schedule_creation(self):
        """Test that a schedule can be created"""
        self.assertEqual(ReportSchedule.objects.count(), 1)
        self.assertEqual(self.schedule.name, "Test Schedule")
        self.assertEqual(self.schedule.frequency, "weekly")

    def test_schedule_entity_relation(self):
        """Test that a schedule is properly related to its entity"""
        self.assertEqual(self.schedule.content_type, self.shop_content_type)
        self.assertEqual(self.schedule.object_id, str(self.shop.id))
        self.assertEqual(self.schedule.content_object, self.shop)

    def test_get_entity_name(self):
        """Test get_entity_name method"""
        self.assertEqual(self.schedule.get_entity_name(), "Test Shop")

    def test_recipients_array(self):
        """Test that recipients is stored as an array"""
        self.assertEqual(self.schedule.recipients, ["test@example.com"])


class ReportExecutionTest(TestCase):
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

        # Get content type for shop
        self.shop_content_type = ContentType.objects.get_for_model(Shop)

        # Create a test report
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
            data={},
        )

        # Create a test report schedule
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

        # Create a test execution
        self.execution = ReportExecution.objects.create(
            schedule=self.schedule, report=self.report, status="success"
        )

    def test_execution_creation(self):
        """Test that an execution can be created"""
        self.assertEqual(ReportExecution.objects.count(), 1)
        self.assertEqual(self.execution.status, "success")

    def test_execution_relations(self):
        """Test that an execution is properly related to schedule and report"""
        self.assertEqual(self.execution.schedule, self.schedule)
        self.assertEqual(self.execution.report, self.report)
