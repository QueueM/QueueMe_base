from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView


class AdminDashboardView(TemplateView):
    template_name = "admin/index.html"

    @method_decorator(staff_member_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add dashboard data
        context.update(
            {
                "total_users": 500,
                "user_growth": 15,
                "active_bookings": 120,
                "booking_growth": 8,
                "total_revenue": 12500,
                "revenue_growth": 22,
                "active_shops": 45,
                "shop_growth": 10,
                "recent_activities": [
                    {
                        "type": "booking",
                        "title": "New Booking Created",
                        "description": "John Doe booked a haircut at Style Salon",
                        "user": "John Doe",
                        "timestamp": "2023-05-15T10:30:00Z",
                        "status": "pending",
                    },
                    {
                        "type": "payment",
                        "title": "Payment Received",
                        "description": "Payment of $50 received for booking #12345",
                        "user": "Jane Smith",
                        "timestamp": "2023-05-15T09:45:00Z",
                        "status": "completed",
                    },
                ],
                "top_shops": [
                    {"name": "Style Salon", "bookings_count": 145, "rating": 4.8},
                    {"name": "Spa Center", "bookings_count": 120, "rating": 4.6},
                ],
            }
        )

        return context
