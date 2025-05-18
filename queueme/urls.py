"""Queue Me project — main URL configuration.

This file wires together Django admin, app APIs, interactive documentation,
health‑checks and development‑only helpers (static files & Debug Toolbar).

Nothing that could leak sensitive information is enabled unless
``settings.DEBUG`` is **True**.
"""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import TemplateView

from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

###############################################################################
# API schema (Swagger / ReDoc)
###############################################################################

schema_view = get_schema_view(
    openapi.Info(
        title="QueueMe API",
        default_version="v1",
        description="REST API for QueueMe",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@example.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

###############################################################################
# Small utility endpoints
###############################################################################

def health(request):
    """Minimal health‑check endpoint used by load‑balancers / uptime checks."""
    return JsonResponse({"status": "ok"})

###############################################################################
# Core URL patterns — order matters!
###############################################################################

urlpatterns: list[path] = [
    # Django admin (default UI)
    path("admin/", admin.site.urls),

    # Application API (versioned)
    path("api/v1/", include("api.v1.urls")),

    # Interactive API docs
    path("api/docs/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("api/redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),

    # Health check
    path("health/", health, name="health_check"),

    # Front‑end fallback (serves the SPA entry point or simple index page)
    path("", TemplateView.as_view(template_name="index.html"), name="index"),
]

###############################################################################
# Development‑only helpers
###############################################################################

if settings.DEBUG:
    # Static & media files served directly by Django’s dev server.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Django Debug Toolbar — only if it’s installed *and* enabled.
    try:
        import debug_toolbar  # noqa: WPS433 — optional debug package

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ModuleNotFoundError:
        # Toolbar not installed; skip silently.
        pass
