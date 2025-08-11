import pytest
from rest_framework.test import APIClient
from datetime import date, timedelta
from bookings.models import Booking
from properties.models import Property

@pytest.mark.django_db
class TestBookingFlow:
    @pytest.fixture
    def renter(self, django_user_model):
        return django_user_model.objects.create_user(
            email="renterB@example.com", password="Pass12345", role="renter",
            first_name="Rent", last_name="Er", date_of_birth="1995-01-01"
        )

    @pytest.fixture
    def landlord(self, django_user_model):
        return django_user_model.objects.create_user(
            email="landlordB@example.com", password="Pass12345", role="landlord",
            first_name="Land", last_name="Lord", date_of_birth="1990-01-01"
        )

    @pytest.fixture
    def property_active(self, landlord):
        return Property.objects.create(
            title="Квартира",
            description="Test",
            location="Berlin",
            price="1300.00",
            number_of_rooms=2,
            property_type="apartment",
            owner=landlord,
            status="active",
        )

    def auth(self, client, user):
        token = client.post("/api/token/", {"email": user.email, "password": "Pass12345"}, format="json").data["access"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_booking_success_and_overlap_pending(self, renter, property_active):
        client = APIClient()
        self.auth(client, renter)
        start = (date.today() + timedelta(days=10)).isoformat()
        end = (date.today() + timedelta(days=13)).isoformat()
        resp = client.post("/api/bookings/", {
            "property": property_active.id,
            "start_date": start,
            "end_date": end
        }, format="json")
        assert resp.status_code == 201, resp.data
        # Повторно с пересечением (ожидаем 400 при проверке overlap)
        resp2 = client.post("/api/bookings/", {
            "property": property_active.id,
            "start_date": (date.today() + timedelta(days=11)).isoformat(),
            "end_date": (date.today() + timedelta(days=12)).isoformat()
        }, format="json")
        assert resp2.status_code in (400, 422)

    def test_booking_list_visibility_renter_and_landlord(self, renter, landlord, property_active):
        # Создаём 2 бронирования от renter
        b1 = Booking.objects.create(
            property=property_active,
            user=renter,
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=7),
            status=Booking.Status.PENDING
        )
        b2 = Booking.objects.create(
            property=property_active,
            user=renter,
            start_date=date.today() + timedelta(days=8),
            end_date=date.today() + timedelta(days=9),
            status=Booking.Status.CONFIRMED
        )
        # Рентер видит свои
        client_r = APIClient()
        self.auth(client_r, renter)
        resp_r = client_r.get("/api/bookings/")
        assert resp_r.status_code == 200
        assert resp_r.data["count"] == 2

        # Владелец видит бронирования на свой объект
        client_l = APIClient()
        self.auth(client_l, landlord)
        resp_l = client_l.get("/api/bookings/")
        assert resp_l.status_code == 200
        ids = {item["id"] for item in resp_l.data["results"]}
        assert b1.id in ids and b2.id in ids

    def test_confirm_and_reject_by_owner_only(self, renter, landlord, property_active):
        booking = Booking.objects.create(
            property=property_active,
            user=renter,
            start_date=date.today() + timedelta(days=3),
            end_date=date.today() + timedelta(days=5),
            status=Booking.Status.PENDING
        )
        # Renter пытается подтвердить
        client_r = APIClient()
        self.auth(client_r, renter)
        r1 = client_r.post(f"/api/bookings/{booking.id}/confirm/")
        assert r1.status_code == 403

        # Владелец подтверждает
        client_l = APIClient()
        self.auth(client_l, landlord)
        r2 = client_l.post(f"/api/bookings/{booking.id}/confirm/")
        assert r2.status_code == 200
        booking.refresh_from_db()
        assert booking.status == Booking.Status.CONFIRMED

        # Повторное подтверждение — ошибка
        r3 = client_l.post(f"/api/bookings/{booking.id}/confirm/")
        assert r3.status_code in (400,)

    def test_cancel_before_start(self, renter, landlord, property_active):
        booking = Booking.objects.create(
            property=property_active,
            user=renter,
            start_date=date.today() + timedelta(days=6),
            end_date=date.today() + timedelta(days=8),
            status=Booking.Status.CONFIRMED,
            cancel_until=date.today() + timedelta(days=5)
        )
        client_r = APIClient()
        self.auth(client_r, renter)
        # Отмена до cancel_until
        resp = client_r.post(f"/api/bookings/{booking.id}/cancel/")
        assert resp.status_code == 200
        booking.refresh_from_db()
        assert booking.status == Booking.Status.CANCELLED

    def test_cancel_after_start_forbidden(self, renter, landlord, property_active):
        booking = Booking.objects.create(
            property=property_active,
            user=renter,
            start_date=date.today(),  # старт сегодня
            end_date=date.today() + timedelta(days=2),
            status=Booking.Status.CONFIRMED,
            cancel_until=date.today()
        )
        client_r = APIClient()
        self.auth(client_r, renter)
        resp = client_r.post(f"/api/bookings/{booking.id}/cancel/")
        # Ожидаем 400 (нельзя отменить в день начала, если бизнес-правило таково)
        assert resp.status_code in (400, 403)

    def test_reject_pending(self, renter, landlord, property_active):
        booking = Booking.objects.create(
            property=property_active,
            user=renter,
            start_date=date.today() + timedelta(days=4),
            end_date=date.today() + timedelta(days=6),
            status=Booking.Status.PENDING
        )
        client_l = APIClient()
        self.auth(client_l, landlord)
        resp = client_l.post(f"/api/bookings/{booking.id}/reject/")
        assert resp.status_code == 200
        booking.refresh_from_db()
        assert booking.status == Booking.Status.REJECTED