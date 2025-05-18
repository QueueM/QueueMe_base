from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    EmployeeAvailabilityView,
    EmployeeLeaveViewSet,
    EmployeeSkillViewSet,
    EmployeeViewSet,
    EmployeeWorkingHoursViewSet,
    EmployeeWorkloadView,
)

router = DefaultRouter()
router.register(r"", EmployeeViewSet, basename="employee")
router.register(
    r"(?P<employee_id>[^/.]+)/working-hours",
    EmployeeWorkingHoursViewSet,
    basename="employee-working-hours",
)
router.register(r"(?P<employee_id>[^/.]+)/skills", EmployeeSkillViewSet, basename="employee-skills")
router.register(r"(?P<employee_id>[^/.]+)/leaves", EmployeeLeaveViewSet, basename="employee-leaves")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "<uuid:employee_id>/availability/",
        EmployeeAvailabilityView.as_view(),
        name="employee-availability",
    ),
    path(
        "<uuid:employee_id>/workload/",
        EmployeeWorkloadView.as_view(),
        name="employee-workload",
    ),
]
