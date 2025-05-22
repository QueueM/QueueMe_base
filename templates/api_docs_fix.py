"""
API Documentation fix for QueueMe
"""

from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.views import get_schema_view as yasg_get_schema_view
from rest_framework.permissions import AllowAny


class CustomOpenAPISchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, request=None, public=False):
        """
        Generate a schema while avoiding problematic serializers
        """
        schema = super().get_schema(request, public)

        # Skip problematic serializers/operations
        paths_to_keep = {}
        for path, path_item in schema.paths.items():
            # Keep only basic endpoints to ensure it works properly
            if (
                path.startswith("/api/health")
                or path.startswith("/api/auth")
                or path.startswith("/api/shops")
            ):
                paths_to_keep[path] = path_item

        schema.paths = paths_to_keep
        return schema


schema_view = yasg_get_schema_view(
    openapi.Info(
        title="QueueMe API",
        default_version="v1",
        description="QueueMe platform API documentation",
        terms_of_service="https://queueme.net/terms/",
        contact=openapi.Contact(email="info@queueme.net"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    generator_class=CustomOpenAPISchemaGenerator,
    permission_classes=(AllowAny,),
)
