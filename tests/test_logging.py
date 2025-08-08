import logging
from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from properties.models import Property
from bookings.models import Booking


@pytest.mark.django_db
def test_booking_confirm_emits_info_log(user_factory, caplog):
    """
    Подтверждение брони владельцем должно писать INFO-лог в bookings.views
    """
    caplog.set_level(logging.INFO)

    # Данные
    owner = user_factory("owner-log@example.com", role="landlord", name="Owner")
    renter = user_factory("renter-log@example.com", role="renter", name="Renter")
    prop = Property.objects.create(
        title="Лофт",
        description="Высокие потолки",
        location="Hamburg",
        price="1500.00",
        number_of_rooms=3,
        property_type="apartment",
        owner=owner,
        status="active",
    )
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        status=Booking.Status.PENDING,
    )

    # Логин владельца
    client = APIClient()
    resp = client.post("/api/token/", {"email": owner.email, "password": "Testpass123"}, format="json")
    assert resp.status_code == 200, resp.data
    access_owner = resp.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_owner}")

    # Действие
    resp = client.post(f"/api/bookings/{booking.id}/confirm/")
    assert resp.status_code == 200, resp.data

    # Проверка логов
    booking_logs = [
        r for r in caplog.records
        if r.name == "bookings.views" and r.levelno == logging.INFO
    ]
    assert any("Booking confirmed" in r.getMessage() for r in booking_logs), [
        (r.name, r.levelname, r.getMessage()) for r in caplog.records
    ]


@pytest.mark.django_db
def test_booking_confirm_forbidden_emits_warning(user_factory, caplog):
    """
    Запрет на подтверждение не-владельцем -> WARNING-лог в bookings.views
    """
    caplog.set_level(logging.WARNING)

    # Данные
    owner = user_factory("owner-log2@example.com", role="landlord", name="Owner2")
    other_user = user_factory("intruder@example.com", role="renter", name="Intruder")
    renter = user_factory("renter2@example.com", role="renter", name="Renter2")
    prop = Property.objects.create(
        title="Дом",
        description="Сад и гараж",
        location="Munich",
        price="2500.00",
        number_of_rooms=5,
        property_type="house",
        owner=owner,
        status="active",
    )
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=3),
        status=Booking.Status.PENDING,
    )

    # Логинимся под посторонним пользователем и пробуем confirm
    client = APIClient()
    resp = client.post("/api/token/", {"email": other_user.email, "password": "Testpass123"}, format="json")
    assert resp.status_code == 200, resp.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")

    resp = client.post(f"/api/bookings/{booking.id}/confirm/")
    assert resp.status_code == 403, resp.data

    # Проверка логов
    warn_logs = [
        r for r in caplog.records
        if r.name == "bookings.views" and r.levelno == logging.WARNING
    ]
    assert any("Confirm forbidden" in r.getMessage() for r in warn_logs), [
        (r.name, r.levelname, r.getMessage()) for r in caplog.records
    ]


@pytest.mark.django_db
def test_requests_middleware_logs_list_properties(caplog):
    """
    Middleware для логирования запросов пишет INFO в логгер 'requests'
    при GET /api/properties/
    """
    # Убедимся, что INFO для логгера 'requests' попадает в caplog
    caplog.set_level(logging.INFO, logger="requests")

    client = APIClient()
    resp = client.get("/api/properties/")
    assert resp.status_code in (200, 204)

    req_logs = [r for r in caplog.records if r.name == "requests" and r.levelno == logging.INFO]
    # В сообщении должен быть путь (middleware логирует словарь как строку)
    assert any("/api/properties/" in r.getMessage() for r in req_logs), [
        (r.name, r.levelname, r.getMessage()) for r in caplog.records
    ]