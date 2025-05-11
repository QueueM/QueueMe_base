"""
URL configuration for Queue Me project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView, TemplateView
from rest_framework import permissions
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from enhanced_docs_generator import schema_view

# Health check view
def health_check(request):
    """Simple health check endpoint for monitoring"""
    return JsonResponse({"status": "healthy"})

# Domain routing based on hostname
def domain_router(request):
    """Route to appropriate view based on the hostname"""
    host = request.get_host().split(':')[0]
    
    if host == 'admin.queueme.net':
        return RedirectView.as_view(url="/admin/")(request)
    elif host == 'api.queueme.net':
        return RedirectView.as_view(url="/api/docs/")(request)
    elif host == 'shop.queueme.net':
        return RedirectView.as_view(url="/api/shops/")(request)
    else:
        # Main domain
        return HttpResponse("<h1>QueueMe</h1><p>Welcome to QueueMe. Please visit the appropriate subdomain.</p>")

urlpatterns = [
    # Domain-based routing for root URL
    path("", domain_router, name="domain_router"),
    
    # Admin site
    path("admin/", admin.site.urls),
    
    # API Documentation
    path("api/docs/", TemplateView.as_view(
        template_name='api_docs.html',
        extra_context={'schema_url':'openapi-schema'}
    ), name="api-docs"),
    
    # Swagger/ReDoc documentation
    path("api/docs/swagger/", schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path("api/docs/redoc/", schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # OpenAPI Schema
    path("api/schema.json", schema_view.without_ui(cache_timeout=0), name='openapi-schema-json'),
    path("api/schema.yaml", schema_view.without_ui(cache_timeout=0), name='openapi-schema-yaml'),
    
    # Backward compatibility
    path("api/docs-static/", RedirectView.as_view(url="/api/docs/"), name="api-docs-static-redirect"),
    path("api/docs-dynamic/", RedirectView.as_view(url="/api/docs/swagger/"), name="api-docs-dynamic-redirect"),
    path("api/docs-fixed/", RedirectView.as_view(url="/api/docs/swagger/"), name="api-docs-fixed-redirect"),
    
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

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Enable debug toolbar in development
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns += [
            path("__debug__/", include(debug_toolbar.urls)),
        ]
