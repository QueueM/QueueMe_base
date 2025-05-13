from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.authapp.models import User

from .models import Employee, EmployeeLeave, EmployeeSkill, EmployeeWorkingHours


class EmployeeWorkingHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeWorkingHours
        fields = [
            "id",
            "weekday",
            "from_hour",
            "to_hour",
            "is_day_off",
            "break_start",
            "break_end",
        ]

    def validate(self, data):
        """Validate working hours data"""
        if "is_day_off" in data and data["is_day_off"]:
            # If it's a day off, time fields are not required
            return data

        from_hour = data.get("from_hour")
        to_hour = data.get("to_hour")
        break_start = data.get("break_start")
        break_end = data.get("break_end")

        if from_hour and to_hour and from_hour >= to_hour:
            raise serializers.ValidationError({"to_hour": _("End time must be after start time.")})

        if break_start and break_end:
            if break_start >= break_end:
                raise serializers.ValidationError(
                    {"break_end": _("Break end time must be after break start time.")}
                )

            if (from_hour and break_start < from_hour) or (to_hour and break_end > to_hour):
                raise serializers.ValidationError(_("Break time must be within working hours."))

        return data


class EmployeeSkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeSkill
        fields = [
            "id",
            "skill_name",
            "proficiency_level",
            "description",
            "years_experience",
        ]


class EmployeeLeaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeLeave
        fields = [
            "id",
            "leave_type",
            "start_date",
            "end_date",
            "reason",
            "status",
            "approved_by",
        ]
        read_only_fields = ["approved_by", "status"]

    def validate(self, data):
        """Validate leave data"""
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"end_date": _("End date must be after start date.")})

        return data


class EmployeeCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new employees with user account"""

    phone_number = serializers.CharField(write_only=True)
    working_hours = EmployeeWorkingHoursSerializer(many=True, required=False)
    skills = EmployeeSkillSerializer(many=True, required=False)

    class Meta:
        model = Employee
        exclude = ["user", "created_at", "updated_at"]

    def validate_phone_number(self, value):
        """Validate that the phone number is not already associated with an employee"""
        try:
            user = User.objects.get(phone_number=value)
            if hasattr(user, "employee_profile"):
                raise serializers.ValidationError(
                    _("This phone number is already associated with an employee.")
                )
        except User.DoesNotExist:
            pass
        return value

    def validate_shop(self, value):
        """Validate that the user has permission to add employees to this shop"""
        user = self.context["request"].user

        # Queue Me admins can add employees to any shop
        if user.user_type == "admin":
            return value

        # Check if user has permission to add employees to this shop
        from apps.rolesapp.services.permission_resolver import PermissionResolver

        if not PermissionResolver.has_shop_permission(user, value.id, "employee", "add"):
            raise serializers.ValidationError(
                _("You don't have permission to add employees to this shop.")
            )

        return value

    def create(self, validated_data):
        """Create a new employee with user account"""
        phone_number = validated_data.pop("phone_number")
        working_hours_data = validated_data.pop("working_hours", [])
        skills_data = validated_data.pop("skills", [])

        # Get or create user account
        from apps.employeeapp.services.employee_service import EmployeeService

        employee = EmployeeService.create_employee(phone_number, validated_data)

        # Create working hours
        for hours_data in working_hours_data:
            EmployeeWorkingHours.objects.create(employee=employee, **hours_data)

        # Create skills
        for skill_data in skills_data:
            EmployeeSkill.objects.create(employee=employee, **skill_data)

        return employee


class EmployeeDetailSerializer(serializers.ModelSerializer):
    """Detailed employee serializer including related data"""

    working_hours = EmployeeWorkingHoursSerializer(many=True, read_only=True)
    skills = EmployeeSkillSerializer(many=True, read_only=True)
    leaves = EmployeeLeaveSerializer(many=True, read_only=True)
    user_phone = serializers.SerializerMethodField()
    shop_name = serializers.SerializerMethodField()
    is_specialist = serializers.BooleanField(read_only=True)

    class Meta:
        model = Employee
        exclude = ["created_at", "updated_at"]

    def get_user_phone(self, obj):
        return obj.user.phone_number

    def get_shop_name(self, obj):
        return obj.shop.name


class EmployeeListSerializer(serializers.ModelSerializer):
    """Simplified employee serializer for list view"""

    shop_name = serializers.SerializerMethodField()
    is_specialist = serializers.BooleanField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "first_name",
            "last_name",
            "position",
            "shop",
            "shop_name",
            "is_active",
            "is_specialist",
            "avatar",
        ]

    def get_shop_name(self, obj):
        return obj.shop.name


class EmployeeUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating employee information"""

    class Meta:
        model = Employee
        exclude = ["user", "shop", "created_at", "updated_at"]
