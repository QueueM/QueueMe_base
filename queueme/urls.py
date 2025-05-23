"""Queue Me project — main URL configuration."""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse, HttpResponse
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

# -----------------------------------------------------------------------------
# Swagger / ReDoc API schema setup
# -----------------------------------------------------------------------------

schema_view = get_schema_view(
    openapi.Info(
        title="QueueMe API",
        default_version="v1",
        description="REST API for QueueMe",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@queueme.net"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    # Add URL prefix to help with schema generation
    url="https://api.queueme.net",
)


# -----------------------------------------------------------------------------
# Custom schema view to handle format parameter
# -----------------------------------------------------------------------------
def schema_view_with_format(request):
    """Handle schema requests with format parameter"""
    format_param = request.GET.get('format', 'json')
    if format_param == 'openapi':
        format_param = 'json'
    
    # Generate schema
    response = schema_view.without_ui(cache_timeout=0)(request, format=f'.{format_param}')
    
    # Add CORS headers if needed
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
    
    return response


# -----------------------------------------------------------------------------
# Health check endpoint
# -----------------------------------------------------------------------------
def health(request):
    """Minimal health-check endpoint used by load-balancers / uptime checks."""
    return JsonResponse({"status": "ok"})


# -----------------------------------------------------------------------------
# URL patterns
# -----------------------------------------------------------------------------
urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),
    
    # Application API (versioned)
    path("api/v1/", include("api.v1.urls")),
    
    # IMPORTANT: Raw schema endpoints MUST come before the UI endpoints
    # This handles the ?format=openapi parameter that Swagger UI uses
    path('api/docs/', schema_view_with_format, name='schema-with-format'),
    
    # Alternative schema endpoints with explicit format
    re_path(
        r"^api/docs/swagger\.json$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-swagger-json",
    ),
    re_path(
        r"^api/docs/swagger\.yaml$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-swagger-yaml",
    ),
    
    # Swagger UI (must come after raw schema endpoints)
    path(
        "api/docs/ui/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    
    # ReDoc UI
    path(
        "api/redoc/",
        schema_view.with_ui("redoc", cache_timeout=0),
        name="schema-redoc"
    ),
    
    # Health check endpoint
    path("health/", health, name="health_check"),
    
    # Redirect home "/" to Swagger UI
    path(
        "",
        RedirectView.as_view(url="/api/docs/ui/", permanent=False),
        name="home",
    ),
]

# -----------------------------------------------------------------------------
# Development-only static/media/debug helpers
# -----------------------------------------------------------------------------
if settings.DEBUG:
    # Static & media files served directly by Django's dev server
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Django Debug Toolbar — only if installed and enabled
    try:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ModuleNotFoundError:
        pass

# END OF FILE
