"""
Queue app views for QueueMe platform
Handles endpoints related to queue management and ticket processing
"""

from django.db.models import Avg, Count, F
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.documentation.api_doc_decorators import document_api_endpoint, document_api_viewset
from apps.rolesapp.decorators import has_permission, has_shop_permission

from .models import Queue, QueueTicket
from .serializers import (
    QueueCallNextSerializer,
    QueueJoinSerializer,
    QueueSerializer,
    QueueTicketPositionSerializer,
    QueueTicketSerializer,
    TicketUpdateSerializer,
)
from .services.queue_service import QueueService


@document_api_endpoint(
    summary="List or create queues",
    description="Retrieve all queues or create a new queue",
    responses={
        200: "Success - Returns list of queues",
        201: "Created - Queue created successfully",
        403: "Forbidden - User doesn't have permission",
    },
    tags=["Queues"],
)
class QueueListView(generics.ListCreateAPIView):
    """List all queues or create a new queue"""

    queryset = Queue.objects.all()
    serializer_class = QueueSerializer

    @has_permission("queue", "view")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @has_permission("queue", "add")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@document_api_endpoint(
    summary="Retrieve, update or delete a queue",
    description="Get details of a specific queue, update it, or delete it",
    responses={
        200: "Success - Returns queue details or updated queue",
        204: "No Content - Queue deleted successfully",
        403: "Forbidden - User doesn't have permission",
        404: "Not Found - Queue not found",
    },
    path_params=[{"name": "pk", "description": "Queue ID", "type": "string"}],
    tags=["Queues"],
)
class QueueDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a queue"""

    queryset = Queue.objects.all()
    serializer_class = QueueSerializer

    @has_permission("queue", "view")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @has_permission("queue", "edit")
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @has_permission("queue", "edit")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @has_permission("queue", "delete")
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


@document_api_endpoint(
    summary="List queues for a shop",
    description="Retrieve all queues for a specific shop",
    responses={
        200: "Success - Returns list of queues for the shop",
        403: "Forbidden - User doesn't have permission",
        404: "Not Found - Shop not found",
    },
    path_params=[{"name": "shop_id", "description": "Shop ID", "type": "string"}],
    tags=["Queues", "Shops"],
)
class ShopQueueListView(generics.ListAPIView):
    """List all queues for a specific shop"""

    serializer_class = QueueSerializer

    def get_queryset(self):
        shop_id = self.kwargs["shop_id"]
        return Queue.objects.filter(shop_id=shop_id)

    @has_shop_permission("queue", "view")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@document_api_endpoint(
    summary="List queue tickets",
    description="Retrieve all queue tickets with optional filtering",
    responses={
        200: "Success - Returns list of queue tickets",
        403: "Forbidden - User doesn't have permission",
    },
    query_params=[
        {
            "name": "queue",
            "description": "Filter by queue ID",
            "required": False,
            "type": "string",
        },
        {
            "name": "status",
            "description": "Filter by ticket status",
            "required": False,
            "type": "string",
        },
        {
            "name": "customer",
            "description": "Filter by customer ID",
            "required": False,
            "type": "string",
        },
    ],
    tags=["Queue Tickets"],
)
class QueueTicketListView(generics.ListAPIView):
    """List all queue tickets"""

    queryset = QueueTicket.objects.all()
    serializer_class = QueueTicketSerializer
    filterset_fields = ["queue", "status", "customer"]

    @has_permission("queue", "view")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@document_api_endpoint(
    summary="Retrieve a queue ticket",
    description="Get details of a specific queue ticket",
    responses={
        200: "Success - Returns queue ticket details",
        403: "Forbidden - User doesn't have permission",
        404: "Not Found - Queue ticket not found",
    },
    path_params=[{"name": "pk", "description": "Queue Ticket ID", "type": "string"}],
    tags=["Queue Tickets"],
)
class QueueTicketDetailView(generics.RetrieveAPIView):
    """Retrieve a queue ticket"""

    queryset = QueueTicket.objects.all()
    serializer_class = QueueTicketSerializer

    @has_permission("queue", "view")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@document_api_endpoint(
    summary="Join a queue",
    description="Add a customer to a queue and create a queue ticket",
    responses={
        201: "Created - Customer successfully joined the queue",
        400: "Bad Request - Invalid data or unable to join queue",
        401: "Unauthorized - Authentication required",
    },
    tags=["Queue Tickets", "Queue Operations"],
)
class JoinQueueView(APIView):
    """Add customer to queue"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = QueueJoinSerializer(data=request.data)

        if serializer.is_valid():
            queue_id = serializer.validated_data["queue_id"]
            customer_id = serializer.validated_data["customer_id"]
            service_id = serializer.validated_data.get("service_id")

            result = QueueService.join_queue(queue_id, customer_id, service_id)

            if isinstance(result, dict) and "error" in result:
                return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

            return Response(QueueTicketSerializer(result).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@document_api_endpoint(
    summary="Call next customer",
    description="Call the next customer in the queue",
    responses={
        200: "Success - Next customer called successfully",
        400: "Bad Request - Invalid data or no customers in queue",
        401: "Unauthorized - Authentication required",
        403: "Forbidden - User doesn't have permission",
    },
    tags=["Queue Operations"],
)
class CallNextView(APIView):
    """Call next customer in queue"""

    permission_classes = [permissions.IsAuthenticated]

    @has_permission("queue", "edit")
    def post(self, request):
        serializer = QueueCallNextSerializer(data=request.data)

        if serializer.is_valid():
            queue_id = serializer.validated_data["queue_id"]
            specialist_id = serializer.validated_data.get("specialist_id")

            result = QueueService.call_next(queue_id, specialist_id)

            if isinstance(result, dict) and "error" in result:
                return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

            return Response(QueueTicketSerializer(result).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@document_api_endpoint(
    summary="Mark customer as being served",
    description="Update a ticket status to indicate customer is currently being served",
    responses={
        200: "Success - Customer marked as being served",
        400: "Bad Request - Invalid data or ticket status",
        401: "Unauthorized - Authentication required",
        403: "Forbidden - User doesn't have permission",
    },
    tags=["Queue Operations"],
)
class MarkServingView(APIView):
    """Mark customer as being served"""

    permission_classes = [permissions.IsAuthenticated]

    @has_permission("queue", "edit")
    def post(self, request):
        serializer = TicketUpdateSerializer(data=request.data)

        if serializer.is_valid():
            ticket_id = serializer.validated_data["ticket_id"]
            specialist_id = serializer.validated_data.get("specialist_id")

            result = QueueService.mark_serving(ticket_id, specialist_id)

            if isinstance(result, dict) and "error" in result:
                return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

            return Response(QueueTicketSerializer(result).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@document_api_endpoint(
    summary="Mark customer as served",
    description="Update a ticket status to indicate service is completed",
    responses={
        200: "Success - Customer marked as served",
        400: "Bad Request - Invalid data or ticket status",
        401: "Unauthorized - Authentication required",
        403: "Forbidden - User doesn't have permission",
    },
    tags=["Queue Operations"],
)
class MarkServedView(APIView):
    """Mark customer as served (completed)"""

    permission_classes = [permissions.IsAuthenticated]

    @has_permission("queue", "edit")
    def post(self, request):
        serializer = TicketUpdateSerializer(data=request.data)

        if serializer.is_valid():
            ticket_id = serializer.validated_data["ticket_id"]

            result = QueueService.mark_served(ticket_id)

            if isinstance(result, dict) and "error" in result:
                return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

            return Response(QueueTicketSerializer(result).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@document_api_endpoint(
    summary="Cancel a queue ticket",
    description="Cancel a customer's place in the queue",
    responses={
        200: "Success - Ticket canceled successfully",
        400: "Bad Request - Invalid data or ticket status",
        401: "Unauthorized - Authentication required",
        403: "Forbidden - User doesn't have permission",
        404: "Not Found - Ticket not found",
    },
    tags=["Queue Operations", "Queue Tickets"],
)
class CancelTicketView(APIView):
    """Cancel a queue ticket"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TicketUpdateSerializer(data=request.data)

        if serializer.is_valid():
            ticket_id = serializer.validated_data["ticket_id"]

            # Get the ticket
            try:
                ticket = QueueTicket.objects.get(id=ticket_id)

                # Check if requesting user is the ticket owner or has queue edit permission
                is_owner = request.user.id == ticket.customer.id
                has_edit_perm = request.user.has_perm("queue.edit_queueticket")

                if not (is_owner or has_edit_perm):
                    return Response(
                        {"error": "You do not have permission to cancel this ticket"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                result = QueueService.cancel_ticket(ticket_id)

                if isinstance(result, dict) and "error" in result:
                    return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

                return Response(QueueTicketSerializer(result).data)

            except QueueTicket.DoesNotExist:
                return Response({"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@document_api_endpoint(
    summary="Get queue status",
    description="Get current status of a queue including active tickets and wait times",
    responses={
        200: "Success - Returns queue status information",
        401: "Unauthorized - Authentication required",
        404: "Not Found - Queue not found",
    },
    path_params=[{"name": "queue_id", "description": "Queue ID", "type": "string"}],
    tags=["Queues", "Queue Status"],
)
class QueueStatusView(APIView):
    """Get current status of a queue"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, queue_id):
        try:
            queue = Queue.objects.get(id=queue_id)

            # Get active tickets (waiting, called, or serving)
            active_tickets = QueueTicket.objects.filter(
                queue=queue, status__in=["waiting", "called", "serving"]
            ).order_by("position")

            # Get counts
            waiting_count = active_tickets.filter(status="waiting").count()
            called_count = active_tickets.filter(status="called").count()
            serving_count = active_tickets.filter(status="serving").count()

            # Get average wait time for recently served tickets
            now = timezone.now()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            avg_wait_time = (
                QueueTicket.objects.filter(
                    queue=queue, status="served", complete_time__gte=today
                ).aggregate(avg_wait=Avg("actual_wait_time"))["avg_wait"]
                or 0
            )

            return Response(
                {
                    "queue": QueueSerializer(queue).data,
                    "active_tickets": QueueTicketSerializer(active_tickets, many=True).data,
                    "counts": {
                        "waiting": waiting_count,
                        "called": called_count,
                        "serving": serving_count,
                        "total": waiting_count + called_count + serving_count,
                    },
                    "average_wait_time": round(avg_wait_time),
                    "timestamp": now,
                }
            )

        except Queue.DoesNotExist:
            return Response({"error": "Queue not found"}, status=status.HTTP_404_NOT_FOUND)


@document_api_endpoint(
    summary="Check queue position",
    description="Check a customer's position in the queue",
    responses={
        200: "Success - Returns position information",
        400: "Bad Request - Invalid data",
        401: "Unauthorized - Authentication required",
        404: "Not Found - Ticket not found or not active",
    },
    tags=["Queue Tickets", "Queue Status"],
)
class CheckPositionView(APIView):
    """Check a customer's position in queue"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = QueueTicketPositionSerializer(data=request.data)

        if serializer.is_valid():
            ticket_number = serializer.validated_data["ticket_number"]
            queue_id = serializer.validated_data["queue_id"]

            try:
                ticket = QueueTicket.objects.get(
                    ticket_number=ticket_number,
                    queue_id=queue_id,
                    status__in=["waiting", "called"],
                )

                # Get count of tickets ahead
                tickets_ahead = QueueTicket.objects.filter(
                    queue_id=queue_id, position__lt=ticket.position, status="waiting"
                ).count()

                return Response(
                    {
                        "ticket": QueueTicketSerializer(ticket).data,
                        "position": ticket.position,
                        "tickets_ahead": tickets_ahead,
                        "estimated_wait_time": ticket.estimated_wait_time,
                        "timestamp": timezone.now(),
                    }
                )

            except QueueTicket.DoesNotExist:
                return Response(
                    {"error": "Ticket not found or not in active status"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@document_api_endpoint(
    summary="Get customer's active tickets",
    description="Get all active queue tickets for a specific customer",
    responses={
        200: "Success - Returns list of active tickets",
        401: "Unauthorized - Authentication required",
        403: "Forbidden - User doesn't have permission",
    },
    path_params=[{"name": "customer_id", "description": "Customer ID", "type": "string"}],
    tags=["Queue Tickets", "Customers"],
)
class CustomerActiveTicketsView(APIView):
    """Get active tickets for a customer"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, customer_id):
        # Check if requesting user is the customer or has permission
        is_owner = str(request.user.id) == str(customer_id)
        has_view_perm = request.user.has_perm("queue.view_queueticket")

        if not (is_owner or has_view_perm):
            return Response(
                {"error": "You do not have permission to view these tickets"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get active tickets for customer
        active_tickets = (
            QueueTicket.objects.filter(customer_id=customer_id, status__in=["waiting", "called"])
            .select_related("queue", "service")
            .order_by("position")
        )

        return Response(QueueTicketSerializer(active_tickets, many=True).data)


@document_api_endpoint(
    summary="Get queue statistics",
    description="Get statistics for a queue including metrics and distribution data",
    responses={
        200: "Success - Returns queue statistics",
        401: "Unauthorized - Authentication required",
        403: "Forbidden - User doesn't have permission",
        404: "Not Found - Queue not found",
    },
    path_params=[{"name": "queue_id", "description": "Queue ID", "type": "string"}],
    query_params=[
        {
            "name": "start_date",
            "description": "Start date for statistics (YYYY-MM-DD), defaults to today",
            "required": False,
            "type": "string",
        },
        {
            "name": "end_date",
            "description": "End date for statistics (YYYY-MM-DD), defaults to start_date",
            "required": False,
            "type": "string",
        },
    ],
    tags=["Queues", "Analytics"],
)
class QueueStatsView(APIView):
    """Get statistics for a queue"""

    permission_classes = [permissions.IsAuthenticated]

    @has_shop_permission("queue", "view")
    def get(self, request, queue_id):
        try:
            queue = Queue.objects.get(id=queue_id)

            # Get date range - default to today
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")

            if start_date:
                start_date = timezone.datetime.strptime(start_date, "%Y-%m-%d").date()
            else:
                start_date = timezone.now().date()

            if end_date:
                end_date = timezone.datetime.strptime(end_date, "%Y-%m-%d").date()
            else:
                end_date = start_date

            # Add day to end_date to make it inclusive
            end_datetime = timezone.datetime.combine(end_date, timezone.datetime.max.time())
            start_datetime = timezone.datetime.combine(start_date, timezone.datetime.min.time())

            # Make timezone aware
            tz = timezone.get_current_timezone()
            start_datetime = timezone.make_aware(start_datetime, tz)
            end_datetime = timezone.make_aware(end_datetime, tz)

            # Get tickets in date range
            tickets = QueueTicket.objects.filter(
                queue=queue, join_time__gte=start_datetime, join_time__lte=end_datetime
            )

            # Calculate statistics
            total_tickets = tickets.count()
            served_tickets = tickets.filter(status="served").count()
            cancelled_tickets = tickets.filter(status="cancelled").count()
            skipped_tickets = tickets.filter(status="skipped").count()

            # Calculate averages
            avg_wait_time = (
                tickets.filter(status="served").aggregate(avg_wait=Avg("actual_wait_time"))[
                    "avg_wait"
                ]
                or 0
            )

            # Get busiest hours
            hour_distribution = (
                tickets.annotate(hour=F("join_time__hour"))
                .values("hour")
                .annotate(count=Count("id"))
                .order_by("hour")
            )

            # Get service distribution
            service_distribution = (
                tickets.values("service__name").annotate(count=Count("id")).order_by("-count")
            )

            # Format the response
            return Response(
                {
                    "queue": QueueSerializer(queue).data,
                    "date_range": {"start_date": start_date, "end_date": end_date},
                    "counts": {
                        "total": total_tickets,
                        "served": served_tickets,
                        "cancelled": cancelled_tickets,
                        "skipped": skipped_tickets,
                        "completion_rate": (
                            round(served_tickets / total_tickets * 100, 2)
                            if total_tickets > 0
                            else 0
                        ),
                    },
                    "averages": {"wait_time": round(avg_wait_time, 2)},
                    "distributions": {
                        "hourly": list(hour_distribution),
                        "services": list(service_distribution),
                    },
                }
            )

        except Queue.DoesNotExist:
            return Response({"error": "Queue not found"}, status=status.HTTP_404_NOT_FOUND)


@document_api_viewset(
    summary="Queue Ticket",
    description="API endpoints for managing queue tickets with CRUD operations",
    tags=["Queue Tickets"],
)
class QueueTicketViewSet(viewsets.ModelViewSet):
    """
    ViewSet for queue tickets.
    Provides complete set of CRUD operations.
    """

    queryset = QueueTicket.objects.all()
    serializer_class = QueueTicketSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["queue", "status", "customer"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission = has_permission("queue", "view")
        elif self.action in ["create"]:
            permission = has_permission("queue", "add")
        elif self.action in ["update", "partial_update"]:
            permission = has_permission("queue", "edit")
        elif self.action in ["destroy"]:
            permission = has_permission("queue", "delete")
        else:
            permission = IsAuthenticated()

        return [permission]

    @document_api_endpoint(
        summary="List queue tickets",
        description="Retrieve all queue tickets with optional filtering",
        responses={
            200: "Success - Returns list of queue tickets",
            403: "Forbidden - User doesn't have permission",
        },
        query_params=[
            {
                "name": "queue",
                "description": "Filter by queue ID",
                "required": False,
                "type": "string",
            },
            {
                "name": "status",
                "description": "Filter by ticket status",
                "required": False,
                "type": "string",
            },
            {
                "name": "customer",
                "description": "Filter by customer ID",
                "required": False,
                "type": "string",
            },
        ],
        tags=["Queue Tickets"],
    )
    def list(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().list(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Create queue ticket",
        description="Create a new queue ticket",
        responses={
            201: "Created - Queue ticket created successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
        },
        tags=["Queue Tickets"],
    )
    def create(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().create(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Retrieve queue ticket",
        description="Get details of a specific queue ticket",
        responses={
            200: "Success - Returns queue ticket details",
            404: "Not Found - Queue ticket not found",
        },
        path_params=[{"name": "pk", "description": "Queue Ticket ID", "type": "string"}],
        tags=["Queue Tickets"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().retrieve(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Update queue ticket",
        description="Update an existing queue ticket",
        responses={
            200: "Success - Queue ticket updated successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Queue ticket not found",
        },
        path_params=[{"name": "pk", "description": "Queue Ticket ID", "type": "string"}],
        tags=["Queue Tickets"],
    )
    def update(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().update(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Delete queue ticket",
        description="Delete a queue ticket",
        responses={
            204: "No Content - Queue ticket deleted successfully",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Queue ticket not found",
        },
        path_params=[{"name": "pk", "description": "Queue Ticket ID", "type": "string"}],
        tags=["Queue Tickets"],
    )
    def destroy(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().destroy(request, *args, **kwargs)


@document_api_viewset(
    summary="Queue",
    description="API endpoints for managing queues with CRUD operations",
    tags=["Queues"],
)
class QueueViewSet(viewsets.ModelViewSet):
    """
    ViewSet for queues.
    Provides complete set of CRUD operations.
    """

    queryset = Queue.objects.all()
    serializer_class = QueueSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission = has_permission("queue", "view")
        elif self.action in ["create"]:
            permission = has_permission("queue", "add")
        elif self.action in ["update", "partial_update"]:
            permission = has_permission("queue", "edit")
        elif self.action in ["destroy"]:
            permission = has_permission("queue", "delete")
        else:
            permission = IsAuthenticated()

        return [permission]

    @document_api_endpoint(
        summary="List queues",
        description="Retrieve all queues",
        responses={
            200: "Success - Returns list of queues",
            403: "Forbidden - User doesn't have permission",
        },
        tags=["Queues"],
    )
    def list(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().list(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Create queue",
        description="Create a new queue",
        responses={
            201: "Created - Queue created successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
        },
        tags=["Queues"],
    )
    def create(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().create(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Retrieve queue",
        description="Get details of a specific queue",
        responses={
            200: "Success - Returns queue details",
            404: "Not Found - Queue not found",
        },
        path_params=[{"name": "pk", "description": "Queue ID", "type": "string"}],
        tags=["Queues"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().retrieve(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Update queue",
        description="Update an existing queue",
        responses={
            200: "Success - Queue updated successfully",
            400: "Bad Request - Invalid data",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Queue not found",
        },
        path_params=[{"name": "pk", "description": "Queue ID", "type": "string"}],
        tags=["Queues"],
    )
    def update(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().update(request, *args, **kwargs)

    @document_api_endpoint(
        summary="Delete queue",
        description="Delete a queue",
        responses={
            204: "No Content - Queue deleted successfully",
            403: "Forbidden - User doesn't have permission",
            404: "Not Found - Queue not found",
        },
        path_params=[{"name": "pk", "description": "Queue ID", "type": "string"}],
        tags=["Queues"],
    )
    def destroy(self, request, *args, **kwargs):
        """Override to add documentation"""
        return super().destroy(request, *args, **kwargs)
