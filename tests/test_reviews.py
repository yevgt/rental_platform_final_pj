# Пример тестов для отзывов.
import pytest
from django.utils import timezone
from bookings.models import Booking
from reviews.models import Review


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