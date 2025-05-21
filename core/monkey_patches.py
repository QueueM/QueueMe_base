"""
Monkey patches for core fixes.

If you really need to patch drf-yasg, make SURE your patch matches the real function signature.
But for almost every project, you should NOT patch drf-yasg—just make sure your get_queryset methods are correct!
"""

# Remove or comment out any patch for drf-yasg
# If you ever need to patch drf_yasg.inspectors.base.call_view_method, do it like this:

# import drf_yasg.inspectors.base
# original_call_view_method = drf_yasg.inspectors.base.call_view_method
#
# def patched_call_view_method(view, method_name, attr_name=None, default=None):
#     try:
#         return original_call_view_method(view, method_name, attr_name, default)
#     except TypeError as e:
#         if 'missing 1 required positional argument' in str(e) and method_name == 'get_queryset':
#             # Fallback: return empty queryset if get_queryset is broken
#             queryset = getattr(view, 'queryset', None)
#             if queryset is not None:
#                 return queryset.none()
#             return default
#         raise
#
# drf_yasg.inspectors.base.call_view_method = patched_call_view_method

# For almost all cases, you do NOT need a monkey patch.
# Just keep this file for future stubs.
