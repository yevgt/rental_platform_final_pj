import pytest
from django.contrib.auth import get_user_model

@pytest.fixture
def user_factory(db):
    def create_user(email, password="Testpass123", role="renter", name="Test User"):
        User = get_user_model()
        user = User.objects.create_user(username=email, email=email, password=password, role=role, name=name)
        return user
    return create_user