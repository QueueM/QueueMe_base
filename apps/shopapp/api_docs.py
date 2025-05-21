"""
Shop API Documentation Helpers

This module defines shared API documentation objects, decorators,
and reusable parameters for the shop app using drf-yasg (Swagger).
"""

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers

# Import the deduplication function from the canonical source
from api.documentation.utils import dedupe_manual_parameters

# ─────────────────────────────────────────────────────────────────────────────
# Example serializers for documenting responses
# ─────────────────────────────────────────────────────────────────────────────
class ShopListResponse(serializers.Serializer):
    id = serializers.IntegerField(help_text="Shop ID")
    name = serializers.CharField(help_text="Shop name")
    description = serializers.CharField(help_text="Shop description")
    address = serializers.CharField(help_text="Shop address")
    rating = serializers.FloatField(help_text="Average rating")
    thumbnail_url = serializers.URLField(help_text="Shop thumbnail image URL")

class ShopDetailResponse(serializers.Serializer):
    id = serializers.IntegerField(help_text="Shop ID")
    name = serializers.CharField(help_text="Shop name")
    description = serializers.CharField(help_text="Shop description")
    address = serializers.CharField(help_text="Shop address")
    rating = serializers.FloatField(help_text="Average rating")
    thumbnail_url = serializers.URLField(help_text="Shop thumbnail image URL")
    phone = serializers.CharField(help_text="Shop phone number", required=False)
    email = serializers.EmailField(help_text="Shop email", required=False)
    categories = serializers.ListField(
        child=serializers.CharField(), help_text="List of category names", required=False
    )
    opening_hours = serializers.CharField(help_text="Opening hours", required=False)
    is_verified = serializers.BooleanField(help_text="Verification status", required=False)

# ─────────────────────────────────────────────────────────────────────────────
# Shared reusable parameters
# ─────────────────────────────────────────────────────────────────────────────
shop_id_param = openapi.Parameter(
    "shop_id",
    in_=openapi.IN_PATH,
    description="Shop ID",
    type=openapi.TYPE_INTEGER,
)

# ─────────────────────────────────────────────────────────────────────────────
# Swagger decorators for views
# ─────────────────────────────────────────────────────────────────────────────

list_shops_docs = swagger_auto_schema(
    operation_summary="List shops",
    operation_description="Returns a paginated list of all shops.",
    manual_parameters=dedupe_manual_parameters([
        openapi.Parameter("page", openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
        openapi.Parameter("limit", openapi.IN_QUERY, description="Results per page", type=openapi.TYPE_INTEGER),
        openapi.Parameter("search", openapi.IN_QUERY, description="Search by shop name", type=openapi.TYPE_STRING),
        openapi.Parameter("category", openapi.IN_QUERY, description="Filter by category ID", type=openapi.TYPE_INTEGER),
        openapi.Parameter("location", openapi.IN_QUERY, description="Filter by location (latitude,longitude)", type=openapi.TYPE_STRING),
    ]),
    responses={
        200: openapi.Response("Success", ShopListResponse(many=True)),
        401: "Unauthorized",
    },
)

shop_detail_docs = swagger_auto_schema(
    operation_summary="Get shop details",
    operation_description="Returns details for a specific shop.",
    manual_parameters=dedupe_manual_parameters([
        shop_id_param,
    ]),
    responses={
        200: openapi.Response("Success", ShopDetailResponse()),
        404: "Not found",
    },
)

# You can add more reusable decorators for create/update/delete if needed, e.g.:
create_shop_docs = swagger_auto_schema(
    operation_summary="Create a new shop",
    operation_description="Create a shop with the given details.",
    request_body=ShopDetailResponse,  # For creation, typically a dedicated input serializer
    responses={
        201: openapi.Response("Created", ShopDetailResponse()),
        400: "Bad Request",
        401: "Unauthorized",
    },
    tags=["Shops"],
)

update_shop_docs = swagger_auto_schema(
    operation_summary="Update a shop",
    operation_description="Update details for an existing shop.",
    manual_parameters=dedupe_manual_parameters([shop_id_param]),
    request_body=ShopDetailResponse,
    responses={
        200: openapi.Response("Updated", ShopDetailResponse()),
        400: "Bad Request",
        404: "Not Found",
    },
    tags=["Shops"],
)

# END OF FILE
