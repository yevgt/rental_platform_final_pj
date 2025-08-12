import pytest
from datetime import timedelta, date
from types import SimpleNamespace

from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

from bookings.views import BookingViewSet
from bookings.models import Booking, Message
from properties.models import Property
from reviews.models import Review
from django.contrib.auth import get_user_model

User = get_user_model()


def make_user(email, role):
    # password не обязателен для force_authenticate
    return User.objects.create_user(email=email, password=None, role=role)


def make_property(owner, title="Flat A", location="City", price="1000.00", status="active"):
    return Property.objects.create(
        title=title,
        description="Nice",
        location=location,
        price=price,
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status=status,
    )


def as_viewset(action_map):
    return BookingViewSet.as_view(action_map)


@pytest.mark.django_db
def test_list_renter_only_their_bookings_and_forbidden_for_unknown_role():
    factory = APIRequestFactory()
    renter = make_user("renter@example.com", "renter")
    other_renter = make_user("renter2@example.com", "renter")
    landlord = make_user("landlord@example.com", "landlord")
    prop = make_property(landlord)

    today = timezone.now().date()
    b1 = Booking.objects.create(property=prop, user=renter, start_date=today + timedelta(days=5),
                                end_date=today + timedelta(days=10), monthly_rent=prop.price, total_amount=prop.price)
    b2 = Booking.objects.create(property=prop, user=other_renter, start_date=today + timedelta(days=6),
                                end_date=today + timedelta(days=11), monthly_rent=prop.price, total_amount=prop.price)

    # renter видит только свои
    req = factory.get("/api/bookings/")
    force_authenticate(req, user=renter)
    resp = as_viewset({"get": "list"})(req)
    assert resp.status_code == 200
    ids = [row["id"] for row in resp.data]
    assert b1.id in ids and b2.id not in ids

    # неизвестная роль -> 403
    stranger = make_user("x@example.com", role="guest")
    req2 = factory.get("/api/bookings/")
    force_authenticate(req2, user=stranger)
    resp2 = as_viewset({"get": "list"})(req2)
    assert resp2.status_code == 403
    assert "Недоступно" in resp2.data["detail"]


@pytest.mark.django_db
def test_retrieve_permissions_renter_and_landlord():
    factory = APIRequestFactory()
    landlord = make_user("l1@example.com", "landlord")
    renter = make_user("r1@example.com", "renter")
    other = make_user("r2@example.com", "renter")
    prop = make_property(landlord)
    today = timezone.now().date()
    booking = Booking.objects.create(property=prop, user=renter, start_date=today + timedelta(days=5),
                                     end_date=today + timedelta(days=10), monthly_rent=prop.price, total_amount=prop.price)

    # renter собственное - OK
    req = factory.get(f"/api/bookings/{booking.id}/")
    force_authenticate(req, user=renter)
    resp = as_viewset({"get": "retrieve"})(req, pk=booking.id)
    assert resp.status_code == 200
    assert resp.data["id"] == booking.id

    # другой renter - 403
    req2 = factory.get(f"/api/bookings/{booking.id}/")
    force_authenticate(req2, user=other)
    resp2 = as_viewset({"get": "retrieve"})(req2, pk=booking.id)
    assert resp2.status_code == 403

    # landlord владелец property - OK
    req3 = factory.get(f"/api/bookings/{booking.id}/")
    force_authenticate(req3, user=landlord)
    resp3 = as_viewset({"get": "retrieve"})(req3, pk=booking.id)
    assert resp3.status_code == 200


