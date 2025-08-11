from datetime import date
import logging
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, decorators, response, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from rental_platform.permissions import IsRenter , IsLandlord
from .models import Booking, Message
from .serializers import BookingSerializer, MessageSerializer
from .filters import BookingFilter

# Для available_properties
from properties.models import Property
from properties.serializers import PropertySerializer
from properties.filters import PropertyFilter  # используем тот же фильтр что и в объявлениях

logger = logging.getLogger(__name__)


class BookingViewSet(viewsets.ModelViewSet):
    """
        Booking API.

        Правила доступа:
          - create (POST /api/bookings/):
              только renter (арендатор).
          - list (GET /api/bookings/):
              renter: только свои бронирования.
              landlord: бронирования по его объявлениям.
          - retrieve (GET /api/bookings/{id}/):
              renter: своё бронирование.
              landlord: бронирование по его объявлению.
          - cancel (POST /api/bookings/{id}/cancel/):
              только renter владелец и только до start_date (см. Booking.can_cancel()).
          - confirm / reject:
              только landlord владелец соответствующего Property и только для PENDING.
          - messages (GET/POST):
              обе стороны (renter или landlord-владелец Property).
          - available_properties (GET /api/bookings/available_properties/):
              публичный вспомогательный endpoint для получения списка активных Property,
              которые можно забронировать (с фильтрами, поиском, сортировкой, пагинацией).
              Доступен анонимно и авторизованно (если пользователь авторизован — исключаются его собственные объекты).

        Фильтрация / поиск / сортировка для бронирований:
          - Фильтры: см. BookingFilter (status, property_id, renter_id, диапазоны дат).
          - Поиск (search=): по полям связанного Property (title, location).
          - Сортировка (ordering=): start_date, end_date, created_at, status (пример: ?ordering=-start_date).
        """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Booking.objects.select_related("property", "property__owner", "user")

    # Поддержка фильтрации / поиска / сортировки для бронирований
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = BookingFilter
    search_fields = ["property__title", "property__location"]
    ordering_fields = ["start_date", "end_date", "created_at", "status"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsRenter()]
        # available_properties должен быть доступен всем (аноним тоже)
        if self.action == "available_properties":
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        """
        Возвращает queryset в зависимости от роли и действия.
        Фильтры/поиск/сортировка применятся поверх (через filter_backends) для list.
        """
        user = self.request.user
        role = getattr(user, "role", None)

        # qs = Booking.objects.select_related("property", "property__owner", "user")
        # Для list применим ограничение
        if self.action == "list":
            if role == "renter":
                return self.queryset.filter(user=user)
            if role == "landlord":
                return self.queryset.filter(property__owner=user)
            return self.queryset.none()

        # Для retrieve вернём шире — потом проверим в retrieve()
        if self.action == "retrieve":
            return self.queryset

        # Для остальных (confirm/reject/cancel/messages) используем полный queryset
        return self.queryset

    def list(self, request, *args, **kwargs):
        role = getattr(request.user, "role", None)
        if role not in ("renter", "landlord"):
            return response.Response({"detail": "Недоступно для вашей роли."}, status=403)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        booking = self.get_object()
        role = getattr(request.user, "role", None)
        if role == "renter":
            if booking.user_id != request.user.id:
                return response.Response({"detail": "Нет доступа."}, status=403)
        elif role == "landlord":
            if booking.property.owner_id != request.user.id:
                return response.Response({"detail": "Нет доступа."}, status=403)
        else:
            return response.Response({"detail": "Нет доступа."}, status=403)
        return response.Response(self.get_serializer(booking).data)

    # Важно: не передаём user здесь — он уже устанавливается в BookingSerializer.create
    def perform_create(self, serializer):
        booking = serializer.save()
        logger.info(
            "Booking created id=%s property=%s renter=%s start=%s end=%s status=%s",
            booking.id,
            booking.property_id,
            booking.user_id,
            booking.start_date,
            booking.end_date,
            booking.status,
        )

    def _get_booking_unrestricted(self, pk: int) -> Booking:
        # Получаем объект без фильтрации по текущему пользователю,
        # чтобы корректно вернуть 403 для посторонних (а не 404).
        return Booking.objects.select_related("property", "property__owner", "user").get(pk=pk)

    @decorators.action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self._get_booking_unrestricted(pk)
        if getattr(request.user, "role", None) != "renter":
            logger.warning(
                "Cancel forbidden booking_id=%s by user_id=%s (not renter)",
                booking.id,
                getattr(request.user, "id", None),
            )
            return response.Response({"detail": "Отмена доступна только арендатору."}, status=403)
        if booking.user_id != request.user.id:
            return response.Response({"detail": "Можно отменить только своё бронирование."}, status=403)
        if not booking.can_cancel(date.today()):
            logger.info(
                "Cancel not allowed (deadline passed) booking_id=%s renter_id=%s cancel_until=%s today=%s",
                booking.id,
                request.user.id,
                getattr(booking, "cancel_until", None),
                date.today(),
            )
            return response.Response({"detail": "Отмена невозможна."}, status=400)
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        logger.info("Booking cancelled booking_id=%s renter_id=%s", booking.id, request.user.id)
        return response.Response({"status": booking.status})

    @decorators.action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        booking = self._get_booking_unrestricted(pk)
        if getattr(request.user, "role", None) != "landlord":
            logger.warning(
                "Confirm forbidden booking_id=%s by user_id=%s (not owner)",
                booking.id,
                getattr(request.user, "id", None),
            )
            return response.Response({"detail": "Только владелец может подтверждать."}, status=403)
        if booking.property.owner_id != request.user.id:
            return response.Response({"detail": "Нет прав на подтверждение."}, status=403)
        if booking.status != Booking.Status.PENDING:
            logger.info(
                "Confirm not allowed for status booking_id=%s status=%s",
                booking.id,
                booking.status,
            )
            return response.Response({"detail": "Можно подтверждать только ожидающие заявки."}, status=400)

        # Проверка пересечений только с уже CONFIRMED
        overlap = Booking.objects.filter(
            property=booking.property,
            status=Booking.Status.CONFIRMED
        ).filter(
            Q(start_date__lt=booking.end_date) & Q(end_date__gt=booking.start_date)
        ).exclude(pk=booking.pk).exists()
        if overlap:
            return response.Response({"detail": "Даты уже заняты."}, status=400)

        booking.status = Booking.Status.CONFIRMED
        booking.confirmed_at = timezone.now()
        booking.save(update_fields=["status", "confirmed_at"])
        logger.info(
                "Booking confirmed booking_id=%s owner_id=%s renter_id=%s",
                booking.id,
                request.user.id,
                booking.user_id,
        )
        return response.Response({"status": booking.status})

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        booking = self._get_booking_unrestricted(pk)
        if getattr(request.user, "role", None) != "landlord":
            logger.warning(
                "Reject forbidden booking_id=%s by user_id=%s (not owner)",
                booking.id,
                getattr(request.user, "id", None),
            )
            return response.Response({"detail": "Только владелец может отклонять."}, status=403)
        if booking.property.owner_id != request.user.id:
            return response.Response({"detail": "Нет прав на отклонение."}, status=403)
        if booking.status != Booking.Status.PENDING:
            logger.info(
                "Reject not allowed for status booking_id=%s status=%s",
                booking.id,
                booking.status,
            )
            return response.Response({"detail": "Можно отклонять только ожидающие заявки."}, status=400)
        booking.status = Booking.Status.REJECTED
        booking.save(update_fields=["status"])
        logger.info(
            "Booking rejected booking_id=%s owner_id=%s renter_id=%s",
            booking.id,
            request.user.id,
            booking.user_id,
        )
        return response.Response({"status": booking.status})

    @decorators.action(detail=True, methods=["get", "post"])
    def messages(self, request, pk=None):
        booking = self._get_booking_unrestricted(pk)
        user = request.user
        # Проверка участника диалога
        if user != booking.user and user != booking.property.owner:
            logger.warning(
                "Messages access forbidden booking_id=%s by user_id=%s",
                booking.id,
                getattr(user, "id", None),
            )
            return response.Response({"detail": "Нет доступа к переписке по этому бронированию."}, status=403)

        if request.method.lower() == "get":
            msgs = booking.messages.select_related("sender", "receiver").all()
            logger.debug(
                "Messages listed booking_id=%s requester_id=%s count=%s",
                booking.id,
                user.id,
                msgs.count(),
            )
            return response.Response(MessageSerializer(msgs, many=True).data)

        # POST: создать сообщение
        text = request.data.get("text", "").strip()
        if not text:
            return response.Response({"detail": "text обязателен."}, status=400)
        receiver = booking.property.owner if user == booking.user else booking.user
        msg = Message.objects.create(booking=booking, sender=user, receiver=receiver, text=text)
        logger.info(
            "Message created message_id=%s booking_id=%s sender_id=%s receiver_id=%s text_len=%s",
            msg.id,
            booking.id,
            user.id,
            receiver.id,
            len(text),
        )
        return response.Response(MessageSerializer(msg).data, status=201)

    @decorators.action(detail=False, methods=["get"])
    def available_properties(self, request):
        """
        Список активных объявлений, доступных для бронирования.
        Поддерживает те же query params, что и PropertyFilter (price_min, price_max, rooms_min, rooms_max,
        location, property_type, status — но статус будет принудительно 'active').
        Дополнительно:
          - search=<строка>  (по title, description, location)
          - ordering=<поле>  (price, -price, created_at, -created_at, views_count, -views_count)

        Исключает объявления пользователя, если он авторизован (чтобы не бронировать своё).
        """
        qs = Property.objects.filter(status=Property.Status.ACTIVE)

        # Исключить собственные, если авторизован
        if request.user.is_authenticated:
            qs = qs.exclude(owner=request.user)

        # Применяем PropertyFilter
        filterset = PropertyFilter(request.query_params, queryset=qs)
        if not filterset.is_valid():
            return response.Response(filterset.errors, status=400)
        qs = filterset.qs

        # Поиск
        search_query = request.query_params.get("search")
        if search_query:
            sq = search_query.strip()
            if sq:
                qs = qs.filter(
                    Q(title__icontains=sq)
                    | Q(description__icontains=sq)
                    | Q(location__icontains=sq)
                )

        # Сортировка
        ordering_param = request.query_params.get("ordering", "")
        allowed_ordering = {"price", "-price", "created_at", "-created_at", "views_count", "-views_count"}
        if ordering_param in allowed_ordering:
            qs = qs.order_by(ordering_param)

        page = self.paginate_queryset(qs)
        if page is not None:
            ser = PropertySerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(ser.data)

        ser = PropertySerializer(qs, many=True, context={"request": request})
        return response.Response(ser.data)

    # Список только pending бронирований для landlord — раскомментируйте при необходимости
    # @decorators.action(detail=False, methods=["get"])
    # def pending_for_landlord(self, request):
    #     if getattr(request.user, "role", None) != "landlord":
    #         return response.Response({"detail": "Недоступно."}, status=403)
    #     qs = Booking.objects.select_related("property", "user").filter(
    #         property__owner=request.user,
    #         status=Booking.Status.PENDING
    #     )
    #     serializer = self.get_serializer(qs, many=True)
    #     return response.Response(serializer.data)

