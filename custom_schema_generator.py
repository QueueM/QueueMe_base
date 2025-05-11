"""
Custom OpenAPI Schema Generator for QueueMe API
Extends the default drf-yasg schema generator with customizations
to handle problematic serializers and provide more robust documentation
"""

from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg import openapi
import logging
from django.urls import get_resolver
import inspect
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

class QueueMeSchemaGenerator(OpenAPISchemaGenerator):
    """
    Custom schema generator that provides more robust error handling
    and additional metadata for QueueMe API endpoints
    """
    
    def get_schema(self, request=None, public=False):
        """
        Override the default schema generation to handle problematic serializers
        and add additional metadata
        """
        try:
            schema = super().get_schema(request, public)
            
            # Add custom schema metadata
            schema.info.contact = openapi.Contact(
                name="QueueMe Support",
                email="support@queueme.net",
                url="https://queueme.net/support"
            )
            
            schema.info.license = openapi.License(
                name="Proprietary",
                url="https://queueme.net/terms"
            )
            
            schema.info.termsOfService = "https://queueme.net/terms"
            
            # Add global security requirement for JWT
            schema.security = [
                {"Bearer": []}
            ]
            
            # Add global security definitions
            schema.securityDefinitions = {
                "Bearer": openapi.SecurityScheme(
                    type=openapi.TYPE_API_KEY,
                    in_=openapi.IN_HEADER,
                    name="Authorization",
                    description="JWT token authentication. Format: Bearer <token>"
                )
            }
            
            # Enhance and sanitize paths to prevent errors
            self._enhance_paths(schema)
            
            # Add custom extensions
            schema.info.extensions = {
                "x-logo": {
                    "url": "https://queueme.net/static/images/logo.png",
                    "backgroundColor": "#FFFFFF",
                    "altText": "QueueMe Logo"
                }
            }
            
            return schema
        except Exception as e:
            logger.error(f"Error generating schema: {str(e)}")
            # Return a minimal but valid schema in case of error
            return self._create_fallback_schema()
    
    def _enhance_paths(self, schema):
        """
        Enhance path objects with additional metadata and sanitize to prevent errors
        """
        enhanced_paths = openapi.Paths()
        problematic_paths = []
        
        # Process and enhance each path
        for path, path_item in schema.paths.items():
            try:
                # Get view for this path to add more metadata
                view_cls = self._get_view_for_path(path)
                if path_item and view_cls:
                    # Add any custom metadata from view decorators if available
                    if hasattr(view_cls, 'api_doc_metadata'):
                        for operation_id, operation in path_item.operations.items():
                            # Add tags if not present
                            if not operation.tags and view_cls.api_doc_metadata.get('tags'):
                                operation.tags = view_cls.api_doc_metadata.get('tags')
                                
                            # Add deprecation info if present
                            if hasattr(view_cls, 'deprecation_info'):
                                operation.deprecated = True
                                operation.description = f"DEPRECATED: {operation.description}\n\n{view_cls.deprecation_info}"
                
                enhanced_paths[path] = path_item
            except Exception as e:
                logger.warning(f"Skipping problematic path {path}: {str(e)}")
                problematic_paths.append(path)
                continue
        
        # Replace the original paths with the enhanced ones
        schema.paths = enhanced_paths
        
        # Log information about problematic paths
        if problematic_paths:
            logger.info(f"Skipped {len(problematic_paths)} problematic paths during schema generation")
    
    def _get_view_for_path(self, path):
        """
        Get the view class for a given path
        """
        try:
            resolver = get_resolver()
            for pattern in resolver.url_patterns:
                if hasattr(pattern, 'pattern') and path.startswith(pattern.pattern.regex.pattern.replace('^', '').replace('$', '')):
                    if hasattr(pattern.callback, 'cls'):
                        return pattern.callback.cls
                    elif hasattr(pattern.callback, 'view_class'):
                        return pattern.callback.view_class
                    elif inspect.isclass(pattern.callback) and issubclass(pattern.callback, APIView):
                        return pattern.callback
            return None
        except Exception as e:
            logger.warning(f"Error finding view for path {path}: {str(e)}")
            return None
    
    def _create_fallback_schema(self):
        """
        Create a minimal but valid schema in case of errors
        """
        info = openapi.Info(
            title="QueueMe API",
            default_version='v1',
            description="QueueMe API Documentation (Fallback Schema)",
            contact=openapi.Contact(email="support@queueme.net"),
        )
        
        schema = openapi.Swagger(
            info=info,
            paths=openapi.Paths({
                '/api/health/': openapi.PathItem(
                    get=openapi.Operation(
                        operation_id='health_check',
                        description='API health check endpoint',
                        responses={
                            200: openapi.Response(description='API is up and running')
                        }
                    )
                )
            }),
        )
        
        return schema
