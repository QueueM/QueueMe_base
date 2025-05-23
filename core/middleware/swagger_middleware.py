"""
Swagger middleware for handling schema requests
"""

from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
import logging

logger = logging.getLogger(__name__)


class SwaggerMiddleware(MiddlewareMixin):
    """
    Middleware that ensures swagger patches have been applied
    and handles schema format parameters
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

    def __call__(self, request):
        # Log schema requests for debugging
        if request.path.startswith('/api/docs'):
            logger.info(f"Schema request: {request.path}?{request.META.get('QUERY_STRING', '')}")
            
            # Log headers for debugging
            if 'format' in request.GET:
                logger.info(f"Format parameter: {request.GET.get('format')}")
        
        response = self.get_response(request)
        
        # Add CORS headers for schema requests if needed
        if request.path.startswith('/api/docs'):
            # Allow Swagger UI to fetch schema from any origin
            origin = request.META.get('HTTP_ORIGIN', '*')
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, X-Requested-With'
            response['Access-Control-Allow-Credentials'] = 'true'
            
            # Handle preflight OPTIONS requests
            if request.method == 'OPTIONS':
                response.status_code = 200
                response.content = b''
        
        return response

    def process_request(self, request):
        """Process request before it reaches the view"""
        # Ensure patches are applied (this happens in yasg_patch.py automatically)
        
        # Handle OPTIONS preflight requests for CORS
        if request.method == 'OPTIONS' and request.path.startswith('/api/docs'):
            response = HttpResponse()
            response['Access-Control-Allow-Origin'] = request.META.get('HTTP_ORIGIN', '*')
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, X-Requested-With'
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Max-Age'] = '86400'
            return response
            
        return None
