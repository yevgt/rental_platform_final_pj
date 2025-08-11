from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PropertyViewSet, PublicPropertyViewSet
from .root_views import properties_root

# Private (landlord) router
private_router = DefaultRouter()
private_router.register(r"", PropertyViewSet, basename="property")

# Public read-only router
public_router = DefaultRouter()
public_router.register(r"", PublicPropertyViewSet, basename="public-property")

# Алиас на создание объявления:
# GET  /api/properties/create/  -> list (покажет список и HTML-форму, если залогинен через сессию)
# POST /api/properties/create/  -> create (создание объявления)
property_list_create_alias = PropertyViewSet.as_view({"get": "list", "post": "create"})

urlpatterns = [
    path("create/", property_list_create_alias, name="property-create"),
    # Корневой список ссылок для /api/properties/
    path("", properties_root, name="properties-root"),
    # Публичный каталог
    path("public/", include(public_router.urls)),
    # Приватные CRUD/доп. actions
    path("", include(private_router.urls)),
]

# from rest_framework.routers import DefaultRouter
# from django.urls import path, include
# from .views import PropertyViewSet, PublicPropertyViewSet
#
# private_router = DefaultRouter()
# private_router.register(r"", PropertyViewSet, basename="property")
#
# public_router = DefaultRouter()
# public_router.register(r"", PublicPropertyViewSet, basename="public-property")
#
# urlpatterns = [
#     # Публичный endpoint: /api/properties/public/
#     path("public/", include(public_router.urls)),
#     # Приватный (для landlord CRUD): /api/properties/
#     path("", include(private_router.urls)),
# ]

# from rest_framework.routers import DefaultRouter
# from django.urls import path, include
# from .views import PropertyViewSet
#
# router = DefaultRouter()
# router.register("", PropertyViewSet, basename="property")
#
# urlpatterns = [
#     path("", include(router.urls)),
# ]