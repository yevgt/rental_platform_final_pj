import pytest
from datetime import date, timedelta
from types import SimpleNamespace

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils import timezone

from bookings.admin import BookingAdmin, MessageAdmin
from bookings.models import Booking, Message
from properties.models import Property

User = get_user_model()


def _make_user(email):
    # password и прочие поля здесь не важны
    return User.objects.create_user(email=email, password=None)


def _make_property(owner, title="Flat"):
    return Property.objects.create(
        title=title,
        description="Center",
        location="Berlin",
        price="1000.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status="active",
    )


@pytest.mark.django_db
def test_booking_admin_owner_email_returns_owner_email_and_none():
    owner = _make_user("owner@example.com")
    renter = _make_user("renter@example.com")
    prop = _make_property(owner)

    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=1),
        status=Booking.Status.PENDING,
        monthly_rent=prop.price,
        total_amount=prop.price,
    )

    admin_obj = BookingAdmin(Booking, admin.site)

    # Основной путь — почта владельца объявления
    assert admin_obj.owner_email(booking) == owner.email

    # Резервный путь — когда нет ни property, ни owner → None
    dummy = SimpleNamespace()
    assert admin_obj.owner_email(dummy) is None


@pytest.mark.django_db
def test_message_admin_timestamp_created_at_and_sent_at_fallback():
    owner = _make_user("owner2@example.com")
    renter = _make_user("renter2@example.com")
    prop = _make_property(owner, title="Another")

    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        status=Booking.Status.PENDING,
        monthly_rent=prop.price,
        total_amount=prop.price,
    )

    msg = Message.objects.create(booking=booking, sender=owner, receiver=renter)
    admin_obj = MessageAdmin(Message, admin.site)

    # Основной путь — у реального Message есть created_at
    ts1 = admin_obj.timestamp(msg)
    assert ts1 is not None

    # Ветвь-фолбэк — объекта с created_at нет, но есть sent_at
    dummy = SimpleNamespace(sent_at=timezone.now())
    ts2 = admin_obj.timestamp(dummy)
    assert ts2 == dummy.sent_at