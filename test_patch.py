"""
Patch for fixing drf-yasg issues
"""

import logging

logger = logging.getLogger(__name__)

# Fix for drf_yasg.inspectors.base.call_view_method
try:
    from drf_yasg.inspectors.base import call_view_method as original_call_view_method

    def patched_call_view_method(view_method):
        """Simple patch that handles missing request parameter"""
        view = getattr(view_method, "__self__", None)
        if view:
            setattr(view, "swagger_fake_view", True)

        try:
            return original_call_view_method(view_method)
        except TypeError as e:
            if "missing 1 required positional argument" in str(e):
                if view and hasattr(view, "queryset"):
                    return view.queryset.none()
                return None
            raise

    # Replace the original function
    import drf_yasg.inspectors.base

    drf_yasg.inspectors.base.call_view_method = patched_call_view_method
    print("✅ Patched drf_yasg.inspectors.base.call_view_method")

except Exception as e:
    logger.error(f"Error patching drf-yasg: {e}")

print("✅ yasg_patch loaded")
