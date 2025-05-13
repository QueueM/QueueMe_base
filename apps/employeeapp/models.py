import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Employee(models.Model):
    """
    Employee model representing shop staff members
    Can be extended with specialist capabilities through the specialistsapp
    """

    GENDER_CHOICES = (
        ("male", _("Male")),
        ("female", _("Female")),
        ("other", _("Other")),
    )

    POSITION_CHOICES = (
        ("manager", _("Manager")),
        ("reception", _("Reception")),
        ("specialist", _("Specialist")),
        ("assistant", _("Assistant")),
        ("cashier", _("Cashier")),
        ("customer_service", _("Customer Service")),
        ("admin", _("Administrator")),
        ("other", _("Other")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        "authapp.User",
        on_delete=models.CASCADE,
        related_name="employee_profile",
        verbose_name=_("User Account"),
    )
    shop = models.ForeignKey(
        "shopapp.Shop",
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name=_("Shop"),
    )
    first_name = models.CharField(_("First Name"), max_length=100)
    last_name = models.CharField(_("Last Name"), max_length=100)
    email = models.EmailField(_("Email"), blank=True, null=True)
    phone_number = models.CharField(_("Phone Number"), max_length=20, blank=True)
    position = models.CharField(_("Position"), max_length=50, choices=POSITION_CHOICES)
    hire_date = models.DateField(_("Hire Date"), default=timezone.now)
    date_of_birth = models.DateField(_("Date of Birth"), null=True, blank=True)
    gender = models.CharField(_("Gender"), max_length=10, choices=GENDER_CHOICES, blank=True)
    address = models.TextField(_("Address"), blank=True)
    avatar = models.ImageField(_("Avatar"), upload_to="employees/avatars/", null=True, blank=True)
    employee_id = models.CharField(_("Employee ID"), max_length=50, blank=True)
    national_id = models.CharField(_("National ID"), max_length=20, blank=True)
    emergency_contact_name = models.CharField(
        _("Emergency Contact Name"), max_length=100, blank=True
    )
    emergency_contact_phone = models.CharField(
        _("Emergency Contact Phone"), max_length=20, blank=True
    )
    is_active = models.BooleanField(_("Active"), default=True)
    notes = models.TextField(_("Notes"), blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Employee")
        verbose_name_plural = _("Employees")
        indexes = [
            models.Index(fields=["shop", "is_active"]),
            models.Index(fields=["position"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_position_display()})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_specialist(self):
        """Check if employee is also a specialist"""
        return hasattr(self, "specialist")

    @property
    def is_manager(self):
        """Check if employee is a manager"""
        return self.position == "manager"


class EmployeeWorkingHours(models.Model):
    """
    Working hours for an employee, defined per weekday
    Used for availability calculation with services
    """

    WEEKDAY_CHOICES = (
        (0, _("Sunday")),
        (1, _("Monday")),
        (2, _("Tuesday")),
        (3, _("Wednesday")),
        (4, _("Thursday")),
        (5, _("Friday")),
        (6, _("Saturday")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="working_hours",
        verbose_name=_("Employee"),
    )
    weekday = models.IntegerField(_("Weekday"), choices=WEEKDAY_CHOICES)
    from_hour = models.TimeField(_("From Hour"))
    to_hour = models.TimeField(_("To Hour"))
    is_day_off = models.BooleanField(_("Day Off"), default=False)
    break_start = models.TimeField(_("Break Start"), null=True, blank=True)
    break_end = models.TimeField(_("Break End"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Working Hours")
        verbose_name_plural = _("Working Hours")
        unique_together = ("employee", "weekday")

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_weekday_display()}: {self.from_hour.strftime('%I:%M %p')} - {self.to_hour.strftime('%I:%M %p')}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.is_day_off and self.from_hour >= self.to_hour:
            raise ValidationError({"to_hour": _("End time must be after start time.")})

        if self.break_start and self.break_end:
            if self.break_start >= self.break_end:
                raise ValidationError(
                    {"break_end": _("Break end time must be after break start time.")}
                )
            if self.break_start < self.from_hour or self.break_end > self.to_hour:
                raise ValidationError(_("Break time must be within working hours."))


class EmployeeSkill(models.Model):
    """
    Skills associated with an employee
    Used for service assignment and workload optimization
    """

    PROFICIENCY_CHOICES = (
        (1, _("Beginner")),
        (2, _("Intermediate")),
        (3, _("Advanced")),
        (4, _("Expert")),
        (5, _("Master")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="skills",
        verbose_name=_("Employee"),
    )
    skill_name = models.CharField(_("Skill Name"), max_length=100)
    proficiency_level = models.IntegerField(
        _("Proficiency Level"),
        choices=PROFICIENCY_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    description = models.TextField(_("Description"), blank=True)
    years_experience = models.PositiveIntegerField(_("Years of Experience"), default=0)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Employee Skill")
        verbose_name_plural = _("Employee Skills")
        unique_together = ("employee", "skill_name")

    def __str__(self):
        return f"{self.employee.full_name} - {self.skill_name} ({self.get_proficiency_level_display()})"


class EmployeeLeave(models.Model):
    """
    Leave record for an employee
    Affects availability for bookings
    """

    LEAVE_TYPE_CHOICES = (
        ("vacation", _("Vacation")),
        ("sick", _("Sick Leave")),
        ("personal", _("Personal Leave")),
        ("maternity", _("Maternity Leave")),
        ("paternity", _("Paternity Leave")),
        ("unpaid", _("Unpaid Leave")),
        ("other", _("Other")),
    )

    STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("approved", _("Approved")),
        ("rejected", _("Rejected")),
        ("cancelled", _("Cancelled")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="leaves",
        verbose_name=_("Employee"),
    )
    leave_type = models.CharField(_("Leave Type"), max_length=20, choices=LEAVE_TYPE_CHOICES)
    start_date = models.DateField(_("Start Date"))
    end_date = models.DateField(_("End Date"))
    reason = models.TextField(_("Reason"), blank=True)
    status = models.CharField(_("Status"), max_length=10, choices=STATUS_CHOICES, default="pending")
    approved_by = models.ForeignKey(
        "authapp.User",
        on_delete=models.SET_NULL,
        related_name="approved_leaves",
        verbose_name=_("Approved By"),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Employee Leave")
        verbose_name_plural = _("Employee Leaves")
        indexes = [
            models.Index(fields=["employee", "start_date", "end_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_leave_type_display()} ({self.start_date} to {self.end_date})"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_date > self.end_date:
            raise ValidationError({"end_date": _("End date must be after start date.")})
