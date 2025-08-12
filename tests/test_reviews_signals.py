import pytest
from django.contrib.auth import get_user_model
import reviews.signals
from reviews.signals import notify_owner_on_new_review

@pytest.fixture
def property_owner(db):
    User = get_user_model()
    return User.objects.create_user(
        email="owner@mail.com",
        password="ownerpass",
        first_name="Owner",
        last_name="Landlord",
        role="landlord"
    )

@pytest.fixture
def reviewer(db):
    User = get_user_model()
    return User.objects.create_user(
        email="reviewer@mail.com",
        password="reviewerpass",
        first_name="Reviewer",
        last_name="Renter",
        role="renter"
    )

@pytest.fixture
def property_obj(property_owner):
    class Property:
        id = 42
        title = "Test House"
        owner = property_owner
    return Property()

@pytest.fixture
def review_instance(property_obj, reviewer):
    class ReviewMock:
        id = 99
        rating = 5
        property = property_obj
        user_id = reviewer.id
    return ReviewMock()

def test_notification_created(monkeypatch, property_obj, review_instance, property_owner):
    # Мокаем Notification
    class NotificationMock:
        objects = type("obj", (), {"create": lambda **kwargs: kwargs})
        class Type:
            REVIEW_NEW = "review_new_type"
    monkeypatch.setattr(reviews.signals, "Notification", NotificationMock)
    monkeypatch.setattr(reviews.signals, "_resolve_notification_type", lambda: "review_new_type")

    called = {}

    def create_mock(**kwargs):
        called.update(kwargs)
        return called

    NotificationMock.objects.create = create_mock

    notify_owner_on_new_review(None, review_instance, created=True)
    assert called["user"] == property_owner
    assert called["type"] == "review_new_type"
    assert "property_id" in called["data"]

def test_no_notification_if_owner_is_author(monkeypatch, property_obj, property_owner):
    class ReviewMock:
        id = 1
        rating = 3
        property = property_obj
        user_id = property_owner.id

    class NotificationMock:
        objects = type("obj", (), {"create": lambda **kwargs: None})

    monkeypatch.setattr(reviews.signals, "Notification", NotificationMock)

    notify_owner_on_new_review(None, ReviewMock(), created=True)
    # Если уведомление не создаётся, ничего не должно упасть

def test_no_notification_if_not_created(monkeypatch, review_instance):
    class NotificationMock:
        objects = type("obj", (), {"create": lambda **kwargs: None})
    monkeypatch.setattr(reviews.signals, "Notification", NotificationMock)

    notify_owner_on_new_review(None, review_instance, created=False)

def test_no_notification_if_no_property(monkeypatch, reviewer):
    class ReviewMock:
        id = 1
        rating = 5
        property = None
        user_id = reviewer.id
    class NotificationMock:
        objects = type("obj", (), {"create": lambda **kwargs: None})
    monkeypatch.setattr(reviews.signals, "Notification", NotificationMock)
    notify_owner_on_new_review(None, ReviewMock(), created=True)

def test_no_notification_if_no_owner(monkeypatch, reviewer):
    class Property:
        id = 2
        title = "No owner"
        owner = None
    class ReviewMock:
        id = 3
        rating = 4
        property = Property()
        user_id = reviewer.id
    class NotificationMock:
        objects = type("obj", (), {"create": lambda **kwargs: None})
    monkeypatch.setattr(reviews.signals, "Notification", NotificationMock)
    notify_owner_on_new_review(None, ReviewMock(), created=True)