from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.storiesapp.views import StoryViewCreateAPIView, StoryViewSet

router = DefaultRouter()
router.register(r"stories", StoryViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("story-views/", StoryViewCreateAPIView.as_view(), name="story-view-create"),
]
