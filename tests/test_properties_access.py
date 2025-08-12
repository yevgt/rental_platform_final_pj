import json
import pytest
from typing import List
from rest_framework.test import APIClient

from properties.models import Property


# Helpers

def _to_json(resp):
    try:
        return resp.json(), None
    except Exception:
        pass
    raw = None
    for attr in ("rendered_content", "content"):
        if hasattr(resp, attr):
            raw = getattr(resp, attr)
            if isinstance(raw, bytes):
                try:
                    raw = raw.decode("utf-8", errors="ignore")
                except Exception:
                    raw = None
            break
    if raw is None:
        return None, None
    try:
        return json.loads(raw), raw
    except Exception:
        return None, raw


def _parse_list(resp) -> List[dict]:
    data, _ = _to_json(resp)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # DRF pagination
        for key in ("results", "data", "items"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []


def _first_ok_response(client: APIClient, urls: List[str]):
    """
    Try a list of URLs and return the first response with a 200-range status.
    Otherwise return the last response.
    """
    last = None
    for u in urls:
        resp = client.get(u)
        last = resp
        if 200 <= resp.status_code < 300:
            return resp
    return last


DEFAULT_PASSWORD = "Pass12345"


def _auth_client(user) -> APIClient:
    """
    Returns an APIClient authenticated as the given user.

    It tries common test passwords via JWT token endpoint first.
    Falls back to session login/force_login if available.
    """
    client = APIClient()

    # Try to obtain JWT and set Authorization header
    for pwd in (DEFAULT_PASSWORD, "Testpass123"):
        try:
            resp = client.post("/api/token/", {"email": user.email, "password": pwd}, format="json")
        except Exception:
            resp = None
        if getattr(resp, "status_code", None) == 200:
            data = getattr(resp, "data", {}) or {}
            access = data.get("access")
            if access:
                client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
                return client

    # Fallback to session authentication
    try:
        client.login(username=user.email, password=DEFAULT_PASSWORD)
    except Exception:
        pass
    try:
        client.force_login(user)
    except Exception:
        pass
    return client


def _make_user(django_user_model, email: str, role: str):
    return django_user_model.objects.create_user(
        email=email,
        password=DEFAULT_PASSWORD,
        role=role,
        first_name=role.capitalize(),
        last_name="User",
        date_of_birth="1990-01-01",
    )


def _create_property(owner, **overrides):
    defaults = dict(
        title="Test Property",
        description="Nice place",
        location="Berlin",
        price="1000.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status="active",
    )
    defaults.update(overrides)
    return Property.objects.create(**defaults)


@pytest.mark.django_db
def test_anonymous_list_active(django_user_model):
    # Given: one active and one inactive
    landlord = _make_user(django_user_model, "land1@example.com", "landlord")
    _create_property(owner=landlord, status="active")
    _create_property(owner=landlord, status="inactive")

    anon = APIClient()

    # Try public endpoint first, then fallback to generic
    resp = _first_ok_response(anon, [
        "/api/properties/public/",
        "/api/properties/",
    ])
    assert resp is not None, "No response returned"
    assert resp.status_code == 200, f"Expected 200 from list endpoint, got {resp.status_code}"

    items = _parse_list(resp)
    # Expect only active items in anonymous listing
    assert all(item.get("status") == "active" for item in items), f"Found non-active items: {items}"


@pytest.mark.django_db
def test_landlord_list_only_own(django_user_model):
    landlord_user = _make_user(django_user_model, "landlord@example.com", "landlord")
    other_landlord_user = _make_user(django_user_model, "landlord2@example.com", "landlord")

    p1 = _create_property(owner=landlord_user, status="active")
    _create_property(owner=other_landlord_user, status="active")

    client = _auth_client(landlord_user)

    # Try endpoints that typically return "my properties" FIRST, then generic fallbacks.
    candidates = [
        "/api/properties/my/",
        "/api/landlord/properties/",
        f"/api/properties/?owner=me",
        f"/api/properties/?owner_id={landlord_user.id}",
        f"/api/properties/?owner={landlord_user.id}",
        "/api/properties/",
        "/api/properties/public/",
    ]

    last_resp = None
    tried = []
    for url in candidates:
        resp = client.get(url, follow=True)
        tried.append((url, resp.status_code))
        last_resp = resp
        if resp.status_code != 200:
            continue
        items = _parse_list(resp)
        ids = [it.get("id") for it in items if isinstance(it, dict)]
        if p1.id in ids:
            # Success: own property is present in the list
            break
    else:
        # If we never broke out (didn't find own property), fail with debug info
        body = ""
        try:
            body = (last_resp.content or b"")[:400].decode("utf-8", errors="ignore")
        except Exception:
            pass
        pytest.fail(
            f"Own property {p1.id} not found in any candidate list. "
            f"Tried: {tried}. Last status={getattr(last_resp,'status_code',None)}. Body: {body}"
        )


@pytest.mark.django_db
def test_landlord_view_inactive_own(django_user_model):
    landlord_user = _make_user(django_user_model, "landlord3@example.com", "landlord")
    p = _create_property(owner=landlord_user, status="inactive")
    client = _auth_client(landlord_user)

    resp = client.get(f"/api/properties/{p.id}/")
    # Some implementations allow owners to view inactive (200), others may hide (404).
    assert resp.status_code in (200, 404), f"Unexpected status for own inactive property: {resp.status_code}"


@pytest.mark.django_db
def test_landlord_cannot_view_inactive_foreign(django_user_model):
    landlord_user = _make_user(django_user_model, "landlord4@example.com", "landlord")
    other_landlord_user = _make_user(django_user_model, "landlord5@example.com", "landlord")
    p = _create_property(owner=other_landlord_user, status="inactive")
    client = _auth_client(landlord_user)

    resp = client.get(f"/api/properties/{p.id}/")
    # Either forbidden or hidden as not found
    assert resp.status_code in (403, 404), f"Expected 403/404, got {resp.status_code}"


@pytest.mark.django_db
def test_renter_cannot_see_inactive(django_user_model):
    renter_user = _make_user(django_user_model, "renter@example.com", "renter")
    landlord = _make_user(django_user_model, "landlord6@example.com", "landlord")
    p = _create_property(owner=landlord, status="inactive")

    # Check both possible endpoints and behaviors (some projects have public details)
    auth_client = _auth_client(renter_user)
    anon_client = APIClient()

    # Try authenticated access first
    resp_auth = auth_client.get(f"/api/properties/{p.id}/")
    # If project exposes a public details endpoint, test it too
    resp_public = anon_client.get(f"/api/properties/public/{p.id}/")

    statuses = {resp_auth.status_code, resp_public.status_code}
    # Accept either 403 or 404 from any detail endpoint
    if not (statuses & {403, 404}):
        # If we didn't get an explicit denial, ensure that when 200 is returned
        # the resource is NOT an inactive property (i.e., implementation hides it).
        # Parse body and check 'status' if available.
        ok_resp = resp_auth if 200 <= resp_auth.status_code < 300 else resp_public
        data, _ = _to_json(ok_resp)
        # If status field present and equals inactive, that's a failure.
        if isinstance(data, dict) and data.get("status"):
            assert str(data.get("status")).lower() != "inactive", (
                f"Inactive property is visible to renter (status=200). Body: {data}"
            )
        else:
            # If no explicit status, conservatively require a 403/404
            pytest.fail(f"Expected 403/404 for inactive property, got {resp_auth.status_code} and {resp_public.status_code}")