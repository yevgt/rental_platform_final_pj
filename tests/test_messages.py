import pytest
from datetime import date, timedelta

@pytest.mark.django_db
def test_messages_flow(api_client, renter_user, landlord_user, property_factory, booking_factory, auth_headers):
    prop = property_factory(owner=landlord_user, status="active")
    start = date.today() + timedelta(days=3)
    end = start + timedelta(days=7)
    booking = booking_factory(property=prop, user=renter_user, start_date=start, end_date=end, status="pending")

    # Renter отправляет сообщение
    resp = api_client.post(
        f"/api/bookings/{booking.id}/messages/",
        {"text": "Здравствуйте!"},
        format="json",
        **auth_headers(renter_user)
    )
    assert resp.status_code == 201

    # Landlord читает
    resp2 = api_client.get(f"/api/bookings/{booking.id}/messages/", **auth_headers(landlord_user))
    assert resp2.status_code == 200
    assert len(resp2.data) >= 1