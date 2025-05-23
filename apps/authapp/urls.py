from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.authapp.views import AuthViewSet, UserViewSet

# Create router for viewsets
router = DefaultRouter()
router.register(r"admin/users", UserViewSet, basename="users")

# URL patterns for authentication views
urlpatterns = [
    path("request-otp/", AuthViewSet.as_view({"post": "request_otp"}), name="request-otp"),
    path("verify-otp/", AuthViewSet.as_view({"post": "verify_otp"}), name="verify-otp"),
    path(
        "token/refresh/",
        AuthViewSet.as_view({"post": "refresh_token"}),
        name="refresh-token",
    ),
    path(
        "change-language/",
        AuthViewSet.as_view({"post": "change_language"}),
        name="change-language",
    ),
    path(
        "profile/",
        AuthViewSet.as_view({
            "get": "get_profile", 
            "put": "update_profile", 
            "patch": "update_profile"
        }),
        name="profile",
    ),
]

# Include router URLs for admin user management
urlpatterns += router.urls
