from django.db.models import F
from rest_framework import viewsets, permissions, decorators, response, status
from rental_platform.permissions import IsOwnerOrReadOnly, IsLandlord
from .models import Property
from .serializers import PropertySerializer
from .filters import PropertyFilter
from analytics.models import ViewHistory, SearchHistory

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.select_related("owner").all()
    serializer_class = PropertySerializer
    filterset_class = PropertyFilter
    search_fields = ["title", "description"]
    ordering_fields = ["price", "created_at", "views_count"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "toggle_status"]:
            return [permissions.IsAuthenticated(), IsLandlord(), IsOwnerOrReadOnly()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        return serializer.save()

    def get_queryset(self):
        qs = super().get_queryset()
        # Только активные по умолчанию для не-владельцев?
        # Оставим все, но можно ограничить при необходимости.
        return qs

    def list(self, request, *args, **kwargs):
        # Пишем историю поиска, если есть search и пользователь авторизован
        search_query = request.query_params.get("search")
        if search_query and request.user.is_authenticated:
            SearchHistory.objects.create(user=request.user, search_query=search_query)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        # инкремент просмотров и запись истории
        Property.objects.filter(pk=obj.pk).update(views_count=F("views_count") + 1)
        if request.user.is_authenticated:
            ViewHistory.objects.create(user=request.user, property=obj)
        serializer = self.get_serializer(obj)
        return response.Response(serializer.data)

    @decorators.action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsLandlord, IsOwnerOrReadOnly])
    def toggle_status(self, request, pk=None):
        obj = self.get_object()
        obj.status = obj.Status.INACTIVE if obj.status == obj.Status.ACTIVE else obj.Status.ACTIVE
        obj.save(update_fields=["status"])
        if hasattr(obj, "listing"):
            obj.listing.is_active = (obj.status == obj.Status.ACTIVE)
            obj.listing.save(update_fields=["is_active"])
        return response.Response({"status": obj.status})