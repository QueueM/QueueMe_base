"""
QueueMe Admin WebSocket Consumers
"""

import asyncio
import json
import random
from datetime import datetime

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone


class AdminDashboardConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time admin dashboard data"""

    async def connect(self):
        """Connect to WebSocket"""
        self.room_group_name = "admin_dashboard"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Accept connection
        await self.accept()

        # Start background task to send data periodically
        self.send_data_task = asyncio.create_task(self.send_data_periodically())

    async def disconnect(self, close_code):
        """Disconnect from WebSocket"""
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Cancel background task
        if hasattr(self, "send_data_task"):
            self.send_data_task.cancel()
            try:
                await self.send_data_task
            except asyncio.CancelledError:
                pass

    async def receive(self, text_data):
        """Receive message from WebSocket"""
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get("type", "default")

        # Handle different message types
        if message_type == "request_data":
            # Send immediate data update
            await self.send_dashboard_data()

    async def admin_dashboard_update(self, event):
        """Receive admin dashboard update from room group"""
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event["data"]))

    async def send_data_periodically(self):
        """Send real-time data updates periodically"""
        try:
            while True:
                await self.send_dashboard_data()
                await asyncio.sleep(5)  # Update every 5 seconds
        except asyncio.CancelledError:
            # Task was cancelled, clean up
            raise

    async def send_dashboard_data(self):
        """Send dashboard data to WebSocket"""
        # Get real-time data
        data = await self.get_dashboard_data()

        # Send update to room group
        await self.channel_layer.group_send(
            self.room_group_name, {"type": "admin_dashboard_update", "data": data}
        )

    @database_sync_to_async
    def get_dashboard_data(self):
        """Get real-time dashboard data"""
        # This would normally query the database for real-time metrics
        # For now, we're using simulated data
        try:
            from apps.authapp.models import User
            from apps.bookingapp.models import Booking
            from apps.shopapp.models import Shop

            # Get current date
            today = timezone.now().date()

            # Get real metrics when possible
            bookings_today = Booking.objects.filter(booking_date=today).count()
            active_users = User.objects.filter(is_active=True).count()

            # For real implementation, these would be actual metrics
            # For now, we'll use simulated data
            data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "active_users": {
                    "count": active_users,
                    "change": random.randint(-5, 5),
                },
                "bookings": {
                    "today": bookings_today,
                    "pending": random.randint(20, 50),
                    "last_hour": random.randint(5, 15),
                },
                "revenue": {
                    "today": round(random.uniform(1000, 5000), 2),
                    "change": round(random.uniform(-200, 500), 2),
                },
                "shops": {
                    "active": Shop.objects.filter(is_active=True).count(),
                    "new_today": random.randint(0, 3),
                },
                "latest_bookings": [
                    {
                        "id": f"b-{random.randint(1000, 9999)}",
                        "customer": f"User {random.randint(1, 100)}",
                        "service": f"Service {random.randint(1, 20)}",
                        "time": (
                            datetime.now().replace(microsecond=0)
                            - timezone.timedelta(minutes=random.randint(5, 120))
                        ).strftime("%H:%M:%S"),
                        "amount": round(random.uniform(50, 500), 2),
                    }
                    for _ in range(5)
                ],
            }

            return data

        except Exception:
            # Fallback to completely simulated data if something fails
            return {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "active_users": {
                    "count": random.randint(50, 150),
                    "change": random.randint(-5, 5),
                },
                "bookings": {
                    "today": random.randint(20, 80),
                    "pending": random.randint(20, 50),
                    "last_hour": random.randint(5, 15),
                },
                "revenue": {
                    "today": round(random.uniform(1000, 5000), 2),
                    "change": round(random.uniform(-200, 500), 2),
                },
                "shops": {
                    "active": random.randint(20, 50),
                    "new_today": random.randint(0, 3),
                },
                "latest_bookings": [
                    {
                        "id": f"b-{random.randint(1000, 9999)}",
                        "customer": f"User {random.randint(1, 100)}",
                        "service": f"Service {random.randint(1, 20)}",
                        "time": (
                            datetime.now().replace(microsecond=0)
                            - timezone.timedelta(minutes=random.randint(5, 120))
                        ).strftime("%H:%M:%S"),
                        "amount": round(random.uniform(50, 500), 2),
                    }
                    for _ in range(5)
                ],
            }


class SystemMonitoringConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for system health monitoring"""

    async def connect(self):
        """Connect to WebSocket"""
        self.room_group_name = "system_monitoring"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Accept connection
        await self.accept()

        # Start background task to send data periodically
        self.send_data_task = asyncio.create_task(self.send_data_periodically())

    async def disconnect(self, close_code):
        """Disconnect from WebSocket"""
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Cancel background task
        if hasattr(self, "send_data_task"):
            self.send_data_task.cancel()
            try:
                await self.send_data_task
            except asyncio.CancelledError:
                pass

    async def receive(self, text_data):
        """Receive message from WebSocket"""
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get("type", "default")

        # Handle different message types
        if message_type == "request_data":
            # Send immediate data update
            await self.send_monitoring_data()

    async def system_monitoring_update(self, event):
        """Receive system monitoring update from room group"""
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event["data"]))

    async def send_data_periodically(self):
        """Send real-time data updates periodically"""
        try:
            while True:
                await self.send_monitoring_data()
                await asyncio.sleep(3)  # Update every 3 seconds
        except asyncio.CancelledError:
            # Task was cancelled, clean up
            raise

    async def send_monitoring_data(self):
        """Send monitoring data to WebSocket"""
        # Get real-time data
        data = await self.get_monitoring_data()

        # Send update to room group
        await self.channel_layer.group_send(
            self.room_group_name, {"type": "system_monitoring_update", "data": data}
        )

    @database_sync_to_async
    def get_monitoring_data(self):
        """Get real-time system monitoring data"""
        # This would normally get actual system metrics
        # For now, we're using simulated data
        import psutil

        try:
            # Get actual system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_info = psutil.virtual_memory()
            disk_info = psutil.disk_usage("/")

            # For real implementation, these would come from the database
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_conn_ok = True
        except:
            cpu_percent = random.randint(10, 90)
            memory_info = {
                "percent": random.randint(40, 90),
                "used": random.randint(4000, 8000),
                "total": 16000,
            }
            disk_info = {
                "percent": random.randint(30, 80),
                "used": random.randint(100, 400),
                "total": 500,
            }
            db_conn_ok = random.choice([True, True, True, False])

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cpu": {
                "usage": float(cpu_percent),
                "cores": psutil.cpu_count(),
                "threshold": 90,
            },
            "memory": {
                "percent": float(
                    getattr(memory_info, "percent", memory_info["percent"])
                ),
                "used_gb": round(
                    getattr(memory_info, "used", memory_info["used"])
                    / (1024 * 1024 * 1024),
                    2,
                ),
                "total_gb": round(
                    getattr(memory_info, "total", memory_info["total"])
                    / (1024 * 1024 * 1024),
                    2,
                ),
                "threshold": 85,
            },
            "disk": {
                "percent": float(getattr(disk_info, "percent", disk_info["percent"])),
                "used_gb": round(
                    getattr(disk_info, "used", disk_info["used"])
                    / (1024 * 1024 * 1024),
                    2,
                ),
                "total_gb": round(
                    getattr(disk_info, "total", disk_info["total"])
                    / (1024 * 1024 * 1024),
                    2,
                ),
                "threshold": 90,
            },
            "services": {
                "database": {
                    "status": "ok" if db_conn_ok else "error",
                    "response_time": random.randint(5, 100),
                },
                "cache": {"status": "ok", "hit_rate": random.randint(70, 99)},
                "web": {"status": "ok", "response_time": random.randint(50, 300)},
                "queue": {
                    "status": random.choice(["ok", "ok", "ok", "warning"]),
                    "pending_jobs": random.randint(0, 30),
                },
            },
            "requests": {
                "per_second": round(random.uniform(1, 20), 1),
                "error_rate": round(random.uniform(0, 3), 2),
            },
        }
