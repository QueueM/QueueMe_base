# apps/subscriptionapp/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CompanySubscriptionView,
    FeatureUsageViewSet,
    PlanViewSet,
    SubscriptionCancelView,
    SubscriptionInvoiceViewSet,
    SubscriptionPaymentView,
    SubscriptionRenewalView,
    SubscriptionViewSet,
)

router = DefaultRouter()
router.register(r"plans", PlanViewSet, basename="plan")
router.register(r"subscriptions", SubscriptionViewSet, basename="subscription")
router.register(
    r"invoices", SubscriptionInvoiceViewSet, basename="subscription-invoice"
)
router.register(r"usage", FeatureUsageViewSet, basename="feature-usage")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "payment/initiate/",
        SubscriptionPaymentView.as_view(),
        name="subscription-payment",
    ),
    path("renewal/", SubscriptionRenewalView.as_view(), name="subscription-renewal"),
    path("cancel/", SubscriptionCancelView.as_view(), name="subscription-cancel"),
    path(
        "company/<uuid:company_id>/",
        CompanySubscriptionView.as_view(),
        name="company-subscription",
    ),
]
