from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"follows", views.FollowViewSet, basename="follow")

# Nested routes for shop followers
shop_followers_router = DefaultRouter()
shop_followers_router.register(
    r"followers", views.ShopFollowersViewSet, basename="shop-followers"
)

app_name = "followapp"

urlpatterns = [
    path("", include(router.urls)),
    path("shops/<uuid:shop_id>/", include(shop_followers_router.urls)),
]
