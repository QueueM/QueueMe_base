"""
URL configuration for Queue Me project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView, TemplateView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

# Import our URL fixes
from urls_fix import apply_urls_fix

# Import custom admin
# Removed custom admin import

# Create the API documentation schema view
schema_view = get_schema_view(
    openapi.Info(
        title="QueueMe API",
        default_version="v1",
        description="REST API for QueueMe",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@example.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,  # Let the API docs be publicly accessible
    permission_classes=(permissions.AllowAny,),
)

# Health check endpoint
def check_health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    # Django Admin - Restored default admin
    path("admin/", admin.site.urls),
    # Removed custom admin path
    # API
    path("api/v1/", include("api.v1.urls")),
    # API Documentation
    path("api/docs/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("api/redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    # Health check
    path("health/", check_health, name="health_check"),
    # Main site
    path("", TemplateView.as_view(template_name="index.html"), name="index"),
]

# Apply URL fixes from the custom module
apply_urls_fix(urlpatterns)

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
