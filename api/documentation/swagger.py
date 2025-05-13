# api/documentation/swagger.py
from django.urls import path, re_path
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

# Create a schema view for Swagger documentation
schema_view = get_schema_view(
    openapi.Info(
        title=_("Queue Me API"),
        default_version="v1",
        description=_(
            "Queue Me platform API provides endpoints for managing bookings, services, "
            "reels, stories, live chat, and specialists efficiently. The platform focuses "
            "on enhancing the customer experience through seamless scheduling, real-time "
            "updates, and flexible service options."
        ),
        terms_of_service="https://queueme.net/terms/",
        contact=openapi.Contact(email="support@queueme.net"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

# Generate the URL patterns for Swagger documentation
swagger_urlpatterns = [
    re_path(
        r"^swagger(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
