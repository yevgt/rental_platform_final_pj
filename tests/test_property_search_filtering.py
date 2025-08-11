import pytest
from rest_framework.test import APIClient
from properties.models import Property

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
    titles = [r["title"] for r in resp.data["results"]]
    assert "Loft Berlin" in titles
    assert "Small room" in titles
    assert "Haus Hamburg" not in titles

    # Фильтр по цене
    resp2 = client.get("/api/properties/public/?price_min=1000&price_max=2000")
    assert resp2.status_code == 200
    assert resp2.data["count"] == 1
    assert resp2.data["results"][0]["title"] == "Loft Berlin"

    # Фильтр по типу
    resp3 = client.get("/api/properties/public/?property_type=house")
    assert resp3.status_code == 200
    assert resp3.data["count"] == 1
    assert resp3.data["results"][0]["title"] == "Haus Hamburg"

    # Сортировка по цене (убывание)
    resp4 = client.get("/api/properties/public/?ordering=-price")
    assert resp4.status_code == 200
    prices = [p["price"] for p in resp4.data["results"]]
    assert prices == sorted(prices, reverse=True)

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