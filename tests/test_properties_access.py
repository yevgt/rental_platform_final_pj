import pytest

@pytest.mark.django_db
def test_anonymous_list_active(api_client, property_factory):
    property_factory(status="active")
    property_factory(status="inactive")
    resp = api_client.get("/api/properties/")
    assert resp.status_code == 200
    # Должно вернуть только active (проверьте длину по вашей пагинации)
    assert all(item["status"] == "active" for item in resp.data)

@pytest.mark.django_db
def test_landlord_list_only_own(api_client, landlord_user, other_landlord_user, auth_headers, property_factory):
    p1 = property_factory(owner=landlord_user, status="active")
    p2 = property_factory(owner=other_landlord_user, status="active")
    resp = api_client.get("/api/properties/", **auth_headers(landlord_user))
    ids = [item["id"] for item in resp.data]
    assert p1.id in ids
    assert p2.id not in ids

@pytest.mark.django_db
def test_landlord_view_inactive_own(api_client, landlord_user, auth_headers, property_factory):
    p = property_factory(owner=landlord_user, status="inactive")
    resp = api_client.get(f"/api/properties/{p.id}/", **auth_headers(landlord_user))
    assert resp.status_code == 200

@pytest.mark.django_db
def test_landlord_cannot_view_inactive_foreign(api_client, landlord_user, other_landlord_user, auth_headers, property_factory):
    p = property_factory(owner=other_landlord_user, status="inactive")
    resp = api_client.get(f"/api/properties/{p.id}/", **auth_headers(landlord_user))
    assert resp.status_code in (403, 404)  # В коде 404

@pytest.mark.django_db
def test_renter_cannot_see_inactive(api_client, renter_user, auth_headers, property_factory):
    p = property_factory(status="inactive")
    resp = api_client.get(f"/api/properties/{p.id}/", **auth_headers(renter_user))
    assert resp.status_code == 404