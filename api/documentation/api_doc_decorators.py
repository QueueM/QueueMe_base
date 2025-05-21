"""
API Documentation Decorators

This module contains decorators for documenting API endpoints
using drf-yasg (Yet Another Swagger Generator).
"""

import functools
from typing import Any, Callable, Dict, List, Optional, Union

from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status

# ----------------------------------------------------------------------
# Import the deduplication utility from utils
# ----------------------------------------------------------------------
from api.documentation.utils import dedupe_manual_parameters

# ----------------------------------------------------------------------
# Endpoint Decorator
# ----------------------------------------------------------------------
def document_api_endpoint(
    summary: str = None,
    description: str = None,
    request_body: Any = None,
    responses: Dict = None,
    tags: List[str] = None,
    query_params: List[Dict] = None,
    path_params: List[Dict] = None,
    operation_id: str = None,
):
    """
    Decorator for documenting API endpoints.

    Args:
        summary: Short summary of what the operation does
        description: Verbose explanation of the operation behavior
        request_body: Request body schema
        responses: Response schemas for different HTTP status codes
        tags: A list of tags for API documentation control
        query_params: List of query parameters with name, description, required, and type
        path_params: List of path parameters with name, description, and type
        operation_id: Unique string used to identify the operation

    Returns:
        Decorated function with Swagger documentation
    """
    if responses is None:
        responses = {
            status.HTTP_200_OK: "Success",
            status.HTTP_400_BAD_REQUEST: "Bad Request",
            status.HTTP_401_UNAUTHORIZED: "Unauthorized",
            status.HTTP_403_FORBIDDEN: "Forbidden",
            status.HTTP_404_NOT_FOUND: "Not Found",
            status.HTTP_500_INTERNAL_SERVER_ERROR: "Server Error",
        }

    manual_parameters = []

    # Add query parameters
    if query_params:
        for param in query_params:
            param_type = param.get("type", openapi.TYPE_STRING)
            required = param.get("required", False)
            manual_parameters.append(
                openapi.Parameter(
                    param["name"],
                    openapi.IN_QUERY,
                    description=param.get("description", ""),
                    type=param_type,
                    required=required,
                )
            )

    # Add path parameters
    if path_params:
        for param in path_params:
            param_type = param.get("type", openapi.TYPE_STRING)
            manual_parameters.append(
                openapi.Parameter(
                    param["name"],
                    openapi.IN_PATH,
                    description=param.get("description", ""),
                    type=param_type,
                    required=True,
                )
            )

    # Deduplicate using the canonical dedupe utility
    manual_parameters = dedupe_manual_parameters(manual_parameters)

    def decorator(view_func):
        # Skip decorating classes directly
        if isinstance(view_func, type):
            return view_func

        @functools.wraps(view_func)
        def wrapped_view(*args, **kwargs):
            return view_func(*args, **kwargs)

        decorated_view = swagger_auto_schema(
            operation_summary=summary,
            operation_description=description,
            request_body=request_body,
            responses=responses,
            tags=tags,
            manual_parameters=manual_parameters or None,
            operation_id=operation_id,
        )(wrapped_view)

        return decorated_view

    return decorator

# ----------------------------------------------------------------------
# ViewSet Decorator
# ----------------------------------------------------------------------
def document_api_viewset(
    summary: str = None,
    description: str = None,
    tags: List[str] = None,
    operation_id_prefix: str = None,
):
    """
    Class decorator for documenting API ViewSets.

    Args:
        summary: A short summary for the ViewSet
        description: General description for all operations in this ViewSet
        tags: A list of tags for API documentation control
        operation_id_prefix: Prefix for all operation IDs in this ViewSet

    Returns:
        Decorated ViewSet class with Swagger documentation
    """

    def decorator(cls):
        # Only decorate actual classes
        if not isinstance(cls, type):
            return cls

        action_descriptions = {
            "list": _("List all objects"),
            "create": _("Create a new object"),
            "retrieve": _("Get a specific object by ID"),
            "update": _("Update an object (full update)"),
            "partial_update": _("Update an object (partial update)"),
            "destroy": _("Delete an object"),
        }

        # Inject docstring
        if not cls.__doc__:
            cls.__doc__ = description
        elif description:
            cls.__doc__ = f"{cls.__doc__}\n\n{description}"

        # Guess actions if not explicit
        actions = []
        if hasattr(cls, "action_map") and cls.action_map:
            actions = list(cls.action_map.values())
        else:
            http_method_names = getattr(cls, "http_method_names", [])
            if "get" in http_method_names and hasattr(cls, "list"):
                actions.append("list")
            if "get" in http_method_names and hasattr(cls, "retrieve"):
                actions.append("retrieve")
            if "post" in http_method_names and hasattr(cls, "create"):
                actions.append("create")
            if "put" in http_method_names and hasattr(cls, "update"):
                actions.append("update")
            if "patch" in http_method_names and hasattr(cls, "partial_update"):
                actions.append("partial_update")
            if "delete" in http_method_names and hasattr(cls, "destroy"):
                actions.append("destroy")

        for action_name in actions:
            if hasattr(cls, action_name):
                action_method = getattr(cls, action_name)
                # Avoid decorating twice
                if hasattr(action_method, "_swagger_auto_schema"):
                    continue

                op_id = f"{operation_id_prefix}_{action_name}" if operation_id_prefix else None
                action_summary = (
                    f"{summary} - {action_descriptions.get(action_name, '')}"
                    if summary else action_descriptions.get(action_name, "")
                )

                decorated_method = swagger_auto_schema(
                    operation_summary=action_summary,
                    operation_description=description,
                    tags=tags,
                    operation_id=op_id,
                )(action_method)
                setattr(cls, action_name, decorated_method)

        return cls

    return decorator

# END OF FILE
