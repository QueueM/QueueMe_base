from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.authapp.views import AuthViewSet, UserProfileViewSet

# Create router for viewsets
router = DefaultRouter()
router.register(r"users", UserProfileViewSet, basename="user-profile")

# URL patterns for standard views
urlpatterns = [
    path("request-otp/", AuthViewSet.as_view({"post": "request_otp"}), name="request-otp"),
    path("verify-otp/", AuthViewSet.as_view({"post": "verify_otp"}), name="verify-otp"),
    path(
        "token/refresh/",
        AuthViewSet.as_view({"post": "refresh_token"}),
        name="refresh-token",
    ),
    path("login/", AuthViewSet.as_view({"post": "login"}), name="login"),
    path("logout/", AuthViewSet.as_view({"post": "logout"}), name="logout"),
    path(
        "change-language/",
        AuthViewSet.as_view({"post": "change_language"}),
        name="change-language",
    ),
    path(
        "profile/",
        UserProfileViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"}),
        name="profile",
    ),
]

# Include router URLs
urlpatterns += router.urls
