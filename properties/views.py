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
    ReviewSerializer,
)
from .filters import PropertyFilter
from analytics.models import ViewHistory, SearchHistory
from reviews.models import Review


class PropertyViewSet(viewsets.ModelViewSet):
    """
    Main private (for authorized roles) ViewSet.
    Rules (previous logic):
    - Anonymous / renter: now use public endpoint /api/properties/public/
    - Landlord: list — only your listings (all statuses);
    retrieve — any of yours, others' (if reached directly) are not intended for this ViewSet (use public).
    - Create/modify/delete/toggle_status: only landlord-owner.
    In reality, this ViewSet is now focused on landlord operations.
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
        # Let's limit list/retrieve here to authorized landlords only (their own)
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), IsLandlord(), IsOwnerOrReadOnly()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        # list: only our own
        if self.action == "list":
            return Property.objects.select_related("owner").filter(owner=user)
        # retrieve: also only our own (leak fix)
        if self.action == "retrieve":
            return Property.objects.select_related("owner").filter(owner=user)
        # Other actions: return everything, object-permission will limit (only the owner will be able to modify)
        return Property.objects.select_related("owner")


    def perform_create(self, serializer):
        serializer.save()  # owner is set in serializer.create

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
        Bulk upload additional images.
        Format (multipart):
        images: (multiple files) images[0], images[1] ...
        captions: (optional) captions[0], captions[1] ...
        """
        prop = self.get_object()
        self.check_object_permissions(request, prop)
        serializer = PropertyImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        images = serializer.validated_data["images"]
        captions = serializer.validated_data.get("captions", [])

        # limit on total number of images per ad
        total_existing = prop.images.count()
        if total_existing + len(images) > 10:
            return response.Response(
                {"detail": "Превышен общий лимит в 10 изображений для объявления."},
                status=400,
            )

        created = []
        # We define the initial max order
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
        Delete one image.
        Body (JSON or multipart):
        {
          "image_id": <id>
        }
        """
        prop = self.get_object()
        self.check_object_permissions(request, prop)
        image_id = request.data.get("image_id")
        if not image_id:
            return response.Response({"detail": "image_id mandatory."}, status=400)
        try:
            img = prop.images.get(id=image_id)
        except PropertyImage.DoesNotExist:
            return response.Response({"detail": "Image not found."}, status=404)
        img.delete()
        return response.Response(status=204)

    @decorators.action(detail=True, methods=["post"], url_path="reorder-images")
    def reorder_images(self, request, pk=None):
        """
        Reordering images.
        Body: {"order": [image_id1, image_id2, ...]}
        """
        prop = self.get_object()
        self.check_object_permissions(request, prop)
        order_list = request.data.get("order", [])
        if not isinstance(order_list, list) or not order_list:
            return response.Response({"detail": "order must be a non-empty list id."}, status=400)

        images = {img.id: img for img in prop.images.all()}
        next_order = 1
        for image_id in order_list:
            img = images.get(image_id)
            if img:
                img.order = next_order
                img.save(update_fields=["order"])
                next_order += 1
        # any images not included in the list go further
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
        Update the signature of one image.
        Body: {"image_id": <id>, "caption": "текст"}
        """
        prop = self.get_object()
        self.check_object_permissions(request, prop)
        image_id = request.data.get("image_id")
        caption = request.data.get("caption", "")
        if not image_id:
            return response.Response({"detail": "image_id mandatory."}, status=400)
        try:
            img = prop.images.get(id=image_id)
        except PropertyImage.DoesNotExist:
            return response.Response({"detail": "Image not found."}, status=404)
        img.caption = caption
        img.save(update_fields=["caption"])
        return response.Response(PropertyImageSerializer(img, context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"], url_path="set-main-image")
    def set_main_image(self, request, pk=None):
        """
        Installing the main image either from already downloaded additional ones, or by new download.
        Formats:
          1) {"image_id": <id already uploaded>}  -> let's take the file from PropertyImage.image and copy it to main_image.
          2) multipart with main_image field (file).
        """
        prop = self.get_object()
        self.check_object_permissions(request, prop)

        image_id = request.data.get("image_id")
        main_file = request.data.get("main_image")

        if not image_id and not main_file:
            return response.Response({"detail": "Pass image_id or main_image file."}, status=400)

        if image_id and main_file:
            return response.Response({"detail": "Use either image_id or main_image file — not both."},
                                     status=400)

        if image_id:
            try:
                p_img = prop.images.get(id=image_id)
            except PropertyImage.DoesNotExist:
                return response.Response({"detail": "Image not found."}, status=404)
            # Just reassign the link (you can make a copy of the file if necessary))
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
    Public (anonymous) viewing of active listings:
    - GET /api/properties/public/ (list) — ACTIVE only
    - GET /api/properties/public/{id}/ (retrieve) — ACTIVE only
    An authorized landlord can also use this endpoint,
    but will only see active other listings (without access to inactive ones).
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
            # We record search history only for authorized users
            SearchHistory.objects.create(user=request.user, search_query=search_q)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        # Views increment
        Property.objects.filter(pk=obj.pk).update(views_count=F("views_count") + 1)
        if request.user.is_authenticated:
            ViewHistory.objects.create(user=request.user, property=obj)
        return response.Response(self.get_serializer(obj).data)

    @decorators.action(detail=True, methods=["get"], url_path="reviews", permission_classes=[permissions.AllowAny])
    def reviews(self, request, pk=None):
        """
        Public list of reviews for the ad.
        GET /api/properties/public/{id}/reviews/
        """
        prop = self.get_object()  # guarantees ACTIVE
        qs = Review.objects.filter(property=prop).order_by("-created_at")

        page = self.paginate_queryset(qs)
        if page is not None:
            ser = ReviewSerializer(page, many=True)
            return self.get_paginated_response(ser.data)
        return response.Response(ReviewSerializer(qs, many=True).data)

