import pytest
from datetime import date, timedelta

@pytest.mark.django_db
def test_landlord_confirm(api_client, renter_user, landlord_user, property_factory, auth_headers, booking_factory):
    prop = property_factory(owner=landlord_user, status="active")
    start = date.today() + timedelta(days=5)
    end = start + timedelta(days=10)
    booking = booking_factory(property=prop, user=renter_user, start_date=start, end_date=end, status="pending")
    resp = api_client.post(f"/api/bookings/{booking.id}/confirm/", **auth_headers(landlord_user))
    assert resp.status_code == 200

@pytest.mark.django_db
def test_landlord_reject(api_client, renter_user, landlord_user, property_factory, auth_headers, booking_factory):
    prop = property_factory(owner=landlord_user, status="active")
    start = date.today() + timedelta(days=5)
    end = start + timedelta(days=10)
    booking = booking_factory(property=prop, user=renter_user, start_date=start, end_date=end, status="pending")
    resp = api_client.post(f"/api/bookings/{booking.id}/reject/", **auth_headers(landlord_user))
    assert resp.status_code == 200

@pytest.mark.django_db
def test_renter_cannot_confirm(api_client, renter_user, landlord_user, property_factory, auth_headers, booking_factory):
    prop = property_factory(owner=landlord_user, status="active")
    start = date.today() + timedelta(days=5)
    end = start + timedelta(days=10)
    booking = booking_factory(property=prop, user=renter_user, start_date=start, end_date=end, status="pending")
    resp = api_client.post(f"/api/bookings/{booking.id}/confirm/", **auth_headers(renter_user))
    assert resp.status_code == 403