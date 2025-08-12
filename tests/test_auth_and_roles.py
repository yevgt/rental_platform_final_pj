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
#############################################
def resp_text(resp) -> str:
    try:
        c = getattr(resp, "content", b"")
        if isinstance(c, bytes):
            return c.decode("utf-8", errors="ignore")
        return str(c)
    except Exception:
        return repr(resp)


@pytest.mark.django_db
def test_landlord_cannot_book_own_property(django_user_model):
    from properties.models import Property
    from bookings.models import Booking

    email = "own@example.com"
    password = "Pass12345"

    landlord = django_user_model.objects.create_user(
        email=email,
        password=password,
        role="landlord",
        first_name="L",
        last_name="O",
        date_of_birth="1990-01-01",
    )

    prop = Property.objects.create(
        title="SelfProp",
        description="Desc",
        location="Berlin",
        price="1000.00",
        number_of_rooms=2,
        property_type="apartment",
        owner=landlord,
        status="active",
    )

    client = APIClient()

    # JWT (если пригодится для DRF-вью)
    token_resp = client.post("/api/token/", {"email": email, "password": password}, format="json")
    if getattr(token_resp, "status_code", 0) == 200:
        try:
            token = token_resp.json().get("access")
        except Exception:
            token = None
        if token:
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # Сессионный логин для HTML/классических Django-вью
    client.login(username=email, password=password)

    count_before = Booking.objects.count()

    payload = {
        "property": prop.id,
        "start_date": "2030-01-10",
        "end_date": "2030-01-12",
    }

    # Пробуем /create/, затем корень
    resp = client.post("/api/bookings/create/", payload, follow=True)
    if resp.status_code == 404:
        resp = client.post("/api/bookings/", payload, follow=True)

    # Разные реализации: DRF может вернуть 400/403, HTML — 200/302/201
    assert resp.status_code in (400, 403, 200, 201, 302), (
        f"Unexpected status: {resp.status_code}, body={resp_text(resp)[:500]}"
    )

    count_after = Booking.objects.count()
    # Ключевая проверка: бронирование НЕ должно создаться
    assert count_after == count_before, (
        "Landlord should not be able to book own property, "
        f"but bookings_count changed: {count_before} -> {count_after}. "
        f"Response: {resp.status_code} {resp_text(resp)[:300]}"
    )

    # Дополнительные проверки сообщений (мягкие, зависят от реализации)
    text = resp_text(resp)
    if resp.status_code == 400:
        assert "Владелец не может бронировать" in text, (
            "Expected explicit validation message for owner booking; got: " + text[:300]
        )
    elif resp.status_code == 403:
        # Принимаем общее сообщение о запрете (например, только для арендаторов)
        assert ("арендатор" in text.lower()) or ("forbidden" in text.lower()) or ("доступ" in text.lower()), (
            "Expected a permission-related message in 403 response; got: " + text[:300]
        )