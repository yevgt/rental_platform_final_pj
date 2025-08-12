# Пример тестов для отзывов (универсальные фикстуры и хелперы, без внешних factory/fixtures).

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from bookings.models import Booking
from properties.models import Property
from reviews.models import Review


# ---------- Helpers ----------

def _json(resp):
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


def _list_items(resp):
    data = _json(resp)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "data", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        if "id" in data:
            return [data]
    return []


def _count_items(resp):
    data = _json(resp)
    if isinstance(data, dict) and "count" in data:
        try:
            return int(data["count"])
        except Exception:
            pass
    return len(_list_items(resp))


def _auth(client: APIClient, user):
    # Пытаемся получить JWT-токен
    token = None
    try:
        resp = client.post("/api/token/", {"email": user.email, "password": "Pass12345"}, format="json")
        if getattr(resp, "status_code", None) == 200:
            payload = getattr(resp, "data", {}) or _json(resp) or {}
            for key in ("access", "token", "access_token", "key"):
                if payload and isinstance(payload, dict) and payload.get(key):
                    token = payload[key]
                    break
    except Exception:
        pass

    if token:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # На всякий случай активируем принудительную аутентификацию
    try:
        client.force_authenticate(user=user)
    except Exception:
        pass


def _ensure_decimal(val) -> Decimal:
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def _create_finished_booking(prop: Property, user, start_days_ago=5, end_days_ago=2, status=None):
    """
    Создаёт завершившееся бронирование c обязательными полями (monthly_rent/total_amount).
    """
    start = date.today() - timedelta(days=start_days_ago)
    end = date.today() - timedelta(days=end_days_ago)
    monthly_rent = _ensure_decimal(prop.price)
    total_amount = monthly_rent

    return Booking.objects.create(
        property=prop,
        user=user,
        start_date=start,
        end_date=end,
        monthly_rent=monthly_rent,
        total_amount=total_amount,
        status=status or getattr(Booking.Status, "CONFIRMED", "confirmed"),
    )


# ---------- Module-level tests (без внешних fixtures) ----------

@pytest.mark.django_db
def test_cannot_review_without_finished_booking(django_user_model):
    renter = django_user_model.objects.create_user(
        email="renter0@example.com", password="Pass12345", role="renter",
        first_name="R", last_name="U", date_of_birth="1990-01-01"
    )
    landlord = django_user_model.objects.create_user(
        email="landlord0@example.com", password="Pass12345", role="landlord",
        first_name="L", last_name="O", date_of_birth="1988-01-01"
    )
    prop = Property.objects.create(
        title="NoBooking",
        description="Desc",
        location="City",
        price="1200.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=landlord,
        status="active",
    )
    client = APIClient()
    _auth(client, renter)
    resp = client.post("/api/reviews/", {"property": prop.id, "rating": 5, "comment": "Great"}, format="json")
    assert resp.status_code in (400, 403), f"Expected 400/403, got {resp.status_code}, body={_json(resp)}"


@pytest.mark.django_db
def test_can_review_after_finished_booking(django_user_model):
    renter = django_user_model.objects.create_user(
        email="renter1@example.com", password="Pass12345", role="renter",
        first_name="R", last_name="U", date_of_birth="1990-01-01"
    )
    landlord = django_user_model.objects.create_user(
        email="landlord1@example.com", password="Pass12345", role="landlord",
        first_name="L", last_name="O", date_of_birth="1988-01-01"
    )
    prop = Property.objects.create(
        title="WithBooking",
        description="Desc",
        location="City",
        price="1400.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=landlord,
        status="active",
    )
    _create_finished_booking(prop, renter, start_days_ago=10, end_days_ago=3)
    client = APIClient()
    _auth(client, renter)
    resp = client.post("/api/reviews/", {"property": prop.id, "rating": 4, "comment": "Ok"}, format="json")
    assert resp.status_code in (201, 200), f"Unexpected status: {resp.status_code}, body={_json(resp)}"
    assert Review.objects.filter(property=prop, user=renter).exists()


# ---------- Class-based tests ----------

