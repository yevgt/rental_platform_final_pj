import pytest
from django.contrib.auth import get_user_model

from notifications.models import Notification

User = get_user_model()


@pytest.mark.django_db
def test_notification_str():
    user = User.objects.create_user(email="user@example.com", password=None)
    n = Notification.objects.create(
        user=user,
        type=Notification.Types.MESSAGE_NEW,
        message="Test message",
    )
    assert str(n) == f"{Notification.Types.MESSAGE_NEW} -> {user.id}"