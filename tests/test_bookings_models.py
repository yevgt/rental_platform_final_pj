import pytest
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from properties.models import Property
from bookings.models import Booking, Message

User = get_user_model()


def make_user(email="user@example.com"):
    return User.objects.create_user(email=email, password=None)


def make_property(owner, title="Flat", price="1000.00"):
    return Property.objects.create(
        title=title,
        description="Nice",
        location="City",
        price=price,
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status="active",
    )


@pytest.mark.django_db
def test_booking_and_message_str():
    owner = make_user("owner@example.com")
    renter = make_user("renter@example.com")
    prop = make_property(owner)

    today = timezone.now().date()
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today + timedelta(days=5),
        end_date=today + timedelta(days=35),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.PENDING,
    )
    assert str(booking) == f"Booking #{booking.id} {booking.property_id} by {booking.user_id} [{booking.status}]"

    msg = Message.objects.create(
        booking=booking,
        sender=owner,
        receiver=renter,
        text="Hello",
    )
    assert str(msg) == f"Msg b#{booking.id} from {owner.id} to {renter.id}"


@pytest.mark.django_db
def test_can_cancel_true_before_start_and_no_cancel_limit():
    owner = make_user("o1@example.com")
    renter = make_user("r1@example.com")
    prop = make_property(owner)
    today = timezone.now().date()

    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today + timedelta(days=10),
        end_date=today + timedelta(days=40),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.PENDING,
        cancel_until=None,
    )
    assert booking.can_cancel(today=today) is True


@pytest.mark.django_db
def test_can_cancel_false_if_status_not_pending_or_confirmed():
    owner = make_user("o2@example.com")
    renter = make_user("r2@example.com")
    prop = make_property(owner)
    today = timezone.now().date()

    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today + timedelta(days=10),
        end_date=today + timedelta(days=40),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.CANCELLED,
    )
    assert booking.can_cancel(today=today) is False


@pytest.mark.django_db
def test_can_cancel_false_if_today_ge_start_date():
    owner = make_user("o3@example.com")
    renter = make_user("r3@example.com")
    prop = make_property(owner)
    today = timezone.now().date()

    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today,  # сегодня уже старт
        end_date=today + timedelta(days=30),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.PENDING,
    )
    assert booking.can_cancel(today=today) is False


@pytest.mark.django_db
def test_can_cancel_false_if_cancel_until_passed():
    owner = make_user("o4@example.com")
    renter = make_user("r4@example.com")
    prop = make_property(owner)
    today = timezone.now().date()

    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today + timedelta(days=10),
        end_date=today + timedelta(days=40),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.CONFIRMED,
        cancel_until=today - timedelta(days=1),  # срок отмены прошёл
    )
    assert booking.can_cancel(today=today) is False


@pytest.mark.django_db
def test_can_cancel_true_within_cancel_until():
    owner = make_user("o5@example.com")
    renter = make_user("r5@example.com")
    prop = make_property(owner)
    today = timezone.now().date()

    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today + timedelta(days=10),
        end_date=today + timedelta(days=40),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.CONFIRMED,
        cancel_until=today + timedelta(days=1),
    )
    assert booking.can_cancel(today=today) is True


@pytest.mark.django_db
def test_mark_completed_false_when_not_confirmed():
    owner = make_user("o6@example.com")
    renter = make_user("r6@example.com")
    prop = make_property(owner)
    today = timezone.now().date()

    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today - timedelta(days=40),
        end_date=today - timedelta(days=10),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.PENDING,  # не подтверждено
    )
    assert booking.mark_completed() is False


@pytest.mark.django_db
def test_mark_completed_false_when_end_date_not_past():
    owner = make_user("o7@example.com")
    renter = make_user("r7@example.com")
    prop = make_property(owner)
    today = timezone.now().date()

    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today - timedelta(days=1),
        end_date=today,  # ещё не в прошлом по условию end_date >= today
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.CONFIRMED,
    )
    assert booking.mark_completed() is False


@pytest.mark.django_db
def test_mark_completed_true_and_persists_when_past():
    owner = make_user("o8@example.com")
    renter = make_user("r8@example.com")
    prop = make_property(owner)
    today = timezone.now().date()

    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today - timedelta(days=40),
        end_date=today - timedelta(days=1),  # в прошлом
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.CONFIRMED,
    )
    changed = booking.mark_completed()
    assert changed is True
    booking.refresh_from_db()
    assert booking.status == Booking.Status.COMPLETED
    assert booking.completed_at is not None


@pytest.mark.django_db
def test_mark_completed_commit_false_does_not_save():
    owner = make_user("o9@example.com")
    renter = make_user("r9@example.com")
    prop = make_property(owner)
    today = timezone.now().date()

    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today - timedelta(days=40),
        end_date=today - timedelta(days=1),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.CONFIRMED,
    )
    # Меняет объект в памяти, но не сохраняет в БД
    changed = booking.mark_completed(commit=False)
    assert changed is True
    assert booking.status == Booking.Status.COMPLETED
    assert booking.completed_at is not None

    # В БД остался прежний статус
    fresh = Booking.objects.get(id=booking.id)
    assert fresh.status == Booking.Status.CONFIRMED
    assert fresh.completed_at is None