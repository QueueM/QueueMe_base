from datetime import datetime, timedelta

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Employee, EmployeeLeave, EmployeeSkill, EmployeeWorkingHours
from .permissions import EmployeePermission, EmployeeWorkingHoursPermission
from .serializers import (
    EmployeeCreateSerializer,
    EmployeeDetailSerializer,
    EmployeeLeaveSerializer,
    EmployeeListSerializer,
    EmployeeSkillSerializer,
    EmployeeUpdateSerializer,
    EmployeeWorkingHoursSerializer,
)
from .services.schedule_service import ScheduleService
from .services.workload_optimizer import WorkloadOptimizer


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    API endpoints for employee management
    """

    permission_classes = [permissions.IsAuthenticated, EmployeePermission]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["shop", "position", "is_active"]
    search_fields = ["first_name", "last_name", "email", "phone_number"]
    ordering_fields = ["first_name", "last_name", "position", "hire_date", "created_at"]
    ordering = ["first_name"]

    def get_queryset(self):
        """Filter employees based on user permissions"""
        user = self.request.user

        # Admin sees all employees
        if user.user_type == "admin":
            return Employee.objects.all()

        # Get shops the user has access to
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        accessible_shops = PermissionResolver.get_user_shops(user)

        # Return employees from accessible shops
        return Employee.objects.filter(shop__in=accessible_shops)

    def get_serializer_class(self):
        if self.action == "create":
            return EmployeeCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return EmployeeUpdateSerializer
        elif self.action == "list":
            return EmployeeListSerializer
        return EmployeeDetailSerializer

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user's employee profile"""
        try:
            employee = Employee.objects.get(user=request.user)
            serializer = EmployeeDetailSerializer(employee)
            return Response(serializer.data)
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        """Toggle employee active status"""
        employee = self.get_object()
        employee.is_active = not employee.is_active
        employee.save()
        return Response({"status": "success", "is_active": employee.is_active})

    @action(detail=True, methods=["post"])
    def make_specialist(self, request, pk=None):
        """Convert employee to specialist"""
        employee = self.get_object()

        # Check if already a specialist
        if employee.is_specialist:
            return Response(
                {"detail": "Employee is already a specialist."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # This requires the specialistsapp to be installed
        try:
            from apps.specialistsapp.services.specialist_service import (
                SpecialistService,
            )

            specialist = SpecialistService.create_specialist_from_employee(employee)
            return Response(
                {
                    "detail": "Employee converted to specialist successfully.",
                    "specialist_id": str(specialist.id),
                }
            )
        except ImportError:
            return Response(
                {"detail": "Specialist module is not available."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

    @action(detail=True, methods=["get"])
    def schedule(self, request, pk=None):
        """Get employee's schedule for a date range"""
        employee = self.get_object()

        # Get date range from query params (default to current week)
        today = datetime.now().date()
        start_date = request.query_params.get("start_date", today.strftime("%Y-%m-%d"))
        end_date = request.query_params.get(
            "end_date", (today + timedelta(days=6)).strftime("%Y-%m-%d")
        )

        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get schedule from service
        schedule = ScheduleService.get_employee_schedule(
            employee.id, start_date, end_date
        )

        return Response(schedule)


class EmployeeWorkingHoursViewSet(viewsets.ModelViewSet):
    """
    API endpoints for employee working hours
    """

    permission_classes = [permissions.IsAuthenticated, EmployeeWorkingHoursPermission]
    serializer_class = EmployeeWorkingHoursSerializer

    def get_queryset(self):
        """Get working hours for specific employee"""
        employee_id = self.kwargs.get("employee_id")
        return EmployeeWorkingHours.objects.filter(employee_id=employee_id)

    def perform_create(self, serializer):
        employee_id = self.kwargs.get("employee_id")
        employee = Employee.objects.get(id=employee_id)
        serializer.save(employee=employee)

    @action(detail=False, methods=["post"])
    def bulk_update(self, request, employee_id=None):
        """Update all working hours for an employee"""
        employee = Employee.objects.get(id=employee_id)

        # Implementation uses ScheduleService for complex operations
        working_hours_data = request.data

        try:
            updated_hours = ScheduleService.update_working_hours(
                employee.id, working_hours_data
            )
            serializer = EmployeeWorkingHoursSerializer(updated_hours, many=True)
            return Response(serializer.data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class EmployeeSkillViewSet(viewsets.ModelViewSet):
    """
    API endpoints for employee skills
    """

    permission_classes = [permissions.IsAuthenticated, EmployeePermission]
    serializer_class = EmployeeSkillSerializer

    def get_queryset(self):
        """Get skills for specific employee"""
        employee_id = self.kwargs.get("employee_id")
        return EmployeeSkill.objects.filter(employee_id=employee_id)

    def perform_create(self, serializer):
        employee_id = self.kwargs.get("employee_id")
        employee = Employee.objects.get(id=employee_id)
        serializer.save(employee=employee)


class EmployeeLeaveViewSet(viewsets.ModelViewSet):
    """
    API endpoints for employee leaves
    """

    permission_classes = [permissions.IsAuthenticated, EmployeePermission]
    serializer_class = EmployeeLeaveSerializer
    filterset_fields = ["leave_type", "status", "start_date", "end_date"]

    def get_queryset(self):
        """Get leaves for specific employee"""
        employee_id = self.kwargs.get("employee_id")
        return EmployeeLeave.objects.filter(employee_id=employee_id)

    def perform_create(self, serializer):
        employee_id = self.kwargs.get("employee_id")
        employee = Employee.objects.get(id=employee_id)
        serializer.save(employee=employee)

    @action(detail=True, methods=["post"])
    def approve(self, request, employee_id=None, pk=None):
        """Approve a leave request"""
        leave = self.get_object()

        # Check if user has permission to approve leaves
        if not request.user.user_type == "admin" and not (
            hasattr(request.user, "employee_profile")
            and request.user.employee_profile.is_manager
            and request.user.employee_profile.shop_id == leave.employee.shop_id
        ):
            return Response(
                {"detail": "You don't have permission to approve leaves."},
                status=status.HTTP_403_FORBIDDEN,
            )

        leave.status = "approved"
        leave.approved_by = request.user
        leave.save()

        return Response({"status": "success", "detail": "Leave approved successfully."})

    @action(detail=True, methods=["post"])
    def reject(self, request, employee_id=None, pk=None):
        """Reject a leave request"""
        leave = self.get_object()

        # Check if user has permission to reject leaves
        if not request.user.user_type == "admin" and not (
            hasattr(request.user, "employee_profile")
            and request.user.employee_profile.is_manager
            and request.user.employee_profile.shop_id == leave.employee.shop_id
        ):
            return Response(
                {"detail": "You don't have permission to reject leaves."},
                status=status.HTTP_403_FORBIDDEN,
            )

        leave.status = "rejected"
        leave.approved_by = request.user
        leave.save()

        return Response({"status": "success", "detail": "Leave rejected successfully."})


class EmployeeAvailabilityView(APIView):
    """
    Get employee availability for a specific date
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, employee_id):
        # Get date from query params (default to today)
        date_str = request.query_params.get("date", datetime.now().strftime("%Y-%m-%d"))

        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get availability from service
        availability = ScheduleService.get_employee_availability(employee_id, date)

        return Response(availability)


class EmployeeWorkloadView(APIView):
    """
    Get employee workload analytics
    """

    permission_classes = [permissions.IsAuthenticated, EmployeePermission]

    def get(self, request, employee_id):
        # Get date range from query params (default to current month)
        today = datetime.now().date()
        start_date = request.query_params.get(
            "start_date", (today.replace(day=1)).strftime("%Y-%m-%d")
        )
        end_date = request.query_params.get("end_date", today.strftime("%Y-%m-%d"))

        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get workload analysis from service
        workload = WorkloadOptimizer.analyze_employee_workload(
            employee_id, start_date, end_date
        )

        return Response(workload)
