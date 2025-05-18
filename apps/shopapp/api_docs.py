# Create a file called api_docs.py in each of your app directories
# Example for /home/arise/queueme/apps/shopapp/api_docs.py

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers


# Define example request/response models for documentation
class ShopListResponse(serializers.Serializer):
    id = serializers.IntegerField(help_text="Shop ID")
    name = serializers.CharField(help_text="Shop name")
    description = serializers.CharField(help_text="Shop description")
    address = serializers.CharField(help_text="Shop address")
    rating = serializers.FloatField(help_text="Average rating")
    thumbnail_url = serializers.URLField(help_text="Shop thumbnail image URL")


# Define documentation decorators to be applied to views
list_shops_docs = swagger_auto_schema(
    operation_summary="List shops",
    operation_description="Returns a paginated list of all shops.",
    manual_parameters=[
        openapi.Parameter(
            "page",
            openapi.IN_QUERY,
            description="Page number",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "limit",
            openapi.IN_QUERY,
            description="Results per page",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "search",
            openapi.IN_QUERY,
            description="Search by shop name",
            type=openapi.TYPE_STRING,
        ),
        openapi.Parameter(
            "category",
            openapi.IN_QUERY,
            description="Filter by category ID",
            type=openapi.TYPE_INTEGER,
        ),
        openapi.Parameter(
            "location",
            openapi.IN_QUERY,
            description="Filter by location (latitude,longitude)",
            type=openapi.TYPE_STRING,
        ),
    ],
    responses={
        200: openapi.Response("Success", ShopListResponse(many=True)),
        401: "Unauthorized",
    },
)

# Create similar decorators for all other endpoints in this app
