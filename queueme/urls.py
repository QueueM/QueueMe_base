"""
URL configuration for Queue Me project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

# Import our URL fixes
from urls_fix import apply_urls_fix

# Create schema view for API documentation
schema_view = get_schema_view(
    openapi.Info(
        title="QueueMe API",
        default_version="v1",
        description="API for QueueMe - Advanced Queue and Appointment Management Platform",
        terms_of_service="https://www.queueme.net/terms/",
        contact=openapi.Contact(email="support@queueme.net"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    # Ensure the schema is freely accessible without authentication
    authentication_classes=[],
)


# Health check view
def health_check(request):
    """Simple health check endpoint for monitoring"""
    return JsonResponse({"status": "healthy"})


# Domain routing based on hostname
def domain_router(request):
    """Route to appropriate view based on the hostname"""
    host = request.get_host().split(":")[0]

    if host == "admin.queueme.net":
        return RedirectView.as_view(url="/admin/")(request)
    elif host == "api.queueme.net":
        return RedirectView.as_view(url="/api/docs/")(request)
    elif host == "shop.queueme.net":
        return RedirectView.as_view(url="/api/shops/")(request)
    else:
        # Main domain
        return HttpResponse(
            "<h1>QueueMe</h1><p>Welcome to QueueMe. Please visit the appropriate subdomain.</p>"
        )


urlpatterns = [
    # Domain-based routing for root URL
    path("", domain_router, name="domain_router"),
    # Admin site
    path("admin/", admin.site.urls),
    # API Documentation Pages - Public Access
    path(
        "api/docs/schema.json",
        TemplateView.as_view(
            template_name="api_docs/static-schema.json",
            content_type="application/json",
        ),
        name="schema-json",
    ),
    path(
        "api/docs/schema.yaml",
        TemplateView.as_view(
            template_name="api_docs/static-schema.yaml",
            content_type="text/yaml",
        ),
        name="schema-yaml",
    ),
    path(
        "api/docs/",
        TemplateView.as_view(
            template_name="api_docs/index.html", extra_context={"active_page": "docs"}
        ),
        name="api-docs",
    ),
    path(
        "api/docs/swagger/",
        TemplateView.as_view(
            template_name="api_docs/swagger.html",
            extra_context={"active_page": "swagger"},
        ),
        name="swagger-ui",
    ),
    path(
        "api/docs/redoc/",
        TemplateView.as_view(
            template_name="api_docs/redoc.html", extra_context={"active_page": "redoc"}
        ),
        name="redoc-ui",
    ),
    path(
        "api/guide/",
        TemplateView.as_view(
            template_name="api_docs/guide.html", extra_context={"active_page": "guide"}
        ),
        name="api-guide",
    ),
    path(
        "api/developers/",
        TemplateView.as_view(
            template_name="api_docs/developers.html",
            extra_context={"active_page": "developers"},
        ),
        name="developer-portal",
    ),
    path(
        "api/support/",
        TemplateView.as_view(
            template_name="api_docs/support.html",
            extra_context={"active_page": "support"},
        ),
        name="support",
    ),
    # Health check
    path("api/health/", health_check, name="health_check"),
    # API Applications - all app URLs
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
    path("api/marketing/", include("apps.marketingapp.urls")),
    path("api/notifications/", include("apps.notificationsapp.urls")),
    path("api/packages/", include("apps.packageapp.urls")),
    path("api/payments/", include("apps.payment.urls")),
    path("api/admin/", include("apps.queueMeAdminApp.urls")),
    path("api/queues/", include("apps.queueapp.urls")),
    path("api/reels/", include("apps.reelsapp.urls")),
    path("api/analytics/", include("apps.reportanalyticsapp.urls")),
    path("api/reviews/", include("apps.reviewapp.urls")),
    path("api/services/", include("apps.serviceapp.urls")),
    path("api/shops/", include("apps.shopapp.urls")),
    path("api/dashboard/", include("apps.shopDashboardApp.urls")),
    path("api/specialists/", include("apps.specialistsapp.urls")),
    path("api/stories/", include("apps.storiesapp.urls")),
    path("api/subscriptions/", include("apps.subscriptionapp.urls")),
]

# Add Prometheus metrics endpoint in production
if not settings.DEBUG:
    urlpatterns += [
        path("", include("django_prometheus.urls")),
    ]

# Serve media and static files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Enable debug toolbar in development
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns += [
            path("__debug__/", include(debug_toolbar.urls)),
        ]
