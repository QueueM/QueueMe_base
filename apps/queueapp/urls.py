from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "queueapp"

# ViewSet router
router = DefaultRouter()
router.register(r"tickets/viewset", views.QueueTicketViewSet, basename="ticket-viewset")
router.register(r"viewset", views.QueueViewSet, basename="queue-viewset")

urlpatterns = [
    # Include router URLs
    path("", include(router.urls)),
    # Queue management
    path("list/", views.QueueListView.as_view(), name="queue-list"),
    path("<uuid:pk>/", views.QueueDetailView.as_view(), name="queue-detail"),
    path("shop/<uuid:shop_id>/", views.ShopQueueListView.as_view(), name="shop-queues"),
    # Queue ticket management
    path("tickets/", views.QueueTicketListView.as_view(), name="ticket-list"),
    path(
        "tickets/<uuid:pk>/",
        views.QueueTicketDetailView.as_view(),
        name="ticket-detail",
    ),
    # Queue operations
    path("join/", views.JoinQueueView.as_view(), name="join-queue"),
    path("call-next/", views.CallNextView.as_view(), name="call-next"),
    path("mark-serving/", views.MarkServingView.as_view(), name="mark-serving"),
    path("mark-served/", views.MarkServedView.as_view(), name="mark-served"),
    path("cancel/", views.CancelTicketView.as_view(), name="cancel-ticket"),
    # Queue status
    path("status/<uuid:queue_id>/", views.QueueStatusView.as_view(), name="queue-status"),
    path("position/", views.CheckPositionView.as_view(), name="check-position"),
    path(
        "customer/<uuid:customer_id>/active/",
        views.CustomerActiveTicketsView.as_view(),
        name="customer-active-tickets",
    ),
    # Statistics
    path("stats/<uuid:queue_id>/", views.QueueStatsView.as_view(), name="queue-stats"),
]
