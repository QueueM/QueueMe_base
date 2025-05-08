# apps/rolesapp/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.rolesapp import views

app_name = "rolesapp"

# Create a router for viewsets
router = DefaultRouter()
router.register(r"permissions", views.PermissionViewSet)
router.register(r"content-types", views.ContentTypeViewSet)
router.register(r"roles", views.RoleViewSet)
router.register(r"user-roles", views.UserRoleViewSet)
router.register(r"logs", views.RolePermissionLogViewSet)

urlpatterns = [
    # Include router URLs
    path("", include(router.urls)),
]
