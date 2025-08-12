import pytest
from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIRequestFactory

from analytics.views import TopPropertiesView, PopularSearchesView, analytics_root
from analytics.models import SearchHistory
from properties.models import Property

# Если в проекте есть модель отзывов (обычно reviews.Review), используем её для подсчёта.
try:
    from reviews.models import Review
except Exception:
    Review = None

User = get_user_model()


def make_user(email="user@example.com", password="InitPass!234", **extra):
    data = {
        "email": email,
        "password": password,
        "first_name": extra.pop("first_name", ""),
        "last_name": extra.pop("last_name", ""),
        "role": extra.pop("role", getattr(User.Roles, "RENTER", "renter")),
        "date_of_birth": extra.pop("date_of_birth", date(1990, 1, 1)),
        **extra,
    }
    user = User.objects.create_user(
        email=data["email"],
        password=data["password"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        role=data["role"],
        date_of_birth=data["date_of_birth"],
    )
    return user


def make_property(owner, title, views_count=0):
    return Property.objects.create(
        title=title,
        description="desc",
        location="City",
        price="1000.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status="active",
        views_count=views_count,
    )


@pytest.mark.django_db
class TestAnalyticsViews:
    def setup_method(self):
        self.factory = APIRequestFactory()

    def test_top_properties_by_views_default(self):
        owner = make_user(email="owner@example.com", password=None)
        p1 = make_property(owner, "P1", views_count=5)
        p2 = make_property(owner, "P2", views_count=10)
        p3 = make_property(owner, "P3", views_count=7)

        req = self.factory.get("/api/analytics/top-properties/")  # by=views по умолчанию
        resp = TopPropertiesView.as_view()(req)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data
        # Проверка порядка по убыванию views_count
        assert [row["id"] for row in data] == [p2.id, p3.id, p1.id]
        assert all("views_count" in row and "title" in row for row in data)

    def test_top_properties_by_reviews_with_limit(self):
        owner = make_user(email="owner2@example.com", password=None)
        top = make_property(owner, "Top", views_count=1)
        low = make_property(owner, "Low", views_count=999)

        # Поднимаем счётчик отзывов: у top больше, чем у low
        if Review is not None:
            # Создаём разных пользователей, т.к. unique (property,user)
            u1 = make_user(email="r1@example.com", password=None)
            u2 = make_user(email="r2@example.com", password=None)
            u3 = make_user(email="r3@example.com", password=None)
            Review.objects.create(property=top, user=u1, rating=5, comment="ok")
            Review.objects.create(property=top, user=u2, rating=4, comment="ok")
            Review.objects.create(property=top, user=u3, rating=3, comment="ok")
            u4 = make_user(email="r4@example.com", password=None)
            Review.objects.create(property=low, user=u4, rating=5, comment="ok")

        req = self.factory.get("/api/analytics/top-properties/?by=reviews&limit=1")
        resp = TopPropertiesView.as_view()(req)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data
        assert len(data) == 1
        # Должен быть топ по числу отзывов (поле reviews_count приходит из annotate)
        assert data[0]["id"] == top.id
        assert "reviews_count" in data[0]

    def test_popular_searches_with_limit(self):
        u = make_user(email="searcher@example.com", password=None)
        # 5 раз один запрос, 2 раза другой
        for _ in range(5):
            SearchHistory.objects.create(user=u, search_query="flat berlin")
        for _ in range(2):
            SearchHistory.objects.create(user=u, search_query="house")

        req = self.factory.get("/api/analytics/popular-searches/?limit=1")
        resp = PopularSearchesView.as_view()(req)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data
        assert len(data) == 1
        assert data[0]["query"] == "flat berlin"
        assert data[0]["count"] == 5

    def test_analytics_root_links(self):
        req = self.factory.get("/api/analytics/")
        resp = analytics_root(req)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.data
        for key in ("top_properties", "popular_searches"):
            assert key in data
            val = data[key]
            assert isinstance(val, str)
            # DRF reverse с request возвращает абсолютные URL — допускаем оба формата
            assert val.startswith("/") or val.startswith("http")