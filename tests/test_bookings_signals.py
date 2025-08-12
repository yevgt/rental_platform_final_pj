import pytest
from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone

import bookings.signals as bs
from bookings.models import Booking
from properties.models import Property
from django.contrib.auth import get_user_model

User = get_user_model()


def make_user(email):
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


# -------------------- _resolve_notif_value --------------------

def test_resolve_notif_value_returns_none_when_notification_none(monkeypatch):
    monkeypatch.setattr(bs, "Notification", None, raising=True)
    assert bs._resolve_notif_value("BOOKING_NEW") is None


def test_resolve_notif_value_uses_Type_constant(monkeypatch):
    class Type:
        BOOKING_NEW = "NEW_BOOKING_CODE"

    class FakeNotification:
        pass

    FakeNotification.Type = Type

    monkeypatch.setattr(bs, "Notification", FakeNotification, raising=True)
    assert bs._resolve_notif_value("BOOKING_NEW", "OTHER") == "NEW_BOOKING_CODE"


def test_resolve_notif_value_uses_choices_fallback(monkeypatch):
    class TypeChoices:
        # нет атрибутов BOOKING_NEW/NEW_BOOKING, но есть choices
        choices = [("FIRST_CODE", "First label")]

    class FakeNotification:
        pass

    FakeNotification.TypeChoices = TypeChoices

    monkeypatch.setattr(bs, "Notification", FakeNotification, raising=True)
    assert bs._resolve_notif_value("ANYTHING") == "FIRST_CODE"


def test_resolve_notif_value_falls_back_to_type_field(monkeypatch):
    class _Field:
        def __init__(self, name):
            self.name = name

    class _Meta:
        fields = [_Field("id"), _Field("type")]

    class FakeNotification:
        _meta = _Meta()

    monkeypatch.setattr(bs, "Notification", FakeNotification, raising=True)
    # Возвращает первый кандидат в lower()
    assert bs._resolve_notif_value("BOOKING_CONFIRMED", "CONFIRMED") == "booking_confirmed"


# -------------------- store_previous_status --------------------

@pytest.mark.django_db
def test_store_previous_status_sets_prev_when_pk_exists():
    owner = make_user("owner@example.com")
    renter = make_user("renter@example.com")
    prop = make_property(owner)

    today = timezone.now().date()
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today + timedelta(days=5),
        end_date=today + timedelta(days=15),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.PENDING,
    )

    # имитируем pre_save: при наличии pk должен найти предыдущее состояние
    bs.store_previous_status(Booking, booking)
    assert getattr(booking, "_previous_status", "MISSING") == Booking.Status.PENDING


@pytest.mark.django_db
def test_store_previous_status_none_when_new_instance():
    # Новый объект без pk
    booking = Booking()
    bs.store_previous_status(Booking, booking)
    assert getattr(booking, "_previous_status", "MISSING") is None


@pytest.mark.django_db
def test_store_previous_status_handles_does_not_exist(monkeypatch):
    # Объект с несуществующим pk
    booking = Booking()
    booking.pk = 999999

    def raise_dne(*args, **kwargs):
        raise Booking.DoesNotExist

    monkeypatch.setattr(Booking.objects, "get", raise_dne, raising=True)
    bs.store_previous_status(Booking, booking)
    assert getattr(booking, "_previous_status", "MISSING") is None


# -------------------- notify_on_booking_events --------------------

@pytest.mark.django_db
def test_notify_on_booking_events_returns_early_if_notification_none(monkeypatch):
    owner = make_user("own1@example.com")
    renter = make_user("rent1@example.com")
    prop = make_property(owner)

    today = timezone.now().date()
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today + timedelta(days=5),
        end_date=today + timedelta(days=15),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.PENDING,
    )

    monkeypatch.setattr(bs, "Notification", None, raising=True)
    # Должно просто вернуться без ошибок
    bs.notify_on_booking_events(Booking, booking, created=True)


@pytest.mark.django_db
def test_notify_on_booking_created_pending_sends_to_landlord(monkeypatch):
    owner = make_user("own2@example.com")
    renter = make_user("rent2@example.com")
    prop = make_property(owner)

    today = timezone.now().date()
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today + timedelta(days=5),
        end_date=today + timedelta(days=15),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.PENDING,
    )

    created_items = []

    class Type:
        BOOKING_NEW = "NEW"

    class FakeManager:
        def create(self, **kwargs):
            created_items.append(kwargs)
            return SimpleNamespace(**kwargs)

    class FakeNotification:
        pass

    FakeNotification.Type = Type
    FakeNotification.objects = FakeManager()

    monkeypatch.setattr(bs, "Notification", FakeNotification, raising=True)

    bs.notify_on_booking_events(Booking, booking, created=True)

    assert len(created_items) == 1
    item = created_items[0]
    assert item["user"] == owner
    assert item["type"] == "NEW"
    assert item["data"]["booking_id"] == booking.id
    assert item["data"]["property_id"] == prop.id
    assert item["data"]["renter_id"] == renter.id
    assert item["data"]["property_title"] == prop.title


