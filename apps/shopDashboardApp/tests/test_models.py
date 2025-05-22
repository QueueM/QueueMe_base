from django.test import TestCase
from django.utils import timezone

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.shopapp.models import Shop
from apps.shopDashboardApp.models import (
    DashboardLayout,
    DashboardPreference,
    DashboardSettings,
    DashboardWidget,
    SavedFilter,
    ScheduledReport,
)


class DashboardModelsTestCase(TestCase):
    """Test cases for Dashboard app models"""

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

        # Create dashboard settings
        self.settings = DashboardSettings.objects.create(
            shop=self.shop, default_date_range="month", auto_refresh_interval=0
        )

        # Create dashboard layout
        self.layout = DashboardLayout.objects.create(
            shop=self.shop,
            name="Test Layout",
            description="Test layout for unit tests",
            is_default=True,
            created_by=self.user,
        )

        # Create dashboard widget
        self.widget = DashboardWidget.objects.create(
            layout=self.layout,
            title="Test Widget",
            widget_type="kpi",
            category="revenue",
            kpi_key="total_revenue",
            position={"x": 0, "y": 0, "w": 3, "h": 1},
            is_visible=True,
        )

        # Create scheduled report
        self.report = ScheduledReport.objects.create(
            shop=self.shop,
            name="Test Report",
            frequency="weekly",
            day_of_week=1,
            time_of_day=timezone.now().time(),
            date_range="month",
            recipients=[{"email": "test@example.com", "type": "email"}],
            created_by=self.user,
        )

        # Create saved filter
        self.filter = SavedFilter.objects.create(
            shop=self.shop,
            name="Test Filter",
            filter_config={"test": "config"},
            created_by=self.user,
        )

        # Create dashboard preference
        self.preference = DashboardPreference.objects.create(
            user=self.user, preferred_layout=self.layout, preferred_date_range="month"
        )

    def test_dashboard_settings(self):
        """Test DashboardSettings model"""
        self.assertEqual(str(self.settings), f"{self.shop.name} - Dashboard Settings")
        self.assertEqual(self.settings.default_date_range, "month")
        self.assertEqual(self.settings.auto_refresh_interval, 0)

    def test_dashboard_layout(self):
        """Test DashboardLayout model"""
        self.assertEqual(str(self.layout), f"{self.shop.name} - Test Layout")
        self.assertTrue(self.layout.is_default)
        self.assertEqual(self.layout.widgets.count(), 1)

        # Test that only one layout can be default
        layout2 = DashboardLayout.objects.create(
            shop=self.shop, name="Test Layout 2", is_default=True, created_by=self.user
        )

        # Refresh from database
        self.layout.refresh_from_db()

        # The first layout should no longer be default
        self.assertFalse(self.layout.is_default)
        self.assertTrue(layout2.is_default)

    def test_dashboard_widget(self):
        """Test DashboardWidget model"""
        self.assertEqual(str(self.widget), f"{self.layout.name} - Test Widget")
        self.assertEqual(self.widget.widget_type, "kpi")
        self.assertEqual(self.widget.kpi_key, "total_revenue")

        # Test position JSON
        self.assertEqual(self.widget.position["x"], 0)
        self.assertEqual(self.widget.position["y"], 0)
        self.assertEqual(self.widget.position["w"], 3)
        self.assertEqual(self.widget.position["h"], 1)

    def test_scheduled_report(self):
        """Test ScheduledReport model"""
        self.assertEqual(str(self.report), f"{self.shop.name} - Test Report")
        self.assertEqual(self.report.frequency, "weekly")
        self.assertEqual(self.report.day_of_week, 1)

        # Test recipients JSON
        self.assertEqual(len(self.report.recipients), 1)
        self.assertEqual(self.report.recipients[0]["email"], "test@example.com")
        self.assertEqual(self.report.recipients[0]["type"], "email")

    def test_saved_filter(self):
        """Test SavedFilter model"""
        self.assertEqual(str(self.filter), f"{self.shop.name} - Test Filter")

        # Test filter_config JSON
        self.assertEqual(self.filter.filter_config["test"], "config")

    def test_dashboard_preference(self):
        """Test DashboardPreference model"""
        self.assertEqual(
            str(self.preference), f"{self.user.phone_number} - Dashboard Preferences"
        )
        self.assertEqual(self.preference.preferred_layout, self.layout)
        self.assertEqual(self.preference.preferred_date_range, "month")
