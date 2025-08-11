from django.db.models import F, Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, decorators, response, status, parsers
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter

from rental_platform.permissions import IsOwnerOrReadOnly, IsLandlord
from .models import Property, PropertyImage
from .serializers import (
    PropertySerializer,
    PropertyImageSerializer,
    PropertyImageUploadSerializer,
)
from .filters import PropertyFilter
from analytics.models import ViewHistory, SearchHistory


class PropertyViewSet(viewsets.ModelViewSet):
    """
    Основной приватный (для авторизованных ролей) ViewSet.
    Правила (предыдущая логика):
      - Аноним / renter: использовать теперь публичный endpoint /api/properties/public/
      - Landlord: list — только свои объявления (все статусы);
                  retrieve — свои любые, чужие (если достигнут напрямую) не предназначены для этого ViewSet (используйте публичный).
      - Создание/изменение/удаление/toggle_status: только landlord-владелец.
    Реально теперь этот ViewSet ориентирован на операции landlord.
    """
    queryset = Property.objects.select_related("owner").all()
    # queryset = Property.objects.select_related("owner")
    serializer_class = PropertySerializer
    filterset_class = PropertyFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "description", "location"]
    ordering_fields = ["price", "created_at", "views_count", "number_of_rooms"]
    ordering = ["-created_at"]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsLandlord()]
        if self.action in [
            "update", "partial_update", "destroy",
            "toggle_status", "upload_images", "delete_image",
            "reorder_images", "update_image_caption", "set_main_image"
        ]:
            return [permissions.IsAuthenticated(), IsLandlord(), IsOwnerOrReadOnly()]
        # Ограничим list/retrieve здесь только авторизованными landlord (их собственные)
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), IsLandlord(), IsOwnerOrReadOnly()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        # list: только свои
        if self.action == "list":
            return Property.objects.select_related("owner").filter(owner=user)
        # retrieve: тоже только свои (исправление утечки)
        if self.action == "retrieve":
            return Property.objects.select_related("owner").filter(owner=user)
        # Остальные действия: вернём все, object-permission ограничит (только владелец сможет модифицировать)
        return Property.objects.select_related("owner")

    # def get_queryset(self):
    #     user = self.request.user
    #     # для list всегда только свои
    #     if self.action == "list":
    #         return self.queryset.filter(owner=user)
    #     # для retrieve тоже ограничиваем своими (чужие — 404, см. твою текущую модель безопасности)
    #     if self.action == "retrieve":
    #         return self.queryset.filter(owner=user)
    #     return self.queryset

    def perform_create(self, serializer):
        serializer.save()  # owner устанавливается в serializer.create

    @decorators.action(detail=True, methods=["post"])
    def toggle_status(self, request, pk=None):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        old_status = obj.status
        obj.status = obj.Status.INACTIVE if obj.status == obj.Status.ACTIVE else obj.Status.ACTIVE
        obj.save(update_fields=["status"])
        if hasattr(obj, "listing"):
            obj.listing.is_active = (obj.status == obj.Status.ACTIVE)
            obj.listing.save(update_fields=["is_active"])
        return response.Response({"old_status": old_status, "new_status": obj.status})

    @decorators.action(detail=True, methods=["post"], url_path="upload-images")
    def upload_images(self, request, pk=None):
        """
        Массовая загрузка дополнительных изображений.
        Формат (multipart):
          images: (многократные файлы) images[0], images[1] ...
          captions: (опционально) captions[0], captions[1] ...
        """
        prop = self.get_object()
        self.check_object_permissions(request, prop)
        serializer = PropertyImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        images = serializer.validated_data["images"]
        captions = serializer.validated_data.get("captions", [])

        # лимит по общему количеству изображений на объявление
        total_existing = prop.images.count()
        if total_existing + len(images) > 10:
            return response.Response(
                {"detail": "Превышен общий лимит в 10 изображений для объявления."},
                status=400,
            )

        created = []
        # Определяем начальный max order
        current_max = prop.images.aggregate(m=models.Max("order")).get("m") or 0
        for idx, img in enumerate(images, start=1):
            caption = captions[idx - 1] if idx - 1 < len(captions) else ""
            pi = PropertyImage.objects.create(
                property=prop,
                image=img,
                caption=caption,
                order=current_max + idx
            )
            created.append(pi)

        return response.Response(
            PropertyImageSerializer(created, many=True, context={"request": request}).data,
            status=201
        )

    @decorators.action(detail=True, methods=["post"], url_path="delete-image")
    def delete_image(self, request, pk=None):
        """
        Удалить одно изображение.
        Тело (JSON или multipart):
        {
          "image_id": <id>
        }
        """
        prop = self.get_object()
        self.check_object_permissions(request, prop)
        image_id = request.data.get("image_id")
        if not image_id:
            return response.Response({"detail": "image_id обязателен."}, status=400)
        try:
            img = prop.images.get(id=image_id)
        except PropertyImage.DoesNotExist:
            return response.Response({"detail": "Изображение не найдено."}, status=404)
        img.delete()
        return response.Response(status=204)

    @decorators.action(detail=True, methods=["post"], url_path="reorder-images")
    def reorder_images(self, request, pk=None):
        """
        Переупорядочивание изображений.
        Тело: {"order": [image_id1, image_id2, ...]}
        """
        prop = self.get_object()
        self.check_object_permissions(request, prop)
        order_list = request.data.get("order", [])
        if not isinstance(order_list, list) or not order_list:
            return response.Response({"detail": "order должен быть непустым списком id."}, status=400)

        images = {img.id: img for img in prop.images.all()}
        next_order = 1
        for image_id in order_list:
            img = images.get(image_id)
            if img:
                img.order = next_order
                img.save(update_fields=["order"])
                next_order += 1
        # любые изображения не попавшие в список — идут далее
        for img_id, img in images.items():
            if img.id not in order_list:
                img.order = next_order
                img.save(update_fields=["order"])
                next_order += 1

        return response.Response(
            PropertyImageSerializer(prop.images.all(), many=True, context={"request": request}).data
        )

    @decorators.action(detail=True, methods=["post"], url_path="update-image-caption")
    def update_image_caption(self, request, pk=None):
        """
        Обновление подписи одного изображения.
        Тело: {"image_id": <id>, "caption": "текст"}
        """
        prop = self.get_object()
        self.check_object_permissions(request, prop)
        image_id = request.data.get("image_id")
        caption = request.data.get("caption", "")
        if not image_id:
            return response.Response({"detail": "image_id обязателен."}, status=400)
        try:
            img = prop.images.get(id=image_id)
        except PropertyImage.DoesNotExist:
            return response.Response({"detail": "Изображение не найдено."}, status=404)
        img.caption = caption
        img.save(update_fields=["caption"])
        return response.Response(PropertyImageSerializer(img, context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"], url_path="set-main-image")
    def set_main_image(self, request, pk=None):
        """
        Установка главной картинки либо из уже загруженных дополнительных,
        либо новой загрузкой.
        Форматы:
          1) {"image_id": <id already uploaded>}  -> возьмём файл из PropertyImage.image и скопируем в main_image.
          2) multipart с полем main_image (файл).
        """
        prop = self.get_object()
        self.check_object_permissions(request, prop)

        image_id = request.data.get("image_id")
        main_file = request.data.get("main_image")

        if not image_id and not main_file:
            return response.Response({"detail": "Передайте image_id или файл main_image."}, status=400)

        if image_id and main_file:
            return response.Response({"detail": "Используйте либо image_id, либо main_image файл — не оба."},
                                     status=400)

        if image_id:
            try:
                p_img = prop.images.get(id=image_id)
            except PropertyImage.DoesNotExist:
                return response.Response({"detail": "Изображение не найдено."}, status=404)
            # Просто переназначаем ссылку (копию файла можно сделать при необходимости)
            prop.main_image = p_img.image
            prop.save(update_fields=["main_image"])
        else:
            # Загрузка нового файла
            prop.main_image = main_file
            prop.save(update_fields=["main_image"])

        return response.Response(
            {"main_image_url": PropertySerializer(prop, context={"request": request}).data["main_image_url"]})


class PublicPropertyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Публичный (анонимный) просмотр активных объявлений:
      - GET /api/properties/public/           (list)  — только ACTIVE
      - GET /api/properties/public/{id}/      (retrieve) — только ACTIVE
    Авторизованный landlord тоже может пользоваться этим endpoint'ом,
    но увидит только активные чужие объявления (без доступа к неактивным).
    """
    serializer_class = PropertySerializer
    permission_classes = [permissions.AllowAny]
    filterset_class = PropertyFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "description", "location"]
    ordering_fields = ["price", "created_at", "views_count"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Property.objects.select_related("owner").filter(status=Property.Status.ACTIVE)
        ordering_param = self.request.query_params.get("ordering", "")
        if "reviews_count" in ordering_param:
            qs = qs.annotate(reviews_count=Count("reviews"))
        return qs

    def list(self, request, *args, **kwargs):
        search_q = request.query_params.get("search")
        if search_q and request.user.is_authenticated:
            # Записываем историю поиска только для авторизованных
            SearchHistory.objects.create(user=request.user, search_query=search_q)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        # Инкремент просмотров
        Property.objects.filter(pk=obj.pk).update(views_count=F("views_count") + 1)
        if request.user.is_authenticated:
            ViewHistory.objects.create(user=request.user, property=obj)
        return response.Response(self.get_serializer(obj).data)


# from django.db.models import F, Count, Q
# from django_filters.rest_framework import DjangoFilterBackend
# from rest_framework import viewsets, permissions, decorators, response, status
# from rest_framework.filters import SearchFilter, OrderingFilter
# from rental_platform.permissions import IsOwnerOrReadOnly, IsLandlord
# from .models import Property
# from .serializers import PropertySerializer
# from .filters import PropertyFilter
# from analytics.models import ViewHistory, SearchHistory
#
# class PropertyViewSet(viewsets.ModelViewSet):
#     queryset = Property.objects.select_related("owner").all()
#     serializer_class = PropertySerializer
#     filterset_class = PropertyFilter
#     filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
#     search_fields = ["title", "description", "location"]
#     ordering_fields = ["price", "created_at", "views_count", "reviews_count"]
#     ordering = ["-created_at"]
#
#     # def get_permissions(self):
#     #     # if self.action in ["create", "update", "partial_update", "destroy", "toggle_status"]:
#     #     #     return [permissions.IsAuthenticated(), IsLandlord(), IsOwnerOrReadOnly()]
#     #     # return [permissions.AllowAny()]
#     #     if self.action == "create":
#     #         return [permissions.IsAuthenticated(), IsLandlord()]
#     #     if self.action in ["update", "partial_update", "destroy", "toggle_status"]:
#     #         return [permissions.IsAuthenticated(), IsLandlord(), IsOwnerOrReadOnly()]
#     #     return [permissions.AllowAny()]
#
#     def get_permissions(self):
#         if self.action == "create":
#             return [permissions.IsAuthenticated(), IsLandlord()]
#         if self.action in ["update", "partial_update", "destroy", "toggle_status"]:
#             return [permissions.IsAuthenticated(), IsLandlord(), IsOwnerOrReadOnly()]
#         # Ограничим list/retrieve здесь только авторизованными landlord (их собственные)
#         if self.action in ["list", "retrieve"]:
#             return [permissions.IsAuthenticated(), IsLandlord()]
#         return [permissions.IsAuthenticated()]
#
#
#     # def get_queryset(self):
#     #     qs = super().get_queryset()
#     #     # Если пользователь запросил сортировку по количеству отзывов — аннотируем
#     #     ordering_param = self.request.query_params.get("ordering", "")
#     #     if "reviews_count" in ordering_param:
#     #         qs = qs.annotate(reviews_count=Count("reviews"))
#     #     return qs
#
#     def get_queryset(self):
#         user = self.request.user
#         action = self.action
#
#         base_qs = Property.objects.select_related("owner")
#
#         # Для list:
#         if action == "list":
#             if user.is_authenticated and getattr(user, "role", None) == "landlord":
#                 # Landlord видит список только своих (все статусы)
#                 return base_qs.filter(owner=user)
#             # Аноним и renter — только ACTIVE
#             qs = base_qs.filter(status=Property.Status.ACTIVE)
#             ordering_param = self.request.query_params.get("ordering", "")
#             if "reviews_count" in ordering_param:
#                 qs = qs.annotate(reviews_count=Count("reviews"))
#             return qs
#
#         # Для retrieve/прочих действий — вернём широкий набор;
#         # object-level логика будет применена в retrieve/toggle_status
#         return base_qs
#
#        # def get_queryset(self):
#     #     qs = super().get_queryset()
#     #     # Только активные по умолчанию для не-владельцев?
#     #     # Оставим все, но можно ограничить при необходимости.
#     #     return qs
#
#     #def list(self, request, *args, **kwargs):
#     #     # Пишем историю поиска, если есть search и пользователь авторизован
#     #     search_query = request.query_params.get("search")
#     #     if search_query and request.user.is_authenticated:
#     #         SearchHistory.objects.create(user=request.user, search_query=search_query)
#     #     return super().list(request, *args, **kwargs)
#
#     def list(self, request, *args, **kwargs):
#         # История поиска: только если юзер аутентифицирован
#         search_q = request.query_params.get("search")
#         if search_q and request.user.is_authenticated:
#             SearchHistory.objects.create(user=request.user, search_query=search_q)
#         return super().list(request, *args, **kwargs)
#
#     def retrieve(self, request, *args, **kwargs):
#         obj = self.get_object()
#         user = request.user
#         role = getattr(user, "role", None)
#
#         # Проверка доступа на чтение:
#         if not user.is_authenticated:
#             # Аноним: только ACTIVE
#             if obj.status != Property.Status.ACTIVE:
#                 return response.Response({"detail": "Объявление недоступно."}, status=404)
#         else:
#             if role == "renter":
#                 if obj.status != Property.Status.ACTIVE:
#                     return response.Response({"detail": "Объявление недоступно."}, status=404)
#             elif role == "landlord":
#                 if obj.owner != user and obj.status != Property.Status.ACTIVE:
#                     # Чужое не-активное — скрываем
#                     return response.Response({"detail": "Объявление недоступно."}, status=404)
#             else:
#                 # Любая другая роль (если появится) — только ACTIVE
#                 if obj.status != Property.Status.ACTIVE:
#                     return response.Response({"detail": "Объявление недоступно."}, status=404)
#
#         # Инкремент просмотров + история (только для аутентифицированных)
#         Property.objects.filter(pk=obj.pk).update(views_count=F("views_count") + 1)
#         if user.is_authenticated:
#             ViewHistory.objects.create(user=user, property=obj)
#
#         return response.Response(self.get_serializer(obj).data)
#
#     def perform_create(self, serializer):
#         serializer.save()  # owner устанавливается в serializer.create
#
#
#     @decorators.action(detail=True, methods=["post"])
#     def toggle_status(self, request, pk=None):
#         obj = self.get_object()
#         self.check_object_permissions(request, obj)  # Проверит владение
#         obj.status = obj.Status.INACTIVE if obj.status == obj.Status.ACTIVE else obj.Status.ACTIVE
#         obj.save(update_fields=["status"])
#         if hasattr(obj, "listing"):
#             obj.listing.is_active = (obj.status == obj.Status.ACTIVE)
#             obj.listing.save(update_fields=["is_active"])
#         return response.Response({"status": obj.status})