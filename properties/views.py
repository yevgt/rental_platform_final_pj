from django.db.models import F, Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, decorators, response, status
from rest_framework.filters import SearchFilter, OrderingFilter
from rental_platform.permissions import IsOwnerOrReadOnly, IsLandlord
from .models import Property
from .serializers import PropertySerializer
from .filters import PropertyFilter
from analytics.models import ViewHistory, SearchHistory

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.select_related("owner").all()
    serializer_class = PropertySerializer
    filterset_class = PropertyFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "description", "location"]
    ordering_fields = ["price", "created_at", "views_count", "reviews_count"]
    ordering = ["-created_at"]

    def get_permissions(self):
        # if self.action in ["create", "update", "partial_update", "destroy", "toggle_status"]:
        #     return [permissions.IsAuthenticated(), IsLandlord(), IsOwnerOrReadOnly()]
        # return [permissions.AllowAny()]
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsLandlord()]
        if self.action in ["update", "partial_update", "destroy", "toggle_status"]:
            return [permissions.IsAuthenticated(), IsLandlord(), IsOwnerOrReadOnly()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        # Если пользователь запросил сортировку по количеству отзывов — аннотируем
        ordering_param = self.request.query_params.get("ordering", "")
        if "reviews_count" in ordering_param:
            qs = qs.annotate(reviews_count=Count("reviews"))
        return qs

    def perform_create(self, serializer):
        # return serializer.save()
        serializer.save()  # owner задаётся в PropertySerializer.create

    # def get_queryset(self):
    #     qs = super().get_queryset()
    #     # Только активные по умолчанию для не-владельцев?
    #     # Оставим все, но можно ограничить при необходимости.
    #     return qs

    #def list(self, request, *args, **kwargs):
    #     # Пишем историю поиска, если есть search и пользователь авторизован
    #     search_query = request.query_params.get("search")
    #     if search_query and request.user.is_authenticated:
    #         SearchHistory.objects.create(user=request.user, search_query=search_query)
    #     return super().list(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
    # История поиска (сохраняем только "search" — фильтры не учитываем)
        q = request.query_params.get("search")
        if q and request.user.is_authenticated:
            SearchHistory.objects.create(user=request.user, search_query=q)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        # Инкремент просмотров (атомарно) + запись истории
        Property.objects.filter(pk=obj.pk).update(views_count=F("views_count") + 1)
        if request.user.is_authenticated:
            ViewHistory.objects.create(user=request.user, property=obj)
        return response.Response(self.get_serializer(obj).data)

    @decorators.action(detail=True, methods=["post"]) #, permission_classes=[permissions.IsAuthenticated, IsLandlord, IsOwnerOrReadOnly])
    def toggle_status(self, request, pk=None):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        obj.status = obj.Status.INACTIVE if obj.status == obj.Status.ACTIVE else obj.Status.ACTIVE
        obj.save(update_fields=["status"])
        if hasattr(obj, "listing"):
            obj.listing.is_active = (obj.status == obj.Status.ACTIVE)
            obj.listing.save(update_fields=["is_active"])
        return response.Response({"status": obj.status})