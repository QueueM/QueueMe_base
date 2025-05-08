from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Employee, EmployeeLeave, EmployeeSkill, EmployeeWorkingHours


class EmployeeWorkingHoursInline(admin.TabularInline):
    model = EmployeeWorkingHours
    extra = 0


class EmployeeSkillInline(admin.TabularInline):
    model = EmployeeSkill
    extra = 0


class EmployeeLeaveInline(admin.TabularInline):
    model = EmployeeLeave
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "first_name",
        "last_name",
        "shop",
        "position",
        "is_active",
    )
    list_filter = ("shop", "position", "is_active")
    search_fields = ("first_name", "last_name", "user__phone_number", "email")
    inlines = [EmployeeWorkingHoursInline, EmployeeSkillInline, EmployeeLeaveInline]
    fieldsets = (
        (
            _("Personal Information"),
            {
                "fields": (
                    "user",
                    "first_name",
                    "last_name",
                    "email",
                    "date_of_birth",
                    "gender",
                    "avatar",
                )
            },
        ),
        (
            _("Employment Details"),
            {
                "fields": (
                    "shop",
                    "position",
                    "hire_date",
                    "employee_id",
                    "national_id",
                    "is_active",
                )
            },
        ),
        (
            _("Contact Information"),
            {
                "fields": (
                    "phone_number",
                    "address",
                    "emergency_contact_name",
                    "emergency_contact_phone",
                )
            },
        ),
    )


@admin.register(EmployeeWorkingHours)
class EmployeeWorkingHoursAdmin(admin.ModelAdmin):
    list_display = ("employee", "weekday", "from_hour", "to_hour", "is_day_off")
    list_filter = ("weekday", "is_day_off")
    search_fields = ("employee__first_name", "employee__last_name")


@admin.register(EmployeeSkill)
class EmployeeSkillAdmin(admin.ModelAdmin):
    list_display = ("employee", "skill_name", "proficiency_level")
    list_filter = ("proficiency_level",)
    search_fields = ("employee__first_name", "employee__last_name", "skill_name")


@admin.register(EmployeeLeave)
class EmployeeLeaveAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "status")
    list_filter = ("leave_type", "status")
    search_fields = ("employee__first_name", "employee__last_name")
    date_hierarchy = "start_date"
