import pytest
from rest_framework.test import APIClient
from properties.models import Property
from reviews.models import Review
from bookings.models import Booking
from datetime import date, timedelta

@pytest.mark.django_db
def test_views_count_and_view_history(django_user_model):
    landlord = django_user_model.objects.create_user(
        email="landpop@example.com", password="Pass12345", role="landlord",
        first_name="L", last_name="Pop", date_of_birth="1990-01-01"
    )
    renter = django_user_model.objects.create_user(
        email="rentpop@example.com", password="Pass12345", role="renter",
        first_name="R", last_name="Pop", date_of_birth="1995-01-01"
    )
    prop = Property.objects.create(
        title="Popular",
        description="Desc",
        location="Berlin",
        price="1500.00",
        number_of_rooms=3,
        property_type="apartment",
        owner=landlord,
        status="active"
    )
    client = APIClient()

    # Анонимный просмотр (инкрементируем views_count, но без ViewHistory)
    r1 = client.get(f"/api/properties/public/{prop.id}/")
    assert r1.status_code == 200
    prop.refresh_from_db()
    assert prop.views_count == 1

    # Авторизованный просмотр — создаётся запись истории
    token = client.post("/api/token/", {"email": renter.email, "password": "Pass12345"}, format="json").data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    r2 = client.get(f"/api/properties/public/{prop.id}/")
    assert r2.status_code == 200
    prop.refresh_from_db()
    assert prop.views_count == 2

    from analytics.models import ViewHistory
    assert ViewHistory.objects.filter(property=prop, user=renter).count() == 1

@pytest.mark.django_db
def test_top_properties_by_views_and_reviews(django_user_model):
    landlord = django_user_model.objects.create_user(
        email="ownp@example.com", password="Pass12345", role="landlord",
        first_name="L", last_name="O", date_of_birth="1990-01-01"
    )
    renter = django_user_model.objects.create_user(
        email="rentp@example.com", password="Pass12345", role="renter",
        first_name="R", last_name="U", date_of_birth="1995-01-01"
    )
    p1 = Property.objects.create(
        title="P1", description="d", location="Berlin",
        price="1000.00", number_of_rooms=2, property_type="apartment",
        owner=landlord, status="active", views_count=10
    )
    p2 = Property.objects.create(
        title="P2", description="d", location="Berlin",
        price="1200.00", number_of_rooms=3, property_type="apartment",
        owner=landlord, status="active", views_count=5
    )

    # Добавляем завершенные бронирования -> отзывы
    Booking.objects.create(
        property=p2, user=renter,
        start_date=date.today() - timedelta(days=6),
        end_date=date.today() - timedelta(days=3),
        status=Booking.Status.CONFIRMED
    )
    # Допустим, можно оставить отзыв
    Review.objects.create(property=p2, user=renter, rating=5, comment="Great")

    client = APIClient()
    # По просмотрам
    r_views = client.get("/api/analytics/top_properties?by=views")
    assert r_views.status_code == 200
    assert r_views.data[0]["id"] == p1.id  # у p1 больше views_count

    # По отзывам
    r_reviews = client.get("/api/analytics/top_properties?by=reviews")
    assert r_reviews.status_code == 200
    assert r_reviews.data[0]["id"] == p2.id  # у p2 есть 1 отзыв

@pytest.mark.django_db
def test_popular_searches_order(django_user_model):
    user = django_user_model.objects.create_user(
        email="usersearch@example.com", password="Pass12345", role="renter",
        first_name="U", last_name="S", date_of_birth="1995-01-01"
    )
    client = APIClient()
    token = client.post("/api/token/", {"email": user.email, "password": "Pass12345"}, format="json").data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # Имитируем разные поиски
    for q in ["Berlin", "Hamburg", "Berlin", "Munich", "Berlin", "Munich"]:
        client.get(f"/api/properties/public/?search={q}")

    resp = client.get("/api/analytics/popular_searches?limit=3")
    assert resp.status_code == 200
    # Berlin должно быть первым (чаще всего)
    queries = [row["search_query"] for row in resp.data]
    assert queries[0].lower() == "berlin"