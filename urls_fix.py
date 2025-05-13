"""
URL patterns fix utility for QueueMe

This script improves and fixes URL patterns in the QueueMe Django project,
particularly for API documentation endpoints.
"""

from django.conf import settings
from django.urls import include, path
from django.views.generic import RedirectView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework.permissions import AllowAny

# Import from our custom API docs fix module
from api_docs_fix import APIDocsFixer

# Create a fixed schema view with our custom generator
schema_view = get_schema_view(
    openapi.Info(
        title="QueueMe API",
        default_version="v1",
        description="QueueMe platform API documentation",
        terms_of_service="https://queueme.net/terms/",
        contact=openapi.Contact(email="info@queueme.net"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=(AllowAny,),
)

# Define URL patterns for API documentation
api_doc_patterns = [
    # Swagger UI
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    # ReDoc UI (more user-friendly alternative)
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    # OpenAPI schema as JSON
    path("schema/", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    # Default redirect to Swagger UI
    path("", RedirectView.as_view(url="swagger/", permanent=False), name="api-docs-root"),
]


def fix_url_patterns(urlpatterns):
    """
    Fix and enhance URL patterns in the project.

    Args:
        urlpatterns: Original URL patterns from urls.py

    Returns:
        Enhanced URL patterns with fixed documentation endpoints
    """
    # Add API documentation URLs
    urlpatterns.append(path("api/docs/", include(api_doc_patterns)))

    # Add debug toolbar if in DEBUG mode
    if settings.DEBUG:
        try:
            import debug_toolbar

            urlpatterns.append(path("__debug__/", include(debug_toolbar.urls)))
        except ImportError:
            pass

    return urlpatterns


def fix_api_docs_urls():
    """Fix API documentation URLs after they've been generated."""
    docs_fixer = APIDocsFixer()
    return docs_fixer.fix_documentation()


def apply_urls_fix(urlpatterns):
    """
    Apply all URL fixes to the project.

    Args:
        urlpatterns: Original URL patterns

    Returns:
        Fixed URL patterns
    """
    # Fix URL patterns
    fixed_patterns = fix_url_patterns(urlpatterns)

    # Also fix API docs if they exist
    fix_api_docs_urls()

    return fixed_patterns
