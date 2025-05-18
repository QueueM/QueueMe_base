from datetime import datetime

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookingapp.services.availability_service import AvailabilityService
from apps.bookingapp.services.dynamic_availability_service import DynamicAvailabilityService


class ServiceAvailabilityAPIView(APIView):
    """API endpoint for service availability"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "service_id",
                openapi.IN_QUERY,
                description="Service UUID",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "date",
                openapi.IN_QUERY,
                description="Date in YYYY-MM-DD format",
                type=openapi.TYPE_STRING,
                required=True,
            ),
        ],
        responses={
            200: openapi.Response(
                description="List of available time slots",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "start": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Start time (HH:MM)",
                            ),
                            "end": openapi.Schema(
                                type=openapi.TYPE_STRING, description="End time (HH:MM)"
                            ),
                            "duration": openapi.Schema(
                                type=openapi.TYPE_INTEGER,
                                description="Duration in minutes",
                            ),
                            "specialist_id": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Available specialist ID",
                            ),
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


class DynamicServiceAvailabilityAPIView(APIView):
    """API endpoint for optimized dynamic service availability"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "service_id",
                openapi.IN_QUERY,
                description="Service UUID",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "date",
                openapi.IN_QUERY,
                description="Date in YYYY-MM-DD format",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "specialist_id",
                openapi.IN_QUERY,
                description="Optional specialist UUID",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "personalize",
                openapi.IN_QUERY,
                description="Whether to personalize results based on customer preferences",
                type=openapi.TYPE_BOOLEAN,
                default=True,
                required=False,
            ),
        ],
        responses={
            200: openapi.Response(
                description="List of optimized time slots",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "start": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Start time (HH:MM)",
                            ),
                            "end": openapi.Schema(
                                type=openapi.TYPE_STRING, description="End time (HH:MM)"
                            ),
                            "duration": openapi.Schema(
                                type=openapi.TYPE_INTEGER,
                                description="Duration in minutes",
                            ),
                            "specialist_id": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Optimal specialist ID",
                            ),
                            "specialist_name": openapi.Schema(
                                type=openapi.TYPE_STRING, description="Specialist name"
                            ),
                            "popularity": openapi.Schema(
                                type=openapi.TYPE_NUMBER,
                                description="Time slot popularity (0-1)",
                            ),
                            "optimization_score": openapi.Schema(
                                type=openapi.TYPE_NUMBER,
                                description="Overall optimization score",
                            ),
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

        # Get customer ID from authenticated user if available
        customer_id = None
        if hasattr(request.user, "customer") and request.user.customer:
            customer_id = str(request.user.customer.id)

        # Get optimized slots
        optimized_slots = DynamicAvailabilityService.get_optimized_availability(
            service_id=service_id,
            target_date=date_obj,
            customer_id=customer_id,
            specialist_id=specialist_id,
            personalize=personalize,
        )

        return Response(optimized_slots)


class PopularTimeSlotsAPIView(APIView):
    """API endpoint for getting popular time slots"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "service_id",
                openapi.IN_QUERY,
                description="Service UUID",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "date",
                openapi.IN_QUERY,
                description="Date in YYYY-MM-DD format",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "limit",
                openapi.IN_QUERY,
                description="Maximum number of slots to return",
                type=openapi.TYPE_INTEGER,
                default=3,
                required=False,
            ),
        ],
        responses={
            200: openapi.Response(
                description="List of popular time slots",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "start": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Start time (HH:MM)",
                            ),
                            "end": openapi.Schema(
                                type=openapi.TYPE_STRING, description="End time (HH:MM)"
                            ),
                            "popularity": openapi.Schema(
                                type=openapi.TYPE_NUMBER,
                                description="Popularity score (0-1)",
                            ),
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

        # Get popular slots
        popular_slots = DynamicAvailabilityService.get_popular_slots(
            service_id=service_id, target_date=date_obj, limit=limit
        )

        return Response(popular_slots)


class QuietTimeSlotsAPIView(APIView):
    """API endpoint for getting quiet/less busy time slots"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "service_id",
                openapi.IN_QUERY,
                description="Service UUID",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "date",
                openapi.IN_QUERY,
                description="Date in YYYY-MM-DD format",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "limit",
                openapi.IN_QUERY,
                description="Maximum number of slots to return",
                type=openapi.TYPE_INTEGER,
                default=3,
                required=False,
            ),
        ],
        responses={
            200: openapi.Response(
                description="List of quiet time slots",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "start": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Start time (HH:MM)",
                            ),
                            "end": openapi.Schema(
                                type=openapi.TYPE_STRING, description="End time (HH:MM)"
                            ),
                            "popularity": openapi.Schema(
                                type=openapi.TYPE_NUMBER,
                                description="Popularity score (0-1)",
                            ),
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

        # Get quiet slots
        quiet_slots = DynamicAvailabilityService.get_quiet_slots(
            service_id=service_id, target_date=date_obj, limit=limit
        )

        return Response(quiet_slots)


class BestSpecialistAPIView(APIView):
    """API endpoint for finding the best specialist for a time slot"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "service_id",
                openapi.IN_QUERY,
                description="Service UUID",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "date",
                openapi.IN_QUERY,
                description="Date in YYYY-MM-DD format",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "time_slot",
                openapi.IN_QUERY,
                description="Time slot in HH:MM format",
                type=openapi.TYPE_STRING,
                required=True,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Best specialist information",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "specialist_id": openapi.Schema(
                            type=openapi.TYPE_STRING, description="Specialist UUID"
                        ),
                        "specialist_name": openapi.Schema(
                            type=openapi.TYPE_STRING, description="Specialist name"
                        ),
                        "optimization_score": openapi.Schema(
                            type=openapi.TYPE_NUMBER, description="Optimization score"
                        ),
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

        # Get best specialist
        specialist_info = DynamicAvailabilityService.get_best_specialist_for_slot(
            service_id=service_id, target_date=date_obj, time_slot=time_slot
        )

        if not specialist_info:
            return Response(
                {"error": "No specialist available for this time slot"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(specialist_info)
