# Пример теста перекрытия дат (pending + confirmed).
import pytest
from datetime import date, timedelta
from bookings.models import Booking


@pytest.mark.django_db
def test_booking_overlap(api_client, renter_user, property_factory, auth_headers):
    prop = property_factory()
    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=5)
    # Первое бронирование (pending)
    resp1 = api_client.post("/api/bookings/", {
        "property": prop.id,
        "start_date": start,
        "end_date": end
    }, **auth_headers(renter_user))
    assert resp1.status_code == 201

    # Второе пересекающееся (должно упасть)
    resp2 = api_client.post("/api/bookings/", {
        "property": prop.id,
        "start_date": start + timedelta(days=2),
        "end_date": end + timedelta(days=2)
    }, **auth_headers(renter_user))
    assert resp2.status_code == 400