@pytest.mark.django_db
class TestReviews:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def landlord(self, django_user_model):
        return django_user_model.objects.create_user(
            email="landlordR@example.com", password="Pass12345", role="landlord",
            first_name="LL", last_name="Owner", date_of_birth="1988-01-01"
        )

    @pytest.fixture
    def renter(self, django_user_model):
        return django_user_model.objects.create_user(
            email="renterR@example.com", password="Pass12345", role="renter",
            first_name="RR", last_name="User", date_of_birth="1992-01-01"
        )

    @pytest.fixture
    def property_obj(self, landlord):
        return Property.objects.create(
            title="Flat",
            description="Desc",
            location="Berlin",
            price="1400.00",
            number_of_rooms=2,
            property_type="apartment",
            owner=landlord,
            status="active"
        )

    def auth(self, client, user):
        _auth(client, user)

    def test_cannot_review_without_finished_confirmed_booking(self, renter, property_obj):
        client = APIClient()
        self.auth(client, renter)
        resp = client.post("/api/reviews/", {
            "property": property_obj.id,
            "rating": 5,
            "comment": "Отлично"
        }, format="json")
        assert resp.status_code in (400, 403), f"Expected 400/403, got {resp.status_code}, body={_json(resp)}"

    def test_can_review_after_finished_confirmed_booking(self, renter, landlord, property_obj):
        # Создаем подтвержденное завершившееся бронирование
        _create_finished_booking(property_obj, renter, start_days_ago=5, end_days_ago=2)
        client = APIClient()
        self.auth(client, renter)
        resp = client.post("/api/reviews/", {
            "property": property_obj.id,
            "rating": 4,
            "comment": "Хорошо"
        }, format="json")
        assert resp.status_code in (201, 200), _json(resp)
        review = Review.objects.get(property=property_obj, user=renter)
        assert review.rating == 4

    def test_unique_review_constraint(self, renter, property_obj):
        _create_finished_booking(property_obj, renter, start_days_ago=4, end_days_ago=1)
        client = APIClient()
        self.auth(client, renter)
        resp1 = client.post("/api/reviews/", {
            "property": property_obj.id, "rating": 5, "comment": "Первый"
        }, format="json")
        assert resp1.status_code in (201, 200), _json(resp1)
        resp2 = client.post("/api/reviews/", {
            "property": property_obj.id, "rating": 3, "comment": "Второй"
        }, format="json")
        # Ожидаем запрет на второй отзыв
        assert resp2.status_code in (400, 409), f"Expected 400/409, got {resp2.status_code}, body={_json(resp2)}"

    def test_only_author_can_update_or_delete(self, renter, landlord, property_obj):
        # Завершённое бронирование для renter
        _create_finished_booking(property_obj, renter, start_days_ago=6, end_days_ago=3)
        client_r = APIClient()
        self.auth(client_r, renter)
        create_resp = client_r.post("/api/reviews/", {
            "property": property_obj.id, "rating": 5, "comment": "Супер"
        }, format="json")
        assert create_resp.status_code in (201, 200), _json(create_resp)
        created_payload = _json(create_resp) or {}
        review_id = created_payload.get("id")
        if not review_id:
            # если id не вернулся — найдём по последнему созданному
            review_id = Review.objects.filter(property=property_obj, user=renter).order_by("-id").values_list("id", flat=True).first()
        assert review_id, f"Review id not found. payload={created_payload}"

        # Другой пользователь (владелец) пытается изменить
        client_l = APIClient()
        self.auth(client_l, landlord)
        patch_resp = client_l.patch(f"/api/reviews/{review_id}/", {"rating": 1}, format="json")
        assert patch_resp.status_code in (403, 404), f"Expected 403/404, got {patch_resp.status_code}, body={_json(patch_resp)}"

        # Автор меняет
        patch_ok = client_r.patch(f"/api/reviews/{review_id}/", {"rating": 4}, format="json")
        assert patch_ok.status_code in (200, 202), f"Unexpected: {patch_ok.status_code}, body={_json(patch_ok)}"

        # Владельцу также нельзя удалять
        del_resp = client_l.delete(f"/api/reviews/{review_id}/")
        assert del_resp.status_code in (403, 404), f"Expected 403/404, got {del_resp.status_code}"

    def test_review_filters_and_ordering(self, renter, property_obj, django_user_model):
        """
        Проверяем фильтры и сортировку по рейтингу.
        Из-за ограничения 1 отзыв на пользователя на объявление создаём отзывы от разных пользователей.
        """
        # Бронирование и отзыв от renter (рейтинг 5)
        _create_finished_booking(property_obj, renter, start_days_ago=10, end_days_ago=5)
        c1 = APIClient()
        self.auth(c1, renter)
        r1 = c1.post("/api/reviews/", {"property": property_obj.id, "rating": 5, "comment": "Rate 5"}, format="json")
        assert r1.status_code in (201, 200), _json(r1)

        # Второй пользователь-арендатор
        renter2 = django_user_model.objects.create_user(
            email="renterR2@example.com", password="Pass12345", role="renter",
            first_name="R2", last_name="User2", date_of_birth="1991-02-02"
        )
        _create_finished_booking(property_obj, renter2, start_days_ago=9, end_days_ago=4)
        c2 = APIClient()
        self.auth(c2, renter2)
        r2 = c2.post("/api/reviews/", {"property": property_obj.id, "rating": 3, "comment": "Rate 3"}, format="json")
        assert r2.status_code in (201, 200), _json(r2)

        # Третий пользователь-арендатор
        renter3 = django_user_model.objects.create_user(
            email="renterR3@example.com", password="Pass12345", role="renter",
            first_name="R3", last_name="User3", date_of_birth="1993-03-03"
        )
        _create_finished_booking(property_obj, renter3, start_days_ago=8, end_days_ago=3)
        c3 = APIClient()
        self.auth(c3, renter3)
        r3 = c3.post("/api/reviews/", {"property": property_obj.id, "rating": 4, "comment": "Rate 4"}, format="json")
        assert r3.status_code in (201, 200), _json(r3)

        # Фильтр: rating == 5
        resp_eq = c1.get(f"/api/reviews/?property={property_obj.id}&rating=5")
        assert resp_eq.status_code == 200
        eq_items = _list_items(resp_eq)
        assert all(it.get("rating") == 5 for it in eq_items), f"Unexpected ratings: {eq_items}"

        # Фильтр: rating_min..rating_max
        resp_range = c1.get(f"/api/reviews/?property={property_obj.id}&rating_min=4&rating_max=5")
        assert resp_range.status_code == 200
        range_items = _list_items(resp_range)
        ratings = [it.get("rating") for it in range_items]
        assert set(ratings).issubset({4, 5})

        # Сортировка по рейтингу (возрастание)
        resp_order = c1.get(f"/api/reviews/?property={property_obj.id}&ordering=rating")
        assert resp_order.status_code == 200
        ord_items = _list_items(resp_order)
        ratings_sorted = [it.get("rating") for it in ord_items]
        assert ratings_sorted == sorted(ratings_sorted), f"Not sorted asc: {ratings_sorted}"