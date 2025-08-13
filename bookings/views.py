from datetime import date
import logging
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, decorators, response, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

from rental_platform.permissions import IsRenter , IsLandlord
from .models import Booking, Message
from .serializers import BookingSerializer, MessageSerializer
from .filters import BookingFilter

# Для available_properties
from properties.models import Property
from properties.serializers import PropertySerializer, ReviewSerializer
from properties.filters import PropertyFilter  # we use the same filter as in the ads
from reviews.models import Review
from notifications.models import Notification


logger = logging.getLogger(__name__)


class BookingViewSet(viewsets.ModelViewSet):
    """
        Booking API.

        Access rules:
        - create (POST /api/bookings/):
        renter only.
        - list (GET /api/bookings/):
        renter: only his own bookings.
        landlord: bookings for his listings.
        - retrieve (GET /api/bookings/{id}/):
        renter: his own booking.
        landlord: booking for his listing.
        - cancel (POST /api/bookings/{id}/cancel/):
        only renter owner and only until start_date (see Booking.can_cancel()).
        - confirm / reject:
        only landlord owner of the corresponding Property and only for PENDING.
        - messages (GET/POST):
        both parties (renter or landlord-owner of the Property).
        -available_properties (GET /api/bookings/available_properties/):
        public helper endpoint for getting the list of active Properties that can be booked (with filters, search, sorting, pagination).
        Available anonymously and authorized (if the user is authorized, their own objects are excluded).

        Filtering / searching / sorting for bookings:
        - Filters: see BookingFilter (status, property_id, renter_id, date ranges).
        - Search (search=): by fields of the associated Property (title, location).
        - Ordering (ordering=): start_date, end_date, created_at, status (example: ?ordering=-start_date).
        """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Booking.objects.select_related("property", "property__owner", "user")
    lookup_value_regex = r"\d+"  # accept only numeric ids

    # Support filtering/searching/sorting for bookings
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = BookingFilter
    search_fields = ["property__title", "property__location"]
    ordering_fields = ["start_date", "end_date", "created_at", "status"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsRenter()]
        # available_properties should be accessible to everyone (anonymous too)
        if self.action == "available_properties":
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        """
        Returns a queryset based on role and action.
        Filters/searching/sorting are applied on top (via filter_backends) of list.
        """
        user = self.request.user
        role = getattr(user, "role", None)

        # qs = Booking.objects.select_related("property", "property__owner", "user")
        # For list, the restriction applies
        if self.action == "list":
            if role == "renter":
                return self.queryset.filter(user=user)
            if role == "landlord":
                return self.queryset.filter(property__owner=user)
            return self.queryset.none()

        # For retrieve we will return wider - then we will check in retrieve()
        if self.action == "retrieve":
            return self.queryset

        # For the rest (confirm/reject/cancel/messages) use the full queryset
        return self.queryset

    def list(self, request, *args, **kwargs):
        role = getattr(request.user, "role", None)
        if role not in ("renter", "landlord"):
            return response.Response({"detail": "Not available for your role."}, status=403)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        booking = self.get_object()
        role = getattr(request.user, "role", None)
        if role == "renter":
            if booking.user_id != request.user.id:
                return response.Response({"detail": "No access."}, status=403)
        elif role == "landlord":
            if booking.property.owner_id != request.user.id:
                return response.Response({"detail": "No access."}, status=403)
        else:
            return response.Response({"detail": "No access."}, status=403)
        return response.Response(self.get_serializer(booking).data)

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
        # We get the object without filtering by the current user
        return Booking.objects.select_related("property", "property__owner", "user").get(pk=pk)

    def _get_booking_unrestricted(self, pk: int) -> Booking:
        """
        We get Booking without filtering by the current user.
        If not found, we return the correct 404 instead of 500.
        """
        try:
            return Booking.objects.select_related("property", "property__owner", "user").get(pk=pk)
        except Booking.DoesNotExist:
            raise NotFound(detail="Reservation not found.")

    @decorators.action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self._get_booking_unrestricted(pk)
        if getattr(request.user, "role", None) != "renter":
            logger.warning(
                "Cancel forbidden booking_id=%s by user_id=%s (not renter)",
                booking.id,
                getattr(request.user, "id", None),
            )
            return response.Response({"detail": "Cancellation is only available to the tenant."}, status=403)
        if booking.user_id != request.user.id:
            return response.Response({"detail": "You can only cancel your own booking.."}, status=403)
        if not booking.can_cancel(date.today()):
            logger.info(
                "Cancel not allowed (deadline passed) booking_id=%s renter_id=%s cancel_until=%s today=%s",
                booking.id,
                request.user.id,
                getattr(booking, "cancel_until", None),
                date.today(),
            )
            return response.Response({"detail": "Cancellation is not possible."}, status=400)
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
            return response.Response({"detail": "Only the owner can confirm."}, status=403)
        if booking.property.owner_id != request.user.id:
            return response.Response({"detail": "No rights to confirm."}, status=403)
        if booking.status != Booking.Status.PENDING:
            logger.info(
                "Confirm not allowed for status booking_id=%s status=%s",
                booking.id,
                booking.status,
            )
            return response.Response({"detail": "Only pending applications can be confirmed."}, status=400)

        # Checking intersections only with already CONFIRMED
        overlap = Booking.objects.filter(
            property=booking.property,
            status=Booking.Status.CONFIRMED
        ).filter(
            Q(start_date__lt=booking.end_date) & Q(end_date__gt=booking.start_date)
        ).exclude(pk=booking.pk).exists()
        if overlap:
            return response.Response({"detail": "The dates are already taken."}, status=400)

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
            return response.Response({"detail": "Only the owner can reject."}, status=403)
        if booking.property.owner_id != request.user.id:
            return response.Response({"detail": "No right to reject."}, status=403)
        if booking.status != Booking.Status.PENDING:
            logger.info(
                "Reject not allowed for status booking_id=%s status=%s",
                booking.id,
                booking.status,
            )
            return response.Response({"detail": "Only pending applications can be rejected.."}, status=400)
        booking.status = Booking.Status.REJECTED
        booking.save(update_fields=["status"])
        logger.info(
            "Booking rejected booking_id=%s owner_id=%s renter_id=%s",
            booking.id,
            request.user.id,
            booking.user_id,
        )
        return response.Response({"status": booking.status})

    @decorators.action(detail=True, methods=["get", "post"], serializer_class=MessageSerializer)
    def messages(self, request, pk=None):
        booking = self._get_booking_unrestricted(pk)
        user = request.user
        # We allow correspondence only to members
        if user != booking.user and user != booking.property.owner:
            logger.warning(
                "Messages access forbidden booking_id=%s by user_id=%s",
                booking.id,
                getattr(user, "id", None),
            )
            return response.Response({"detail": "No access to correspondence for this booking."}, status=403)

        method = request.method.lower()

        if method == "get":
            # Viewing history is available to participants regardless of their booking status.
            msgs = booking.messages.select_related("sender", "receiver").all()
            logger.debug(
                "Messages listed booking_id=%s requester_id=%s count=%s",
                booking.id,
                user.id,
                msgs.count(),
            )
            return response.Response(MessageSerializer(msgs, many=True).data)

        # We only allow correspondence when the booking is confirmed or completed.
        allowed_statuses = {Booking.Status.PENDING, Booking.Status.CONFIRMED}
        if booking.status not in allowed_statuses:
            return response.Response(
                {"detail": "Sending messages is only available when pending "
                           "or confirmed reservation (PENDING or CONFIRMED)."},
                status=400,
            )


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
        text = str(request.data.get("text", "")).strip()
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

        # Create a notification to the recipient
        try:
            Notification.objects.create(
                user=receiver,
                type=Notification.Types.MESSAGE_NEW,
                message=f"New message on booking #{booking.id} от {getattr(user, 'email', user.id)}",
                data={
                    "booking_id": booking.id,
                    "property_id": booking.property_id,
                    "sender_id": user.id,
                    "receiver_id": receiver.id,
                },
            )
        except Exception as e:
            logger.warning("Failed to create message notification: booking_id=%s err=%s", booking.id, e)

        return response.Response(MessageSerializer(msg).data, status=201)

    @decorators.action(detail=False, methods=["get"])
    def available_properties(self, request):
        """
        List of active listings available for booking.
        Supports the same query params as PropertyFilter (price_min, price_max, rooms_min, rooms_max,
        location, property_type, status - but the status will be forced to 'active').
        Additionally:
        - search=<string> (by title, description, location)
        - ordering=<field> (price, -price, created_at, -created_at, views_count, -views_count)

        Excludes the user's ads if he is logged in (so as not to book his own).
        """
        qs = Property.objects.filter(status=Property.Status.ACTIVE)

        # Exclude own if logged in
        if request.user.is_authenticated:
            qs = qs.exclude(owner=request.user)

        # Applying PropertyFilter
        filterset = PropertyFilter(request.query_params, queryset=qs)
        if not filterset.is_valid():
            return response.Response(filterset.errors, status=400)
        qs = filterset.qs

        # Search
        search_query = request.query_params.get("search")
        if search_query:
            sq = search_query.strip()
            if sq:
                qs = qs.filter(
                    Q(title__icontains=sq)
                    | Q(description__icontains=sq)
                    | Q(location__icontains=sq)
                )

        # Sorting
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

    @decorators.action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """
        Create a review for a completed booking.
        Conditions:
        - requester role renter
        - also the owner of the booking
        - booking.status == COMPLETED
        - no review left yet (one review per booking)
        Body: {"rating": 1..5, "text": "..."}
        """
        booking = self._get_booking_unrestricted(pk)

        if getattr(request.user, "role", None) != "renter":
            return response.Response({"detail": "Only the tenant can leave reviews."}, status=403)
        if booking.user_id != request.user.id:
            return response.Response({"detail": "You can only leave a review for your booking.."}, status=403)
        if booking.status != Booking.Status.COMPLETED:
            return response.Response({"detail": "Feedback can only be left after booking is completed.."},
                                     status=400)
        # Let's determine if the Review model has a booking field.
        review_fields = {f.name for f in Review._meta.get_fields()}

        if "booking" in review_fields:
            # One review per booking
            if Review.objects.filter(booking=booking).exists():
                return response.Response({"detail": "A review has already been left for this booking.."}, status=400)
            review = Review.objects.create(
                property=booking.property,
                booking=booking,
                user=request.user,
                rating=int(request.data.get("rating")),
                text=str(request.data.get("text", "")).strip(),
            )
        else:
            # Fallback: one review per pair (property, user)
            if Review.objects.filter(property=booking.property, user=request.user).exists():
                return response.Response({"detail": "You have already left a review for this listing.."}, status=400)
            review = Review.objects.create(
                property=booking.property,
                user=request.user,
                rating=int(request.data.get("rating")),
                text=str(request.data.get("text", "")).strip(),
            )

        return response.Response(ReviewSerializer(review).data, status=201)
