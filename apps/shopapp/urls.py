from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"shops", views.ShopViewSet, basename="shop")
router.register(r"hours", views.ShopHoursViewSet, basename="shop-hours")
router.register(r"followers", views.FollowerViewSet, basename="shop-followers")
router.register(r"locations", views.ShopLocationViewSet, basename="shop-location")
router.register(r"settings", views.ShopSettingsViewSet, basename="shop-settings")
router.register(
    r"verifications", views.ShopVerificationViewSet, basename="shop-verification"
)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "shops/<uuid:shop_id>/hours/",
        views.ShopHoursListView.as_view(),
        name="shop-hours-list",
    ),
    path(
        "shops/<uuid:shop_id>/followers/",
        views.ShopFollowersListView.as_view(),
        name="shop-followers-list",
    ),
    path(
        "shops/<uuid:shop_id>/verify/",
        views.VerifyShopView.as_view(),
        name="shop-verify",
    ),
    path(
        "shops/<uuid:shop_id>/follow/",
        views.FollowShopView.as_view(),
        name="shop-follow",
    ),
    path(
        "shops/<uuid:shop_id>/unfollow/",
        views.UnfollowShopView.as_view(),
        name="shop-unfollow",
    ),
    path("shops/nearby/", views.NearbyShopsView.as_view(), name="nearby-shops"),
    path("shops/top/", views.TopShopsView.as_view(), name="top-shops"),
    path("shops/followed/", views.FollowedShopsView.as_view(), name="followed-shops"),
]
