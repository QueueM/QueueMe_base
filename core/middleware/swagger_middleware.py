"""
Legacy middleware for compatibility - actual patches are applied in monkey_patches.py
"""

from django.utils.deprecation import MiddlewareMixin

class SwaggerMiddleware(MiddlewareMixin):
    """
    Middleware that ensures swagger patches have been applied
    """
    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response
        
    def __call__(self, request):
        # Make sure patches are applied
        from core import monkey_patches
        return self.get_response(request)
