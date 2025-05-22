"""
OpenAPI schema generation configuration for QueueMe API.
"""

from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

# Basic API Info
API_INFO = openapi.Info(
    title="QueueMe API",
    default_version="v1",
    description="""
# QueueMe Platform API

The QueueMe API provides comprehensive access to all functionality of the QueueMe platform,
including authentication, queue management, booking, payment processing, and more.

## Authentication

Most endpoints require authentication using JWT tokens. Include the token in the
Authorization header as follows:

```
Authorization: Bearer <your_token>
```

To obtain a token, use the `/auth/token/` endpoint with your credentials.

## Rate Limiting

API requests are subject to rate limiting to ensure fair usage:
- 60 requests per minute for authenticated users
- 20 requests per minute for anonymous users

## Response Formats

All responses are in JSON format and follow a standard structure:
- Success responses include the requested data
- Error responses include detailed error information with appropriate HTTP status codes

## Pagination

List endpoints are paginated with 20 items per page by default. Use `page` and `page_size` parameters to navigate.
    """,
    terms_of_service="https://queueme.net/terms/",
    contact=openapi.Contact(email="api@queueme.net"),
    license=openapi.License(name="Proprietary"),
)

# Schema view settings
SCHEMA_VIEW = get_schema_view(
    API_INFO,
    public=True,
    permission_classes=(permissions.AllowAny,),
    validators=["ssv"],
    patterns=None,
)

# Common response schemas for consistent documentation
STANDARD_RESPONSES = {
    400: openapi.Response(
        description="Bad Request",
        schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "error": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Error message"
                ),
                "code": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Error code"
                ),
                "details": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Detailed error information",  # noqa: E501
                ),
            },
        ),
        examples={
            "application/json": {
                "error": "Invalid input",
                "code": "invalid_input",
                "details": {"field_name": ["Error details"]},
            }
        },
    ),
    401: openapi.Response(
        description="Unauthorized - Authentication credentials were not provided or are invalid",
        schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING),
                "code": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        examples={
            "application/json": {
                "error": "Authentication credentials were not provided",
                "code": "authentication_failed",
            }
        },
    ),
    403: openapi.Response(
        description="Forbidden - You do not have permission to perform this action",
        schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING),
                "code": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        examples={
            "application/json": {
                "error": "You do not have permission to perform this action",
                "code": "permission_denied",
            }
        },
    ),
    404: openapi.Response(
        description="Not Found - The requested resource does not exist",
        schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING),
                "code": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        examples={
            "application/json": {"error": "Resource not found", "code": "not_found"}
        },
    ),
    429: openapi.Response(
        description="Too Many Requests - Rate limit exceeded",
        schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING),
                "code": openapi.Schema(type=openapi.TYPE_STRING),
                "retry_after": openapi.Schema(type=openapi.TYPE_INTEGER),
            },
        ),
        examples={
            "application/json": {
                "error": "Rate limit exceeded",
                "code": "rate_limit_exceeded",
                "retry_after": 30,
            }
        },
    ),
    500: openapi.Response(
        description="Internal Server Error - Something went wrong on our end",
        schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING),
                "code": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        examples={
            "application/json": {
                "error": "Internal server error",
                "code": "server_error",
            }
        },
    ),
}

# Security definitions
SECURITY_DEFINITIONS = {
    "Bearer": {
        "type": "apiKey",
        "name": "Authorization",
        "in": "header",
        "description": 'JWT Token authentication. Enter your token in the format: "Bearer {token}"',
    },
}

# Common query parameters for list endpoints
PAGINATION_PARAMETERS = [
    openapi.Parameter(
        "page",
        openapi.IN_QUERY,
        description="Page number",
        type=openapi.TYPE_INTEGER,
        default=1,
    ),
    openapi.Parameter(
        "page_size",
        openapi.IN_QUERY,
        description="Number of items per page",
        type=openapi.TYPE_INTEGER,
        default=20,
        maximum=100,
    ),
]

ORDERING_PARAMETERS = [
    openapi.Parameter(
        "ordering",
        openapi.IN_QUERY,
        description="Order results by field. Prefix field with '-' for descending order.",
        type=openapi.TYPE_STRING,
        example="created_at or -created_at",
    ),
]

SEARCH_PARAMETER = openapi.Parameter(
    "search",
    openapi.IN_QUERY,
    description="Search term to filter results",
    type=openapi.TYPE_STRING,
)


# Helper function to generate standard list response schemas


def get_list_response_schema(item_schema, description="List of items"):
    """Generate a standard paginated list response schema"""
    return openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "count": openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description="Total number of items across all pages",
            ),
            "next": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_URI,
                description="URL to next page of results (null if no more pages)",
                x_nullable=True,
            ),
            "previous": openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_URI,
                description="URL to previous page of results (null if first page)",
                x_nullable=True,
            ),
            "results": openapi.Schema(
                type=openapi.TYPE_ARRAY, items=item_schema, description=description
            ),
        },
        description="Paginated list response",
    )