@pytest.mark.django_db
def test_notify_on_booking_created_handles_notification_exception(monkeypatch):
    owner = make_user("own3@example.com")
    renter = make_user("rent3@example.com")
    prop = make_property(owner)

    today = timezone.now().date()
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today + timedelta(days=5),
        end_date=today + timedelta(days=15),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.PENDING,
    )

    class Type:
        BOOKING_NEW = "NEW"

    class RaisingManager:
        def create(self, **kwargs):
            raise RuntimeError("boom")

    class FakeNotification:
        pass

    FakeNotification.Type = Type
    FakeNotification.objects = RaisingManager()

    monkeypatch.setattr(bs, "Notification", FakeNotification, raising=True)

    # Исключение должно быть проглочено (pass)
    bs.notify_on_booking_events(Booking, booking, created=True)


@pytest.mark.django_db
def test_notify_on_booking_status_change_confirmed(monkeypatch):
    owner = make_user("own4@example.com")
    renter = make_user("rent4@example.com")
    prop = make_property(owner)

    today = timezone.now().date()
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=5),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.CONFIRMED,
    )
    # Эмулируем, что раньше был другой статус
    booking._previous_status = Booking.Status.PENDING

    created_items = []

    class Type:
        BOOKING_CONFIRMED = "CONFIRM_CODE"

    class FakeManager:
        def create(self, **kwargs):
            created_items.append(kwargs)
            return SimpleNamespace(**kwargs)

    class FakeNotification:
        pass

    FakeNotification.Type = Type
    FakeNotification.objects = FakeManager()

    monkeypatch.setattr(bs, "Notification", FakeNotification, raising=True)

    bs.notify_on_booking_events(Booking, booking, created=False)
    assert len(created_items) == 1
    assert created_items[0]["user"] == renter
    assert created_items[0]["type"] == "CONFIRM_CODE"
    assert created_items[0]["data"]["status"] == Booking.Status.CONFIRMED


@pytest.mark.django_db
def test_notify_on_booking_status_change_rejected_with_Types_class(monkeypatch):
    owner = make_user("own5@example.com")
    renter = make_user("rent5@example.com")
    prop = make_property(owner)

    today = timezone.now().date()
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today + timedelta(days=1),
        end_date=today + timedelta(days=2),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.REJECTED,
    )
    booking._previous_status = Booking.Status.PENDING

    created_items = []

    class Types:
        REJECTED = "REJECT_CODE"

    class FakeManager:
        def create(self, **kwargs):
            created_items.append(kwargs)
            return SimpleNamespace(**kwargs)

    class FakeNotification:
        pass

    FakeNotification.Types = Types
    FakeNotification.objects = FakeManager()

    monkeypatch.setattr(bs, "Notification", FakeNotification, raising=True)

    bs.notify_on_booking_events(Booking, booking, created=False)
    assert len(created_items) == 1
    assert created_items[0]["user"] == renter
    assert created_items[0]["type"] == "REJECT_CODE"
    assert created_items[0]["data"]["status"] == Booking.Status.REJECTED


@pytest.mark.django_db
def test_notify_on_booking_status_change_other_noop(monkeypatch):
    # Для ветки else (не CONFIRMED/REJECTED): уведомление не создаётся
    owner = make_user("own6@example.com")
    renter = make_user("rent6@example.com")
    prop = make_property(owner)

    today = timezone.now().date()
    booking = Booking.objects.create(
        property=prop,
        user=renter,
        start_date=today + timedelta(days=3),
        end_date=today + timedelta(days=6),
        monthly_rent=prop.price,
        total_amount=prop.price,
        status=Booking.Status.CANCELLED,  # не CONFIRMED/REJECTED
    )
    booking._previous_status = Booking.Status.PENDING

    created_items = []

    class Type:
        # Не будет использовано, но оставим для совместимости
        BOOKING_CONFIRMED = "CONFIRM"
        BOOKING_REJECTED = "REJECT"

    class FakeManager:
        def create(self, **kwargs):
            created_items.append(kwargs)
            return SimpleNamespace(**kwargs)

    class FakeNotification:
        pass

    FakeNotification.Type = Type
    FakeNotification.objects = FakeManager()

    monkeypatch.setattr(bs, "Notification", FakeNotification, raising=True)

    bs.notify_on_booking_events(Booking, booking, created=False)
    assert created_items == []