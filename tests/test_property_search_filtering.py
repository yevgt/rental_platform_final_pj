import json
from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from properties.models import Property

def _json(resp):
    # Универсальный парсер JSON для DRF Response и обычного HttpResponse
    try:
        return resp.json()
    except Exception:
        try:
            raw = getattr(resp, "content", b"")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            return json.loads(raw)
        except Exception:
            return None


def _items_from_payload(data):
    """
    Возвращает список элементов из возможных форматов ответа:
    - список (list)
    - словарь с ключами results/data/items
    - одиночный объект (dict с полем id) -> оборачиваем в список
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "data", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        if "id" in data:
            return [data]
    return []


def _get_items(resp):
    return _items_from_payload(_json(resp))


def _get_count(resp):
    data = _json(resp)
    if isinstance(data, dict) and "count" in data:
        try:
            return int(data["count"])
        except Exception:
            return len(_items_from_payload(data))
    return len(_items_from_payload(data))


@pytest.mark.django_db
def test_search_and_filters(django_user_model):
    landlord = django_user_model.objects.create_user(
        email="landowner@example.com", password="Pass12345", role="landlord",
        first_name="L", last_name="O", date_of_birth="1990-01-01"
    )
    Property.objects.bulk_create([
        Property(
            title="Loft Berlin",
            description="Высокие потолки",
            location="Berlin Mitte",
            price="1500.00",
            number_of_rooms=2,
            property_type="apartment",
            owner=landlord,
            status=Property.Status.ACTIVE,
        ),
        Property(
            title="Haus Hamburg",
            description="Сад и гараж",
            location="Hamburg Nord",
            price="2500.00",
            number_of_rooms=5,
            property_type="house",
            owner=landlord,
            status=Property.Status.ACTIVE,
        ),
        Property(
            title="Small room",
            description="Cheap",
            location="Berlin Neukölln",
            price="600.00",
            number_of_rooms=1,
            property_type="room",
            owner=landlord,
            status=Property.Status.ACTIVE,
        ),
    ])

    client = APIClient()

    # Поиск по ключевому слову title/description/location
    resp = client.get("/api/properties/public/?search=Berlin")
    assert resp.status_code == 200
    items = _get_items(resp)
    titles = [r.get("title") for r in items]
    assert "Loft Berlin" in titles
    assert "Small room" in titles
    assert "Haus Hamburg" not in titles

    # Фильтр по цене
    resp2 = client.get("/api/properties/public/?price_min=1000&price_max=2000")
    assert resp2.status_code == 200
    count2 = _get_count(resp2)
    items2 = _get_items(resp2)
    assert count2 == 1, f"Ожидался 1 объект, получили {count2} (items={items2})"
    assert items2[0].get("title") == "Loft Berlin"

    # Фильтр по типу
    resp3 = client.get("/api/properties/public/?property_type=house")
    assert resp3.status_code == 200
    count3 = _get_count(resp3)
    items3 = _get_items(resp3)
    assert count3 == 1
    assert items3[0].get("title") == "Haus Hamburg"

    # Сортировка по цене (убывание)
    resp4 = client.get("/api/properties/public/?ordering=-price")
    assert resp4.status_code == 200
    items4 = _get_items(resp4)
    prices = []
    for p in items4:
        val = p.get("price")
        try:
            prices.append(Decimal(str(val)))
        except Exception:
            # если пришёл нечисловой формат, провалимся на сравнение строк
            prices.append(val)
    assert prices == sorted(prices, reverse=True), f"Неверная сортировка: {prices}"

@pytest.mark.django_db
def test_search_history_saved_only_for_authenticated(django_user_model):
    user = django_user_model.objects.create_user(
        email="renter@example.com", password="Pass12345", role="renter",
        first_name="R", last_name="U", date_of_birth="1995-01-01"
    )
    from analytics.models import SearchHistory
    client = APIClient()

    # Анонимный поиск — запись не создаём
    resp = client.get("/api/properties/public/?search=Berlin")
    assert resp.status_code == 200
    assert SearchHistory.objects.count() == 0

    # Авторизованный — запись создаём
    token = client.post("/api/token/", {"email": user.email, "password": "Pass12345"}, format="json").data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    resp2 = client.get("/api/properties/public/?search=Hamburg")
    assert resp2.status_code == 200
    assert SearchHistory.objects.count() == 1
    sh = SearchHistory.objects.first()
    assert sh.search_query.lower() == "hamburg"