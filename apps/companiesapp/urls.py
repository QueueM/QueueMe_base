# apps/companiesapp/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CompanyDocumentViewSet, CompanyViewSet

router = DefaultRouter()
router.register(r"", CompanyViewSet)
router.register(
    r"(?P<company_id>[0-9a-f-]+)/documents",
    CompanyDocumentViewSet,
    basename="company-documents",
)

urlpatterns = [
    path("", include(router.urls)),
]