# from datetime import date
# from rest_framework import viewsets, permissions, decorators, response, status, views
# from rental_platform.permissions import IsRenter
# from .models import Booking, Message
# from .serializers import BookingSerializer, MessageSerializer
# import logging
# from rest_framework.response import Response
#
# logger = logging.getLogger(__name__)
#
# class BookingViewSet(viewsets.ModelViewSet):
#     serializer_class = BookingSerializer
#     permission_classes = [permissions.IsAuthenticated]
#
#     def get_queryset(self):
#         user = self.request.user
#         qs = Booking.objects.select_related("property", "property__owner", "user")
#         role = getattr(user, "role", None)
#         if role == "landlord":
#             return qs.filter(property__owner=user)
#         return qs.filter(user=user)
#
#     def get_permissions(self):
#         if self.action == "create":
#             return [permissions.IsAuthenticated(), IsRenter()]
#         return super().get_permissions()
#
#     @decorators.action(detail=True, methods=["post"])
#     def cancel(self, request, pk=None):
#         booking = self.get_object()
#         if booking.user != request.user:
#             return response.Response({"detail": "Можно отменять только свои бронирования."}, status=403)
#         if not booking.can_cancel(date.today()):
#             return response.Response({"detail": "Отмена невозможна."}, status=400)
#         booking.status = Booking.Status.CANCELLED
#         booking.save(update_fields=["status"])
#         return response.Response({"status": booking.status})
#
#     @decorators.action(detail=True, methods=["post"])
#     def confirm(self, request, pk=None):
#         booking = self.get_object()
#         if booking.property.owner != request.user:
#             return response.Response({"detail": "Только владелец может подтверждать."}, status=403)
#         if booking.status != Booking.Status.PENDING:
#             return response.Response({"detail": "Можно подтверждать только ожидающие заявки."}, status=400)
#         booking.status = Booking.Status.CONFIRMED
#         booking.save(update_fields=["status"])
#         return response.Response({"status": booking.status})
#
#     @decorators.action(detail=True, methods=["post"])
#     def reject(self, request, pk=None):
#         booking = self.get_object()
#         if booking.property.owner != request.user:
#             return response.Response({"detail": "Только владелец может отклонять."}, status=403)
#         if booking.status != Booking.Status.PENDING:
#             return response.Response({"detail": "Можно отклонять только ожидающие заявки."}, status=400)
#         booking.status = Booking.Status.REJECTED
#         booking.save(update_fields=["status"])
#         return response.Response({"status": booking.status})
#
#     @decorators.action(detail=True, methods=["get", "post"])
#     def messages(self, request, pk=None):
#         booking = self.get_object()
#         user = request.user
#         # Проверка участника диалога
#         if user != booking.user and user != booking.property.owner:
#             return response.Response({"detail": "Нет доступа к переписке по этому бронированию."}, status=403)
#
#         if request.method.lower() == "get":
#             msgs = booking.messages.select_related("sender", "receiver").all()
#             return response.Response(MessageSerializer(msgs, many=True).data)
#
#         # POST: создать сообщение
#         text = request.data.get("text", "").strip()
#         if not text:
#             return response.Response({"detail": "text обязателен."}, status=400)
#         receiver = booking.property.owner if user == booking.user else booking.user
#         msg = Message.objects.create(booking=booking, sender=user, receiver=receiver, text=text)
#         return response.Response(MessageSerializer(msg).data, status=201)