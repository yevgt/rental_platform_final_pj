import pytest
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from rest_framework.test import APIRequestFactory

from bookings.models import Booking
from bookings.serializers import BookingSerializer
from properties.models import Property

User = get_user_model()


def make_user(email="user@example.com"):
    return User.objects.create_user(email=email, password=None)


def make_property(owner, title="Flat", price="1000.00", status="active"):
    return Property.objects.create(
        title=title,
        description="Nice",
        location="City",
        price=price,
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status=status,
    )


@pytest.mark.django_db
def test_validate_missing_dates_raises():
    owner = make_user("o1@example.com")
    prop = make_property(owner)

    data = {
        "property": prop.id,
        # "start_date" отсутствует, упадёт на обязательности поля у DRF
        "end_date": (timezone.now().date() + timedelta(days=10)).isoformat(),
    }
    ser = BookingSerializer(data=data)
    assert not ser.is_valid()
    assert "start_date" in ser.errors


@pytest.mark.django_db
def test_validate_start_ge_end_raises():
    owner = make_user("o2@example.com")
    prop = make_property(owner)
    start = timezone.now().date() + timedelta(days=5)
    data = {
        "property": prop.id,
        "start_date": start.isoformat(),
        "end_date": start.isoformat(),  # start == end
    }
    ser = BookingSerializer(data=data)
    with pytest.raises(serializers.ValidationError) as exc:
        ser.is_valid(raise_exception=True)
    assert "раньше end_date" in str(exc.value)


@pytest.mark.django_db
def test_validate_start_in_past_raises():
    owner = make_user("o3@example.com")
    prop = make_property(owner)
    today = timezone.now().date()
    data = {
        "property": prop.id,
        "start_date": (today - timedelta(days=1)).isoformat(),
        "end_date": (today + timedelta(days=5)).isoformat(),
    }
    ser = BookingSerializer(data=data)
    with pytest.raises(serializers.ValidationError) as exc:
        ser.is_valid(raise_exception=True)
    assert "прошедшие даты" in str(exc.value)


@pytest.mark.django_db
def test_validate_inactive_property_raises():
    owner = make_user("o4@example.com")
    prop = make_property(owner, status="active")
    # Сделаем объект неактивным
    prop.status = "inactive"
    prop.save(update_fields=["status"])

    today = timezone.now().date()
    data = {
        "property": prop.id,
        "start_date": (today + timedelta(days=5)).isoformat(),
        "end_date": (today + timedelta(days=10)).isoformat(),
    }
    ser = BookingSerializer(data=data)
    with pytest.raises(serializers.ValidationError) as exc:
        ser.is_valid(raise_exception=True)
    assert "неактивное объявление" in str(exc.value)


@pytest.mark.django_db
def test_validate_overlap_raises():
    owner = make_user("o5@example.com")
    renter1 = make_user("r5a@example.com")
    prop = make_property(owner)

    today = timezone.now().date()
    # Существующая бронь с пересечением
    Booking.objects.create(
        property=prop,
        user=renter1,
        start_date=today + timedelta(days=5),
        end_date=today + timedelta(days=15),
        monthly_rent=Decimal(str(prop.price)) if not isinstance(prop.price, Decimal) else prop.price,
        total_amount=Decimal(str(prop.price)) if not isinstance(prop.price, Decimal) else prop.price,
        status=Booking.Status.CONFIRMED,
    )

    # Новая заявка пересекается: [10, 20] пересекает [5, 15]
    data = {
        "property": prop.id,
        "start_date": (today + timedelta(days=10)).isoformat(),
        "end_date": (today + timedelta(days=20)).isoformat(),
    }
    ser = BookingSerializer(data=data)
    with pytest.raises(serializers.ValidationError) as exc:
        ser.is_valid(raise_exception=True)
    assert "уже есть подтверждённое бронирование" in str(exc.value)


@pytest.mark.django_db
def test_create_owner_cannot_book_raises():
    owner = make_user("owner@example.com")
    prop = make_property(owner)

    factory = APIRequestFactory()
    req = factory.post("/api/bookings/create/")
    req.user = owner  # владелец

    today = timezone.now().date()
    ser = BookingSerializer(
        data={
            "property": prop.id,
            "start_date": (today + timedelta(days=10)).isoformat(),
            "end_date": (today + timedelta(days=40)).isoformat(),
        },
        context={"request": req},
    )
    assert ser.is_valid(), ser.errors
    with pytest.raises(serializers.ValidationError) as exc:
        ser.save()
    assert "Владелец не может бронировать" in str(exc.value)


@pytest.mark.django_db
def test_create_uses_price_monthly_and_sets_cancel_until():
    owner = make_user("o6@example.com")
    renter = make_user("r6@example.com")
    prop = make_property(owner, price="1500.00")

    # Добавим динамический атрибут на конкретный экземпляр (не хранится в БД)
    prop.price_monthly = Decimal("2000.00")

    factory = APIRequestFactory()
    req = factory.post("/api/bookings/create/")
    req.user = renter

    start = timezone.now().date() + timedelta(days=10)
    end = start + timedelta(days=61)  # ~2 месяца

    ser = BookingSerializer(
        data={
            "property": prop.id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        context={"request": req},
    )

    # Важно: заменить queryset у поля property так, чтобы .get(...) вернул наш prop с price_monthly
    class _QS:
        def get(self, *args, **kwargs):
            return prop

    ser.fields["property"].queryset = _QS()

    assert ser.is_valid(), ser.errors
    booking = ser.save()

    # Использован price_monthly, а не price
    assert booking.monthly_rent == Decimal("2000.00")

    # Проверяем расчёт total_amount по формуле в сериализаторе
    days = (end - start).days
    months = Decimal(days) / Decimal("30.44")
    expected_total = (Decimal("2000.00") * months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert booking.total_amount == expected_total

    # cancel_until = start_date
    assert booking.cancel_until == start
    assert booking.status == Booking.Status.PENDING
    assert booking.user == renter


@pytest.mark.django_db
def test_create_fallback_to_price_when_no_price_monthly():
    owner = make_user("o7@example.com")
    renter = make_user("r7@example.com")
    prop = make_property(owner, price="1200.00")  # нет price_monthly у модели

    factory = APIRequestFactory()
    req = factory.post("/api/bookings/create/")
    req.user = renter

    start = timezone.now().date() + timedelta(days=10)
    end = start + timedelta(days=30)

    ser = BookingSerializer(
        data={
            "property": prop.id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        context={"request": req},
    )
    assert ser.is_valid(), ser.errors
    booking = ser.save()

    # Приводим к Decimal, т.к. prop.price в проекте — строка
    expected_monthly = Decimal(str(prop.price)) if not isinstance(prop.price, Decimal) else prop.price
    assert booking.monthly_rent == expected_monthly

    days = (end - start).days
    months = Decimal(days) / Decimal("30.44")
    expected_total = (expected_monthly * months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert booking.total_amount == expected_total