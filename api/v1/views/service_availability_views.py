"""
Service availability API views with improved parameter handling.
"""

from datetime import datetime

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookingapp.services.availability_service import AvailabilityService
from apps.bookingapp.services.dynamic_availability_service import DynamicAvailabilityService

# Import shared parameters
from api.documentation.parameters import (
    SERVICE_ID_PARAM, 
    DATE_PARAM,
    SPECIALIST_ID_PARAM
)

# Import deduplication utility
from api.documentation.utils import dedupe_manual_parameters

# --------------------------------------------------------------------------
# API: Service Availability
# --------------------------------------------------------------------------
class ServiceAvailabilityAPIView(APIView):
    """
    API endpoint for service availability
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=dedupe_manual_parameters([
            SERVICE_ID_PARAM,
            DATE_PARAM,
        ]),
        responses={
            200: openapi.Response(
                description="List of available time slots",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "start": openapi.Schema(type=openapi.TYPE_STRING, description="Start time (HH:MM)"),
                            "end": openapi.Schema(type=openapi.TYPE_STRING, description="End time (HH:MM)"),
                            "duration": openapi.Schema(type=openapi.TYPE_INTEGER, description="Duration in minutes"),
                            "specialist_id": openapi.Schema(type=openapi.TYPE_STRING, description="Available specialist ID"),
                        },
                    ),
                ),
            ),
            400: "Bad request",
            404: "Service not found",
        },
    )
    def get(self, request):
        """
        Get available time slots for a service on a specific date
        """
        service_id = request.query_params.get("service_id")
        date_str = request.query_params.get("date")

        if not service_id or not date_str:
            return Response(
                {"error": "service_id and date parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get available slots
        available_slots = AvailabilityService.get_service_availability(service_id, date_obj)
        return Response(available_slots)

# --------------------------------------------------------------------------
# API: Dynamic (Optimized) Service Availability
# --------------------------------------------------------------------------
class DynamicServiceAvailabilityAPIView(APIView):
    """
    API endpoint for optimized dynamic service availability
    """
    permission_classes = [IsAuthenticated]

    # Custom parameter - not defined in centralized parameters module
    PERSONALIZE_PARAM = openapi.Parameter(
        "personalize",
        openapi.IN_QUERY,
        description="Whether to personalize results based on customer preferences",
        type=openapi.TYPE_BOOLEAN,
        default=True,
        required=False,
    )

    @swagger_auto_schema(
        manual_parameters=dedupe_manual_parameters([
            SERVICE_ID_PARAM,
            DATE_PARAM,
            SPECIALIST_ID_PARAM,
            PERSONALIZE_PARAM,
        ]),
        responses={
            200: openapi.Response(
                description="List of optimized time slots",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "start": openapi.Schema(type=openapi.TYPE_STRING, description="Start time (HH:MM)"),
                            "end": openapi.Schema(type=openapi.TYPE_STRING, description="End time (HH:MM)"),
                            "duration": openapi.Schema(type=openapi.TYPE_INTEGER, description="Duration in minutes"),
                            "specialist_id": openapi.Schema(type=openapi.TYPE_STRING, description="Optimal specialist ID"),
                            "specialist_name": openapi.Schema(type=openapi.TYPE_STRING, description="Specialist name"),
                            "popularity": openapi.Schema(type=openapi.TYPE_NUMBER, description="Time slot popularity (0-1)"),
                            "optimization_score": openapi.Schema(type=openapi.TYPE_NUMBER, description="Overall optimization score"),
                        },
                    ),
                ),
            ),
            400: "Bad request",
            404: "Service not found",
        },
    )
    def get(self, request):
        """
        Get optimized time slots for a service using intelligent scheduling algorithm
        """
        service_id = request.query_params.get("service_id")
        date_str = request.query_params.get("date")
        specialist_id = request.query_params.get("specialist_id")
        personalize = request.query_params.get("personalize", "true").lower() == "true"

        if not service_id or not date_str:
            return Response(
                {"error": "service_id and date parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer_id = None
        if hasattr(request.user, "customer") and request.user.customer:
            customer_id = str(request.user.customer.id)

        optimized_slots = DynamicAvailabilityService.get_optimized_availability(
            service_id=service_id,
            target_date=date_obj,
            customer_id=customer_id,
            specialist_id=specialist_id,
            personalize=personalize,
        )

        return Response(optimized_slots)

# --------------------------------------------------------------------------
# API: Most Popular Time Slots
# --------------------------------------------------------------------------
class PopularTimeSlotsAPIView(APIView):
    """
    API endpoint for getting popular time slots
    """
    permission_classes = [IsAuthenticated]

    LIMIT_PARAM = openapi.Parameter(
        "limit",
        openapi.IN_QUERY,
        description="Maximum number of slots to return",
        type=openapi.TYPE_INTEGER,
        default=3,
        required=False,
    )

    @swagger_auto_schema(
        manual_parameters=dedupe_manual_parameters([
            SERVICE_ID_PARAM,
            DATE_PARAM,
            LIMIT_PARAM,
        ]),
        responses={
            200: openapi.Response(
                description="List of popular time slots",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "start": openapi.Schema(type=openapi.TYPE_STRING, description="Start time (HH:MM)"),
                            "end": openapi.Schema(type=openapi.TYPE_STRING, description="End time (HH:MM)"),
                            "popularity": openapi.Schema(type=openapi.TYPE_NUMBER, description="Popularity score (0-1)"),
                        },
                    ),
                ),
            ),
            400: "Bad request",
        },
    )
    def get(self, request):
        """
        Get the most popular time slots for a service
        """
        service_id = request.query_params.get("service_id")
        date_str = request.query_params.get("date")
        limit = int(request.query_params.get("limit", 3))

        if not service_id or not date_str:
            return Response(
                {"error": "service_id and date parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        popular_slots = DynamicAvailabilityService.get_popular_slots(
            service_id=service_id, target_date=date_obj, limit=limit
        )
        return Response(popular_slots)

# --------------------------------------------------------------------------
# API: Quiet (Least Busy) Time Slots
# --------------------------------------------------------------------------
class QuietTimeSlotsAPIView(APIView):
    """
    API endpoint for getting quiet/less busy time slots
    """
    permission_classes = [IsAuthenticated]

    LIMIT_PARAM = openapi.Parameter(
        "limit",
        openapi.IN_QUERY,
        description="Maximum number of slots to return",
        type=openapi.TYPE_INTEGER,
        default=3,
        required=False,
    )

    @swagger_auto_schema(
        manual_parameters=dedupe_manual_parameters([
            SERVICE_ID_PARAM,
            DATE_PARAM,
            LIMIT_PARAM,
        ]),
        responses={
            200: openapi.Response(
                description="List of quiet time slots",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "start": openapi.Schema(type=openapi.TYPE_STRING, description="Start time (HH:MM)"),
                            "end": openapi.Schema(type=openapi.TYPE_STRING, description="End time (HH:MM)"),
                            "popularity": openapi.Schema(type=openapi.TYPE_NUMBER, description="Popularity score (0-1)"),
                        },
                    ),
                ),
            ),
            400: "Bad request",
        },
    )
    def get(self, request):
        """
        Get the least busy time slots for a service
        """
        service_id = request.query_params.get("service_id")
        date_str = request.query_params.get("date")
        limit = int(request.query_params.get("limit", 3))

        if not service_id or not date_str:
            return Response(
                {"error": "service_id and date parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quiet_slots = DynamicAvailabilityService.get_quiet_slots(
            service_id=service_id, target_date=date_obj, limit=limit
        )
        return Response(quiet_slots)

# --------------------------------------------------------------------------
# API: Best Specialist For A Time Slot
# --------------------------------------------------------------------------
class BestSpecialistAPIView(APIView):
    """
    API endpoint for finding the best specialist for a time slot
    """
    permission_classes = [IsAuthenticated]

    TIME_SLOT_PARAM = openapi.Parameter(
        "time_slot",
        openapi.IN_QUERY,
        description="Time slot in HH:MM format",
        type=openapi.TYPE_STRING,
        required=True,
    )

    @swagger_auto_schema(
        manual_parameters=dedupe_manual_parameters([
            SERVICE_ID_PARAM,
            DATE_PARAM,
            TIME_SLOT_PARAM,
        ]),
        responses={
            200: openapi.Response(
                description="Best specialist information",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "specialist_id": openapi.Schema(type=openapi.TYPE_STRING, description="Specialist UUID"),
                        "specialist_name": openapi.Schema(type=openapi.TYPE_STRING, description="Specialist name"),
                        "optimization_score": openapi.Schema(type=openapi.TYPE_NUMBER, description="Optimization score"),
                        "alternative_specialists": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(type=openapi.TYPE_STRING),
                            description="Alternative specialist IDs",
                        ),
                    },
                ),
            ),
            400: "Bad request",
            404: "No specialist available for this slot",
        },
    )
    def get(self, request):
        """
        Get the best specialist for a specific time slot
        """
        service_id = request.query_params.get("service_id")
        date_str = request.query_params.get("date")
        time_slot = request.query_params.get("time_slot")

        if not service_id or not date_str or not time_slot:
            return Response(
                {"error": "service_id, date, and time_slot parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        specialist_info = DynamicAvailabilityService.get_best_specialist_for_slot(
            service_id=service_id, target_date=date_obj, time_slot=time_slot
        )

        if not specialist_info:
            return Response(
                {"error": "No specialist available for this time slot"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(specialist_info)
