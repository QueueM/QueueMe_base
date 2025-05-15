from django.urls import include, path

from .admin import admin_site
from .views import AdminDashboardView

# Custom URL patterns for the admin site
custom_urls = [
    path("", AdminDashboardView.as_view(), name="index"),
    # Add more custom admin views here as needed
]

# Main URL pattern that includes both the custom admin site and custom views
urlpatterns = [
    path("", admin_site.urls),
]
