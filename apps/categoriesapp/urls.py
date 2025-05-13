from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CategoryRelationViewSet, CategoryViewSet

router = DefaultRouter()
router.register(r"", CategoryViewSet, basename="category")
router.register(r"relations", CategoryRelationViewSet, basename="category-relation")

urlpatterns = [
    path("", include(router.urls)),
]
