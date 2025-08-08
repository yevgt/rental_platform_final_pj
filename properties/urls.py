from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import PropertyViewSet

router = DefaultRouter()
router.register("", PropertyViewSet, basename="property")

urlpatterns = [
    path("", include(router.urls)),
]