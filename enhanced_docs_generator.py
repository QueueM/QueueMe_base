"""
Enhanced Documentation Generator for QueueMe API

This module creates a robust Swagger/OpenAPI schema generator that:
1. Handles problematic serializers and views
2. Generates complete documentation
3. Provides fallbacks when schema generation fails
"""

import logging
import inspect
import importlib
from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.views import get_schema_view
from rest_framework import permissions, serializers, views

logger = logging.getLogger(__name__)

class EnhancedOpenAPISchemaGenerator(OpenAPISchemaGenerator):
    """
    Enhanced schema generator that handles problematic serializers and views gracefully.
    If schema generation fails for any endpoint, it falls back to a safe representation.
    """
    
    def get_schema(self, request=None, public=False):
        """
        Generate schema with error handling for problematic serializers or views.
        """
        try:
            # Try standard schema generation
            return super().get_schema(request, public)
        except Exception as e:
            logger.error(f"Error generating schema: {str(e)}")
            return self._get_fallback_schema()
    
    def _get_fallback_schema(self):
        """Create minimal fallback schema when full schema generation fails"""
        info = openapi.Info(
            title="QueueMe API",
            default_version='v1',
            description="Complete API documentation for the QueueMe platform",
            terms_of_service="https://queueme.net/terms/",
            contact=openapi.Contact(email="info@queueme.net"),
            license=openapi.License(name="Proprietary"),
        )
        
        paths = {}
        
        # Add core API resources to ensure at least these are documented
        self._add_auth_endpoints(paths)
        self._add_shop_endpoints(paths)
        self._add_specialist_endpoints(paths)
        self._add_service_endpoints(paths)
        self._add_booking_endpoints(paths)
        self._add_package_endpoints(paths)
        self._add_health_endpoint(paths)
        
        return self.get_schema_object(paths, info=info)
    
    def _add_health_endpoint(self, paths):
        """Add health check endpoint"""
        paths['/api/health/'] = openapi.PathItem(
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
    
    def _add_auth_endpoints(self, paths):
        """Add authentication endpoints"""
        # Token endpoint
        paths['/api/auth/token/'] = openapi.PathItem(
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
        
        # Refresh token endpoint
        paths['/api/auth/token/refresh/'] = openapi.PathItem(
            post=openapi.Operation(
                operation_id='token_refresh',
                description='Refresh JWT token',
                request_body=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    required=['refresh'],
                    properties={
                        'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                ),
                responses={
                    200: openapi.Response(
                        description='Token refreshed successfully',
                        schema=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'access': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    ),
                    401: openapi.Response(description='Invalid refresh token')
                }
            )
        )
        
        # Register endpoint
        paths['/api/auth/register/'] = openapi.PathItem(
            post=openapi.Operation(
                operation_id='register',
                description='Register a new user',
                request_body=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    required=['phone', 'password', 'password_confirm', 'first_name', 'last_name'],
                    properties={
                        'phone': openapi.Schema(type=openapi.TYPE_STRING),
                        'password': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD),
                        'password_confirm': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD),
                        'first_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'last_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'email': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL),
                    }
                ),
                responses={
                    201: openapi.Response(description='User created successfully'),
                    400: openapi.Response(description='Invalid request data')
                }
            )
        )
    
    def _add_shop_endpoints(self, paths):
        """Add basic shop endpoints"""
        # List shops
        paths['/api/shops/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='list_shops',
                description='List all shops',
                parameters=[
                    openapi.Parameter('page', openapi.IN_QUERY, description='Page number', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('page_size', openapi.IN_QUERY, description='Results per page', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('search', openapi.IN_QUERY, description='Search shops by name', type=openapi.TYPE_STRING),
                    openapi.Parameter('city', openapi.IN_QUERY, description='Filter by city', type=openapi.TYPE_STRING),
                    openapi.Parameter('is_active', openapi.IN_QUERY, description='Filter by active status', type=openapi.TYPE_BOOLEAN),
                    openapi.Parameter('is_verified', openapi.IN_QUERY, description='Filter by verification status', type=openapi.TYPE_BOOLEAN),
                ],
                responses={
                    200: openapi.Response(description='List of shops'),
                    401: openapi.Response(description='Unauthorized')
                }
            ),
            post=openapi.Operation(
                operation_id='create_shop',
                description='Create a new shop',
                request_body=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    required=['name', 'company', 'username', 'phone', 'location_lat', 'location_lng', 'location_address', 'location_city', 'location_country'],
                    properties={
                        'name': openapi.Schema(type=openapi.TYPE_STRING),
                        'description': openapi.Schema(type=openapi.TYPE_STRING),
                        'company': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'username': openapi.Schema(type=openapi.TYPE_STRING),
                        'phone': openapi.Schema(type=openapi.TYPE_STRING),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                        'location_lat': openapi.Schema(type=openapi.TYPE_NUMBER, format=openapi.FORMAT_FLOAT),
                        'location_lng': openapi.Schema(type=openapi.TYPE_NUMBER, format=openapi.FORMAT_FLOAT),
                        'location_address': openapi.Schema(type=openapi.TYPE_STRING),
                        'location_city': openapi.Schema(type=openapi.TYPE_STRING),
                        'location_country': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                ),
                responses={
                    201: openapi.Response(description='Shop created successfully'),
                    400: openapi.Response(description='Invalid request data'),
                    401: openapi.Response(description='Unauthorized'),
                    403: openapi.Response(description='Permission denied')
                }
            )
        )
        
        # Single shop operations
        paths['/api/shops/{id}/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='retrieve_shop',
                description='Retrieve a specific shop',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Shop ID', type=openapi.TYPE_INTEGER, required=True),
                ],
                responses={
                    200: openapi.Response(description='Shop details'),
                    404: openapi.Response(description='Shop not found')
                }
            ),
            put=openapi.Operation(
                operation_id='update_shop',
                description='Update a shop',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Shop ID', type=openapi.TYPE_INTEGER, required=True),
                ],
                responses={
                    200: openapi.Response(description='Shop updated successfully'),
                    400: openapi.Response(description='Invalid request data'),
                    401: openapi.Response(description='Unauthorized'),
                    403: openapi.Response(description='Permission denied'),
                    404: openapi.Response(description='Shop not found')
                }
            ),
            patch=openapi.Operation(
                operation_id='partial_update_shop',
                description='Partially update a shop',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Shop ID', type=openapi.TYPE_INTEGER, required=True),
                ],
                responses={
                    200: openapi.Response(description='Shop updated successfully'),
                    400: openapi.Response(description='Invalid request data'),
                    401: openapi.Response(description='Unauthorized'),
                    403: openapi.Response(description='Permission denied'),
                    404: openapi.Response(description='Shop not found')
                }
            ),
            delete=openapi.Operation(
                operation_id='delete_shop',
                description='Delete a shop',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Shop ID', type=openapi.TYPE_INTEGER, required=True),
                ],
                responses={
                    204: openapi.Response(description='Shop deleted successfully'),
                    401: openapi.Response(description='Unauthorized'),
                    403: openapi.Response(description='Permission denied'),
                    404: openapi.Response(description='Shop not found')
                }
            )
        )
    
    def _add_specialist_endpoints(self, paths):
        """Add specialist endpoints"""
        # List specialists
        paths['/api/specialists/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='list_specialists',
                description='List all specialists',
                parameters=[
                    openapi.Parameter('page', openapi.IN_QUERY, description='Page number', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('page_size', openapi.IN_QUERY, description='Results per page', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('shop_id', openapi.IN_QUERY, description='Filter by shop ID', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('service_id', openapi.IN_QUERY, description='Filter by service ID', type=openapi.TYPE_INTEGER),
                ],
                responses={
                    200: openapi.Response(description='List of specialists'),
                    401: openapi.Response(description='Unauthorized')
                }
            )
        )
        
        # Get specialist details
        paths['/api/specialists/{id}/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='retrieve_specialist',
                description='Retrieve a specific specialist',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Specialist ID', type=openapi.TYPE_INTEGER, required=True),
                ],
                responses={
                    200: openapi.Response(description='Specialist details'),
                    404: openapi.Response(description='Specialist not found')
                }
            )
        )
        
        # Get specialist availability
        paths['/api/specialists/{id}/availability/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='specialist_availability',
                description='Get availability for a specialist',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Specialist ID', type=openapi.TYPE_INTEGER, required=True),
                    openapi.Parameter('date', openapi.IN_QUERY, description='Date (YYYY-MM-DD)', type=openapi.TYPE_STRING),
                ],
                responses={
                    200: openapi.Response(description='Specialist availability'),
                    404: openapi.Response(description='Specialist not found')
                }
            )
        )
    
    def _add_service_endpoints(self, paths):
        """Add service endpoints"""
        # List services
        paths['/api/services/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='list_services',
                description='List all services',
                parameters=[
                    openapi.Parameter('page', openapi.IN_QUERY, description='Page number', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('page_size', openapi.IN_QUERY, description='Results per page', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('shop_id', openapi.IN_QUERY, description='Filter by shop ID', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('category_id', openapi.IN_QUERY, description='Filter by category ID', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('min_price', openapi.IN_QUERY, description='Minimum price', type=openapi.TYPE_NUMBER),
                    openapi.Parameter('max_price', openapi.IN_QUERY, description='Maximum price', type=openapi.TYPE_NUMBER),
                ],
                responses={
                    200: openapi.Response(description='List of services'),
                    401: openapi.Response(description='Unauthorized')
                }
            )
        )
        
        # Get service details
        paths['/api/services/{id}/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='retrieve_service',
                description='Retrieve a specific service',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Service ID', type=openapi.TYPE_INTEGER, required=True),
                ],
                responses={
                    200: openapi.Response(description='Service details'),
                    404: openapi.Response(description='Service not found')
                }
            )
        )
        
        # List service categories
        paths['/api/services/categories/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='list_service_categories',
                description='List service categories',
                responses={
                    200: openapi.Response(description='List of categories')
                }
            )
        )
    
    def _add_booking_endpoints(self, paths):
        """Add booking endpoints"""
        # List bookings
        paths['/api/bookings/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='list_bookings',
                description='List bookings for the authenticated user',
                parameters=[
                    openapi.Parameter('page', openapi.IN_QUERY, description='Page number', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('page_size', openapi.IN_QUERY, description='Results per page', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('status', openapi.IN_QUERY, description='Booking status', type=openapi.TYPE_STRING, enum=['scheduled', 'confirmed', 'completed', 'cancelled']),
                    openapi.Parameter('from_date', openapi.IN_QUERY, description='From date (YYYY-MM-DD)', type=openapi.TYPE_STRING),
                    openapi.Parameter('to_date', openapi.IN_QUERY, description='To date (YYYY-MM-DD)', type=openapi.TYPE_STRING),
                ],
                responses={
                    200: openapi.Response(description='List of bookings'),
                    401: openapi.Response(description='Unauthorized')
                }
            ),
            post=openapi.Operation(
                operation_id='create_booking',
                description='Create a new booking',
                request_body=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    required=['shop_id', 'service_id', 'specialist_id', 'start_time'],
                    properties={
                        'shop_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'service_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'specialist_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'start_time': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME),
                        'notes': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                ),
                responses={
                    201: openapi.Response(description='Booking created successfully'),
                    400: openapi.Response(description='Invalid request data'),
                    401: openapi.Response(description='Unauthorized')
                }
            )
        )
        
        # Single booking operations
        paths['/api/bookings/{id}/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='retrieve_booking',
                description='Retrieve a specific booking',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Booking ID', type=openapi.TYPE_INTEGER, required=True),
                ],
                responses={
                    200: openapi.Response(description='Booking details'),
                    401: openapi.Response(description='Unauthorized'),
                    403: openapi.Response(description='Permission denied'),
                    404: openapi.Response(description='Booking not found')
                }
            ),
            put=openapi.Operation(
                operation_id='update_booking',
                description='Update a booking',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Booking ID', type=openapi.TYPE_INTEGER, required=True),
                ],
                responses={
                    200: openapi.Response(description='Booking updated successfully'),
                    400: openapi.Response(description='Invalid request data'),
                    401: openapi.Response(description='Unauthorized'),
                    403: openapi.Response(description='Permission denied'),
                    404: openapi.Response(description='Booking not found')
                }
            ),
            delete=openapi.Operation(
                operation_id='cancel_booking',
                description='Cancel a booking',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Booking ID', type=openapi.TYPE_INTEGER, required=True),
                ],
                responses={
                    204: openapi.Response(description='Booking cancelled successfully'),
                    401: openapi.Response(description='Unauthorized'),
                    403: openapi.Response(description='Permission denied or cancellation window passed'),
                    404: openapi.Response(description='Booking not found')
                }
            )
        )
    
    def _add_package_endpoints(self, paths):
        """Add package endpoints"""
        # List packages
        paths['/api/packages/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='list_packages',
                description='List all service packages',
                parameters=[
                    openapi.Parameter('page', openapi.IN_QUERY, description='Page number', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('page_size', openapi.IN_QUERY, description='Results per page', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('shop_id', openapi.IN_QUERY, description='Filter by shop ID', type=openapi.TYPE_INTEGER),
                    openapi.Parameter('min_price', openapi.IN_QUERY, description='Minimum price', type=openapi.TYPE_NUMBER),
                    openapi.Parameter('max_price', openapi.IN_QUERY, description='Maximum price', type=openapi.TYPE_NUMBER),
                ],
                responses={
                    200: openapi.Response(description='List of packages'),
                    401: openapi.Response(description='Unauthorized')
                }
            )
        )
        
        # Get package details
        paths['/api/packages/{id}/'] = openapi.PathItem(
            get=openapi.Operation(
                operation_id='retrieve_package',
                description='Retrieve a specific package',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Package ID', type=openapi.TYPE_INTEGER, required=True),
                ],
                responses={
                    200: openapi.Response(description='Package details'),
                    404: openapi.Response(description='Package not found')
                }
            )
        )
        
        # Purchase package
        paths['/api/packages/{id}/purchase/'] = openapi.PathItem(
            post=openapi.Operation(
                operation_id='purchase_package',
                description='Purchase a package',
                parameters=[
                    openapi.Parameter('id', openapi.IN_PATH, description='Package ID', type=openapi.TYPE_INTEGER, required=True),
                ],
                request_body=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    required=['payment_method'],
                    properties={
                        'payment_method': openapi.Schema(type=openapi.TYPE_STRING, enum=['card', 'wallet']),
                    }
                ),
                responses={
                    200: openapi.Response(description='Package purchased successfully'),
                    400: openapi.Response(description='Invalid request data'),
                    401: openapi.Response(description='Unauthorized'),
                    404: openapi.Response(description='Package not found')
                }
            )
        )

# Create schema view with enhanced generator
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
    generator_class=EnhancedOpenAPISchemaGenerator,
)
