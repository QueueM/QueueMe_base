import json
from datetime import timedelta

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Count
from django.utils import timezone
from django.utils.timesince import timesince

from apps.bookingapp.models import Booking


class BookingStatsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for providing real-time booking statistics to the admin dashboard.
    """

    async def connect(self):
        """
        Called when the WebSocket is handshaking as part of initial connection.
        """
        # Check if user is authenticated and has admin permissions
        if self.scope["user"].is_anonymous or not self.scope["user"].is_staff:
            await self.close()
            return

        # Add the channel to the group
        await self.channel_layer.group_add("admin_booking_stats", self.channel_name)

        # Accept the connection
        await self.accept()

    async def disconnect(self, close_code):
        """
        Called when the WebSocket closes for any reason.
        """
        # Remove the channel from the group
        await self.channel_layer.group_discard("admin_booking_stats", self.channel_name)

    async def receive(self, text_data):
        """
        Called when we receive a text frame from the client.
        """
        data = json.loads(text_data)
        action = data.get("action")

        if action == "get_initial_data":
            # Get initial data for stats and chart
            stats_data = await self.get_booking_stats()
            await self.send(text_data=json.dumps(stats_data))

        elif action == "refresh_data":
            # Get refreshed data for stats and chart
            stats_data = await self.get_booking_stats()
            await self.send(text_data=json.dumps(stats_data))

    async def new_booking(self, event):
        """
        Called when a new booking is created.
        This method is triggered by the group_send from other parts of the application.
        """
        # Forward the message to the WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "new_booking",
                    "booking": event["booking"],
                    "stats": event.get("stats", {}),
                }
            )
        )

    @sync_to_async
    def get_booking_stats(self):
        """
        Get booking statistics for the dashboard.
        """
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # Get today's bookings
        today_bookings = Booking.objects.filter(created_at__date=today).count()

        # Get yesterday's bookings for trend calculation
        yesterday_bookings = Booking.objects.filter(created_at__date=yesterday).count()

        # Calculate trend percentage
        if yesterday_bookings > 0:
            trend_percentage = int(
                ((today_bookings - yesterday_bookings) / yesterday_bookings) * 100
            )
        else:
            trend_percentage = 100 if today_bookings > 0 else 0

        # Get pending and completed bookings
        pending_bookings = Booking.objects.filter(status="PENDING").count()

        completed_bookings = Booking.objects.filter(status="COMPLETED").count()

        # Get chart data for last 7 days
        last_week = today - timedelta(days=6)
        chart_data = self.get_chart_data(last_week, today)

        # Get recent activity
        recent_activity = self.get_recent_activity()

        # Return all stats
        return {
            "type": "initial_data",
            "today_bookings": today_bookings,
            "pending_bookings": pending_bookings,
            "completed_bookings": completed_bookings,
            "today_trend": trend_percentage,
            "chart_data": chart_data,
            "recent_activity": recent_activity,
        }

    def get_chart_data(self, start_date, end_date):
        """
        Get booking data for chart display over a date range.
        """
        # Generate list of dates from start_date to end_date
        delta = end_date - start_date
        dates = [start_date + timedelta(days=i) for i in range(delta.days + 1)]

        # Get booking counts for each date
        date_counts = {}
        bookings_by_date = (
            Booking.objects.filter(
                created_at__date__gte=start_date, created_at__date__lte=end_date
            )
            .values("created_at__date")
            .annotate(count=Count("id"))
        )

        # Convert to dictionary for easy lookup
        for item in bookings_by_date:
            date_counts[item["created_at__date"]] = item["count"]

        # Format for chart.js
        labels = [date.strftime("%a") for date in dates]
        data = [date_counts.get(date, 0) for date in dates]

        return {"labels": labels, "data": data}

    def get_recent_activity(self, limit=10):
        """
        Get recent booking activity.
        """
        recent_bookings = Booking.objects.select_related(
            "customer__user", "service"
        ).order_by("-created_at")[:limit]

        activity = []

        for booking in recent_bookings:
            customer_name = (
                booking.customer.user.get_full_name() or booking.customer.user.username
            )

            activity_item = {
                "id": booking.id,
                "customer_name": customer_name,
                "service_name": booking.service.name,
                "action": "booked",
                "status": booking.status,
                "time_ago": timesince(booking.created_at),
            }

            activity.append(activity_item)

        return activity
