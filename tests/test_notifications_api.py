import json
import pytest
from datetime import date, timedelta
from rest_framework.test import APIClient

from properties.models import Property
from bookings.models import Booking
from notifications.models import Notification  # noqa: F401


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


def _parse_list(resp):
    data, _ = _to_json(resp)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "data", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


@pytest.mark.django_db
def test_notifications_list_and_read_actions(django_user_model):
    client = APIClient()
    password = "Testpass123"

    landlord = django_user_model.objects.create_user(
        email="landlord2@example.com",
        password=password,
        role="landlord",
        first_name="Owner2",
        last_name="User",
        date_of_birth="1990-01-01",
    )
    renter = django_user_model.objects.create_user(
        email="renter2@example.com",
        password=password,
        role="renter",
        first_name="Renter2",
        last_name="User",
        date_of_birth="1995-01-01",
    )

    # Создаём объект
    prop = Property.objects.create(
        title="Лофт",
        description="Высокие потолки",
        location="Hamburg",
        price="1500.00",
        number_of_rooms=3,
        property_type="apartment",
        owner=landlord,
        status="active",
    )

    # Арендатор создаёт бронь -> уведомление арендодателю (booking_new)
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        status=Booking.Status.PENDING,
        # обязательные поля модели
        monthly_rent=prop.price,
        total_amount=prop.price,
    )

    # Лендлорд логинится и проверяет уведомления
    _auth(client, landlord, password)

    resp = client.get("/api/notifications/?is_read=false", follow=True)
    assert resp.status_code in (200, 302), f"Notifications list failed: {resp.status_code} {_resp_text(resp)[:400]}"
    items = _parse_list(resp)
    assert isinstance(items, list) and len(items) >= 1, f"No unread notifications. Body: {_resp_text(resp)[:400]}"

    # Берём первый id, если доступен
    notif_id = None
    for it in items:
        if isinstance(it, dict) and "id" in it:
            notif_id = it["id"]
            break

    # Отмечаем как прочитанное (если API поддерживает по id)
    if notif_id is not None:
        resp = client.post(f"/api/notifications/{notif_id}/read/", follow=True)
        assert resp.status_code in (200, 302), f"Mark read failed: {resp.status_code} {_resp_text(resp)[:400]}"
        data, _ = _to_json(resp)
        if isinstance(data, dict) and "is_read" in data:
            assert data["is_read"] is True

    # Подтверждаем бронь — должно прийти уведомление арендатору
    resp = client.post(f"/api/bookings/{booking.id}/confirm/", follow=True)
    assert resp.status_code in (200, 302), f"Confirm failed: {resp.status_code} {_resp_text(resp)[:400]}"

    # Логинимся под арендатором и проверяем
    _auth(client, renter, password)
    resp = client.get("/api/notifications/?is_read=false", follow=True)
    assert resp.status_code in (200, 302), f"Renter notifications list failed: {resp.status_code}"
    renter_items = _parse_list(resp)
    # Ищем тип или текст подтверждения
    assert any(
        (isinstance(n, dict) and (
            n.get("type") == "booking_confirmed" or
            "confirm" in str(n.get("message", "")).lower() or
            "подтвержден" in str(n.get("message", "")).lower()
        ))
        for n in renter_items
    ), f"No booking_confirmed-like notification found: {renter_items}"

    # Отмечаем все как прочитанные (если API поддерживает)
    resp = client.post("/api/notifications/read_all/", follow=True)
    assert resp.status_code in (200, 302), f"read_all failed: {resp.status_code}"

    resp = client.get("/api/notifications/?is_read=false", follow=True)
    assert resp.status_code in (200, 302)
    assert len(_parse_list(resp)) == 0