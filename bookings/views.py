from datetime import date
import logging

from rest_framework import viewsets, permissions, decorators, response
from rest_framework.response import Response

from rental_platform.permissions import IsRenter
from .models import Booking, Message
from .serializers import BookingSerializer, MessageSerializer

logger = logging.getLogger(__name__)


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Booking.objects.select_related("property", "property__owner", "user")
        role = getattr(user, "role", None)
        if role == "landlord":
            logger.debug("Bookings queryset for landlord user_id=%s", getattr(user, "id", None))
            return qs.filter(property__owner=user)
        logger.debug("Bookings queryset for renter user_id=%s", getattr(user, "id", None))
        return qs.filter(user=user)

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsRenter()]
        return super().get_permissions()

    # Важно: не передаём user здесь — он уже устанавливается в BookingSerializer.create
    def perform_create(self, serializer):
        booking = serializer.save()
        logger.info(
            "Booking created booking_id=%s property_id=%s renter_id=%s start=%s end=%s status=%s",
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
        if booking.user != request.user:
            logger.warning(
                "Cancel forbidden booking_id=%s by user_id=%s (not renter)",
                booking.id,
                getattr(request.user, "id", None),
            )
            return response.Response({"detail": "Можно отменять только свои бронирования."}, status=403)
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
        if booking.property.owner != request.user:
            logger.warning(
                "Confirm forbidden booking_id=%s by user_id=%s (not owner)",
                booking.id,
                getattr(request.user, "id", None),
            )
            return response.Response({"detail": "Только владелец может подтверждать."}, status=403)
        if booking.status != Booking.Status.PENDING:
            logger.info(
                "Confirm not allowed for status booking_id=%s status=%s",
                booking.id,
                booking.status,
            )
            return response.Response({"detail": "Можно подтверждать только ожидающие заявки."}, status=400)
        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=["status"])
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
        if booking.property.owner != request.user:
            logger.warning(
                "Reject forbidden booking_id=%s by user_id=%s (not owner)",
                booking.id,
                getattr(request.user, "id", None),
            )
            return response.Response({"detail": "Только владелец может отклонять."}, status=403)
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