import pytest
from datetime import date, timedelta
from rest_framework.test import APIClient

###
def _resp_text(resp) -> str:
    try:
        c = getattr(resp, "content", b"")
        if isinstance(c, bytes):
            return c.decode("utf-8", errors="ignore")
        return str(c)
    except Exception:
        return repr(resp)


@pytest.mark.django_db
def test_landlord_confirm(django_user_model):
    from properties.models import Property
    from bookings.models import Booking

    # 1) Создаём пользователей
    owner_email = "landlord_confirm@example.com"
    renter_email = "renter_confirm@example.com"
    password = "Passw0rd123"

    landlord = django_user_model.objects.create_user(
        email=owner_email,
        password=password,
        role="landlord",
        first_name="L",
        last_name="O",
        date_of_birth="1990-01-01",
    )
    renter = django_user_model.objects.create_user(
        email=renter_email,
        password=password,
        role="renter",
        first_name="R",
        last_name="U",
        date_of_birth="1990-01-01",
    )

    # 2) Логинимся как арендодатель (JWT + сессия) и создаём объект недвижимости
    owner_client = APIClient()
    resp = owner_client.post("/api/token/", {"email": owner_email, "password": password}, format="json")
    assert resp.status_code == 200, f"Owner JWT failed: {_resp_text(resp)[:400]}"
    owner_access = resp.json().get("access")
    if owner_access:
        owner_client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_access}")
    owner_client.login(username=owner_email, password=password)

    prop_payload = {
        "title": "Confirm-Property",
        "description": "Test",
        "location": "Berlin",
        "price": "1500.00",
        "number_of_rooms": 3,
        "property_type": "apartment",
        "status": "active",
    }
    # сначала пробуем HTML-вью
    resp = owner_client.post("/api/properties/create/", prop_payload, follow=True)
    if resp.status_code == 404:
        resp = owner_client.post("/api/properties/", prop_payload, follow=True)
    assert resp.status_code in (200, 201, 302), f"Property create failed: {resp.status_code} {_resp_text(resp)[:400]}"

    prop = Property.objects.filter(owner=landlord, title="Confirm-Property").order_by("-id").first()
    assert prop is not None, "Property not found after creation"

    # 3) Логинимся как арендатор (JWT + сессия) и создаём бронирование
    renter_client = APIClient()
    resp = renter_client.post("/api/token/", {"email": renter_email, "password": password}, format="json")
    assert resp.status_code == 200, f"Renter JWT failed: {_resp_text(resp)[:400]}"
    renter_access = resp.json().get("access")
    if renter_access:
        renter_client.credentials(HTTP_AUTHORIZATION=f"Bearer {renter_access}")
    renter_client.login(username=renter_email, password=password)

    start = date.today() + timedelta(days=5)
    end = start + timedelta(days=10)
    booking_payload = {
        "property": prop.id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    resp = renter_client.post("/api/bookings/create/", booking_payload, follow=True)
    if resp.status_code == 404:
        resp = renter_client.post("/api/bookings/", booking_payload, follow=True)
    assert resp.status_code in (200, 201, 302), f"Booking create failed: {resp.status_code} {_resp_text(resp)[:400]}"

    booking = Booking.objects.filter(property=prop).order_by("-id").first()
    assert booking is not None, "Booking not found after creation"

    # 4) Арендодатель подтверждает бронирование
    resp = owner_client.post(f"/api/bookings/{booking.id}/confirm/", follow=True)
    assert resp.status_code == 200, f"Expected 200 on confirm, got {resp.status_code}: {_resp_text(resp)[:400]}"
###
@pytest.mark.django_db
def test_landlord_reject(django_user_model):
    from properties.models import Property
    from bookings.models import Booking

    # 1) Пользователи
    owner_email = "landlord_reject@example.com"
    renter_email = "renter_reject@example.com"
    password = "Passw0rd123"

    landlord = django_user_model.objects.create_user(
        email=owner_email,
        password=password,
        role="landlord",
        first_name="L",
        last_name="O",
        date_of_birth="1990-01-01",
    )
    renter = django_user_model.objects.create_user(
        email=renter_email,
        password=password,
        role="renter",
        first_name="R",
        last_name="U",
        date_of_birth="1990-01-01",
    )

    # 2) Логин арендодателя (JWT + сессия) и создание объявления
    owner_client = APIClient()
    resp = owner_client.post("/api/token/", {"email": owner_email, "password": password}, format="json")
    assert resp.status_code == 200, f"Owner JWT failed: {_resp_text(resp)[:400]}"
    owner_access = resp.json().get("access")
    if owner_access:
        owner_client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_access}")
    owner_client.login(username=owner_email, password=password)

    prop_payload = {
        "title": "Reject-Property",
        "description": "Test",
        "location": "Munich",
        "price": "1200.00",
        "number_of_rooms": 2,
        "property_type": "apartment",
        "status": "active",
    }
    resp = owner_client.post("/api/properties/create/", prop_payload, follow=True)
    if resp.status_code == 404:
        resp = owner_client.post("/api/properties/", prop_payload, follow=True)
    assert resp.status_code in (200, 201, 302), f"Property create failed: {resp.status_code} {_resp_text(resp)[:400]}"

    prop = Property.objects.filter(owner=landlord, title="Reject-Property").order_by("-id").first()
    assert prop is not None, "Property not found after creation"

    # 3) Логин арендатора (JWT + сессия) и создание бронирования
    renter_client = APIClient()
    resp = renter_client.post("/api/token/", {"email": renter_email, "password": password}, format="json")
    assert resp.status_code == 200, f"Renter JWT failed: {_resp_text(resp)[:400]}"
    renter_access = resp.json().get("access")
    if renter_access:
        renter_client.credentials(HTTP_AUTHORIZATION=f"Bearer {renter_access}")
    renter_client.login(username=renter_email, password=password)

    start = date.today() + timedelta(days=5)
    end = start + timedelta(days=10)
    booking_payload = {
        "property": prop.id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    resp = renter_client.post("/api/bookings/create/", booking_payload, follow=True)
    if resp.status_code == 404:
        resp = renter_client.post("/api/bookings/", booking_payload, follow=True)
    assert resp.status_code in (200, 201, 302), f"Booking create failed: {resp.status_code} {_resp_text(resp)[:400]}"

    booking = Booking.objects.filter(property=prop).order_by("-id").first()
    assert booking is not None, "Booking not found after creation"

    # 4) Отклонение арендодателем
    resp = owner_client.post(f"/api/bookings/{booking.id}/reject/", follow=True)
    assert resp.status_code == 200, f"Expected 200 on reject, got {resp.status_code}: {_resp_text(resp)[:400]}"
###
@pytest.mark.django_db
def test_renter_cannot_confirm(django_user_model):
    from properties.models import Property
    from bookings.models import Booking

    # 1) Пользователи
    owner_email = "landlord_block_confirm@example.com"
    renter_email = "renter_block_confirm@example.com"
    password = "Passw0rd123"

    landlord = django_user_model.objects.create_user(
        email=owner_email,
        password=password,
        role="landlord",
        first_name="L",
        last_name="O",
        date_of_birth="1990-01-01",
    )
    renter = django_user_model.objects.create_user(
        email=renter_email,
        password=password,
        role="renter",
        first_name="R",
        last_name="U",
        date_of_birth="1990-01-01",
    )

    # 2) Логин арендодателя (JWT + сессия) и создание объявления
    owner_client = APIClient()
    resp = owner_client.post("/api/token/", {"email": owner_email, "password": password}, format="json")
    assert resp.status_code == 200, f"Owner JWT failed: {_resp_text(resp)[:400]}"
    owner_access = resp.json().get("access")
    if owner_access:
        owner_client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_access}")
    owner_client.login(username=owner_email, password=password)

    prop_payload = {
        "title": "Renter-Confirm-Property",
        "description": "Test",
        "location": "Hamburg",
        "price": "1400.00",
        "number_of_rooms": 2,
        "property_type": "apartment",
        "status": "active",
    }
    resp = owner_client.post("/api/properties/create/", prop_payload, follow=True)
    if resp.status_code == 404:
        resp = owner_client.post("/api/properties/", prop_payload, follow=True)
    assert resp.status_code in (200, 201, 302), f"Property create failed: {resp.status_code} {_resp_text(resp)[:400]}"

    prop = Property.objects.filter(owner=landlord, title="Renter-Confirm-Property").order_by("-id").first()
    assert prop is not None, "Property not found after creation"

    # 3) Логин арендатора (JWT + сессия) и создание бронирования
    renter_client = APIClient()
    resp = renter_client.post("/api/token/", {"email": renter_email, "password": password}, format="json")
    assert resp.status_code == 200, f"Renter JWT failed: {_resp_text(resp)[:400]}"
    renter_access = resp.json().get("access")
    if renter_access:
        renter_client.credentials(HTTP_AUTHORIZATION=f"Bearer {renter_access}")
    renter_client.login(username=renter_email, password=password)

    start = date.today() + timedelta(days=5)
    end = start + timedelta(days=10)
    booking_payload = {
        "property": prop.id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    resp = renter_client.post("/api/bookings/create/", booking_payload, follow=True)
    if resp.status_code == 404:
        resp = renter_client.post("/api/bookings/", booking_payload, follow=True)
    assert resp.status_code in (200, 201, 302), f"Booking create failed: {resp.status_code} {_resp_text(resp)[:400]}"

    booking = Booking.objects.filter(property=prop).order_by("-id").first()
    assert booking is not None, "Booking not found after creation"

    # 4) Попытка подтверждения арендатором — должна быть запрещена
    pre_status = getattr(booking, "status", None)

    resp = renter_client.post(f"/api/bookings/{booking.id}/confirm/", follow=True)

    # В идеале 403, но допускаем разные реализации (напр., 400 или HTML-ответ 200/302 без изменения состояния)
    assert resp.status_code in (403, 400, 200, 302), (
        f"Unexpected status for renter confirm: {resp.status_code}. Body: {_resp_text(resp)[:400]}"
    )

    booking.refresh_from_db()
    if pre_status is not None and hasattr(booking, "status"):
        assert booking.status == pre_status, (
            f"Renter should not be able to change booking status via confirm. "
            f"Before={pre_status}, after={booking.status}"
        )