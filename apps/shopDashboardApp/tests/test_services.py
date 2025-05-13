from datetime import date, timedelta

from django.test import TestCase

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.shopapp.models import Shop
from apps.shopDashboardApp.models import DashboardLayout, DashboardSettings
from apps.shopDashboardApp.services.dashboard_service import DashboardService
from apps.shopDashboardApp.services.kpi_service import KPIService
from apps.shopDashboardApp.services.settings_service import SettingsService


class DashboardServicesTestCase(TestCase):
    """Test cases for Dashboard app services"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create(
            phone_number="1234567890",
            user_type="employee",
            is_verified=True,
            profile_completed=True,
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

        # Initialize services
        self.dashboard_service = DashboardService()
        self.kpi_service = KPIService()
        self.settings_service = SettingsService()

    def test_calculate_date_range(self):
        """Test date range calculation in DashboardService"""
        today = date.today()

        # Test 'today' period
        date_range = self.dashboard_service.calculate_date_range("today")
        self.assertEqual(date_range["start_date"], today)
        self.assertEqual(date_range["end_date"], today)

        # Test 'yesterday' period
        date_range = self.dashboard_service.calculate_date_range("yesterday")
        self.assertEqual(date_range["start_date"], today - timedelta(days=1))
        self.assertEqual(date_range["end_date"], today - timedelta(days=1))

        # Test 'month' period
        date_range = self.dashboard_service.calculate_date_range("month")
        self.assertEqual(date_range["start_date"], today.replace(day=1))
        self.assertEqual(date_range["end_date"], today)

        # Test 'custom' period
        start_date = "2023-01-01"
        end_date = "2023-01-31"
        date_range = self.dashboard_service.calculate_date_range("custom", start_date, end_date)
        self.assertEqual(date_range["start_date"], date(2023, 1, 1))
        self.assertEqual(date_range["end_date"], date(2023, 1, 31))

    def test_create_default_settings(self):
        """Test creating default dashboard settings"""
        # Delete any existing settings
        DashboardSettings.objects.filter(shop=self.shop).delete()

        # Create default settings
        settings = self.settings_service.create_default_settings(self.shop.id)

        # Verify settings
        self.assertEqual(settings.shop, self.shop)
        self.assertEqual(settings.default_date_range, "month")
        self.assertEqual(settings.auto_refresh_interval, 0)

    def test_create_default_layout(self):
        """Test creating default dashboard layout"""
        # Delete any existing layouts
        DashboardLayout.objects.filter(shop=self.shop).delete()

        # Create default layout
        layout = self.settings_service.create_default_layout(self.shop.id, self.user.id)

        # Verify layout
        self.assertEqual(layout.shop, self.shop)
        self.assertEqual(layout.name, "Default Layout")
        self.assertTrue(layout.is_default)

        # Verify widgets were created
        self.assertTrue(layout.widgets.count() > 0)

        # Check for specific widget types
        self.assertTrue(layout.widgets.filter(widget_type="kpi").exists())
        self.assertTrue(layout.widgets.filter(widget_type="chart").exists())
        self.assertTrue(layout.widgets.filter(widget_type="table").exists())

    def test_get_available_widgets(self):
        """Test getting available widgets"""
        widgets = self.dashboard_service.get_available_widgets(self.shop.id)

        # Check for widget categories
        self.assertIn("kpi_widgets", widgets)
        self.assertIn("chart_widgets", widgets)
        self.assertIn("table_widgets", widgets)
        self.assertIn("other_widgets", widgets)

        # Check for specific widgets
        self.assertTrue(len(widgets["kpi_widgets"]) > 0)
        self.assertTrue(len(widgets["chart_widgets"]) > 0)
        self.assertTrue(len(widgets["table_widgets"]) > 0)
