"""
URL configuration for Queue Me project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

# API Documentation schema configuration
schema_view = get_schema_view(
    openapi.Info(
        title="Queue Me API",
        default_version="v1",
        description="API documentation for the Queue Me platform",
        terms_of_service="https://queueme.net/terms/",
        contact=openapi.Contact(email="support@queueme.net"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)


# Health check view
def health_check(request):
    """Simple health check endpoint for monitoring"""
    from django.http import JsonResponse

    return JsonResponse({"status": "healthy"})


urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),
    # API Documentation
    path(
        "api/docs/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path(
        "api/redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"
    ),
    re_path(
        r"^api/swagger(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    # API versioning
    path("api/v1/", include("api.v1.urls")),
    # Health check
    path("api/health/", health_check, name="health_check"),
    # Application endpoints
    path("api/auth/", include("apps.authapp.urls")),
    path("api/roles/", include("apps.rolesapp.urls")),
    path("api/bookings/", include("apps.bookingapp.urls")),
    path("api/categories/", include("apps.categoriesapp.urls")),
    path("api/chat/", include("apps.chatapp.urls")),
    path("api/companies/", include("apps.companiesapp.urls")),
    path("api/customers/", include("apps.customersapp.urls")),
    path("api/discounts/", include("apps.discountapp.urls")),
    path("api/employees/", include("apps.employeeapp.urls")),
    path("api/follow/", include("apps.followapp.urls")),
    path("api/geo/", include("apps.geoapp.urls")),
    path("api/notifications/", include("apps.notificationsapp.urls")),
    path("api/packages/", include("apps.packageapp.urls")),
    path("api/payments/", include("apps.payment.urls")),
    path("api/admin/", include("apps.queueMeAdminApp.urls")),
    path("api/reels/", include("apps.reelsapp.urls")),
    path("api/analytics/", include("apps.reportanalyticsapp.urls")),
    path("api/reviews/", include("apps.reviewapp.urls")),
    path("api/services/", include("apps.serviceapp.urls")),
    path("api/shops/", include("apps.shopapp.urls")),
    path("api/dashboard/", include("apps.shopDashboardApp.urls")),
    path("api/specialists/", include("apps.specialistsapp.urls")),
    path("api/stories/", include("apps.storiesapp.urls")),
    path("api/subscriptions/", include("apps.subscriptionapp.urls")),
    # Frontend app redirect - catch-all for React router
    path("", RedirectView.as_view(url="https://queueme.net/")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Enable debug toolbar in development
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns += [
            path("__debug__/", include(debug_toolbar.urls)),
        ]
