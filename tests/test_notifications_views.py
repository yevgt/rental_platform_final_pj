import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from notifications.models import Notification
from notifications.views import NotificationViewSet

User = get_user_model()


@pytest.mark.django_db
def test_list_filters_is_read_false_branch():
    user = User.objects.create_user(email="u1@example.com", password=None)
    # One unread, one read
    n_unread = Notification.objects.create(
        user=user, type=Notification.Types.MESSAGE_NEW, message="m1", is_read=False
    )
    Notification.objects.create(
        user=user, type=Notification.Types.MESSAGE_NEW, message="m2", is_read=True
    )

    factory = APIRequestFactory()
    request = factory.get("/notifications/", {"is_read": "0"})  # should hit elif false branch
    force_authenticate(request, user=user)
    view = NotificationViewSet.as_view({"get": "list"})
    resp = view(request)

    assert resp.status_code == 200
    ids = {item["id"] for item in resp.data}
    assert ids == {n_unread.id}


@pytest.mark.django_db
def test_list_ignores_is_read_when_value_invalid():
    user = User.objects.create_user(email="u2@example.com", password=None)
    n1 = Notification.objects.create(
        user=user, type=Notification.Types.BOOKING_NEW, message="m1", is_read=False
    )
    n2 = Notification.objects.create(
        user=user, type=Notification.Types.BOOKING_NEW, message="m2", is_read=True
    )

    factory = APIRequestFactory()
    request = factory.get("/notifications/", {"is_read": "maybe"})  # not in accepted sets
    force_authenticate(request, user=user)
    view = NotificationViewSet.as_view({"get": "list"})
    resp = view(request)

    assert resp.status_code == 200
    ids = {item["id"] for item in resp.data}
    assert ids == {n1.id, n2.id}


@pytest.mark.django_db
def test_list_filters_by_type():
    user = User.objects.create_user(email="u3@example.com", password=None)
    n_target = Notification.objects.create(
        user=user, type=Notification.Types.REVIEW_NEW, message="review"
    )
    Notification.objects.create(
        user=user, type=Notification.Types.MESSAGE_NEW, message="msg"
    )

    factory = APIRequestFactory()
    request = factory.get("/notifications/", {"type": Notification.Types.REVIEW_NEW})
    force_authenticate(request, user=user)
    view = NotificationViewSet.as_view({"get": "list"})
    resp = view(request)

    assert resp.status_code == 200
    assert [item["id"] for item in resp.data] == [n_target.id]


@pytest.mark.django_db
def test_read_forbidden_for_other_user():
    owner = User.objects.create_user(email="owner@example.com", password=None)
    other = User.objects.create_user(email="other@example.com", password=None)
    notif = Notification.objects.create(
        user=owner, type=Notification.Types.MESSAGE_NEW, message="secret", is_read=False
    )

    # By default, DRF's get_object uses get_queryset() filtered by current user,
    # which would yield 404. To cover the explicit 403 branch in the view, override
    # get_queryset to not filter by user for this test only.
    class OpenNotificationViewSet(NotificationViewSet):
        def get_queryset(self):
            return Notification.objects.order_by("-created_at")

    factory = APIRequestFactory()
    request = factory.post(f"/notifications/{notif.id}/read/")
    force_authenticate(request, user=other)
    view = OpenNotificationViewSet.as_view({"post": "read"})
    resp = view(request, pk=notif.id)

    assert resp.status_code == 403
    notif.refresh_from_db()
    assert notif.is_read is False


@pytest.mark.django_db
def test_read_already_read_skips_update_and_returns_ok():
    user = User.objects.create_user(email="u4@example.com", password=None)
    notif = Notification.objects.create(
        user=user, type=Notification.Types.MESSAGE_NEW, message="already", is_read=True
    )

    factory = APIRequestFactory()
    request = factory.post(f"/notifications/{notif.id}/read/")
    force_authenticate(request, user=user)
    view = NotificationViewSet.as_view({"post": "read"})
    resp = view(request, pk=notif.id)

    assert resp.status_code == 200
    data = resp.data
    assert data["id"] == notif.id
    assert data["is_read"] is True
    notif.refresh_from_db()
    assert notif.is_read is True  # remains true


@pytest.mark.django_db
def test_read_all_updates_only_current_users_unread():
    user = User.objects.create_user(email="u5@example.com", password=None)
    other = User.objects.create_user(email="u6@example.com", password=None)

    # user: 2 unread, 1 read
    Notification.objects.create(user=user, type=Notification.Types.MESSAGE_NEW, message="u-a", is_read=False)
    Notification.objects.create(user=user, type=Notification.Types.BOOKING_NEW, message="u-b", is_read=False)
    Notification.objects.create(user=user, type=Notification.Types.BOOKING_NEW, message="u-c", is_read=True)

    # other: 1 unread (should not be affected)
    other_unread = Notification.objects.create(
        user=other, type=Notification.Types.MESSAGE_NEW, message="o-a", is_read=False
    )

    factory = APIRequestFactory()
    request = factory.post("/notifications/read_all/")
    force_authenticate(request, user=user)
    view = NotificationViewSet.as_view({"post": "read_all"})
    resp = view(request)

    assert resp.status_code == 200
    assert resp.data["updated"] == 2

    # Verify user notifications are all read now
    assert Notification.objects.filter(user=user, is_read=False).count() == 0
    # Verify other user's unread not touched
    other_unread.refresh_from_db()
    assert other_unread.is_read is False