from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.authapp.models import User
from apps.companiesapp.models import Company
from apps.rolesapp.models import Permission, Role, UserRole
from apps.shopapp.models import Shop
from apps.shopDashboardApp.models import DashboardLayout, DashboardSettings, DashboardWidget


class DashboardViewsTestCase(TestCase):
    """Test cases for Dashboard app views"""

    def setUp(self):
        """Set up test data and client"""
        self.client = APIClient()

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

        # Create dashboard permissions
        self.view_permission = Permission.objects.create(resource="dashboard", action="view")

        self.edit_permission = Permission.objects.create(resource="dashboard", action="edit")

        # Create role with permissions
        self.role = Role.objects.create(
            name="Shop Manager", role_type="shop_manager", shop=self.shop
        )
        self.role.permissions.add(self.view_permission, self.edit_permission)

        # Assign role to user
        UserRole.objects.create(user=self.user, role=self.role)

        # Create dashboard settings
        self.settings = DashboardSettings.objects.create(
            shop=self.shop, default_date_range="month", auto_refresh_interval=0
        )

        # Create dashboard layout
        self.layout = DashboardLayout.objects.create(
            shop=self.shop,
            name="Test Layout",
            description="Test layout for API tests",
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

        # Authenticate client
        self.client.force_authenticate(user=self.user)

    def test_dashboard_layout_list(self):
        """Test listing dashboard layouts"""
        response = self.client.get(f"/api/dashboard/layouts/?shop_id={self.shop.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Test Layout")

    def test_dashboard_layout_create(self):
        """Test creating a dashboard layout"""
        data = {
            "shop": str(self.shop.id),
            "name": "New Layout",
            "description": "A new test layout",
            "is_default": False,
            "widgets": [
                {
                    "title": "New Widget",
                    "widget_type": "kpi",
                    "category": "bookings",
                    "kpi_key": "total_bookings",
                    "position": {"x": 0, "y": 0, "w": 3, "h": 1},
                    "is_visible": True,
                }
            ],
        }

        response = self.client.post("/api/dashboard/layouts/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Layout")

        # Check that widget was created
        layout_id = response.data["id"]
        layout = DashboardLayout.objects.get(id=layout_id)
        self.assertEqual(layout.widgets.count(), 1)
        self.assertEqual(layout.widgets.first().title, "New Widget")

    def test_dashboard_layout_default(self):
        """Test getting default layout"""
        response = self.client.get(f"/api/dashboard/layouts/default/?shop_id={self.shop.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.layout.id))
        self.assertTrue(response.data["is_default"])

    def test_dashboard_widget_list(self):
        """Test listing dashboard widgets"""
        response = self.client.get(f"/api/dashboard/widgets/?layout_id={self.layout.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Test Widget")

    def test_dashboard_widget_create(self):
        """Test creating a dashboard widget"""
        data = {
            "layout": str(self.layout.id),
            "title": "Another Widget",
            "widget_type": "chart",
            "chart_type": "line",
            "data_source": "revenue_trend",
            "position": {"x": 3, "y": 0, "w": 6, "h": 2},
            "is_visible": True,
        }

        response = self.client.post("/api/dashboard/widgets/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Another Widget")

        # Verify widget in database
        widget_id = response.data["id"]
        widget = DashboardWidget.objects.get(id=widget_id)
        self.assertEqual(widget.chart_type, "line")
        self.assertEqual(widget.data_source, "revenue_trend")

    def test_dashboard_data(self):
        """Test getting dashboard data"""
        response = self.client.get(f"/api/dashboard/data/?shop_id={self.shop.id}&time_period=month")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check structure of response
        self.assertIn("time_period", response.data)
        self.assertIn("date_range", response.data)
        self.assertIn("kpis", response.data)
        self.assertIn("charts", response.data)
        self.assertIn("tables", response.data)

        # Check time period
        self.assertEqual(response.data["time_period"], "month")

    def test_dashboard_kpis(self):
        """Test getting dashboard KPIs"""
        response = self.client.get(
            f"/api/dashboard/data/kpis/?shop_id={self.shop.id}&time_period=month"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify it's a list
        self.assertIsInstance(response.data, list)

        # If any KPIs were returned, verify structure
        if response.data:
            kpi = response.data[0]
            self.assertIn("key", kpi)
            self.assertIn("name", kpi)
            self.assertIn("value", kpi)
            self.assertIn("category", kpi)
            self.assertIn("format", kpi)

    def test_dashboard_settings(self):
        """Test getting dashboard settings"""
        response = self.client.get(f"/api/dashboard/settings/for_shop/?shop_id={self.shop.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.settings.id))
        self.assertEqual(response.data["default_date_range"], "month")

        # Test updating settings
        data = {"default_date_range": "week", "auto_refresh_interval": 300}

        response = self.client.patch(
            f"/api/dashboard/settings/{self.settings.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["default_date_range"], "week")
        self.assertEqual(response.data["auto_refresh_interval"], 300)
