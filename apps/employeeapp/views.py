"""
Employee app views for QueueMe platform
Handles endpoints related to employees, working hours, skills, leaves, availability, and workload.
"""

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

    Provides CRUD operations for shop employees with different serializers for
    create, update, list, and detail operations.

    Endpoints:
    - GET /api/employees/ - List employees (filtered by permissions)
    - POST /api/employees/ - Create a new employee
    - GET /api/employees/{id}/ - Get employee details
    - PUT/PATCH /api/employees/{id}/ - Update employee details
    - DELETE /api/employees/{id}/ - Delete an employee
    - GET /api/employees/me/ - Get current user's employee profile
    - POST /api/employees/{id}/toggle_active/ - Toggle employee active status
    - POST /api/employees/{id}/make_specialist/ - Convert employee to specialist
    - GET /api/employees/{id}/schedule/ - Get employee's schedule

    Permissions:
    - User must be authenticated
    - User must have proper permissions (admin, shop manager, or employee themselves)

    Filtering:
    - shop: Filter by shop ID
    - position: Filter by position
    - is_active: Filter by active status

    Search fields:
    - first_name: Employee's first name
    - last_name: Employee's last name
    - email: Employee's email
    - phone_number: Employee's phone number

    Ordering:
    - first_name: Employee's first name
    - last_name: Employee's last name
    - position: Employee's position
    - hire_date: Date the employee was hired
    - created_at: Date the employee record was created
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
        """
        Filter employees based on user permissions

        - Admins see all employees
        - Shop managers see employees in their shops
        - Regular users see their own employee profile

        Returns:
            QuerySet: Filtered list of employees
        """
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
        """
        Use appropriate serializer based on action

        - Create: EmployeeCreateSerializer (includes user creation)
        - Update: EmployeeUpdateSerializer (excludes user-related fields)
        - List: EmployeeListSerializer (simplified data for lists)
        - Detail/Retrieve: EmployeeDetailSerializer (full data)

        Returns:
            Serializer class: The appropriate serializer for the current action
        """
        if self.action == "create":
            return EmployeeCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return EmployeeUpdateSerializer
        elif self.action == "list":
            return EmployeeListSerializer
        return EmployeeDetailSerializer

    @action(detail=False, methods=["get"])
    def me(self, request):
        """
        Get current user's employee profile

        Returns the employee profile for the authenticated user.

        Returns:
            Response: Employee profile data

        Status codes:
            200: Profile retrieved successfully
            404: Employee profile not found
        """
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
        """
        Toggle employee active status

        Changes an employee's active status from active to inactive or vice versa.
        This can be used to temporarily disable an employee's account without deleting it.

        Returns:
            Response: Success message and updated active status
                {
                    "status": "success",
                    "is_active": boolean
                }
        """
        employee = self.get_object()
        employee.is_active = not employee.is_active
        employee.save()
        return Response({"status": "success", "is_active": employee.is_active})

    @action(detail=True, methods=["post"])
    def make_specialist(self, request, pk=None):
        """
        Convert employee to specialist

        Transforms an employee into a specialist, which allows them to provide services
        and be booked by customers.

        Returns:
            Response: Success message and specialist ID
                {
                    "detail": "Employee converted to specialist successfully.",
                    "specialist_id": "uuid"
                }

        Status codes:
            200: Conversion successful
            400: Employee is already a specialist
            501: Specialist module not available
        """
        employee = self.get_object()

        # Check if already a specialist
        if employee.is_specialist:
            return Response(
                {"detail": "Employee is already a specialist."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # This requires the specialistsapp to be installed
        try:
            from apps.specialistsapp.services.specialist_service import SpecialistService

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
        """
        Get employee's schedule for a date range

        Returns the employee's schedule including working hours, appointments,
        and leaves for the specified date range.

        Query parameters:
            start_date: Start date (YYYY-MM-DD, default: today)
            end_date: End date (YYYY-MM-DD, default: today + 6 days)

        Returns:
            Response: Schedule data grouped by date
                {
                    "2023-01-01": {
                        "working_hours": [...],
                        "appointments": [...],
                        "leaves": [...]
                    },
                    ...
                }

        Status codes:
            200: Schedule retrieved successfully
            400: Invalid date format
        """
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
        schedule = ScheduleService.get_employee_schedule(employee.id, start_date, end_date)

        return Response(schedule)


class EmployeeWorkingHoursViewSet(viewsets.ModelViewSet):
    """
    API endpoints for employee working hours

    Manages working hours for a specific employee, including creation,
    modification, and deletion of working hour slots.

    Endpoints:
    - GET /api/employees/{employee_id}/working-hours/ - List working hours
    - POST /api/employees/{employee_id}/working-hours/ - Create working hours
    - GET /api/employees/{employee_id}/working-hours/{id}/ - Get specific working hours
    - PUT/PATCH /api/employees/{employee_id}/working-hours/{id}/ - Update working hours
    - DELETE /api/employees/{employee_id}/working-hours/{id}/ - Delete working hours
    - POST /api/employees/{employee_id}/working-hours/bulk_update/ - Bulk update working hours

    Permissions:
    - User must be authenticated
    - User must have proper permissions to manage employee working hours
    """

    permission_classes = [permissions.IsAuthenticated, EmployeeWorkingHoursPermission]
    serializer_class = EmployeeWorkingHoursSerializer

    def get_queryset(self):
        """
        Get working hours for specific employee

        Filters working hours by the employee ID in the URL.

        Returns:
            QuerySet: Working hours for the specified employee
        """
        employee_id = self.kwargs.get("employee_id")
        return EmployeeWorkingHours.objects.filter(employee_id=employee_id)

    def perform_create(self, serializer):
        """
        Create working hours for an employee

        Automatically associates the hours with the employee from the URL.

        Args:
            serializer: The working hours serializer instance
        """
        employee_id = self.kwargs.get("employee_id")
        employee = Employee.objects.get(id=employee_id)
        serializer.save(employee=employee)

    @action(detail=False, methods=["post"])
    def bulk_update(self, request, employee_id=None):
        """
        Update all working hours for an employee

        Allows batch updating of an employee's working hours for efficiency.
        This is useful for setting a new weekly schedule all at once.

        Request body:
            Array of working hours objects
                [
                    {
                        "day_of_week": integer (0-6),
                        "start_time": "HH:MM:SS",
                        "end_time": "HH:MM:SS",
                        "is_day_off": boolean
                    },
                    ...
                ]

        Returns:
            Response: Updated working hours data

        Status codes:
            200: Hours updated successfully
            400: Invalid data in request
        """
        employee = Employee.objects.get(id=employee_id)

        # Implementation uses ScheduleService for complex operations
        working_hours_data = request.data

        try:
            updated_hours = ScheduleService.update_working_hours(employee.id, working_hours_data)
            serializer = EmployeeWorkingHoursSerializer(updated_hours, many=True)
            return Response(serializer.data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class EmployeeSkillViewSet(viewsets.ModelViewSet):
    """
    API endpoints for employee skills

    Manages skills for a specific employee, which can be used to match them
    with appropriate services and assignments.

    Endpoints:
    - GET /api/employees/{employee_id}/skills/ - List employee skills
    - POST /api/employees/{employee_id}/skills/ - Add a skill to employee
    - GET /api/employees/{employee_id}/skills/{id}/ - Get specific skill
    - PUT/PATCH /api/employees/{employee_id}/skills/{id}/ - Update skill
    - DELETE /api/employees/{employee_id}/skills/{id}/ - Remove skill from employee

    Permissions:
    - User must be authenticated
    - User must have proper permissions to manage employee skills
    """

    permission_classes = [permissions.IsAuthenticated, EmployeePermission]
    serializer_class = EmployeeSkillSerializer

    def get_queryset(self):
        """
        Get skills for specific employee

        Filters skills by the employee ID in the URL.

        Returns:
            QuerySet: Skills for the specified employee
        """
        employee_id = self.kwargs.get("employee_id")
        return EmployeeSkill.objects.filter(employee_id=employee_id)

    def perform_create(self, serializer):
        """
        Create a skill for an employee

        Automatically associates the skill with the employee from the URL.

        Args:
            serializer: The skill serializer instance
        """
        employee_id = self.kwargs.get("employee_id")
        employee = Employee.objects.get(id=employee_id)
        serializer.save(employee=employee)


class EmployeeLeaveViewSet(viewsets.ModelViewSet):
    """
    API endpoints for employee leaves

    Manages leave requests and approvals for a specific employee,
    including vacation, sick leave, and other absence types.

    Endpoints:
    - GET /api/employees/{employee_id}/leaves/ - List employee leaves
    - POST /api/employees/{employee_id}/leaves/ - Create leave request
    - GET /api/employees/{employee_id}/leaves/{id}/ - Get specific leave
    - PUT/PATCH /api/employees/{employee_id}/leaves/{id}/ - Update leave request
    - DELETE /api/employees/{employee_id}/leaves/{id}/ - Delete leave request
    - POST /api/employees/{employee_id}/leaves/{id}/approve/ - Approve leave request
    - POST /api/employees/{employee_id}/leaves/{id}/reject/ - Reject leave request

    Permissions:
    - User must be authenticated
    - User must have proper permissions to manage employee leaves

    Filtering:
    - leave_type: Filter by leave type
    - status: Filter by leave status
    - start_date: Filter by start date
    - end_date: Filter by end date
    """

    permission_classes = [permissions.IsAuthenticated, EmployeePermission]
    serializer_class = EmployeeLeaveSerializer
    filterset_fields = ["leave_type", "status", "start_date", "end_date"]

    def get_queryset(self):
        """
        Get leaves for specific employee

        Filters leaves by the employee ID in the URL.

        Returns:
            QuerySet: Leaves for the specified employee
        """
        employee_id = self.kwargs.get("employee_id")
        return EmployeeLeave.objects.filter(employee_id=employee_id)

    def perform_create(self, serializer):
        """
        Create a leave request for an employee

        Automatically associates the leave with the employee from the URL.

        Args:
            serializer: The leave serializer instance
        """
        employee_id = self.kwargs.get("employee_id")
        employee = Employee.objects.get(id=employee_id)
        serializer.save(employee=employee)

    @action(detail=True, methods=["post"])
    def approve(self, request, employee_id=None, pk=None):
        """
        Approve a leave request

        Changes a leave request's status to approved.
        Only shop managers and admins can approve leave requests.

        Returns:
            Response: Success message
                {
                    "status": "success",
                    "detail": "Leave approved successfully."
                }

        Status codes:
            200: Leave approved successfully
            403: Insufficient permissions
        """
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
        """
        Reject a leave request

        Changes a leave request's status to rejected.
        Only shop managers and admins can reject leave requests.

        Returns:
            Response: Success message
                {
                    "status": "success",
                    "detail": "Leave rejected successfully."
                }

        Status codes:
            200: Leave rejected successfully
            403: Insufficient permissions
        """
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

    Returns time slots when an employee is available for new appointments,
    taking into account working hours, existing appointments, and leaves.

    Endpoint:
    - GET /api/employees/{employee_id}/availability/ - Get availability

    Query parameters:
        date: Date to check availability (YYYY-MM-DD, default: today)

    Returns:
        Response: List of available time slots
            [
                {
                    "start_time": "HH:MM:SS",
                    "end_time": "HH:MM:SS",
                    "duration_minutes": integer
                },
                ...
            ]

    Status codes:
        200: Availability retrieved successfully
        400: Invalid date format
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, employee_id):
        """
        Get employee availability for a specific date

        Args:
            request: The HTTP request
            employee_id: The employee ID

        Returns:
            Response: List of available time slots
        """
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

    Returns workload statistics for an employee over a specified time period,
    including booked hours, utilization, and efficiency metrics.

    Endpoint:
    - GET /api/employees/{employee_id}/workload/ - Get workload analytics

    Query parameters:
        start_date: Start date (YYYY-MM-DD, default: first day of current month)
        end_date: End date (YYYY-MM-DD, default: today)

    Returns:
        Response: Workload analytics data
            {
                "total_hours": float,
                "booked_hours": float,
                "utilization_rate": float,
                "appointments_count": integer,
                "average_duration": float,
                "daily_breakdown": [...],
                "service_breakdown": [...]
            }

    Status codes:
        200: Workload data retrieved successfully
        400: Invalid date format
    """

    permission_classes = [permissions.IsAuthenticated, EmployeePermission]

    def get(self, request, employee_id):
        """
        Get employee workload analytics

        Args:
            request: The HTTP request
            employee_id: The employee ID

        Returns:
            Response: Workload analytics data
        """
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
        workload = WorkloadOptimizer.analyze_employee_workload(employee_id, start_date, end_date)

        return Response(workload)
