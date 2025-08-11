# Пример тестов для отзывов.
import pytest
from django.utils import timezone
from bookings.models import Booking
from reviews.models import Review
from rest_framework.test import APIClient
from datetime import date, timedelta
from properties.models import Property

@pytest.mark.django_db
def test_cannot_review_without_finished_booking(api_client, renter_user, property_factory, auth_headers):
    prop = property_factory()  # не бронировал
    resp = api_client.post("/api/reviews/", {
        "property": prop.id,
        "rating": 5,
        "comment": "Great"
    }, **auth_headers(renter_user))
    assert resp.status_code == 400


@pytest.mark.django_db
def test_can_review_after_finished_booking(api_client, renter_user, property_factory, auth_headers):
    prop = property_factory()
    # Создаем завершённое бронирование
    Booking.objects.create(
        property=prop,
        user=renter_user,
        start_date=timezone.now().date().replace(year=timezone.now().year - 1),
        end_date=timezone.now().date().replace(year=timezone.now().year - 1, month=timezone.now().month),
        status=Booking.Status.CONFIRMED
    )
    resp = api_client.post("/api/reviews/", {
        "property": prop.id,
        "rating": 4,
        "comment": "Ok"
    }, **auth_headers(renter_user))
    assert resp.status_code == 201
    assert Review.objects.filter(property=prop, user=renter_user).exists()



@pytest.mark.django_db
class TestReviews:
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
        token = client.post("/api/token/", {"email": user.email, "password": "Pass12345"}, format="json").data["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_cannot_review_without_finished_confirmed_booking(self, renter, property_obj):
        client = APIClient()
        self.auth(client, renter)
        resp = client.post("/api/reviews/", {
            "property": property_obj.id,
            "rating": 5,
            "comment": "Отлично"
        }, format="json")
        assert resp.status_code == 400

    def test_can_review_after_finished_confirmed_booking(self, renter, landlord, property_obj):
        # Создаем подтвержденное завершившееся бронирование
        Booking.objects.create(
            property=property_obj,
            user=renter,
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() - timedelta(days=2),
            status=Booking.Status.CONFIRMED
        )
        client = APIClient()
        self.auth(client, renter)
        resp = client.post("/api/reviews/", {
            "property": property_obj.id,
            "rating": 4,
            "comment": "Хорошо"
        }, format="json")
        assert resp.status_code == 201, resp.data
        review = Review.objects.get(property=property_obj, user=renter)
        assert review.rating == 4

    def test_unique_review_constraint(self, renter, property_obj):
        Booking.objects.create(
            property=property_obj,
            user=renter,
            start_date=date.today() - timedelta(days=4),
            end_date=date.today() - timedelta(days=1),
            status=Booking.Status.CONFIRMED
        )
        client = APIClient()
        self.auth(client, renter)
        resp1 = client.post("/api/reviews/", {
            "property": property_obj.id, "rating": 5, "comment": "Первый"
        }, format="json")
        assert resp1.status_code == 201
        resp2 = client.post("/api/reviews/", {
            "property": property_obj.id, "rating": 3, "comment": "Второй"
        }, format="json")
        assert resp2.status_code in (400, 409)

    def test_only_author_can_update_or_delete(self, renter, landlord, property_obj):
        # Завершённое бронирование для renter
        Booking.objects.create(
            property=property_obj, user=renter,
            start_date=date.today() - timedelta(days=6),
            end_date=date.today() - timedelta(days=3),
            status=Booking.Status.CONFIRMED
        )
        client_r = APIClient()
        self.auth(client_r, renter)
        create_resp = client_r.post("/api/reviews/", {
            "property": property_obj.id, "rating": 5, "comment": "Супер"
        }, format="json")
        assert create_resp.status_code == 201
        review_id = create_resp.data["id"]

        # Другой пользователь (владелец) пытается изменить
        client_l = APIClient()
        self.auth(client_l, landlord)
        patch_resp = client_l.patch(f"/api/reviews/{review_id}/", {"rating": 1}, format="json")
        assert patch_resp.status_code == 403

        # Автор меняет
        patch_ok = client_r.patch(f"/api/reviews/{review_id}/", {"rating": 4}, format="json")
        assert patch_ok.status_code == 200
        del_resp = client_l.delete(f"/api/reviews/{review_id}/")
        assert del_resp.status_code == 403

    def test_review_filters_and_ordering(self, renter, property_obj):
        Booking.objects.create(
            property=property_obj,
            user=renter,
            start_date=date.today() - timedelta(days=10),
            end_date=date.today() - timedelta(days=5),
            status=Booking.Status.CONFIRMED
        )
        client = APIClient()
        self.auth(client, renter)
        for rate in [5, 3, 4]:
            client.post("/api/reviews/", {
                "property": property_obj.id, "rating": rate, "comment": f"Rate {rate}"
            }, format="json")

        resp_eq = client.get(f"/api/reviews/?property={property_obj.id}&rating=5")
        assert resp_eq.status_code == 200
        assert all(r["rating"] == 5 for r in resp_eq.data["results"])

        resp_range = client.get(f"/api/reviews/?property={property_obj.id}&rating_min=4&rating_max=5")
        assert resp_range.status_code == 200
        ratings = [r["rating"] for r in resp_range.data["results"]]
        assert set(ratings).issubset({4, 5})

        resp_order = client.get(f"/api/reviews/?property={property_obj.id}&ordering=rating")
        ratings_sorted = [r["rating"] for r in resp_order.data["results"]]
        assert ratings_sorted == sorted(ratings_sorted)