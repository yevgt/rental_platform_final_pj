import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
def test_registration_and_login(django_user_model):
    client = APIClient()
    # Регистрация
    data = {
        "email": "newuser@example.com",
        "password": "Pass12345",
        "password_confirm": "Pass12345",
        "first_name": "New",
        "last_name": "User",
        "date_of_birth": "1995-01-01",
        "role": "renter"
    }
    resp = client.post("/api/accounts/register/", data, format="json")
    assert resp.status_code in (201, 200), resp.data

    # Логин
    resp2 = client.post("/api/token/", {"email": "newuser@example.com", "password": "Pass12345"}, format="json")
    assert resp2.status_code == 200
    assert "access" in resp2.data

@pytest.mark.django_db
def test_renter_cannot_switch_to_landlord_via_profile_update(django_user_model):
    # Предполагаем, что поле role read_only или запрещено менять (если нет — тест скорректируй)
    user = django_user_model.objects.create_user(
        email="renter2@example.com", password="Pass12345", role="renter",
        first_name="R", last_name="User2", date_of_birth="1990-01-01"
    )
    client = APIClient()
    token = client.post("/api/token/", {"email": user.email, "password": "Pass12345"}, format="json").data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    resp = client.patch("/api/accounts/profile/", {"role": "landlord"}, format="json")
    # Ожидаем что сервер не даст изменить (422/400/200 но значение не меняется)
    user.refresh_from_db()
    assert user.role == "renter"

@pytest.mark.django_db
def test_landlord_cannot_book_own_property(django_user_model):
    from properties.models import Property
    landlord = django_user_model.objects.create_user(
        email="own@example.com", password="Pass12345", role="landlord",
        first_name="L", last_name="O", date_of_birth="1990-01-01"
    )
    prop = Property.objects.create(
        title="SelfProp",
        description="Desc",
        location="Berlin",
        price="1000.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=landlord,
        status="active"
    )
    client = APIClient()
    token = client.post("/api/token/", {"email": landlord.email, "password": "Pass12345"}, format="json").data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    resp = client.post("/api/bookings/", {
        "property": prop.id,
        "start_date": "2030-01-10",
        "end_date": "2030-01-12"
    }, format="json")
    assert resp.status_code == 400
    assert "Владелец не может бронировать" in str(resp.data)