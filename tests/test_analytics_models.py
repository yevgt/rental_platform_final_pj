import pytest
from django.contrib.auth import get_user_model

from properties.models import Property
from analytics.models import ViewHistory, SearchHistory


User = get_user_model()


@pytest.mark.django_db
def test_viewhistory_and_searchhistory_str():
    # Владедец объявления
    owner = User.objects.create_user(email="owner@example.com", password=None)

    # Объявление (Property)
    prop = Property.objects.create(
        title="Квартира",
        description="Центр",
        location="Berlin",
        price="1000.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=owner,
        status="active",
    )

    # Простой просмотр без авторизации (user=None)
    vh_anon = ViewHistory.objects.create(user=None, property=prop)
    assert str(vh_anon) == f"View p#{prop.id} by u#None"

    # Просмотр авторизованным пользователем
    u = User.objects.create_user(email="viewer@example.com", password=None)
    vh = ViewHistory.objects.create(user=u, property=prop)
    assert str(vh) == f"View p#{prop.id} by u#{u.id}"

    # История поиска
    sh = SearchHistory.objects.create(user=u, search_query="apartment berlin")
    assert str(sh) == f"{sh.search_query} ({u.id})"