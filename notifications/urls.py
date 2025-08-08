from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import NotificationViewSet

router = DefaultRouter()
router.register("", NotificationViewSet, basename="notification")

urlpatterns = [
    path("", include(router.urls)),
]