import pytest
from datetime import date, timedelta
from rest_framework.test import APIClient

@pytest.mark.django_db
def test_booking_flow_and_review(user_factory):
    client = APIClient()

    # Create landlord and renter
    landlord = user_factory("owner2@example.com", role="landlord")
    renter = user_factory("renter@example.com", role="renter")

    # Login landlord (use email per new auth)
    resp = client.post("/api/token/", {"email": landlord.email, "password": "Testpass123"}, format="json")
    assert resp.status_code == 200, resp.data
    access_owner = resp.data["access"]

    # Create property
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_owner}")
    resp = client.post("/api/properties/", {
        "title": "Дом",
        "description": "Сад и гараж",
        "location": "Munich",
        "price": "2500.00",
        "number_of_rooms": 5,
        "property_type": "house",
        "status": "active"
    }, format="json")
    assert resp.status_code == 201, resp.data
    prop_id = resp.data["id"]

    # Login renter and create booking (use email per new auth)
    resp = client.post("/api/token/", {"email": renter.email, "password": "Testpass123"}, format="json")
    assert resp.status_code == 200, resp.data
    access_renter = resp.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_renter}")

    start = date.today()
    end = date.today() + timedelta(days=3)
    resp = client.post("/api/bookings/", {
        "property": prop_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "cancel_until": (date.today() + timedelta(days=1)).isoformat()
    }, format="json")
    assert resp.status_code == 201, resp.data
    booking_id = resp.data["id"]

    # Owner confirms
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_owner}")
    resp = client.post(f"/api/bookings/{booking_id}/confirm/")
    assert resp.status_code == 200, resp.data

    # Try to review before end -> should fail
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_renter}")
    resp = client.post("/api/reviews/", {"property": prop_id, "rating": 5, "comment": "Отлично"}, format="json")
    assert resp.status_code == 400, resp.data

    # Simulate end in the past: update booking end_date (in real life — крон/фактическое время)
    from bookings.models import Booking
    b = Booking.objects.get(pk=booking_id)
    b.end_date = date.today() - timedelta(days=1)
    b.save(update_fields=["end_date"])

    # Now review should pass
    resp = client.post("/api/reviews/", {"property": prop_id, "rating": 5, "comment": "Отлично"}, format="json")
    assert resp.status_code == 201, resp.data

    # List reviews by property
    resp = client.get(f"/api/reviews/?property={prop_id}")
    assert resp.status_code == 200, resp.data
    assert len(resp.data) >= 1