from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet, ads_webhook, merchant_webhook, subscription_webhook
from .webhooks import MoyasarWebhookView

router = DefaultRouter()
router.register(r"payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("", include(router.urls)),
    # Generic Moyasar webhook (legacy)
    path("webhook/moyasar/", MoyasarWebhookView.as_view(), name="moyasar-webhook"),
    # Specific webhooks for each wallet
    path("webhooks/subscription/", subscription_webhook, name="subscription_webhook"),
    path("webhooks/ads/", ads_webhook, name="ads_webhook"),
    path("webhooks/merchant/", merchant_webhook, name="merchant_webhook"),
    path(
        "callback/<uuid:transaction_id>/",
        PaymentViewSet.as_view({"get": "check_payment_status"}),
        name="payment-callback",
    ),
]
