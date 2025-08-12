import json
from decimal import Decimal
from urllib.parse import urlencode

import pytest
from rest_framework.test import APIClient

from properties.models import Property


def _extract_ids(resp):
    try:
        data = resp.json()
    except Exception:
        try:
            raw = getattr(resp, "content", b"")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            data = json.loads(raw)
        except Exception:
            return set()

    if isinstance(data, list):
        return {item.get("id") for item in data if isinstance(item, dict) and "id" in item}
    if isinstance(data, dict):
        # Common pagination containers
        for key in ("results", "data", "items"):
            if isinstance(data.get(key), list):
                return {item.get("id") for item in data[key] if isinstance(item, dict) and "id" in item}
        # Sometimes a single object is returned
        if "id" in data:
            return {data.get("id")}
    return set()


def _make_owner(django_user_model, email="landlord@example.com"):
    return django_user_model.objects.create_user(
        email=email,
        password="Pass12345",
        role="landlord",
        first_name="L",
        last_name="O",
        date_of_birth="1990-01-01",
    )


def _create_property(owner, **kw):
    defaults = dict(
        title="Test Property",
        description="Nice place",
        location="Berlin",
        price=Decimal("1000.00"),
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status="active",
    )
    defaults.update(kw)
    # Ensure price is Decimal
    if isinstance(defaults["price"], (int, float, str)):
        defaults["price"] = Decimal(str(defaults["price"]))
    return Property.objects.create(**defaults)


@pytest.mark.django_db
def test_search_in_title_description_location(django_user_model):
    owner = _make_owner(django_user_model, "landlord+search@example.com")
    p1 = _create_property(owner, title="Светлая квартира", description="уютная", location="Berlin Mitte")
    p2 = _create_property(owner, title="Дом у озера", description="lake view", location="Hamburg")

    client = APIClient()

    # Try multiple endpoints and param names used in various implementations
    endpoints = [
        "/api/properties/",
        "/api/properties/public/",
        "/api/properties/search/",
    ]
    search_param_keys = ["search", "q", "query", "term"]

    debug = []
    for ep in endpoints:
        for key in search_param_keys:
            url = f"{ep}?{urlencode({key: 'Berlin'})}"
            resp = client.get(url, follow=True)
            ids = _extract_ids(resp)
            if p1.id in ids and p2.id not in ids:
                return
            debug.append((url, resp.status_code, ids))

    raise AssertionError(f"Search mismatch. Tried: {debug}")


@pytest.mark.django_db
def test_filter_price_and_rooms(django_user_model):
    owner = _make_owner(django_user_model, "landlord+filters@example.com")
    _create_property(owner, price=Decimal("500.00"), number_of_rooms=1)
    p_ok = _create_property(owner, price=Decimal("1500.00"), number_of_rooms=3)
    _create_property(owner, price=Decimal("4000.00"), number_of_rooms=5)

    client = APIClient()

    endpoints = [
        "/api/properties/",
        "/api/properties/public/",
        "/api/properties/search/",
    ]
    price_min_keys = ["price_min", "min_price", "price_from", "minPrice"]
    price_max_keys = ["price_max", "max_price", "price_to", "maxPrice"]
    rooms_min_keys = ["rooms_min", "min_rooms", "rooms_from", "minRooms"]
    rooms_max_keys = ["rooms_max", "max_rooms", "rooms_to", "maxRooms"]

    debug = []
    for ep in endpoints:
        for k1 in price_min_keys:
            for k2 in price_max_keys:
                for k3 in rooms_min_keys:
                    for k4 in rooms_max_keys:
                        params = {k1: 1000, k2: 2000, k3: 2, k4: 3}
                        url = f"{ep}?{urlencode(params)}"
                        resp = client.get(url, follow=True)
                        ids = _extract_ids(resp)
                        if p_ok.id in ids:
                            return
                        debug.append((url, resp.status_code, sorted(ids)))

    raise AssertionError(f"Filtered property {p_ok.id} not found. Tried: {debug[:10]} ... total={len(debug)} attempts")