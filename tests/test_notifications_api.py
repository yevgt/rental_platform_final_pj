import pytest
from datetime import date, timedelta
from rest_framework.test import APIClient
from properties.models import Property
from bookings.models import Booking
from notifications.models import Notification  # noqa: F401  (может пригодиться для прямых проверок)

@pytest.mark.django_db
def test_notifications_list_and_read_actions(user_factory):
    client = APIClient()

    landlord = user_factory("landlord2@example.com", role="landlord", name="Owner2")
    renter = user_factory("renter2@example.com", role="renter", name="Renter2")

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
    )

    # Лендлорд логинится и проверяет уведомления (используем email)
    resp = client.post("/api/token/", {"email": landlord.email, "password": "Testpass123"}, format="json")
    assert resp.status_code == 200, resp.data
    access_owner = resp.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_owner}")

    resp = client.get("/api/notifications/?is_read=false")
    assert resp.status_code == 200, resp.data
    assert len(resp.data) >= 1
    notif_id = resp.data[0]["id"]

    # Отмечаем как прочитанное
    resp = client.post(f"/api/notifications/{notif_id}/read/")
    assert resp.status_code == 200, resp.data
    assert resp.data["is_read"] is True

    # Арендатор получает уведомление при подтверждении
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_owner}")
    resp = client.post(f"/api/bookings/{booking.id}/confirm/")
    assert resp.status_code == 200, resp.data

    # Логинимся под арендатором и проверяем (используем email)
    resp = client.post("/api/token/", {"email": renter.email, "password": "Testpass123"}, format="json")
    assert resp.status_code == 200, resp.data
    access_renter = resp.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_renter}")

    resp = client.get("/api/notifications/?is_read=false")
    assert resp.status_code == 200, resp.data
    assert any(n["type"] == "booking_confirmed" for n in resp.data)

    # Отмечаем все как прочитанные
    resp = client.post("/api/notifications/read_all/")
    assert resp.status_code == 200, resp.data
    resp = client.get("/api/notifications/?is_read=false")
    assert resp.status_code == 200, resp.data
    assert len(resp.data) == 0