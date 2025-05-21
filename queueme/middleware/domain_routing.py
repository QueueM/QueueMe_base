import logging
from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class DomainRoutingMiddleware(MiddlewareMixin):
    """Middleware for handling domain-specific routing and behavior."""

    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization
        self.domain_routing = getattr(settings, "DOMAIN_ROUTING", {})

    def __call__(self, request):
        # Get the current domain
        domain = request.get_host().split(":")[0]  # remove port if present

        # Special case: Allow access to django-admin and its static files on api.queueme.net
        if domain == 'api.queueme.net' and (
            request.path.startswith('/django-admin/') or 
            request.path.startswith('/static/admin/') or
            request.path.startswith('/django-admin/static/admin/')
        ):
            # Let django-admin and its static files pass through
            response = self.get_response(request)
            return response

        # Get the app for this domain
        app_name = self.domain_routing.get(domain)

        # Set an attribute on the request for views to use
        request.app_name = app_name

        # Handle redirects for certain paths based on domain
        if self._should_redirect(request, domain, app_name):
            target_domain = self._get_target_domain(request.path, app_name)
            if target_domain:
                return self._build_redirect(request, target_domain)

        # Process request normally
        response = self.get_response(request)
        return response

    def _should_redirect(self, request, domain, app_name):
        """
        Determine if a request should be redirected to another domain.
        For example, API requests coming to main domain should go to api.queueme.net
        """
        path = request.path

        # Skip redirecting django-admin and its static assets
        if path.startswith('/django-admin/') or path.startswith('/static/admin/'):
            return False

        # API paths should go to the API domain
        if path.startswith("/api/") and app_name != "api":
            return True

        # Admin paths should go to the admin domain
        if path.startswith("/admin/") and app_name != "admin":
            return True

        # Shop paths should go to the shop domain
        if path.startswith("/shop/") and app_name != "shop":
            return True

        return False

    def _get_target_domain(self, path, current_app):
        """Get the target domain for a redirect based on the path"""
        if path.startswith("/api/"):
            # Find API domain
            for domain, app in self.domain_routing.items():
                if app == "api":
                    return domain

        elif path.startswith("/admin/"):
            # Find admin domain
            for domain, app in self.domain_routing.items():
                if app == "admin":
                    return domain

        elif path.startswith("/shop/"):
            # Find shop domain
            for domain, app in self.domain_routing.items():
                if app == "shop":
                    return domain

        return None

    def _build_redirect(self, request, target_domain):
        """Build the redirect response with the same path but new domain"""
        scheme = "https" if request.is_secure() else "http"
        new_url = f"{scheme}://{target_domain}{request.path}"

        if request.GET:
            query_string = request.GET.urlencode()
            new_url = f"{new_url}?{query_string}"

        logger.info(f"Redirecting from {request.get_host()} to {target_domain}")
        return HttpResponseRedirect(new_url)

    def process_request(self, request):
        """
        Process the request based on the domain being accessed.

        This allows different behavior or templates to be used based on
        the domain, even though all requests go to the same Django application.

        Args:
            request: The HTTP request

        Returns:
            None or HttpResponse: None to continue processing or HttpResponse for early return
        """
        # Skip for static/media requests
        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return None
            
        # Skip for django-admin requests
        if request.path.startswith("/django-admin/"):
            return None

        # Extract domain from host
        host = request.get_host().split(":")[0]  # Remove port if present

        # Check for domain override from proxy (for development or special configs)
        interface = request.META.get("HTTP_X_QUEUEME_INTERFACE", "")
        if interface:
            request.interface = interface
            return None

        # Set interface based on domain
        if host in ["api.queueme.net", "api.localhost", "api.127.0.0.1"]:
            request.interface = "api"

            # Force redirect to API docs if accessing root on API domain
            if request.path == "/" and not request.is_ajax():
                return redirect("/api/docs/")

        elif host in ["admin.queueme.net", "admin.localhost", "admin.127.0.0.1"]:
            request.interface = "admin"

            # Force redirect to Django admin if accessing root on admin domain
            if request.path == "/" and not request.is_ajax():
                return redirect("/admin/")

        elif host in ["shop.queueme.net", "shop.localhost", "shop.127.0.0.1"]:
            request.interface = "shop"

        else:
            # Default to main site
            request.interface = "main"

        # Add log entry for debugging in development
        if settings.DEBUG:
            logger.debug(f"Domain routing: {host} → {request.interface}")

        return None

    def process_template_response(self, request, response):
        """
        Process template response to add interface context variable.

        This allows templates to adjust behavior based on which domain
        is being accessed.

        Args:
            request: The HTTP request
            response: The template response

        Returns:
            TemplateResponse: The modified template response
        """
        if (
            hasattr(request, "interface")
            and hasattr(response, "context_data")
            and response.context_data is not None
        ):
            response.context_data["interface"] = request.interface

        return response
