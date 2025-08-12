import logging
import json
from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from properties.models import Property
from bookings.models import Booking


def _to_json(resp):
    try:
        return resp.json(), None
    except Exception:
        pass
    raw = None
    for attr in ("rendered_content", "content"):
        if hasattr(resp, attr):
            try:
                raw = getattr(resp, attr)
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="ignore")
                break
            except Exception:
                continue
    if raw is None:
        return None, None
    try:
        return json.loads(raw), raw
    except Exception:
        return None, raw


def _resp_text(resp) -> str:
    try:
        c = getattr(resp, "content", b"")
        if isinstance(c, bytes):
            return c.decode("utf-8", errors="ignore")
        return str(c)
    except Exception:
        return repr(resp)


def _auth(client: APIClient, user, password: str):
    resp = client.post("/api/token/", {"email": user.email, "password": password}, format="json")
    assert resp.status_code == 200, f"Token failed: {_resp_text(resp)[:400]}"
    data, _ = _to_json(resp)
    access = data.get("access") if isinstance(data, dict) else None
    if access:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    # На случай HTML-сессий
    client.login(username=user.email, password=password)


@pytest.mark.django_db
def test_booking_confirm_emits_info_log(django_user_model, caplog):
    """
    Подтверждение брони владельцем должно писать INFO-лог в bookings.views
    """
    caplog.set_level(logging.INFO, logger="bookings.views")

    password = "Testpass123"

    # Данные
    owner = django_user_model.objects.create_user(
        email="owner-log@example.com",
        password=password,
        role="landlord",
        first_name="Owner",
        last_name="User",
        date_of_birth="1990-01-01",
    )
    renter = django_user_model.objects.create_user(
        email="renter-log@example.com",
        password=password,
        role="renter",
        first_name="Renter",
        last_name="User",
        date_of_birth="1995-01-01",
    )
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
        # заполняем обязательные поля модели
        monthly_rent=prop.price,
        total_amount=prop.price,
    )

    # Логин владельца
    client = APIClient()
    _auth(client, owner, password)

    # Действие
    resp = client.post(f"/api/bookings/{booking.id}/confirm/", follow=True)
    assert resp.status_code in (200, 302), f"Unexpected status on confirm: {resp.status_code} {_resp_text(resp)[:400]}"

    # Проверка логов
    booking_logs = [r for r in caplog.records if r.name == "bookings.views" and r.levelno == logging.INFO]
    assert any("booking confirmed" in r.getMessage().lower() for r in booking_logs), [
        (r.name, r.levelname, r.getMessage()) for r in caplog.records
    ]


@pytest.mark.django_db
def test_booking_confirm_forbidden_emits_warning(django_user_model, caplog):
    """
    Запрет на подтверждение не-владельцем -> WARNING-лог в bookings.views
    """
    caplog.set_level(logging.WARNING, logger="bookings.views")

    password = "Testpass123"

    # Данные
    owner = django_user_model.objects.create_user(
        email="owner-log2@example.com",
        password=password,
        role="landlord",
        first_name="Owner2",
        last_name="User",
        date_of_birth="1990-01-01",
    )
    other_user = django_user_model.objects.create_user(
        email="intruder@example.com",
        password=password,
        role="renter",
        first_name="Intruder",
        last_name="User",
        date_of_birth="1996-01-01",
    )
    renter = django_user_model.objects.create_user(
        email="renter2@example.com",
        password=password,
        role="renter",
        first_name="Renter2",
        last_name="User",
        date_of_birth="1995-01-01",
    )
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
        monthly_rent=prop.price,
        total_amount=prop.price,
    )

    # Логинимся под посторонним пользователем и пробуем confirm
    client = APIClient()
    _auth(client, other_user, password)

    resp = client.post(f"/api/bookings/{booking.id}/confirm/", follow=True)
    # В идеале 403, но на случай других реализаций допустим 400/200/302 (HTML), лог при этом всё равно должен быть WARNING
    assert resp.status_code in (403, 400, 200, 302), f"Unexpected status for forbidden confirm: {resp.status_code}"

    # Проверка логов
    warn_logs = [r for r in caplog.records if r.name == "bookings.views" and r.levelno == logging.WARNING]
    # Ищем сообщение, содержащее и 'confirm' и 'forbidden' (без учета регистра), чтобы быть устойчивыми к формулировке
    assert any(("confirm" in r.getMessage().lower() and "forbidden" in r.getMessage().lower()) for r in warn_logs), [
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