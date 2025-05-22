"""Queue Me project — main URL configuration."""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path  # <-- Added re_path here
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
)


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
    # API Documentation (Swagger & Redoc via drf-yasg)
    path(
        "api/docs/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path(
        "api/redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"
    ),
    # --- THIS is the key line for raw OpenAPI schema JSON/YAML ---
    re_path(
        r"^api/docs/swagger(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    # Health check endpoint
    path("health/", health, name="health_check"),
    # Redirect home "/" to your Swagger homepage (optional)
    path(
        "",
        RedirectView.as_view(url="/static/swagger/", permanent=False),
        name="static-swagger-ui-home",
    ),
]

# -----------------------------------------------------------------------------
# Development-only static/media/debug helpers
# -----------------------------------------------------------------------------
if settings.DEBUG:
    # Static & media files served directly by Django’s dev server
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
