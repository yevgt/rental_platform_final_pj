import json
import pytest
from datetime import date, timedelta
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
    client.login(username=user.email, password=password)


def _extract_messages(resp):
    data, raw = _to_json(resp)
    # Возможные форматы: список, {"results": [...]}, {"data": [...]}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "data", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    # Если это HTML, пробуем простейший хак: не проверяем содержимое
    return []


@pytest.mark.django_db
def test_messages_flow(django_user_model):
    password = "Pass12345"

    renter = django_user_model.objects.create_user(
        email="msg_renter@example.com",
        password=password,
        role="renter",
        first_name="Renter",
        last_name="User",
        date_of_birth="1995-01-01",
    )
    landlord = django_user_model.objects.create_user(
        email="msg_landlord@example.com",
        password=password,
        role="landlord",
        first_name="Land",
        last_name="Lord",
        date_of_birth="1990-01-01",
    )

    prop = Property.objects.create(
        title="Messaging Property",
        description="Test",
        location="Berlin",
        price="1300.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=landlord,
        status="active",
    )

    # Бронирование в будущем, чтобы логика разрешала обмен сообщениями
    start = date.today() + timedelta(days=3)
    end = start + timedelta(days=7)
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=start,
        end_date=end,
        status=Booking.Status.PENDING,
        # обязательные поля модели
        monthly_rent=prop.price,
        total_amount=prop.price,
    )

    # Рентер отправляет сообщение
    renter_client = APIClient()
    _auth(renter_client, renter, password)

    resp = renter_client.post(
        f"/api/bookings/{booking.id}/messages/",
        {"text": "Здравствуйте!"},
        format="json",
        follow=True,
    )
    # Допускаем 200/201/302 для разных реализаций API/HTML
    assert resp.status_code in (200, 201, 302), f"Message send failed: {resp.status_code} {_resp_text(resp)[:400]}"

    # Лендлорд читает сообщения
    landlord_client = APIClient()
    _auth(landlord_client, landlord, password)

    resp2 = landlord_client.get(f"/api/bookings/{booking.id}/messages/", follow=True)
    assert resp2.status_code in (200, 302), f"Messages list failed: {resp2.status_code} {_resp_text(resp2)[:400]}"
    messages = _extract_messages(resp2)
    # Ожидаем минимум одно сообщение после отправки
    assert isinstance(messages, list) and len(messages) >= 1