"""
Minimal URL configuration for testing

This module provides a minimal URL configuration that avoids importing
problematic dependencies like drf_yasg.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

# Create minimal URL patterns without including app URLs that might import problematic modules
urlpatterns = [
    path("admin/", admin.site.urls),
    # Don't include app URLs that might import problematic modules
]

# Add static and media URLs for testing
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
