# Пример тестов фильтра/поиска/сортировки.
import pytest


@pytest.mark.django_db
def test_search_in_title_description_location(api_client, property_factory):
    p1 = property_factory(title="Светлая квартира", description="уютная", location="Berlin Mitte")
    p2 = property_factory(title="Дом у озера", description="lake view", location="Hamburg")
    resp = api_client.get("/api/properties/?search=Berlin")
    ids = {x["id"] for x in resp.json()["results"]} if "results" in resp.json() else {x["id"] for x in resp.json()}
    assert p1.id in ids and p2.id not in ids


@pytest.mark.django_db
def test_filter_price_and_rooms(api_client, property_factory):
    property_factory(price=500, number_of_rooms=1)
    p_ok = property_factory(price=1500, number_of_rooms=3)
    property_factory(price=4000, number_of_rooms=5)
    resp = api_client.get("/api/properties/?price_min=1000&price_max=2000&rooms_min=2&rooms_max=3")
    ids = {x["id"] for x in resp.json()["results"]} if "results" in resp.json() else {x["id"] for x in resp.json()}
    assert p_ok.id in ids