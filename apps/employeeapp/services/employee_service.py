from django.db import transaction

from apps.authapp.models import User
from apps.employeeapp.models import Employee, EmployeeWorkingHours
from apps.shopapp.models import Shop


class EmployeeService:
    """
    Service for employee management operations
    """

    @staticmethod
    @transaction.atomic
    def create_employee(phone_number, employee_data):
        """
        Create a new employee with user account
        Args:
            phone_number: Phone number for the user account
            employee_data: Data for the employee record
        Returns:
            Employee object
        """
        # Get or create user account
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                "user_type": "employee",
                "is_verified": True,  # Skip OTP verification for employees created by managers
            },
        )

        # If user exists but is not an employee, update user type
        if not created and user.user_type != "employee":
            user.user_type = "employee"
            user.save()

        # Create employee record
        employee = Employee.objects.create(user=user, **employee_data)

        # Add default working hours if not provided
        if not hasattr(employee, "working_hours") or not employee.working_hours.exists():
            EmployeeService.create_default_working_hours(employee)

        return employee

    @staticmethod
    def create_default_working_hours(employee):
        """
        Create default working hours for a new employee
        Based on shop's operating hours
        """
        # Get shop hours
        from apps.shopapp.models import ShopHours

        shop_hours = ShopHours.objects.filter(shop=employee.shop)

        # If shop hours exist, use them as template
        if shop_hours.exists():
            for shop_hour in shop_hours:
                # Create employee working hours based on shop hours
                EmployeeWorkingHours.objects.create(
                    employee=employee,
                    weekday=shop_hour.weekday,
                    from_hour=shop_hour.from_hour,
                    to_hour=shop_hour.to_hour,
                    is_day_off=shop_hour.is_closed,
                )
        else:
            # Create standard 9-5 working hours, closed on Friday (Saudi weekend)
            for weekday in range(7):
                is_day_off = weekday == 5  # Friday is closed

                EmployeeWorkingHours.objects.create(
                    employee=employee,
                    weekday=weekday,
                    from_hour="09:00:00",
                    to_hour="17:00:00",
                    is_day_off=is_day_off,
                )

    @staticmethod
    def get_employee_by_user(user_id):
        """
        Get employee profile for a user
        Args:
            user_id: User ID
        Returns:
            Employee object or None
        """
        try:
            return Employee.objects.get(user_id=user_id)
        except Employee.DoesNotExist:
            return None

    @staticmethod
    def get_shop_employees(shop_id, include_inactive=False, position=None):
        """
        Get all employees for a shop
        Args:
            shop_id: Shop ID
            include_inactive: Whether to include inactive employees
            position: Filter by position
        Returns:
            QuerySet of Employee objects
        """
        queryset = Employee.objects.filter(shop_id=shop_id)

        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        if position:
            queryset = queryset.filter(position=position)

        return queryset

    @staticmethod
    def get_specialists(shop_id, include_inactive=False):
        """
        Get all specialists for a shop
        Specialists are employees that have a specialist profile
        Args:
            shop_id: Shop ID
            include_inactive: Whether to include inactive employees
        Returns:
            QuerySet of Employee objects that are specialists
        """
        # First get employees
        employees = EmployeeService.get_shop_employees(shop_id, include_inactive)

        # Then filter those that have a specialist profile
        # This works because of the OneToOne relationship with specialist model
        return employees.filter(specialist__isnull=False)

    @staticmethod
    @transaction.atomic
    def transfer_employee(employee_id, new_shop_id):
        """
        Transfer an employee to a different shop
        Args:
            employee_id: Employee ID
            new_shop_id: New shop ID
        Returns:
            Updated Employee object
        """
        employee = Employee.objects.get(id=employee_id)
        new_shop = Shop.objects.get(id=new_shop_id)

        # Update employee record
        old_shop = employee.shop
        employee.shop = new_shop
        employee.save()

        # Update roles if roles app is installed
        try:
            from apps.rolesapp.models import Role, UserRole

            # Remove old shop roles
            UserRole.objects.filter(user=employee.user, role__shop=old_shop).delete()

            # Add default role for new shop
            default_role, created = Role.objects.get_or_create(
                role_type="shop_employee", shop=new_shop, defaults={"name": "Employee"}
            )

            UserRole.objects.create(user=employee.user, role=default_role)
        except ImportError:
            # Roles app not installed, skip
            pass

        return employee
