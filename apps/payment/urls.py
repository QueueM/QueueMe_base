from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet
from .webhooks import MoyasarWebhookView

router = DefaultRouter()
router.register(r"payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("", include(router.urls)),
    path("webhook/moyasar/", MoyasarWebhookView.as_view(), name="moyasar-webhook"),
    path(
        "callback/<uuid:transaction_id>/",
        PaymentViewSet.as_view({"get": "check_payment_status"}),
        name="payment-callback",
    ),
]