@pytest.mark.django_db
def test_cancel_happy_path_and_denials(monkeypatch):
    factory = APIRequestFactory()
    renter = make_user("r1@example.com", "renter")
    other_renter = make_user("r2@example.com", "renter")
    landlord = make_user("l1@example.com", "landlord")
    prop = make_property(landlord)

    future = timezone.now().date() + timedelta(days=7)
    # Создадим две брони:
    # 1) для успешной отмены
    booking_ok = Booking.objects.create(property=prop, user=renter, start_date=future, end_date=future + timedelta(days=3),
                                        monthly_rent=prop.price, total_amount=prop.price, status=Booking.Status.PENDING,
                                        cancel_until=future)  # cancel_until = start_date => True при today < start_date
    # 2) для "нельзя отменить" (сегодня >= start_date)
    today = timezone.now().date()
    booking_late = Booking.objects.create(property=prop, user=renter, start_date=today, end_date=today + timedelta(days=2),
                                          monthly_rent=prop.price, total_amount=prop.price, status=Booking.Status.PENDING)

    # Не renter -> 403
    req0 = factory.post(f"/api/bookings/{booking_ok.id}/cancel/", {})
    force_authenticate(req0, user=landlord)
    resp0 = as_viewset({"post": "cancel"})(req0, pk=booking_ok.id)
    assert resp0.status_code == 403

    # Не владелец брони -> 403
    req1 = factory.post(f"/api/bookings/{booking_ok.id}/cancel/", {})
    force_authenticate(req1, user=other_renter)
    resp1 = as_viewset({"post": "cancel"})(req1, pk=booking_ok.id)
    assert resp1.status_code == 403

    # Просрочено -> 400
    req2 = factory.post(f"/api/bookings/{booking_late.id}/cancel/", {})
    force_authenticate(req2, user=renter)
    resp2 = as_viewset({"post": "cancel"})(req2, pk=booking_late.id)
    assert resp2.status_code == 400

    # Успех
    req3 = factory.post(f"/api/bookings/{booking_ok.id}/cancel/", {})
    force_authenticate(req3, user=renter)
    resp3 = as_viewset({"post": "cancel"})(req3, pk=booking_ok.id)
    assert resp3.status_code == 200
    booking_ok.refresh_from_db()
    assert booking_ok.status == Booking.Status.CANCELLED

    # Не найдено -> 404 (NotFound из _get_booking_unrestricted)
    req4 = factory.post("/api/bookings/999999/cancel/", {})
    force_authenticate(req4, user=renter)
    resp4 = as_viewset({"post": "cancel"})(req4, pk=999999)
    assert resp4.status_code == 404


@pytest.mark.django_db
def test_confirm_overlap_and_success():
    factory = APIRequestFactory()
    landlord = make_user("l2@example.com", "landlord")
    other_landlord = make_user("l3@example.com", "landlord")
    renter = make_user("r3@example.com", "renter")
    prop = make_property(landlord)
    today = timezone.now().date()

    # Уже подтвержденная бронь [10,15]
    confirmed = Booking.objects.create(property=prop, user=renter, start_date=today + timedelta(days=10),
                                       end_date=today + timedelta(days=15),
                                       monthly_rent=prop.price, total_amount=prop.price,
                                       status=Booking.Status.CONFIRMED)
    # Ожидающая [12,14] (пересекается)
    pending_overlap = Booking.objects.create(property=prop, user=renter, start_date=today + timedelta(days=12),
                                            end_date=today + timedelta(days=14),
                                            monthly_rent=prop.price, total_amount=prop.price,
                                            status=Booking.Status.PENDING)
    # Ожидающая [16,18] (не пересекается)
    pending_ok = Booking.objects.create(property=prop, user=renter, start_date=today + timedelta(days=16),
                                       end_date=today + timedelta(days=18),
                                       monthly_rent=prop.price, total_amount=prop.price,
                                       status=Booking.Status.PENDING)

    # Не landlord -> 403
    req0 = factory.post(f"/api/bookings/{pending_ok.id}/confirm/", {})
    force_authenticate(req0, user=renter)
    resp0 = as_viewset({"post": "confirm"})(req0, pk=pending_ok.id)
    assert resp0.status_code == 403

    # Не владелец property ->