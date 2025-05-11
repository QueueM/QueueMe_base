"""
Decorators to simplify API documentation
These decorators can be applied to view methods or classes to provide standardized documentation
"""

from functools import wraps
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

def document_api_endpoint(summary, description, responses=None, request_body=None, query_params=None, path_params=None, tags=None):
    """
    Comprehensive decorator for documenting API endpoints
    
    Args:
        summary (str): Short summary of what the endpoint does
        description (str): Detailed explanation of the endpoint functionality
        responses (dict): Dict mapping status codes to response descriptions and examples
        request_body (dict): Description and schema for request body
        query_params (list): List of query parameters
        path_params (list): List of path parameters
        tags (list): List of tags for grouping endpoints
    """
    if responses is None:
        responses = {
            200: "Success",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            500: "Server Error"
        }
    
    # Convert any provided parameters to proper Swagger parameters
    swagger_params = []
    
    if query_params:
        for param in query_params:
            name = param.get('name')
            param_type = param.get('type', openapi.TYPE_STRING)
            required = param.get('required', False)
            description = param.get('description', '')
            
            swagger_params.append(
                openapi.Parameter(
                    name=name,
                    in_=openapi.IN_QUERY,
                    type=param_type,
                    required=required,
                    description=description
                )
            )
    
    if path_params:
        for param in path_params:
            name = param.get('name')
            param_type = param.get('type', openapi.TYPE_STRING)
            description = param.get('description', '')
            
            swagger_params.append(
                openapi.Parameter(
                    name=name,
                    in_=openapi.IN_PATH,
                    type=param_type,
                    required=True,  # Path parameters are always required
                    description=description
                )
            )
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Apply swagger_auto_schema
        wrapper = swagger_auto_schema(
            operation_summary=summary,
            operation_description=description,
            responses=responses,
            request_body=request_body,
            manual_parameters=swagger_params or None,
            tags=tags,
        )(wrapper)
        
        # Store metadata for our custom documentation
        wrapper.api_doc_metadata = {
            'summary': summary,
            'description': description,
            'responses': responses,
            'request_body': request_body,
            'query_params': query_params,
            'path_params': path_params,
            'tags': tags,
        }
        
        return wrapper
    return decorator

def document_api_viewset(summary, description, tags=None):
    """
    Class decorator for ViewSets to document all standard actions
    
    Args:
        summary (str): Base summary for all viewset actions
        description (str): Base description for all viewset actions
        tags (list): List of tags for grouping endpoints
    """
    def decorator(cls):
        # Define standard action descriptions
        action_descriptions = {
            'list': f"List all {summary}",
            'retrieve': f"Retrieve a specific {summary}",
            'create': f"Create a new {summary}",
            'update': f"Update an existing {summary}",
            'partial_update': f"Partially update an existing {summary}",
            'destroy': f"Delete an existing {summary}"
        }
        
        # Apply documentation to each standard method if it exists
        for action, action_desc in action_descriptions.items():
            if hasattr(cls, action):
                method = getattr(cls, action)
                documented_method = document_api_endpoint(
                    summary=action_desc,
                    description=f"{description} - {action_desc}",
                    tags=tags
                )(method)
                setattr(cls, action, documented_method)
        
        # Store metadata on the class for custom documentation generators
        cls.api_doc_metadata = {
            'summary': summary,
            'description': description,
            'tags': tags,
        }
        
        return cls
    return decorator
