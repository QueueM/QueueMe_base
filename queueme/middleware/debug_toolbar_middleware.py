"""
Custom middleware to restrict Django Debug Toolbar by hostname.
"""


class DebugToolbarMiddleware:
    """
    Middleware that controls when the Django Debug Toolbar should be shown.
    This restricts it to only appear on admin.queueme.net or localhost/127.0.0.1 for admin urls.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    @staticmethod
    def show_toolbar(request):
        """
        Show toolbar based on hostname and path.
        """
        # Skip for AJAX requests
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return False

        # Allow on local development
        if request.META.get("REMOTE_ADDR") in ("127.0.0.1", "localhost", "::1"):
            if request.path.startswith("/admin/"):
                return True

        host = request.get_host().split(":")[0]

        # Only show on admin domain
        if host in ("admin.queueme.net", "admin.localhost", "admin.127.0.0.1"):
            return True

        return False
