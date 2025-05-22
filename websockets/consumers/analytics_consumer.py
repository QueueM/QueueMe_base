"""
Analytics WebSocket Consumer

Provides real-time analytics data through WebSocket connections:
- Real-time booking metrics
- Transaction monitoring
- Fraud alerts
- System health monitoring
"""

import asyncio
import json
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from algorithms.analytics.anomaly import fraud_detection
from algorithms.analytics.time_series import booking_prediction, revenue_forecasting
from apps.authapp.models import User
from apps.reportanalyticsapp.services import dashboard_service
from apps.rolesapp.services import roles_service


class AnalyticsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time analytics data.
    Streams analytics data to admin dashboards.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_name = None
        self.room_group_name = None
        self.user = None
        self.shop_id = None
        self.update_task = None
        self.has_admin_permission = False

    async def connect(self):
        """Handle WebSocket connection."""
        # Get user from scope (set by AuthMiddleware)
        self.user = self.scope.get("user")

        # Anonymous users can't connect
        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        # Get parameters from URL route
        self.room_name = self.scope["url_route"]["kwargs"].get("room_name", "analytics")
        self.shop_id = self.scope["url_route"]["kwargs"].get("shop_id")

        # Create group name
        self.room_group_name = f"analytics_{self.room_name}"

        # Check permissions
        self.has_admin_permission = await self.check_admin_permission()

        if not self.has_admin_permission:
            await self.close()
            return

        # Join analytics group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        # Send initial data
        await self.send_initial_data()

        # Start periodic updates
        self.update_task = asyncio.create_task(self.periodic_updates())

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave analytics group
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

        # Cancel periodic update task
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

    async def receive(self, text_data):
        """
        Handle incoming messages from WebSocket.

        Args:
            text_data: JSON string with message data
        """
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "get_booking_forecast":
                await self.send_booking_forecast(
                    data.get("shop_id"), data.get("days_ahead", 14)
                )
            elif message_type == "get_revenue_forecast":
                await self.send_revenue_forecast(
                    data.get("shop_id"), data.get("days_ahead", 30)
                )
            elif message_type == "get_fraud_alerts":
                await self.send_fraud_alerts(data.get("lookback_days", 30))
            elif message_type == "get_booking_anomalies":
                await self.send_booking_anomalies(
                    data.get("shop_id"), data.get("days", 7)
                )
            elif message_type == "get_dashboard_metrics":
                await self.send_dashboard_metrics()
        except json.JSONDecodeError:
            # Handle invalid JSON
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            )
        except Exception as e:
            # Handle other errors
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    @database_sync_to_async
    def check_admin_permission(self):
        """Check if the user has admin permissions."""
        # Must be authenticated
        if not self.user or self.user.is_anonymous:
            return False

        # If superuser, always grant access
        if self.user.is_superuser:
            return True

        # Check admin permissions using roles service
        if hasattr(roles_service, "has_admin_analytics_permission"):
            return roles_service.has_admin_analytics_permission(self.user)

        # Fallback to basic staff check if roles service not available
        return self.user.is_staff

    async def send_initial_data(self):
        """Send initial analytics data upon connection."""
        # Send welcome message
        await self.send(
            text_data=json.dumps(
                {
                    "type": "welcome",
                    "message": "Connected to analytics real-time stream",
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

        # Send dashboard metrics
        await self.send_dashboard_metrics()

    async def periodic_updates(self):
        """Send periodic analytics updates."""
        try:
            while True:
                # Send updated metrics every 60 seconds
                await asyncio.sleep(60)
                await self.send_dashboard_metrics()

                # Send fraud alerts every 5 minutes
                if (timezone.now().minute % 5) == 0:
                    await self.send_fraud_alerts()
        except asyncio.CancelledError:
            # Task was cancelled, exit gracefully
            return

    @database_sync_to_async
    def get_dashboard_metrics(self):
        """Get current dashboard metrics from the database."""
        try:
            # Use the dashboard service to get metrics
            metrics = dashboard_service.get_real_time_metrics(self.shop_id)
            return metrics
        except Exception as e:
            # Return error information
            return {"error": str(e)}

    async def send_dashboard_metrics(self):
        """Send dashboard metrics to the WebSocket."""
        metrics = await self.get_dashboard_metrics()

        await self.send(
            text_data=json.dumps(
                {
                    "type": "dashboard_metrics",
                    "data": metrics,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    @database_sync_to_async
    def get_booking_forecast(self, shop_id=None, days_ahead=14):
        """Get booking forecast using prediction algorithm."""
        try:
            forecast = booking_prediction.get_booking_forecast(shop_id, days_ahead)
            return forecast
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_booking_forecast(self, shop_id=None, days_ahead=14):
        """Send booking forecast data to the WebSocket."""
        forecast = await self.get_booking_forecast(shop_id, days_ahead)

        await self.send(
            text_data=json.dumps(
                {
                    "type": "booking_forecast",
                    "data": forecast,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    @database_sync_to_async
    def get_revenue_forecast(self, shop_id=None, days_ahead=30):
        """Get revenue forecast using prediction algorithm."""
        try:
            if shop_id:
                forecast = revenue_forecasting.forecast_shop_revenue(
                    shop_id, days_ahead, "ml"
                )
            else:
                forecast = revenue_forecasting.get_platform_revenue_forecast(days_ahead)
            return forecast
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_revenue_forecast(self, shop_id=None, days_ahead=30):
        """Send revenue forecast data to the WebSocket."""
        forecast = await self.get_revenue_forecast(shop_id, days_ahead)

        await self.send(
            text_data=json.dumps(
                {
                    "type": "revenue_forecast",
                    "data": forecast,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    @database_sync_to_async
    def get_fraud_alerts(self, lookback_days=30):
        """Get fraud alerts using anomaly detection."""
        try:
            alerts = fraud_detection.detect_payment_fraud(
                lookback_days=lookback_days, anomaly_threshold=0.75
            )
            return alerts
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_fraud_alerts(self, lookback_days=30):
        """Send fraud alerts to the WebSocket."""
        alerts = await self.get_fraud_alerts(lookback_days)

        await self.send(
            text_data=json.dumps(
                {
                    "type": "fraud_alerts",
                    "data": alerts,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    @database_sync_to_async
    def get_booking_anomalies(self, shop_id=None, days=7):
        """Get booking anomalies using anomaly detection."""
        try:
            anomalies = fraud_detection.detect_booking_anomalies(shop_id, days)
            return anomalies
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_booking_anomalies(self, shop_id=None, days=7):
        """Send booking anomalies to the WebSocket."""
        anomalies = await self.get_booking_anomalies(shop_id, days)

        await self.send(
            text_data=json.dumps(
                {
                    "type": "booking_anomalies",
                    "data": anomalies,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    async def analytics_update(self, event):
        """
        Handle analytics updates from other consumers or background tasks.

        Args:
            event: Event data containing the update
        """
        # Forward the update to the WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": event["type"],
                    "data": event["data"],
                    "timestamp": event.get("timestamp", timezone.now().isoformat()),
                }
            )
        )


class AdminDashboardConsumer(AnalyticsConsumer):
    """
    WebSocket consumer for admin dashboard real-time updates.
    Extends AnalyticsConsumer with admin-specific metrics.
    """

    async def send_initial_data(self):
        """Send initial admin dashboard data upon connection."""
        # Send welcome message
        await self.send(
            text_data=json.dumps(
                {
                    "type": "welcome",
                    "message": "Connected to admin dashboard real-time stream",
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

        # Send admin metrics
        await self.send_admin_metrics()

        # Send recent fraud alerts
        await self.send_fraud_alerts(lookback_days=7)

    async def periodic_updates(self):
        """Send periodic admin dashboard updates."""
        try:
            while True:
                # Send updated admin metrics every 30 seconds
                await asyncio.sleep(30)
                await self.send_admin_metrics()

                # Send fraud alerts every 5 minutes
                if (timezone.now().minute % 5) == 0:
                    await self.send_fraud_alerts(lookback_days=7)
        except asyncio.CancelledError:
            # Task was cancelled, exit gracefully
            return

    @database_sync_to_async
    def get_admin_metrics(self):
        """Get current admin dashboard metrics from the database."""
        try:
            # Use the dashboard service to get admin metrics
            metrics = dashboard_service.get_admin_dashboard_metrics()

            # Add revenue forecast for today
            today_forecast = revenue_forecasting.get_platform_revenue_forecast(
                days_ahead=1
            )
            if today_forecast.get("success", False):
                metrics["today_revenue_forecast"] = (
                    today_forecast["forecast"][0]["forecasted_revenue"]
                    if today_forecast["forecast"]
                    else 0
                )

            # Add active user count
            cutoff = timezone.now() - timedelta(minutes=15)
            active_users = User.objects.filter(last_login__gte=cutoff).count()
            metrics["active_users"] = active_users

            return metrics
        except Exception as e:
            # Return error information
            return {"error": str(e)}

    async def send_admin_metrics(self):
        """Send admin dashboard metrics to the WebSocket."""
        metrics = await self.get_admin_metrics()

        await self.send(
            text_data=json.dumps(
                {
                    "type": "admin_metrics",
                    "data": metrics,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    async def receive(self, text_data):
        """
        Handle incoming messages for admin dashboard.

        Args:
            text_data: JSON string with message data
        """
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            # Handle admin-specific message types
            if message_type == "get_admin_metrics":
                await self.send_admin_metrics()
            else:
                # Forward to parent class for handling general analytics messages
                await super().receive(text_data)
        except json.JSONDecodeError:
            # Handle invalid JSON
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            )
        except Exception as e:
            # Handle other errors
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))
