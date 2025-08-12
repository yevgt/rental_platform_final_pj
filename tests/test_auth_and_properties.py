import json
import uuid
import pytest
from rest_framework.test import APIClient


def to_json(resp):
    """
    Универсальный парсер JSON из DRF Response или Django HttpResponse.
    Возвращает (data, raw_text).
    """
    # 1) Попробуем стандартный .json()
    try:
        return resp.json(), None
    except Exception:
        pass

    # 2) Попробуем извлечь сырой текст
    raw = None
    for attr in ("rendered_content", "content"):
        if hasattr(resp, attr):
            try:
                raw = getattr(resp, attr)
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="ignore")
                break
            except Exception:
                continue

    if raw is None:
        return None, None

    # 3) Попробуем распарсить JSON
    try:
        return json.loads(raw), raw
    except Exception:
        return None, raw


@pytest.mark.django_db
def test_register_and_login_and_create_property():
    client = APIClient()

    # 1) Регистрация
    email = "owner@example.com"
    password = "StrongPass123"

    resp = client.post(
        "/api/accounts/register/",
        {
            "username": email,  # если бэкенд требует username
            "first_name": "Owner",
            "last_name": "Owner",
            "email": email,
            "password": password,
            "password_confirm": password,
            "role": "landlord",
            "date_of_birth": "1990-01-01",
            "phone_number": "+10000000000",
        },
        format="json",
    )
    assert resp.status_code in (200, 201), f"Register failed: status={resp.status_code}, body={getattr(resp, 'content', b'')[:500]}"

    # 2) JWT-логин (если где-то нужен)
    resp = client.post(
        "/api/token/",
        {"username": email, "email": email, "password": password},
        format="json",
    )
    assert resp.status_code == 200, f"Login failed: status={resp.status_code}, body={getattr(resp, 'content', b'')[:500]}"
    login_json, raw = to_json(resp)
    assert isinstance(login_json, dict) and "access" in login_json, f"Login JSON has no 'access': {raw or ''[:500]}"
    access = login_json["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    # ВАЖНО: для HTML-вью используем сессионный логин, чтобы request.user был не anon
    # (JWT не обрабатывается обычными Django CBV/FBV)
    client.login(username=email, password=password)

    # 3) Создание объявления
    # Используем уникальный title, чтобы найти объект в публичном списке
    unique_suffix = str(uuid.uuid4())[:8]
    title = f"Уютная квартира {unique_suffix}"

    # Пытаемся сначала туда, где документация указывает POST (в некоторых проектах — /api/properties/create/)
    # Шаг A: пробуем POST на /api/properties/create/ (форма; follow=True на случай редиректа)
    created = False
    create_payload = {
        "title": title,
        "description": "Центр города",
        "location": "Berlin",
        "price": "1200.00",
        "number_of_rooms": 2,
        "property_type": "apartment",
        "status": "active",
    }

    resp = client.post("/api/properties/create/", create_payload, follow=True)
    if resp.status_code in (200, 201, 302):
        created = True

    # Шаг B: если /create/ не сработал, попробуем POST на /api/properties/ (как задекларировано в подсказке)
    if not created:
        # Важно: для HTML-вью отправляем как форму (без format="json")
        resp = client.post("/api/properties/", create_payload, follow=True)
        assert resp.status_code in (200, 201, 302), f"Create property failed: status={resp.status_code}, body={getattr(resp, 'content', b'')[:500]}"

    # 4) Публичный список + поиск
    # Переходим на анонимного клиента (по условию проверки публичности)
    client.credentials()
    client.logout()

    # Ищем по уникальной части title через публичный эндпоинт
    resp = client.get(f"/api/properties/public/?search={unique_suffix}&ordering=-price")
    assert resp.status_code == 200, f"Public list failed: status={resp.status_code}, body={getattr(resp, 'content', b'')[:500]}"

    list_json, raw = to_json(resp)

    # Поддерживаем как пагинированный, так и непагинированный ответ
    if isinstance(list_json, dict) and "results" in list_json:
        items = list_json["results"]
    else:
        items = list_json

    assert isinstance(items, list), f"Properties list is not a list: {raw or list_json}"

    # Находим созданный объект по заголовку (уникальный)
    matched = [it for it in items if isinstance(it, dict) and it.get("title") == title]
    assert matched, f"Created property with title='{title}' not found in public list"