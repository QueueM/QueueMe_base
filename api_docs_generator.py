# File: /home/arise/queueme/api_docs_generator.py

from django.conf import settings
from rest_framework import permissions
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.utils import swagger_auto_schema
import logging

logger = logging.getLogger(__name__)

class SafeOpenAPISchemaGenerator(OpenAPISchemaGenerator):
    """Schema generator that handles problematic endpoints safely"""
    
    def get_schema(self, request=None, public=False):
        """Generate schema with error handling for problematic serializers"""
        try:
            schema = super().get_schema(request, public)
            return schema
        except Exception as e:
            logger.error(f"Error generating schema: {e}")
            # Return minimal schema on error
            return self._get_fallback_schema()
    
    def _get_fallback_schema(self):
        """Create minimal schema when full schema generation fails"""
        info = openapi.Info(
            title="QueueMe API",
            default_version='v1',
            description="QueueMe platform API documentation"
        )
        
        schema = openapi.Schema(
            title=info.title,
            description=info.description,
            type=openapi.TYPE_OBJECT,
        )
        
        # Add core endpoints manually
        paths = {
            '/api/health/': self._get_health_endpoint(),
            '/api/auth/token/': self._get_auth_endpoint(),
            '/api/shops/': self._get_shops_endpoint(),
            # Add more basic endpoints manually
        }
        
        return self.get_schema_object(paths, info=info)
    
    def _get_health_endpoint(self):
        """Create health endpoint documentation"""
        return openapi.PathItem(
            get=openapi.Operation(
                operation_id='health_check',
                description='Check API health status',
                responses={
                    200: openapi.Response(
                        description='Healthy response',
                        schema=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'status': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    )
                }
            )
        )
    
    def _get_auth_endpoint(self):
        """Create authentication endpoint documentation"""
        return openapi.PathItem(
            post=openapi.Operation(
                operation_id='token_obtain',
                description='Obtain JWT token for authentication',
                request_body=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    required=['phone', 'password'],
                    properties={
                        'phone': openapi.Schema(type=openapi.TYPE_STRING),
                        'password': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD),
                    }
                ),
                responses={
                    200: openapi.Response(
                        description='Token obtained successfully',
                        schema=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'access': openapi.Schema(type=openapi.TYPE_STRING),
                                'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    ),
                    401: openapi.Response(description='Authentication failed')
                }
            )
        )
    
    def _get_shops_endpoint(self):
        """Create shops endpoint documentation"""
        return openapi.PathItem(
            get=openapi.Operation(
                operation_id='list_shops',
                description='List all available shops',
                responses={
                    200: openapi.Response(
                        description='List of shops',
                        schema=openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'description': openapi.Schema(type=openapi.TYPE_STRING),
                                }
                            )
                        )
                    )
                }
            )
        )


# Create schema views
schema_view = get_schema_view(
    openapi.Info(
        title="QueueMe API",
        default_version='v1',
        description="Complete API documentation for the QueueMe platform",
        terms_of_service="https://queueme.net/terms/",
        contact=openapi.Contact(email="info@queueme.net"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    generator_class=SafeOpenAPISchemaGenerator,
)

# Decorator to add standard responses to all endpoints
def standard_api_responses(function):
    """Add standard API responses to all endpoints"""
    return swagger_auto_schema(
        responses={
            400: 'Bad request',
            401: 'Unauthorized',
            403: 'Permission denied',
            404: 'Not found',
            500: 'Server error',
        }
    )(function)
