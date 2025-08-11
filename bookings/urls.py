from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BookingViewSet
from .root_views import bookings_root

router = DefaultRouter()
router.register(r"", BookingViewSet, basename="booking")

# Алиас на создание бронирования: POST /api/bookings/create/
booking_create = BookingViewSet.as_view({"post": "create"})
booking_list = BookingViewSet.as_view({"get": "list"})

urlpatterns = [
    path("create/", booking_create, name="booking-create"),
    path("list/", booking_list, name="booking-list-alias"),
    # Корневой список ссылок для /api/bookings/
    path("", bookings_root, name="bookings-root"),
    path("", include(router.urls)),
]

# from rest_framework.routers import DefaultRouter
# from django.urls import path, include
# from .views import BookingViewSet
#
# router = DefaultRouter()
# router.register("", BookingViewSet, basename="booking")
#
# urlpatterns = [
#     path("", include(router.urls)),
# ]