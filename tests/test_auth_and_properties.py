import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_register_and_login_and_create_property():
    client = APIClient()

    # Register landlord
    resp = client.post(
        "/api/accounts/register/",
        {
            "name": "Owner",
            "email": "owner@example.com",
            "password": "StrongPass123",
            "role": "landlord",
        },
        format="json",
    )
    assert resp.status_code == 201

    # Login (по новым условиям: используем email)
    resp = client.post(
        "/api/token/",
        {"email": "owner@example.com", "password": "StrongPass123"},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    access = resp.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    # Create property
    resp = client.post(
        "/api/properties/",
        {
            "title": "Уютная квартира",
            "description": "Центр города",
            "location": "Berlin",
            "price": "1200.00",
            "number_of_rooms": 2,
            "property_type": "apartment",
            "status": "active",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    prop_id = resp.data["id"]

    # Public list + search + ordering
    client.credentials()  # anonymous
    resp = client.get("/api/properties/?search=квартира&ordering=-price")
    assert resp.status_code == 200
    assert any(item["id"] == prop_id for item in resp.data)