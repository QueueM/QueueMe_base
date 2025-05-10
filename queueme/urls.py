"""
URL configuration for Queue Me project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

# Add simple test views
def test_view(request):
    """Simple test view to verify basic Django functionality"""
    return HttpResponse("<h1>Django is working!</h1><p>This is a simple test view.</p>")

def debug_view(request):
    """Debug view to show request information"""
    import sys
    html = "<h1>Debug Information</h1>"
    html += "<h2>Python</h2>"
    html += f"<p>Version: {sys.version}</p>"
    html += "<h2>Request</h2>"
    html += f"<p>Path: {request.path}</p>"
    html += f"<p>Host: {request.get_host()}</p>"
    html += f"<p>Headers: {request.headers}</p>"
    return HttpResponse(html)

# Add a test view to check static files
def static_test(request):
    """Test view to verify static files are working properly"""
    from django.http import HttpResponse
    html = """
    <html>
    <head>
        <title>Static Files Test</title>
        <link rel='stylesheet' type='text/css' href='/static/admin/css/base.css'>
        <link rel='stylesheet' type='text/css' href='/static/admin/css/nav_sidebar.css'>
        <link rel='stylesheet' type='text/css' href='/static/admin/css/responsive.css'>
        <style>
            body { padding: 20px; }
            .test-block { background-color: #f8f8f8; border: 1px solid #ddd; padding: 10px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>Static Files Test</h1>
        <p>If styling is working, this text should be styled like the Django admin interface.</p>
        
        <div class="test-block">
            <h2>Request Information</h2>
            <p>Host: """ + request.get_host() + """</p>
            <p>Path: """ + request.path + """</p>
        </div>
        
        <div class="test-block">
            <h2>Static Files Being Tested</h2>
            <ul>
                <li>/static/admin/css/base.css</li>
                <li>/static/admin/css/nav_sidebar.css</li>
                <li>/static/admin/css/responsive.css</li>
            </ul>
        </div>
        
        <div class="module">
            <h2>This should be styled as a Django admin module</h2>
            <p>If you see styling here, the admin CSS is loading correctly.</p>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html)

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

# Route based on hostname
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
        # Main domain - could point to a static frontend
        return HttpResponse("<h1>QueueMe</h1><p>Welcome to QueueMe. Please visit the appropriate subdomain.</p>")


urlpatterns = [
    # Test views
    path("test/", test_view, name="test_view"),
    path("debug/", debug_view, name="debug_view"),
    path("static-test/", static_test, name="static_test"),
    
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
    
    # Root URL - domain-based routing
    path("", domain_router, name="domain_router"),
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
