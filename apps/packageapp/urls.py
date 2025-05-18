from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PackageFAQViewSet, PackageViewSet

router = DefaultRouter()
router.register(r"packages", PackageViewSet)
router.register(r"package-faqs", PackageFAQViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
